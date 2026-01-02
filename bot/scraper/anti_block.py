import asyncio
import random
import logging
from bot.config import Config

logger = logging.getLogger(__name__)

class AntiBlock:
    def __init__(self):
        # Hardcoded list to avoid fake_useragent fetch failures/limitations
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36"
        ]
        self.last_request_time = 0

    def get_headers(self) -> dict:
        """
        Generates headers with a random User-Agent.
        """
        ua = random.choice(self.user_agents) if Config.USER_AGENT_ROTATION else self.user_agents[0]
        
        headers = {
            "Accept": "text/html,application/json,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": ua
        }
        return headers

    async def sleep_random(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """
        Sleeps for a random duration to mimic human behavior.
        """
        delay = random.uniform(min_seconds, max_seconds)
        # logger.debug(f"Sleeping for {delay:.2f}s") # Reduced logging noise
        await asyncio.sleep(delay)

    async def backoff(self, attempt: int):
        """
        Exponential backoff sleep.
        """
        delay = (Config.RETRY_DELAY_EXPONENT ** attempt) + random.uniform(0, 1)
        logger.warning(f"Backing off for {delay:.2f}s (Attempt {attempt})")
        await asyncio.sleep(delay)
