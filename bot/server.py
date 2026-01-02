from aiohttp import web
import os
import logging

logger = logging.getLogger("KeepAlive")

async def root_handler(request):
    return web.Response(text="🤖 Bot is Active & Running 24/7!")

async def start_server():
    app = web.Application()
    app.router.add_get('/', root_handler)
    
    # Render provides PORT environment variable
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    logger.info(f"🌍 Keep-Alive Server started on port {port}")
    await site.start()
