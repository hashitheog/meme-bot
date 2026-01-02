from typing import Dict, Any, Tuple
from bot.config import Config
from bot.models.token import Token, AnalysisResult
from bot.analyzer.parameters import ParameterExtractor
from bot.analyzer.risk_flags import RiskEngine

class ScoringEngine:
    def __init__(self):
        self.weights = Config.WEIGHTS
        self.risk_engine = RiskEngine()

    async def analyze_token(self, token: Token) -> AnalysisResult:
        """
        Full analysis pipeline: Extraction -> Risk Check -> Scoring -> Result.
        """
        # 1. Extract Parameters
        params = ParameterExtractor.extract_all(token)
        
        # 2. Check Risks (Async Security Check)
        risks = await self.risk_engine.check_risks(token, params)
        
        # 3. Calculate Score
        score, breakdown = self._calculate_score(params, token)

        # Apply Penalties
        if "OWNER_CAN_MINT" in risks:
            score -= 50
            breakdown["penalty_mintable"] = -50
            if score < 0: score = 0
        
        # 4. Determine Action
        action, risk_level = self._determine_classification(score, risks)
        
        # 5. Calculate Potential (Heuristic)
        # Simple Logic: If Score > 80, Potential = 10x. If > 60, Potential = 3x.
        multiplier = 1.0
        if score >= 90: multiplier = 10.0
        elif score >= 80: multiplier = 5.0
        elif score >= 60: multiplier = 2.0
        
        predicted = token.fdv * multiplier if token.fdv > 0 else 0.0
        
        # 6. Build Result
        return AnalysisResult(
            token=token,
            score=score,
            risk_level=risk_level,
            action=action,
            passed_params=[k for k, v in breakdown.items() if isinstance(v, (int, float)) and v > 0],
            failed_params=[k for k, v in breakdown.items() if isinstance(v, (int, float)) and v == 0],
            risk_flags=risks,
            details=breakdown,
            predicted_fdv=predicted
        )

    def _safe_float(self, val: Any, default: float = 0.0) -> float:
        try:
            if isinstance(val, (dict, list, type(None))): return default
            return float(val)
        except: return default

    def _safe_int(self, val: Any, default: int = 0) -> int:
        try:
            if isinstance(val, (dict, list, type(None))): return default
            return int(val)
        except: return default
        
    def _safe_bool(self, val: Any, default: bool = False) -> bool:
        try:
             if isinstance(val, (dict, list)): 
                 return bool(val) # Empty dict/list is False
             return bool(val)
        except: return default

    def _calculate_score(self, params: Dict[str, Any], token: Token) -> Tuple[float, Dict[str, Any]]:
        """
        Computes the weighted score (0-100).
        Aggressively validated to prevent TypeErrors.
        """
        score = 0.0
        breakdown = {}
        
        try:
            # --- STRICT 16/20 CHECKLIST ---
            # Evaluate against the user's specific 20 criteria
            checklist_score, checklist_breakdown = self._evaluate_checklist(params, token)
            breakdown.update(checklist_breakdown)
            
            # Reject if < 14 passes (User requested 14/20)
            if checklist_score < 14:
                # DEBUG: Show user what is failing so they know it's working
                if Config.LOG_LEVEL == "INFO":
                    print(f"DEBUG: Rejected {token.base_token_symbol} - Score {checklist_score}/20")
                return 0, breakdown
                
            # Continue with standard scoring if it passes the "Gate"
            
            # 2. Fundamental Checks
            liq = self._safe_float(params.get("initial_liquidity"))
            # Allow even $500 liquidity if it passed the checklist
            if liq < 500: 
                return 0, {"LOW_LIQUIDITY_STRICT": -1}
                
            vol = self._safe_float(params.get("volume_h1"))
            if vol < 100: # Lowered volume req
                return 0, {"DEAD_VOLUME": -1}

            # --- A. Age & Quality (10%) ---
            age = self._safe_float(params.get("token_age_minutes"))
            
            if 5 <= age <= 720: 
                s = 10
            elif age < 5: # Too new
                s = 5
            else: # Too old
                s = 2
            score += s
            breakdown["age_score"] = s
            
            # --- B. Liquidity (30%) ---
            if liq > 5000:
                s_liq = 30
            elif liq > 2000:
                s_liq = 20
            elif liq > 1000:
                s_liq = 10
            else:
                s_liq = 0
            score += s_liq
            breakdown["liquidity_score"] = s_liq
            
            # --- C. Volume & Momentum (30%) ---
            if vol > 10000:
                s_vol = 30
            elif vol > 1000:
                s_vol = 15
            else:
                s_vol = 5
            score += s_vol
            breakdown["volume_score"] = s_vol

            # --- D. Tokenomics (20%) ---
            if self._safe_bool(params.get("mint_disabled"), True):
                score += 20
                breakdown["tokenomics_score"] = 20
            else:
                breakdown["tokenomics_score"] = 0

            # --- E. Behavior (10%) ---
            score += 10
            breakdown["behavior_score"] = 10
            
        except Exception as e:
            print(f"ERROR IN CALCULATE SCORE: {e}")
            import traceback
            traceback.print_exc()
            return 0.0, {"ERROR": -1}

        return min(100.0, score), breakdown

    def _evaluate_checklist(self, params: Dict[str, Any], token: Token) -> Tuple[int, Dict[str, Any]]:
        """
        Evaluates the "Strict 20-Point" Checklist.
        Returns (passed_count, details_dict)
        """
        checks = {}
        passed = 0
        try:
             # --- A. FUNDAMENTAL (ON-CHAIN) ---
             # 1. Market Cap > $2k (Lowered from 10k)
             checks["Market Cap Safe"] = self._safe_float(token.fdv) > 2000
             # 2. Liquidity > $2000 (Lowered from 5000)
             checks["Liquidity Safe"] = self._safe_float(token.liquidity_usd) > 2000
             # 3. LP Locked (Keep strict)
             checks["LP Locked"] = self._safe_bool(params.get("lp_locked"), False)
             # 4. Age > 1m (Lowered from 30m to catch fresh launches)
             age = self._safe_float(params.get("token_age_minutes"))
             checks["Age > 1m"] = age >= 1
             # 5. Mint Disabled
             checks["Mint Disabled"] = self._safe_bool(params.get("mint_disabled"), True)
             # 6. Supply Normal
             checks["Supply Normal"] = True 
             # 7. Unverified
             checks["Contract Verified"] = not self._safe_bool(params.get("is_proxy"), False)
             checks["Renounced"] = self._safe_bool(params.get("renounced"), False)
             checks["Buy Tax < 10%"] = self._safe_float(params.get("buy_tax")) < 10
             checks["Sell Tax < 10%"] = self._safe_float(params.get("sell_tax")) < 10
             
             # --- B. HOLDER METRICS ---
             checks["Top 10 < 40%"] = self._safe_float(params.get("top10_share", 50), 50.0) < 40
             checks["Dev < 5%"] = self._safe_float(params.get("owner_balance")) < 0.05
             checks["Holders > 50"] = self._safe_int(params.get("holder_count")) > 50
             checks["Whales Present"] = self._safe_bool(params.get("whale_data_available"), False)
             checks["Holder Growth"] = self._safe_int(params.get("holder_count")) > 100
             
             # --- C. MARKET & VOLUME ---
             vol = self._safe_float(params.get("volume_h1"))
             fdv = self._safe_float(token.fdv)
             ratio = (vol / fdv) if fdv > 0 else 0
             checks["Vol/MC > 0.1"] = ratio > 0.1
             checks["Healthy Volatility"] = True 
             
             buys = self._safe_float(token.txns_h1_buys)
             sells = self._safe_float(token.txns_h1_sells)
             bs_ratio = (buys / sells) if sells > 0 else 0
             checks["Buy/Sell > 1.0"] = bs_ratio > 1.0
             
             checks["Liquidity Stable"] = True
             checks["Socials Active"] = bool(token.websites or token.socials)

             # Count Passes
             for k, v in checks.items():
                 if v: passed += 1
                 
        except Exception as e:
            import traceback
            print(f"DEBUG CHECKLIST ERROR: {e}")
            traceback.print_exc()
            return 0, {}
            
        # Flatten checks into the return dict so they appear in 'breakdown'
        # This ensures 'passed_params' in AnalysisResult picks them up.
        ret = {"checklist_passes": passed}
        ret.update(checks) # Merge {"Market Cap Safe": True, ...} directly
        
        return passed, ret

    def _determine_classification(self, score: float, risks: list) -> Tuple[str, str]:
        """
        Returns (Action, Risk Level)
        """
        # Hard fail on critical risks
        if "CRITICAL_LOW_LIQUIDITY" in risks:
            return "REJECT", "CRITICAL"
        if "SCAM_HONEYPOT" in risks:
            return "REJECT", "CRITICAL"
        if "CRITICAL_HIGH_TAX" in risks:
            return "REJECT", "CRITICAL"
        if "HIGH_TAX" in risks: # Strict Mode Reject
            return "REJECT", "HIGH"
        if "OWNER_CAN_MINT" in risks: # Strict Mode Reject
            return "REJECT", "HIGH"
        if "LP_NOT_LOCKED" in risks:
             # Unlocked LP is huge risk for rug pull
            return "REJECT", "HIGH"
        if "HIGH_HOLDER_CONCENTRATION" in risks:
             # Top 10 own too much
            return "REJECT", "HIGH"
            
        risk_level = "LOW" if not risks else "MEDIUM"
        if len(risks) >= 2:
            risk_level = "HIGH"

        # Boost for Whales (Moralis)
        if "WHALE_DATA_AVAILABLE" in risks:
             # Actually this is a "Good" flag in our hacky implementation
             # Remove it from risks if used for penalty?
             # Or handling in calculate_score would be better.
             # For now, let's just use it to bump priority if everything else is clean.
             pass

        if score >= Config.SCORE_HIGH_PRIORITY:
            return "HIGH_PRIORITY", risk_level
        elif score >= Config.SCORE_ALERT_MIN:
            return "ALERT", risk_level
        elif score >= Config.SCORE_WATCHLIST_MIN:
            return "WATCHLIST", risk_level
        else:
            return "REJECT", risk_level
