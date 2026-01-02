import asyncio
import logging
import sys
import os
import sqlite3

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot.simulator.trader import PaperTrader
from bot.models.token import Token

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestSim")

def mock_token(price, name="TestCoin", address="0x123"):
    return Token(
        chain_id="ethereum",
        pair_address=address,
        base_token_address=address,
        base_token_name=name,
        base_token_symbol=name,
        quote_token_address="0xUSDC",
        quote_token_symbol="USDC",
        price_usd=price,
        liquidity_usd=100000,
        fdv=1000000,
        pair_created_at=0,
        volume_h1=1000,
        volume_h6=1000,
        volume_h24=1000,
        price_change_h1=0,
        price_change_h6=0,
        price_change_h24=0,
        txns_h1_buys=10,
        txns_h1_sells=10,
        url="http://test",
        websites=[],
        socials=[]
    )

from bot.storage.db import Database

def test_paper_trader():
    # 1. Init
    db_path = "bot/storage/test_sim.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        
    # Initialize DB Tables
    db = Database(db_path=db_path)
    
    trader = PaperTrader(db_path=db_path)
    
    print("\n--- Initial Portfolio ---")
    print(trader.get_portfolio())
    
    # 2. Buy (Enter Trade)
    t1 = mock_token(1.0, "GEM1", "0xGEM1")
    print("\n--- Buying GEM1 at $1.0 ---")
    trader.enter_trade(t1)
    port = trader.get_portfolio()
    print(f"Balance: {port['balance']:.2f}")
    
    # 3. Update Price (No Change)
    trader.update_positions({"0xGEM1": t1})
    
    # 4. Update Price (2x -> TP)
    print("\n--- GEM1 Pumps to $2.0 (2x) ---")
    t1_pump = mock_token(2.0, "GEM1", "0xGEM1")
    trader.update_positions({"0xGEM1": t1_pump})
    
    port = trader.get_portfolio()
    print(f"Balance after TP: {port['balance']:.2f}")
    print(f"PnL: {port['realized_pnl']:.2f}")

    # 5. Check Trade State (Via Stats)
    # conn = sqlite3.connect("bot/storage/test_sim.db")
    # c = conn.cursor()
    # c.execute("SELECT current_quantity, status, log FROM trades")
    # print("Trade Data:", c.fetchone())
    # conn.close()

    # 6. Verify Stats
    print("\n--- Detailed Stats ---")
    stats = trader.get_detailed_stats()
    for k, v in stats.items():
        print(f"{k}: {v}")
    
    print("\n--- Summary Text (Telegram) ---")
    print(trader.get_summary_text())

if __name__ == "__main__":
    test_paper_trader()
