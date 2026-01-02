import aiohttp
import logging
from typing import Dict, Any, List
from bot.config import Config

logger = logging.getLogger("Moralis")

class MoralisClient:
    BASE_URL = "https://deep-index.moralis.io/api/v2.2"
    
    # Map DexScreener chain IDs to Moralis Chain Hex/Names
    # Moralis usually takes "eth", "0x1", "bsc", "0x38", "solana"
    CHAIN_MAP = {
        "ethereum": "0x1",
        "bsc": "0x38",
        "solana": "solana", 
        "arbitrum": "0xa4b1",
        "polygon": "0x89",
        "optimism": "0xa",
        "avalanche": "0xa86a",
        "base": "0x2105"
    }

    def __init__(self):
        self.api_key = Config.MORALIS_API_KEY
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key
        }

    async def get_token_holders_distribution(self, address: str, chain: str) -> Dict[str, Any]:
        """
        Fetches holder stats to check for centralization.
        Note: Moralis Free Tier might have limits on extensive holder lists, but stats are efficient.
        """
        # For EVM
        chain_id = self.CHAIN_MAP.get(chain.lower(), chain)
        if chain_id == "solana":
             # Solana uses different endpoint usually: /solana/
             return {} # Placeholder for Solana if needed

        url = f"{self.BASE_URL}/erc20/{address}/owners"
        params = {"chain": chain_id, "limit": 20, "order": "DESC"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # data['result'] list of owners
                        # We can calculate top holder concentration here if GoPlus didn't
                        owners = data.get("result", [])
                        return {"owners": owners, "count": len(owners)}
                    else:
                        logger.warning(f"Moralis Holders Error: {resp.status}")
                        return {}
        except Exception as e:
            logger.error(f"Moralis request failed: {e}")
            return {}

    async def get_whale_activity(self, address: str, chain: str) -> List[Dict]:
        """
        Fetches recent large transfers to detect 'Whale' buys.
        Logic: Look for transfers TO current holders or FROM Dex pair.
        """
        chain_id = self.CHAIN_MAP.get(chain.lower(), chain)
        url = f"{self.BASE_URL}/erc20/{address}/transfers"
        params = {"chain": chain_id, "limit": 50, "order": "DESC"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("result", [])
                    return []
        except Exception:
            return []
