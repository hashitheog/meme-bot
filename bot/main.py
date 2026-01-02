import asyncio
import logging
import sys
import os
import time
import colorama
from colorama import Fore, Style

# Fix ModuleNotFoundError by adding project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.config import Config
from bot.scraper.dex_scraper import DexScraper
from bot.analyzer.scoring import ScoringEngine
from bot.models.token import AnalysisResult
from bot.alerts.desktop import DesktopNotifier
from bot.alerts.telegram import TelegramAlert
from bot.storage.db import Database

# Setup logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Main")

# Initialize Colorama
colorama.init(autoreset=True)

from bot.simulator.trader import PaperTrader
from bot.server import start_server

class Bot:
    def __init__(self):
        self.scraper = DexScraper()
        self.scorer = ScoringEngine()
        self.db = Database()
        self.trader = PaperTrader() # Initialize Trader
        self.running = True
        self.last_report_time = 0
        self.tele_offset = 0

    async def start(self):
        logger.info("🔥 Meme Coin Analysis Bot Started")
        logger.info(f"Param Config: Age < {Config.MAX_AGE_HOURS}h, Liq > ${Config.MIN_LIQUIDITY}")
        
        # --- START KEEP-ALIVE SERVER (Render) ---
        await start_server()
        
        # --- AUTO-RESET ON STARTUP ---
        logger.info("♻️ Performing startup reset (Fresh Start)...")
        self.trader.reset_portfolio(initial_balance=200.0)
        self.db.reset_data()
        # Also clear chat history on startup to be clean? 
        # User said "when i run the bot... database cleared". 
        # Might be annoying to wipe chat on every restart if debugging, but user asked for "fresh start".
        # Let's clean chat history too for consistency with /reset.
        msg_ids = self.db.get_and_clear_message_ids()
        for cid, mid in msg_ids:
             await TelegramAlert.delete_message(cid, mid)
             await asyncio.sleep(0.05)
        
        await TelegramAlert.send_message("🔥 **Bot Started!**\n\nFresh session initialized.\nBalance: **$200.00**\nStrict Mode: **ON**")
        
        while self.running:
            try:
                # 0. Check Telegram Commands
                updates, self.tele_offset = await TelegramAlert.get_updates(self.tele_offset)
                for update in updates:
                     msg = update.get("message", {}).get("text", "")
                     
                     if "/balance" in msg:
                         report = self.trader.get_summary_text()
                         mid = await TelegramAlert.send_message(report)
                         if mid: self.db.log_message(Config.TELEGRAM_CHAT_ID, mid)
                         logger.info("Sent balance report by command.")
                         
                     elif "/reset" in msg:
                         # 1. Reset Sim Data
                         self.trader.reset_portfolio(initial_balance=200.0)
                         self.db.reset_data()
                         
                         # 2. Clear Chat History (Of bot messages)
                         msg_ids = self.db.get_and_clear_message_ids()
                         for cid, mid in msg_ids:
                             await TelegramAlert.delete_message(cid, mid)
                             await asyncio.sleep(0.05) # Rate limit safety
                             
                         # 3. Send confirmation
                         mid = await TelegramAlert.send_message("♻️ **Bot Reset!**\n\nHistory wiped.\nBalance: $200.00.")
                         if mid: self.db.log_message(Config.TELEGRAM_CHAT_ID, mid)
                         logger.info("Bot execution state reset by command.")

                # 1. Scrape
                tokens = await self.scraper.run_cycle()
                
                # Update positions first with latest prices
                # We need a map of address -> Token to update prices. 
                # Since scrape returns list, let's map it.
                token_map = {t.pair_address: t for t in tokens}
                notifications = self.trader.update_positions(token_map)
                
                # Send Trade Updates (TP/SL)
                for notif in notifications:
                    mid = await TelegramAlert.send_message(notif)
                    if mid: self.db.log_message(Config.TELEGRAM_CHAT_ID, mid)
                
                if tokens:
                    logger.info(f"Analyzing {len(tokens)} tokens...")
                
                for token in tokens:
                    # 2. Check Cache
                    if self.db.is_seen(token.pair_address):
                        continue
                    
                    # 3. Analyze
                    result = await self.scorer.analyze_token(token)
                    
                    # 4. Filter & Output & Trade
                    await self._process_result(result)
                    
                    # 5. Mark seen
                    self.db.mark_seen(token.pair_address, token.chain_id)
                
                # Check for Hourly Report
                if time.time() - self.last_report_time > 3600:
                    await self._send_report()
                    self.last_report_time = time.time()
                
                # Wait before next cycle
                logger.info("Cycle complete. Waiting...")
                await asyncio.sleep(30) 
                
            except KeyboardInterrupt:
                self.stop()
            except Exception as e:
                logger.error(f"Cycle error: {e}")
                await asyncio.sleep(30)

    async def _process_result(self, result: AnalysisResult):
        token = result.token
        
        # Decide color based on action
        color = Fore.WHITE
        if result.action == "HIGH_PRIORITY":
            color = Fore.GREEN
        elif result.action == "ALERT":
            color = Fore.CYAN
        elif result.action == "WATCHLIST":
            color = Fore.YELLOW
        elif result.action == "REJECT":
            color = Fore.RED

        # Console Output
        if result.action != "REJECT" or Config.LOG_LEVEL == "DEBUG":
            print(f"\n{color}{'='*50}")
            print(f"{Style.BRIGHT}Token: {token.base_token_name} ({token.base_token_symbol})")
            print(f"{color}Score: {result.score:.0f}/100 [{result.action}]")
            print(f"{Fore.WHITE}Chain: {token.chain_id} | Pair Age: {result.details.get('token_age_minutes',0):.1f}m")
            print(f"CA: {token.base_token_address}")
            if token.websites:
                print(f"Web: {token.websites[0].get('url', 'N/A')}")
            if result.predicted_fdv > 0:
                print(f"{Fore.GREEN}Potential MC: ${result.predicted_fdv:,.0f} ({(result.predicted_fdv/token.fdv):.1f}x)")
            print(f"Liq: ${token.liquidity_usd:,.0f} | MC: ${token.fdv:,.0f}")
            print(f"Risks: {result.risk_flags}")
            print(f"{color}{'='*50}\n")
        
        # Alerts & Trading
        if result.action in ["HIGH_PRIORITY", "ALERT"]:
            # Check Trade Limit BEFORE alerting
            open_count = self.trader.get_open_count()
            if open_count >= 4:
                # Limit reached: Do not alert, do not enter trade
                # Maybe log it as "Missed Signal"
                logger.info(f"Buffered Max Signals ({open_count}/4). Suppressing alert for {token.base_token_symbol}.")
                # Optional: Send a "Missed" notification if desired, but user said "only 4 signals at most".
                # So we stay silent.
                return 

            # Send Alert
            mid = await TelegramAlert.send_alert(result)
            if mid: self.db.log_message(Config.TELEGRAM_CHAT_ID, mid)
            DesktopNotifier.send_notification(result)
            
            # Enter Paper Trade
            self.trader.enter_trade(token)

    async def _send_report(self):
        """Send hourly portfolio report"""
        port = self.trader.get_portfolio()
        msg = (
            f"📊 **Hourly Portfolio Report** 📊\n\n"
            f"Balance: `${port['balance']:.2f}`\n"
            f"Realized PnL: `${port['realized_pnl']:.2f}`\n"
            f"Fees Paid: `${port['fees_paid']:.2f}`\n"
            f"Strategy: Risk 5% | Sell Half @ 2x"
        )
        # Using a dummy method for now, or assume TelegramAlert has send_message
        await TelegramAlert.send_message(msg)

    def stop(self):
        self.running = False
        logger.info("Stopping bot...")

if __name__ == "__main__":
    try:
        # Windows selector loop policy fix
        if sys.platform == 'win32':
             asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
             
        bot = Bot()
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        pass
