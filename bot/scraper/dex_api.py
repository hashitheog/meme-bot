import aiohttp
import asyncio
import logging
from typing import List, Optional, Dict, Any
from bot.config import Config
from bot.scraper.anti_block import AntiBlock

logger = logging.getLogger(__name__)

class DexAPI:
    def __init__(self):
        self.anti_block = AntiBlock()

    async def fetch_latest_pairs(self) -> List[Dict[str, Any]]:
        """
        Fetches the latest token profiles/pairs. 
        Note: This uses a common endpoint pattern. If it changes, update here.
        """
        # "https://api.dexscreener.com/token-profiles/latest/v1" is often used for new tokens events
        # Alternatively, we can use https://api.dexscreener.com/latest/dex/search/?q=* (but that's search)
        # Let's try the token-profiles one as it's the standard feed for many bots.
        url = "https://api.dexscreener.com/token-profiles/latest/v1"
        return await self._make_request(url)

    async def get_token_pairs(self, chain_id: str, pair_addresses: List[str]) -> List[Dict[str, Any]]:
        """
        Fetches specific pair details. 
        DexScreener allows multiple pairs: /latest/dex/pairs/{chainId}/{pairAddresses}
        """
        if not pair_addresses:
            return []
        
        # Max 30 pairs per request usually, let's chunk if valid
        pairs_str = ",".join(pair_addresses[:30]) 
        url = f"https://api.dexscreener.com/latest/dex/pairs/{chain_id}/{pairs_str}"
        data = await self._make_request(url)
        return data.get("pairs", []) if data else []
        
    async def get_pairs_by_token_address(self, token_address: str) -> List[Dict[str, Any]]:
        """
        Fetches pairs for a specific token address.
        """
        url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
        data = await self._make_request(url)
        return data.get("pairs", []) if data else []

    async def _make_request(self, url: str) -> Optional[Any]:
        """
        Internal method to handle requests with retries and anti-block.
        """
        headers = self.anti_block.get_headers()
        
        for attempt in range(Config.MAX_RETRIES):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, timeout=Config.REQUEST_TIMEOUT) as response:
                        if response.status == 200:
                            return await response.json()
                        elif response.status == 429:
                            logger.warning(f"Rate limited on {url}. Retrying...")
                            await self.anti_block.backoff(attempt + 1)
                        else:
                            logger.error(f"Failed to fetch {url}: Status {response.status}")
                            await self.anti_block.backoff(attempt)
                            
            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
                await self.anti_block.backoff(attempt)
        
        return None
