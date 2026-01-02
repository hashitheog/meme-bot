from bot.config import Config
from bot.models.token import Token
from bot.analyzer.goplus import GoPlusClient

class RiskEngine:
    def __init__(self):
        self.goplus = GoPlusClient()

    async def check_risks(self, token: Token, params: dict) -> list[str]:
        """
        Evaluates parameters for specific risk flags, including external Security API.
        """
        flags = []
        
        # 1. Low Liquidity
        try:
            liq = float(params.get("initial_liquidity", 0))
        except: liq = 0.0
            
        if liq < 500: # Very low liquidity
            flags.append("CRITICAL_LOW_LIQUIDITY")

        # 2. Imbalanced Liquidity/MCap
        try:
            liq_ratio = float(params.get("liquidity_mcap_ratio", 0))
        except: liq_ratio = 0.0
        
        if liq_ratio < 0.05 and liq > 1000:
            flags.append("LOW_LIQUIDITY_RATIO")

        # 3. GoPlus Security Checks
        try:
            sec_data = await self.goplus.check_token_security(token.base_token_address, token.chain_id)
            token.security_data = sec_data # Store for reference
            
            # A. Honeypot
            if int(sec_data.get("is_honeypot", 0)) == 1:
                flags.append("SCAM_HONEYPOT")
                
            # B. Taxes (High Tax > 30% is risky, > 50% is instant reject)
            buy_tax = float(sec_data.get("buy_tax", 0) or 0)
            sell_tax = float(sec_data.get("sell_tax", 0) or 0)
            
            if buy_tax > 0.50 or sell_tax > 0.50:
                flags.append("CRITICAL_HIGH_TAX")
            elif buy_tax > 0.30 or sell_tax > 0.30:
                flags.append("HIGH_TAX")
                
            # C. Ownership & Minting
            # isOpenSource: 0=No, 1=Yes. If 0 and not specialized, ris ky.
            if int(sec_data.get("is_open_source", 1)) == 0:
                 pass # Not necessarily a scam, but higher risk.
                 
            # Owner can mint? (owner_change_balance)
            if int(sec_data.get("owner_change_balance", 0)) == 1:
                flags.append("OWNER_CAN_MINT")

            # D. Holder Concentration (Top 10)
            holders = sec_data.get("holders", [])
            total_holdings = 0.0
            for h in holders[:10]:
                try:
                    p = float(h.get("percent", 0))
                    total_holdings += p
                except: pass
            
            if total_holdings > 0.60: 
                flags.append("HIGH_HOLDER_CONCENTRATION")

            # E. LP Locked?
            lp_holders = sec_data.get("lp_holders", [])
            is_lp_locked = False
            
            for lh in lp_holders:
                addr = lh.get("address", "").lower()
                is_locked = int(lh.get("is_locked", 0))
                percent = float(lh.get("percent", 0))
                
                # Check for burn/lock
                if is_locked == 1:
                    is_lp_locked = True
                elif "0x000000000000000000000000000000000000dead" in addr:
                    is_lp_locked = True
                elif "0x0000000000000000000000000000000000000000" in addr:
                    is_lp_locked = True
                    
                if is_lp_locked and percent > 0.50:
                    break
            
            if not is_lp_locked and lp_holders:
                 flags.append("LP_NOT_LOCKED")
                 
            # F. Moralis Whale Tracking
            if Config.MORALIS_API_KEY:
                from bot.analyzer.moralis import MoralisClient
                if not hasattr(self, 'moralis'): self.moralis = MoralisClient()
                
                # Check recent activity
                transfers = await self.moralis.get_whale_activity(token.base_token_address, token.chain_id)
                if transfers:
                    flags.append("WHALE_DATA_AVAILABLE")
                
        except Exception as e:
            pass
        
        token.security_flags = flags
        return flags
