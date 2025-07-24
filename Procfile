web: gunicorn app.main:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --workers 2
bot: python -m app.discord_bot
release: python -c "from app.models.database import init_db; import asyncio; asyncio.run(init_db())"