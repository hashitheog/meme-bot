import asyncio
import aiohttp
import sys
import os

# Fix path to import config
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot.config import Config

async def send_ping():
    if not Config.TELEGRAM_BOT_TOKEN or not Config.TELEGRAM_CHAT_ID:
        print("Error: Missing Telegram credentials in Config.")
        return

    url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": Config.TELEGRAM_CHAT_ID,
        "text": "🟢 **System Check**: The Meme Coin Bot is connected and active! 🚀",
        "parse_mode": "Markdown"
    }

    print(f"Sending test message to {Config.TELEGRAM_CHAT_ID}...")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            if resp.status == 200:
                print("✅ Message sent successfully!")
            else:
                print(f"❌ Failed to send message. Status: {resp.status}")
                print(await resp.text())

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(send_ping())
