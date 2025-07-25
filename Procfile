web: python live_api_mcp_server.py
bot: python -m app.discord_bot
release: python -c "from app.models.database import init_db; import asyncio; asyncio.run(init_db())"