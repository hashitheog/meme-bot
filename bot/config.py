import os

class Config:
    # --- API ---
    DEX_SCREENER_API_URL = "https://api.dexscreener.com/latest/dex/tokens/" # Verify precise endpoint for new pairs if different
    # DexScreener doesn't have a simple "latest pairs" endpoint in their public free API usually, 
    # but often people use specific chain endpoints or search. 
    # For this bot, we might need to rely on their search or specific chain latest endpoints if available.
    # However, standard practice is often `https://api.dexscreener.com/token-profiles/latest/v1` or similar if documented.
    # Let's assume we'll use a known working endpoint or search for now.
    # Actually, the user prompt implies collecting "newly listed token pairs". 
    # Many bots scrape `https://api.dexscreener.com/token-profiles/latest/v1` or use the `search` endpoint.
    # We will use the standard public API root for now.
    
    # --- SCRAPER ---
    REQUEST_TIMEOUT = 10
    MAX_RETRIES = 3
    RETRY_DELAY_EXPONENT = 2
    USER_AGENT_ROTATION = True
    
    # --- SECURITY (GoPlus) ---
    GOPLUS_KEY = os.getenv("GOPLUS_KEY", "Q47k1kVumUUHf5hFXtf0")
    GOPLUS_SECRET = os.getenv("GOPLUS_SECRET", "EUFYPjrxSq8f0x6Me62YN0Sm9U4A7aeP")
    
    # --- ANALYTICS (Moralis) ---
    MORALIS_API_KEY = os.getenv("MORALIS_API_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJub25jZSI6Ijg2NjBlY2NhLTA0N2EtNGJiYy04ZTJlLTNlYWIyZjZkOGY2OSIsIm9yZ0lkIjoiNDg4NDAyIiwidXNlcklkIjoiNTAyNTA4IiwidHlwZUlkIjoiYjAyOWNjNjktOWQzOS00ZGNkLThmN2MtZDkzYjk5YTc3NmE5IiwidHlwZSI6IlBST0pFQ1QiLCJpYXQiOjE3NjczODAyMDEsImV4cCI6NDkyMzE0MDIwMX0.e2fxTOXTbjEqZ6H8hIwfBynY-h7rZKkQdRwEPu7N3Uc")
    
    # --- SCORING THRESHOLDS ---
    SCORE_REJECT = 70
    SCORE_WATCHLIST_MIN = 80
    SCORE_WATCHLIST_MAX = 89
    SCORE_ALERT_MIN = 90 # Strict: Only >90
    SCORE_ALERT_MAX = 98
    SCORE_HIGH_PRIORITY = 99 # Pretty much perfect only
    
    # --- 20-PARAMETER CONFIG ---
    # Define weights or thresholds here
    MIN_LIQUIDITY = 1000 # Sniper Mode
    MIN_AGE_MINUTES = 0 # Fresh from the oven
    MAX_AGE_HOURS = 24
    
    # Weights (Total should ideally sum to ~100 or be normalized)
    WEIGHTS = {
        "age_quality": 10,
        "liquidity_safety": 30,
        "volume_momentum": 30,
        "contract_tokenomics": 20,
        "behavioral": 10
    }

    # --- ALERTS ---
    TELEGRAM_ENABLED = True
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8368684518:AAHHx-XA6oVFRKP2Z-zgs3l55HBkSaS4abA")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7944897949")
    
    # --- SYSTEM ---
    LOG_LEVEL = "INFO"
