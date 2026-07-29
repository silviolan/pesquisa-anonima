"""
Configuração do Gunicorn (carregada automaticamente quando o comando é `gunicorn app:app`).

Por que este arquivo existe:
- O Render, por padrão, inicia apps Python com `gunicorn app:app`.
- Mas o FastAPI é ASGI e NÃO funciona com o worker padrão (síncrono) do Gunicorn.
- Aqui trocamos para o worker do Uvicorn (ASGI) e usamos a porta que o Render fornece ($PORT).

Assim o deploy funciona com QUALQUER comando de início:
- `gunicorn app:app`  (padrão do Render)  -> usa este arquivo
- `uvicorn app:app ...` (do render.yaml)   -> ignora este arquivo e roda direto
"""

import os

# O Render (e a maioria das plataformas) informa a porta via variável $PORT.
bind = "0.0.0.0:" + os.environ.get("PORT", "10000")

# FastAPI é ASGI -> precisa do worker do Uvicorn.
worker_class = "uvicorn.workers.UvicornWorker"

# 1 worker no plano gratuito (respeita WEB_CONCURRENCY, que o Render define como 1).
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))

# Envia os logs para a saída padrão (aparecem no painel de Logs do Render).
accesslog = "-"
errorlog = "-"

# Reinicia workers que ficarem presos (segurança extra).
timeout = 120
