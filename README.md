# Pesquisa de Clima (anônima) + Dashboard em tempo real

Sistema completo em 3 partes:

| Parte | Arquivo | O que faz |
|-------|---------|-----------|
| 🗳️ Pesquisa | `static/pesquisa.html` | Formulário anônimo que o time responde |
| ⚙️ Back-end | `app.py` (Python / FastAPI) | Recebe e guarda as respostas no banco |
| 📊 Dashboard | `static/dashboard.html` | Painel do gestor, atualizado em tempo real |

O mesmo back-end serve os dois HTMLs e a API. Fluxo:

```
Pessoa responde  ──POST /api/submit──►  FastAPI  ──►  Banco (PostgreSQL/SQLite)
                                           │
Gestor abre /dashboard  ──GET /api/results (a cada 15s)──►  lê o banco e mostra
```

**Privacidade:** não coletamos nome, e-mail, IP nem cookies. Só data/hora + respostas.

---

## 1) Rodar na sua máquina (teste local)

Pré-requisito: Python 3.11+ instalado.

```bash
pip install -r requirements.txt
python app.py
```

Abra no navegador:
- Pesquisa: <http://localhost:8000/>
- Dashboard: <http://localhost:8000/dashboard>

Sem `DATABASE_URL`, os dados ficam num arquivo local `responses.db` (SQLite).

---

## 2) Subir no GitHub

Dentro da pasta do projeto:

```bash
git init
git add .
git commit -m "Pesquisa de clima anonima + dashboard"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/SEU_REPO.git
git push -u origin main
```

---

## 3) Publicar no Render (recomendado)

### Opção A — Automática (Blueprint) ✅ mais fácil
1. Faça o passo 2 (GitHub).
2. No [Render](https://render.com): **New → Blueprint** e selecione o repositório.
3. O Render lê o `render.yaml` e cria **o serviço web + um banco PostgreSQL grátis** já conectados.
4. Aguarde o deploy. Você terá uma URL tipo `https://pesquisa-clima.onrender.com`.

### Opção B — Manual
1. **New → Web Service** apontando para o repositório.
2. Configure:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app:app --host 0.0.0.0 --port $PORT`
3. (Recomendado) **New → PostgreSQL** (plano free) e, no Web Service, em **Environment**, crie a variável `DATABASE_URL` com a *Internal Connection String* do banco.
4. Deploy.

### Links finais
- **Pesquisa (enviar para o time):** `https://SEU-APP.onrender.com/`
- **Dashboard (só você):** `https://SEU-APP.onrender.com/dashboard`

---

## 🔒 Proteger o dashboard com token

Para que só você veja os resultados, defina a variável de ambiente **`ADMIN_TOKEN`**
(no Blueprint ela já é gerada automaticamente — veja o valor em *Environment*).

- Com `ADMIN_TOKEN` definido, o dashboard pede um token, ou acesse direto:
  `https://SEU-APP.onrender.com/dashboard?token=SEU_TOKEN`
- A pesquisa (`/`) continua **aberta** para todos — só os *resultados* ficam protegidos.

---

## ⚠️ Persistência dos dados
- **Com PostgreSQL** (passos acima): os dados ficam salvos de forma permanente. **Recomendado.**
- **Sem PostgreSQL** (só SQLite no Render): o disco do plano free é temporário e os
  dados podem se perder quando o serviço reinicia. Use SQLite apenas para teste local.
- No plano free do Render, o serviço "hiberna" após inatividade; a primeira visita depois
  disso pode levar ~30s para acordar (os dados **não** se perdem se estiver usando PostgreSQL).

---

## Hospedar os HTMLs em outro lugar (opcional)
Se quiser servir os HTMLs no GitHub Pages e só o back-end no Render, abra
`static/pesquisa.html` e `static/dashboard.html` e ajuste no topo do `<script>`:

```js
const API_BASE = "https://SEU-APP.onrender.com";
```

A API já está com CORS liberado para isso funcionar.

---

## Estrutura do projeto
```
.
├── app.py               # back-end FastAPI (API + serve os HTMLs)
├── requirements.txt     # dependências Python
├── render.yaml          # blueprint do Render (web + banco)
├── Procfile             # comando de start (portável)
├── runtime.txt          # versão do Python
├── .gitignore
└── static/
    ├── pesquisa.html    # formulário anônimo
    └── dashboard.html   # painel do gestor (tempo real)
```
