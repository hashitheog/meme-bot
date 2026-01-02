import aiohttp
import logging
from bot.config import Config
from bot.models.token import AnalysisResult

logger = logging.getLogger(__name__)

class TelegramAlert:
    @staticmethod
    async def send_alert(result: AnalysisResult):
        """
        Sends a formatted alert to Telegram.
        """
        if not Config.TELEGRAM_ENABLED or not Config.TELEGRAM_BOT_TOKEN:
            return

        token = result.token
        emoji = "🟢" if result.action == "HIGH_PRIORITY" else "⚠️"
        
        web_link = f" <a href='{token.websites[0]['url']}'>[Web]</a>" if token.websites else ""
        social_links = " ".join([f"<a href='{s['url']}'>[{s['type']}]</a>" for s in token.socials[:3]])
        
        # Format Passed Checks for display
        passed_list = result.passed_params
        # Filter out checklist items for display to save space/cleanliness, or show top ones
        # User wants to know "criteria it passed". listing all 15 might be long but let's try.
        # We can format them nicely.
        
        passed_text = "\n".join([f"✅ {k}" for k in passed_list[:10]]) # Show top 10 to avoid spam
        if len(passed_list) > 10: passed_text += f"\n...and {len(passed_list)-10} more"

        message = (
            f"{emoji} <b>{result.action} {result.score:.0f}/100</b>\n"
            f"🎯 <b>Strictness: {len(result.passed_params)}/20 Passed</b>\n\n"
            f"🪙 <b>{token.base_token_name}</b> ({token.base_token_symbol})\n"
            f"<code>{token.base_token_address}</code>\n"
            f"🔗 Chain: {token.chain_id} {web_link} {social_links}\n\n"
            f"💧 Liq: ${token.liquidity_usd:,.0f} | 🧢 MC: ${token.fdv:,.0f}\n"
            f"🚀 <b>Potential: ${(result.predicted_fdv):,.0f} ({(result.predicted_fdv/token.fdv if token.fdv else 0):.1f}x)</b>\n"
            f"📊 1H Vol: ${token.volume_h1:,.0f} | ⏰ Age: {(result.details.get('token_age_minutes', 0)):.1f}m\n\n"
            f"<b>🛡️ Verified Criteria:</b>\n{passed_text}\n\n"
            f"📡 <b>Data Sources:</b> DexScreener, GoPlus Security, Moralis\n"
            f"❌ Failed: {len(result.failed_params)} items\n"
            f"🚩 Risks: {', '.join(result.risk_flags) if result.risk_flags else 'None'}\n\n"
            f"<a href='{token.url}'>🔎 View on DexScreener</a>"
        )
        
        # Determine endpoint (Photo or Text)
        if token.icon_url:
            url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendPhoto"
            payload = {
                "chat_id": Config.TELEGRAM_CHAT_ID,
                "photo": token.icon_url,
                "caption": message,
                "parse_mode": "HTML"
            }
        else:
            url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": Config.TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
        
        try:
            async with aiohttp.ClientSession() as session:
                # For photo, we use 'json' for params? No, usually params or data for POST
                # Aiohttp handles json kwarg as JSON body. Telegram API supports JSON for sendMessage
                # For sendPhoto with URL, JSON body works if keys are correct
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                         data = await resp.json()
                         return data.get("result", {}).get("message_id")
                    else:
                        logger.error(f"Failed to send Telegram alert: {resp.status} {await resp.text()}")
        except Exception as e:
            logger.error(f"Error sending Telegram alert: {e}")
        return None

    @staticmethod
    async def send_message(text: str):
        """
        Sends a simple text message. Returns message_id.
        """
        if not Config.TELEGRAM_ENABLED or not Config.TELEGRAM_BOT_TOKEN:
            return None

        url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": Config.TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("result", {}).get("message_id")
                    else:
                        logger.error(f"Report send failed: {resp.status}")
        except Exception as e:
             logger.error(f"Error sending report: {e}")
        return None

    @staticmethod
    async def delete_message(chat_id, message_id):
        if not Config.TELEGRAM_ENABLED or not Config.TELEGRAM_BOT_TOKEN:
            return

        url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/deleteMessage"
        payload = {"chat_id": chat_id, "message_id": message_id}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    # Ignore errors (e.g. message too old or already deleted)
                    pass 
        except Exception:
            pass

    @staticmethod
    async def get_updates(offset: int = 0):
        """
        Polls for new updates (messages).
        Returns Tuple(updates_list, next_offset)
        """
        if not Config.TELEGRAM_ENABLED or not Config.TELEGRAM_BOT_TOKEN:
            return [], offset

        url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/getUpdates"
        params = {"offset": offset, "timeout": 1}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result = data.get("result", [])
                        
                        if not result:
                            return [], offset
                            
                        # Calculate next offset
                        last_update_id = result[-1]["update_id"]
                        next_offset = last_update_id + 1
                        
                        return result, next_offset
                    else:
                        return [], offset
        except Exception:
            return [], offset
