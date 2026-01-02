import aiohttp
import time
import hashlib
import random
import logging
from typing import Optional, Dict, Any
from bot.config import Config

logger = logging.getLogger("GoPlus")

class GoPlusClient:
    BASE_URL = "https://api.gopluslabs.io/api/v1"
    
    # Map DexScreener chain IDs to GoPlus Chain IDs
    CHAIN_MAP = {
        "ethereum": "1",
        "bsc": "56",
        "solana": "solana", # Verify if GoPlus uses 'solana' or ID
        "arbitrum": "42161",
        "polygon": "137",
        "optimism": "10",
        "avalanche": "43114",
        "base": "8453"
    }

    def __init__(self):
        self.key = Config.GOPLUS_KEY
        self.secret = Config.GOPLUS_SECRET
        self._token = None
        self._token_expiry = 0

    async def get_access_token(self) -> Optional[str]:
        """
        Generates access token if needed. 
        (Note: Most GoPlus public endpoints don't strictly require this signature flow 
        unless using higher tiers, but we'll implement header auth if needed).
        
        Actually, for the standard free API, we often just query directly. 
        However, if an App Key is provided, it usually goes in headers or params.
        We will try standard public calls first, or check docs for Key usage.
        
        Based on standard Key usage: 
        Usually headers: {"Authorization": type + " " + signature} or similar.
        But for now, we will assume public endpoint usage which is often open.
        If we need to use the Key/Secret, we would generate a signature.
        
        Let's stick to the simple public endpoint for now, and log if 401/403.
        """
        return None

    async def check_token_security(self, address: str, chain_id: str) -> Dict[str, Any]:
        """
        Checks token security via GoPlus API.
        """
        goplus_chain_id = self.CHAIN_MAP.get(chain_id.lower())
        if not goplus_chain_id:
            # If not mapped, maybe it's already an ID or unchecked
            goplus_chain_id = chain_id 

        url = f"{self.BASE_URL}/token_security/{goplus_chain_id}"
        params = {"contract_addresses": address}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Structure: {"code": 1, "message": "OK", "result": {"addr": {...}}}
                        if data.get("code") == 1 and data.get("result"):
                            # The result is a dict where keys are addresses
                            # We normalize keys to lowercase just in case
                            normalized_result = {k.lower(): v for k, v in data["result"].items()}
                            return normalized_result.get(address.lower(), {})
                    else:
                        logger.warning(f"GoPlus API Error: {response.status} for {chain_id}:{address}")
        except Exception as e:
            logger.error(f"GoPlus request failed: {e}")
            
        return {}
