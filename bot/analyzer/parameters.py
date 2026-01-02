import time
from bot.models.token import Token

class ParameterExtractor:
    @staticmethod
    def get_token_age_minutes(token: Token) -> float:
        """1. Token age (minutes)"""
        now_ms = time.time() * 1000
        diff_ms = now_ms - token.pair_created_at
        return max(0, diff_ms / 60000)

    @staticmethod
    def get_liquidity_mcap_ratio(token: Token) -> float:
        """5. Liquidity / market cap ratio"""
        if token.fdv == 0:
            return 0.0
        return token.liquidity_usd / token.fdv

    @staticmethod
    def get_buy_sell_ratio(token: Token) -> float:
        """11. Buy vs sell ratio"""
        if token.txns_h1_sells == 0:
            return float(token.txns_h1_buys) if token.txns_h1_buys > 0 else 0.0
        return token.txns_h1_buys / token.txns_h1_sells

    @staticmethod
    def get_volume_liquidity_ratio(token: Token) -> float:
        """12. Volume / liquidity ratio"""
        if token.liquidity_usd == 0:
            return 0.0
        return token.volume_h1 / token.liquidity_usd

    @staticmethod
    def extract_all(token: Token) -> dict:
        """
        Extracts all calculable parameters into a dictionary.
        Some parameters require external tools (contract analysis) and are stubbed.
        """
        age = ParameterExtractor.get_token_age_minutes(token)
        
        return {
            # A. Age & Launch Quality
            "token_age_minutes": age,
            "initial_liquidity": token.liquidity_usd,
            
            # B. Liquidity & Safety
            "liquidity_mcap_ratio": ParameterExtractor.get_liquidity_mcap_ratio(token),
            "chain": token.chain_id,
            
            # C. Volume & Momentum
            "volume_h1": token.volume_h1,
            "buy_sell_ratio": ParameterExtractor.get_buy_sell_ratio(token),
            "vol_liq_ratio": ParameterExtractor.get_volume_liquidity_ratio(token),
            "price_change_h1": token.price_change_h1,
            
            # D. Contract & Tokenomics (Stubs/Placeholders - requires deep contract scraping)
            "mint_disabled": True, # Placeholder: Assume safe for basic filter, or implement scraper
            "is_honeypot": False, # Placeholder
            
            # E. Behavioral
            "tx_count": token.txns_h1_buys + token.txns_h1_sells
        }
