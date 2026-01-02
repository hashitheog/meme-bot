from dataclasses import dataclass
from typing import Optional, List, Dict, Any

@dataclass
class Token:
    """
    Represents a token pair from DexScreener.
    """
    chain_id: str
    pair_address: str
    base_token_address: str
    base_token_name: str
    base_token_symbol: str
    quote_token_address: str
    quote_token_symbol: str
    price_usd: float
    liquidity_usd: float
    fdv: float  # Market Cap (Fully Diluted Valuation)
    pair_created_at: int # Timestamp in ms
    volume_h1: float
    volume_h6: float
    volume_h24: float
    price_change_h1: float
    price_change_h6: float
    price_change_h24: float
    txns_h1_buys: int
    txns_h1_sells: int
    url: str
    icon_url: Optional[str] = None
    websites: List[Dict[str, str]] = None
    socials: List[Dict[str, str]] = None
    
    # Raw data for extra flexibility
    raw_data: Dict[str, Any] = None
    
    # Security Data (GoPlus)
    security_data: Dict[str, Any] = None
    security_flags: List[str] = None

@dataclass
class AnalysisResult:
    """
    Result of the token analysis process.
    """
    token: Token
    score: float
    risk_level: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    action: str      # "REJECT", "WATCHLIST", "ALERT", "HIGH_PRIORITY"
    passed_params: List[str]
    failed_params: List[str]
    risk_flags: List[str]
    details: Dict[str, Any] # Detailed breakdown of scores
    predicted_fdv: float = 0.0 # Predicted Market Cap Potential
