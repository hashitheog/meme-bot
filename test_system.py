import asyncio
import time
from bot.models.token import Token
from bot.analyzer.scoring import ScoringEngine

def test_scoring():
    print("Testing Scoring Engine...")
    
    # Mock Token: Good Setup
    good_token = Token(
        chain_id="solana",
        pair_address="mock_pair_good",
        base_token_address="mock_token_good",
        base_token_name="Good Coin",
        base_token_symbol="GOOD",
        quote_token_address="sol",
        quote_token_symbol="SOL",
        price_usd=0.001,
        liquidity_usd=50000, # High Liquidity
        fdv=100000,
        pair_created_at=int((time.time() - 3600) * 1000), # 1 hour old (60 mins) -> Ideal age
        volume_h1=15000, # High Volume
        volume_h6=0,
        volume_h24=0,
        price_change_h1=10,
        price_change_h6=0,
        price_change_h24=0,
        txns_h1_buys=100,
        txns_h1_sells=50,
        url="http://mock",
        raw_data={}
    )
    
    # Mock Token: Bad Setup (Rug risk)
    bad_token = Token(
        chain_id="solana",
        pair_address="mock_pair_bad",
        base_token_address="mock_token_bad",
        base_token_name="Bad Coin",
        base_token_symbol="BAD",
        quote_token_address="sol",
        quote_token_symbol="SOL",
        price_usd=0.0001,
        liquidity_usd=3000, # OK Liquidity
        fdv=1000000, # Huge MC vs Liq -> BAD ratio
        pair_created_at=int((time.time() - 60) * 1000), # 1 min old -> Too new
        volume_h1=100,
        volume_h6=0,
        volume_h24=0,
        price_change_h1=0,
        price_change_h6=0,
        price_change_h24=0,
        txns_h1_buys=5,
        txns_h1_sells=0,
        url="http://mock",
        raw_data={}
    )

    engine = ScoringEngine()
    
    # Analyze Good
    res_good = engine.analyze_token(good_token)
    print(f"\nGood Token Result: {res_good.action} (Score: {res_good.score})")
    print(f"Risks: {res_good.risk_flags}")
    print(f"Details: {res_good.details}")
    
    # Analyze Bad
    res_bad = engine.analyze_token(bad_token)
    print(f"\nBad Token Result: {res_bad.action} (Score: {res_bad.score})")
    print(f"Risks: {res_bad.risk_flags}")
    print(f"Details: {res_bad.details}")

if __name__ == "__main__":
    test_scoring()
