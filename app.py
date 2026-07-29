"""
Back-end da Pesquisa de Clima (anônima).

O que este arquivo faz:
- Serve o HTML da PESQUISA em "/"
- Serve o HTML do DASHBOARD em "/dashboard"
- Recebe as respostas em  POST /api/submit
- Entrega os dados agregados em  GET /api/results  (o dashboard consulta em tempo real)

Armazenamento:
- Se a variável de ambiente DATABASE_URL existir, usa PostgreSQL
  (recomendado no Render, para os dados NÃO se perderem em reinícios).
- Caso contrário, usa um arquivo SQLite local (responses.db) — ótimo para testar na sua máquina.

Privacidade (pesquisa anônima):
- Não guardamos nome, e-mail, IP, cookies nem qualquer identificador.
- Cada resposta é apenas: data/hora (UTC) + as respostas do formulário.
"""

import os
import json
from datetime import datetime, timezone, date
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlalchemy as sa

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# Token opcional para proteger o dashboard/resultados.
# Defina ADMIN_TOKEN no Render para que só você veja os dados.
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "").strip()

# ----------------------------------------------------------------------
# Banco de dados
# ----------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL.startswith("postgres://"):
    # O Render entrega "postgres://", mas o SQLAlchemy espera "postgresql://".
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///" + (BASE_DIR / "responses.db").as_posix()

engine = sa.create_engine(DATABASE_URL, pool_pre_ping=True)

metadata = sa.MetaData()
responses = sa.Table(
    "responses",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("payload", sa.Text, nullable=False),
)
metadata.create_all(engine)

# ----------------------------------------------------------------------
# Limites simples para evitar abuso de envios
# ----------------------------------------------------------------------
MAX_TEXT = 5000    # máx. de caracteres por campo de texto
MAX_FIELDS = 100   # máx. de campos por tipo (notas / textos)

app = FastAPI(title="Pesquisa de Clima")

# Libera o acesso à API de qualquer origem (a pesquisa é pública e sem cookies).
# Isso permite hospedar os HTMLs em outro lugar, se você quiser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------------
# Funções de limpeza/validação
# ----------------------------------------------------------------------
def clean_text(value):
    if not isinstance(value, str):
        return ""
    return value.strip()[:MAX_TEXT]


def clean_answers(d):
    """Mantém apenas notas inteiras de 0 a 10."""
    out = {}
    if isinstance(d, dict):
        for k, v in list(d.items())[:MAX_FIELDS]:
            try:
                n = int(v)
            except (TypeError, ValueError):
                continue
            if 0 <= n <= 10:
                out[str(k)[:100]] = n
    return out


def clean_texts(d):
    out = {}
    if isinstance(d, dict):
        for k, v in list(d.items())[:MAX_FIELDS]:
            t = clean_text(v)
            if t:
                out[str(k)[:100]] = t
    return out


def check_token(request: Request):
    """Se ADMIN_TOKEN estiver definido, exige o token para ver os resultados."""
    if ADMIN_TOKEN:
        token = request.query_params.get("token") or request.headers.get("x-admin-token", "")
        if token != ADMIN_TOKEN:
            raise HTTPException(status_code=401, detail="Token inválido")


# ----------------------------------------------------------------------
# Páginas
# ----------------------------------------------------------------------
@app.get("/")
def survey_page():
    return FileResponse(STATIC_DIR / "pesquisa.html")


@app.get("/dashboard")
def dashboard_page():
    # O HTML em si não contém dados; os dados só vêm de /api/results (protegido pelo token).
    return FileResponse(STATIC_DIR / "dashboard.html")


@app.get("/health")
def health():
    return {"ok": True}


# ----------------------------------------------------------------------
# API
# ----------------------------------------------------------------------
@app.post("/api/submit")
async def submit(request: Request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON inválido")

    payload = {
        "answers": clean_answers(data.get("answers")),
        "openAnswers": clean_texts(data.get("openAnswers")),
        "generalAnswers": clean_texts(data.get("generalAnswers")),
        "comment": clean_text(data.get("comment")),
    }

    # Ignora envios totalmente vazios.
    if (not payload["answers"] and not payload["openAnswers"]
            and not payload["generalAnswers"] and not payload["comment"]):
        raise HTTPException(status_code=400, detail="Resposta vazia")

    with engine.begin() as conn:
        conn.execute(
            responses.insert().values(
                created_at=datetime.now(timezone.utc),
                payload=json.dumps(payload, ensure_ascii=False),
            )
        )
    return {"ok": True}


@app.get("/api/results")
def results(request: Request):
    check_token(request)

    per_question = {}   # qid -> {"sum": int, "count": int, "dist": [11]}
    open_answers = {}   # categoria -> [textos]
    general = {}        # pergunta geral -> [textos]
    comments = []
    timeline = {}       # "AAAA-MM-DD" -> quantidade
    total = 0

    with engine.connect() as conn:
        rows = conn.execute(
            sa.select(responses.c.created_at, responses.c.payload)
        ).all()

    for created_at, payload_text in rows:
        try:
            p = json.loads(payload_text)
        except Exception:
            continue
        total += 1

        # Linha do tempo por dia.
        try:
            day = created_at.date().isoformat()
        except Exception:
            day = date.today().isoformat()
        timeline[day] = timeline.get(day, 0) + 1

        for qid, v in (p.get("answers") or {}).items():
            if not isinstance(v, int) or not (0 <= v <= 10):
                continue
            slot = per_question.setdefault(qid, {"sum": 0, "count": 0, "dist": [0] * 11})
            slot["sum"] += v
            slot["count"] += 1
            slot["dist"][v] += 1

        for k, t in (p.get("openAnswers") or {}).items():
            if t:
                open_answers.setdefault(k, []).append(t)
        for k, t in (p.get("generalAnswers") or {}).items():
            if t:
                general.setdefault(k, []).append(t)
        if p.get("comment"):
            comments.append(p["comment"])

    per_question_out = {
        qid: {
            "avg": round(s["sum"] / s["count"], 2) if s["count"] else None,
            "count": s["count"],
            "dist": s["dist"],
        }
        for qid, s in per_question.items()
    }

    timeline_out = [{"date": k, "count": v} for k, v in sorted(timeline.items())]

    return JSONResponse({
        "count": total,
        "perQuestion": per_question_out,
        "open": open_answers,
        "general": general,
        "comments": comments,
        "timeline": timeline_out,
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=True,
    )
