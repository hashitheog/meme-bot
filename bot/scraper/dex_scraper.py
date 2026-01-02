import asyncio
import logging
import time
from typing import List, Optional, Tuple
from bot.scraper.dex_api import DexAPI
from bot.models.token import Token

logger = logging.getLogger(__name__)

class DexScraper:
    def __init__(self):
        self.api = DexAPI()

    async def run_cycle(self) -> List[Token]:
        """
        Runs a single scraping cycle:
        1. Fetch latest profiles
        2. Get detailed pair info (Concurrent)
        3. Normalize to Token objects
        """
        logger.info("Starting scrape cycle...")
        
        # 1. Fetch Latest Profiles
        profiles = await self.api.fetch_latest_pairs()
        if not profiles:
            logger.warning("No new profiles found.")
            return []
            
        logger.info(f"Found {len(profiles)} new profiles. Fetching details concurrently...")
        
        tokens: List[Token] = []
        tasks = []
        
        # Prepare Tasks
        for profile in profiles:
            token_address = profile.get("tokenAddress")
            if not token_address:
                continue
            
            # Pass profile data (like icon) to be merged later
            tasks.append(self._fetch_and_normalize(token_address, profile))
            
        # Execute Concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for res in results:
            if isinstance(res, Token):
                tokens.append(res)
            elif isinstance(res, Exception):
                logger.debug(f"Task failed: {res}")
            
        return tokens

    async def _fetch_and_normalize(self, token_address: str, profile: dict) -> Optional[Token]:
        # Helper to fetch pairs and normalize specific token
        try:
            pairs_data = await self.api.get_pairs_by_token_address(token_address)
            if not pairs_data:
                return None
            
            best_pair = pairs_data[0]
            # Merge profile info (icon) into pair data for normalization
            if "icon" in profile:
                best_pair["info"] = best_pair.get("info", {})
                best_pair["info"]["icon"] = profile["icon"] # some endpoints use 'icon', others 'imageUrl'
            elif "imageUrl" in profile:
                best_pair["info"] = best_pair.get("info", {})
                best_pair["info"]["icon"] = profile["imageUrl"]

            return self._normalize_pair(best_pair)
        except Exception as e:
            return None

    def _normalize_pair(self, data: dict) -> Optional[Token]:
        """
        Converts raw API dict to Token model.
        """
        try:
            base = data.get("baseToken", {})
            quote = data.get("quoteToken", {})
            
            # timestamps in API are often ms
            created_at = data.get("pairCreatedAt", int(time.time() * 1000))
            
            token = Token(
                chain_id=data.get("chainId", "unknown"),
                pair_address=data.get("pairAddress", ""),
                base_token_address=base.get("address", ""),
                base_token_name=base.get("name", "Unknown"),
                base_token_symbol=base.get("symbol", "UNK"),
                quote_token_address=quote.get("address", ""),
                quote_token_symbol=quote.get("symbol", "UNK"),
                
                price_usd=float(data.get("priceUsd", 0) or 0),
                liquidity_usd=float(data.get("liquidity", {}).get("usd", 0) or 0),
                fdv=float(data.get("fdv", 0) or 0),
                
                pair_created_at=created_at,
                
                volume_h1=float(data.get("volume", {}).get("h1", 0) or 0),
                volume_h6=float(data.get("volume", {}).get("h6", 0) or 0),
                volume_h24=float(data.get("volume", {}).get("h24", 0) or 0),
                
                price_change_h1=float(data.get("priceChange", {}).get("h1", 0) or 0),
                price_change_h6=float(data.get("priceChange", {}).get("h6", 0) or 0),
                price_change_h24=float(data.get("priceChange", {}).get("h24", 0) or 0),
                
                txns_h1_buys=int(data.get("txns", {}).get("h1", {}).get("buys", 0) or 0),
                txns_h1_sells=int(data.get("txns", {}).get("h1", {}).get("sells", 0) or 0),
                
                url=data.get("url", ""),
                websites=data.get("info", {}).get("websites", []),
                socials=data.get("info", {}).get("socials", []),
                icon_url=data.get("info", {}).get("icon", None) or data.get("info", {}).get("imageUrl", None),
                raw_data=data
            )
            return token
            return token
        except Exception as e:
            logger.error(f"Normalization failed: {e}")
            return None

    async def fetch_specific_pairs(self, pairs_to_fetch: List[Tuple[str, str]]) -> List[Token]:
        """
        Fetches up-to-date data for specific pairs.
        pairs_to_fetch: List of (chain_id, pair_address) tuples
        """
        if not pairs_to_fetch:
            return []
            
        # Group by chain
        by_chain = {}
        for chain, addr in pairs_to_fetch:
            if chain not in by_chain: by_chain[chain] = []
            by_chain[chain].append(addr)
            
        tasks = []
        for chain, addrs in by_chain.items():
            # DexAPI.get_token_pairs internally chunks/calls API
            tasks.append(self.api.get_token_pairs(chain, addrs))
            
        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        tokens = []
        for chain_res in results:
            if isinstance(chain_res, list):
                for pair_data in chain_res:
                    token = self._normalize_pair(pair_data)
                    if token: tokens.append(token)
            elif isinstance(chain_res, Exception):
                logger.error(f"Error fetching specific pairs: {chain_res}")
                    
        return tokens
