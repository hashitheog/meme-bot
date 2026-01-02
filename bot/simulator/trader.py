import logging
import json
import time
import sqlite3
from typing import List, Dict, Any
from bot.models.token import Token
from bot.config import Config

logger = logging.getLogger("PaperTrader")

class PaperTrader:
    def __init__(self, db_path="bot/storage/cache.db"):
        self.db_path = db_path
        # Strategy Constants
        self.RISK_PER_TRADE = 0.05 # 5%
        self.GAS_FEE = 0.05       # $0.05 per trade
        self.SLIPPAGE = 0.01      # 1% slippage on sells

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def get_portfolio(self):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT balance, realized_pnl, fees_paid FROM portfolio WHERE id=1")
        row = c.fetchone()
        conn.close()
        if row:
            return {"balance": row[0], "realized_pnl": row[1], "fees_paid": row[2]}
        return {"balance": 200.0, "realized_pnl": 0.0, "fees_paid": 0.0}

    def _update_portfolio(self, balance_change=0.0, pnl_change=0.0, fee=0.0):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""
            UPDATE portfolio 
            SET balance = balance + ?, 
                realized_pnl = realized_pnl + ?,
                fees_paid = fees_paid + ?,
                last_updated = CURRENT_TIMESTAMP
            WHERE id=1
        """, (balance_change, pnl_change, fee))
        conn.commit()
        conn.close()

    def enter_trade(self, token: Token) -> bool:
        """
        Enters a trade if balance allows.
        Risk 5% of CURRENT balance.
        """
        # Check if already open
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT 1 FROM trades WHERE token_address = ? AND status='OPEN'", (token.pair_address,))
        if c.fetchone():
            conn.close()
            return False

        # Enforce Max Concurrent Trades (Risk Management)
        # User wants Max 20% risk with 5% per trade => 4 Trades Max.
        c.execute("SELECT COUNT(*) FROM trades WHERE status='OPEN'")
        open_count = c.fetchone()[0]
        if open_count >= 4:
            logger.info(f"Buffered Max Trades ({open_count}/4). Skipping {token.base_token_symbol}.")
            conn.close()
            return False
            
    def get_active_pairs(self) -> List[tuple]:
        """Returns list of (chain_id, token_address) for all open trades."""
        conn = self._get_conn()
        c = conn.cursor()
        try:
            # chain_id column name check? In enter_trade we used 'chain_id'
            c.execute("SELECT chain_id, token_address FROM trades WHERE status='OPEN'")
            return c.fetchall()
        except:
             return []
        finally:
             conn.close()

    def get_open_count(self) -> int:
        """Returns number of currently open trades"""
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM trades WHERE status='OPEN'")
        count = c.fetchone()[0]
        conn.close()
        return count

        port = self.get_portfolio()
        balance = port["balance"]
        
        # Calculate Risk Amount
        position_size = balance * self.RISK_PER_TRADE
        if position_size < 1.0 or balance < (position_size + self.GAS_FEE):
            logger.warning(f"Insufficient funds for trade: ${balance}")
            conn.close()
            return False

        # Calculate Quantity
        price = token.price_usd
        if price <= 0: 
            conn.close()
            return False
            
        quantity = position_size / price
        
        # Execute Buy
        # Deduct Balance (Cost + Gas)
        cost = position_size
        self._update_portfolio(balance_change=-(cost + self.GAS_FEE), fee=self.GAS_FEE)
        
        # Log Trade
        log_entry = {
            "action": "BUY",
            "price": price,
            "quantity": quantity,
            "cost": cost,
            "time": time.time()
        }
        
        c.execute("""
            INSERT INTO trades (
                token_address, symbol, chain_id, entry_price, current_quantity, 
                cost_basis, last_tp_price, status, log, entry_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            token.pair_address, token.base_token_symbol, token.chain_id, 
            price, quantity, cost, price, "OPEN", json.dumps([log_entry])
        ))
        conn.commit()
        conn.close()
        
        logger.info(f"Entered Trade: {token.base_token_symbol} | Size: ${position_size:.2f} | Qty: {quantity}")
        return True

    def update_positions(self, token_map: Dict[str, Token]) -> List[str]:
        """
        Updates OPEN positions based on latest prices.
        Returns a list of notification strings to send to Telegram.
        """
        notifications = []
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT token_address, entry_price, current_quantity, last_tp_price, log, cost_basis, symbol FROM trades WHERE status='OPEN'")
        rows = c.fetchall()
        
        for row in rows:
            addr, entry, qty, last_tp, log_json, cost_basis, symbol = row
            
            if addr not in token_map:
                continue 
                
            current_token = token_map[addr]
            current_price = current_token.price_usd
            
            # --- 1. STOP LOSS (50% Drop) ---
            # "If down to 50% of original value, exit and save other 50%"
            if current_price <= (entry * 0.5):
                self._close_position(addr, current_price, qty, "STOP_LOSS_50", log_json, cost_basis)
                
                loss_amt = cost_basis - (qty * current_price)
                saved_amt = (qty * current_price)
                msg = (
                    f"🛑 **STOP LOSS HIT: {symbol}**\n"
                    f"📉 Dropped 50% below entry.\n"
                    f"💸 Exited at loss of **${loss_amt:.2f}**\n"
                    f"🛡️ Saved remaining **${saved_amt:.2f}**"
                )
                notifications.append(msg)
                logger.info(f"SL Triggered for {symbol}: Loss ${loss_amt:.2f}")
                continue

            # --- 2. TAKE PROFIT (Double MC) ---
            # "Every time market cap doubles... one is out" -> Full Exit to free slot
            if current_price >= (last_tp * 2.0):
                # Sell 100% (Full Exit) to free up one of the 4 slots
                self._close_position(addr, current_price, qty, "TAKE_PROFIT_2X", log_json, cost_basis)
                
                sell_val = (qty * current_price) * (1 - self.SLIPPAGE)
                price_gain = (current_price - entry) / entry * 100
                pnl = sell_val - cost_basis
                
                # Get updated balance for notification
                port = self.get_portfolio() 
                
                msg = (
                    f"✅ **TAKE PROFIT HIT: {symbol}**\n"
                    f"🚀 Market Cap Doubled! ({price_gain:.0f}%)\n"
                    f"💰 **Position Closed** for **${sell_val:.2f}**\n"
                    f"🤑 Profit: **${pnl:.2f}**\n"
                    f"♻️ **Slot Freed Up!** (Active: {len(token_map)-1 if len(token_map)>0 else 0}/4)\n"
                    f"🏦 New Balance: **${port['balance']:.2f}**"
                )
                notifications.append(msg)
                logger.info(f"TP Triggered for {symbol}: Sold All ${sell_val:.2f} (PnL: ${pnl:.2f})")
            else:
                # Just update current price if no action taken
                c.execute("UPDATE trades SET current_price = ? WHERE token_address = ?", (current_price, addr))
                conn.commit()

        conn.close()
        return notifications

    def _close_position(self, addr, price, qty, reason, log_json, cost_basis):
        conn = self._get_conn()
        c = conn.cursor()
        
        sell_val = (qty * price) * (1 - self.SLIPPAGE)
        pnl = sell_val - cost_basis
        
        self._update_portfolio(balance_change=(sell_val - self.GAS_FEE), pnl_change=pnl, fee=self.GAS_FEE)
        
        new_log = json.loads(log_json)
        new_log.append({
            "action": reason,
            "price": price,
            "quantity": qty,
            "value": sell_val,
            "pnl": pnl,
            "time": time.time()
        })
        
        c.execute("""
            UPDATE trades 
            SET current_quantity = 0, cost_basis = 0, status = ?, log = ? 
            WHERE token_address = ?
        """, (reason, json.dumps(new_log), addr))
        conn.commit()
        conn.close()

    def get_detailed_stats(self) -> Dict[str, Any]:
        """
        Calculates detailed performance metrics from trade history.
        """
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT log FROM trades")
        rows = c.fetchall()
        conn.close()

        total_trades = len(rows)
        if total_trades == 0:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "wins": 0,
                "losses": 0
            }

        wins = 0
        losses = 0
        total_win_pnl = 0.0
        total_loss_pnl = 0.0

        for row in rows:
            try:
                log_entries = json.loads(row[0])
                trade_pnl = 0.0
                has_sells = False
                
                for entry in log_entries:
                    if "pnl" in entry:
                        trade_pnl += float(entry["pnl"])
                        has_sells = True
                
                # Only count as Win/Loss if we have actually sold something or realized PnL
                # If completely OPEN with no TPs, it's unrealized.
                # But user wants "Avg Win Rate", usually checking Closed or Partial.
                # Let's count it based on realized PnL so far.
                if has_sells or trade_pnl != 0:
                    if trade_pnl > 0:
                        wins += 1
                        total_win_pnl += trade_pnl
                    else:
                        losses += 1
                        total_loss_pnl += abs(trade_pnl)
                else:
                    # No realized PnL yet (just opened)
                    pass

            except Exception:
                continue
                
        # Calculate Derived Stats
        counted_trades = wins + losses
        win_rate = (wins / counted_trades * 100) if counted_trades > 0 else 0.0
        avg_win = (total_win_pnl / wins) if wins > 0 else 0.0
        avg_loss = (total_loss_pnl / losses) if losses > 0 else 0.0
        profit_factor = (total_win_pnl / total_loss_pnl) if total_loss_pnl > 0 else float('inf') if total_win_pnl > 0 else 0.0

        return {
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "total_pnl": total_win_pnl - total_loss_pnl
        }

    def get_summary_text(self) -> str:
        """
        Returns a formatted, entertaining summary with Live Equity.
        """
        port = self.get_portfolio()
        stats = self.get_detailed_stats()
        
        conn = self._get_conn()
        c = conn.cursor()
        
        # Open Positions
        try:
             # Try selecting current_price, fall back if column missing (migration issue)
             c.execute("SELECT symbol, current_quantity, entry_price, current_price, log FROM trades WHERE status='OPEN'")
        except:
             # Fallback if migration didn't run properly on existing db
            c.execute("SELECT symbol, current_quantity, entry_price, entry_price, log FROM trades WHERE status='OPEN'")

        open_rows = c.fetchall()
        
        # Closed History (Last 5)
        c.execute("SELECT symbol, log FROM trades WHERE status != 'OPEN' ORDER BY entry_time DESC LIMIT 5")
        history_rows = c.fetchall()
        
        conn.close()
        
        # 1. Calculate Live Equity
        cash_balance = port['balance']
        holdings_value = 0.0
        
        active_bets_msg = ""
        open_count = len(open_rows)
        
        if not open_rows:
            active_bets_msg += "<i>No active bets. Searching for gems...</i> 🕵️‍♂️"
        else:
            for row in open_rows:
                sym, qty, entry, curr_price, log = row
                curr_price = curr_price if curr_price > 0 else entry # Fallback
                val = qty * curr_price
                holdings_value += val
                
                # Trade specific PnL (Unrealized)
                upnl = val - (qty * entry) # Rough estimate
                upnl_pct = ((curr_price - entry) / entry) * 100
                emoji = "🟢" if upnl >= 0 else "🔴"
                
                active_bets_msg += f"{emoji} **{sym}**\n"
                active_bets_msg += f"   Entry: ${entry:.6f} | Curr: ${curr_price:.6f}\n"
                active_bets_msg += f"   Value: `${val:.2f}` ({upnl_pct:+.1f}%)\n"
                
                # Locked In profit logic
                try:
                    logs = json.loads(log)
                    realized_on_this = sum([float(x.get('pnl',0)) for x in logs])
                    if realized_on_this > 0:
                        active_bets_msg += f"   💰 Locked In: `${realized_on_this:.2f}`\n"
                except: pass
                active_bets_msg += "\n"

        total_equity = cash_balance + holdings_value
        start_bal = 200.0 # Hardcoded starting, or track it? User said 200.
        total_pnl = total_equity - start_bal
        pnl_emoji = "🚀" if total_pnl >= 0 else "🔻"

        msg = f"🎰 **DEGEN CASINO DASHBOARD** 🎰\n\n"
        
        # 1. Live Balance
        msg += f"🏦 **LIVE EQUITY**: `${total_equity:.2f}`\n"
        msg += f"💵 **Cash**: `${cash_balance:.2f}`\n"
        msg += f"💎 **Holdings**: `${holdings_value:.2f}`\n"
        msg += f"{pnl_emoji} **Total Profit**: `${total_pnl:+.2f}`\n"
        msg += "━━━━━━━━━━━━━━━━━━━\n"
        
        # 2. Scoreboard
        msg += f"📊 **STATS**\n"
        msg += f"🏆 {stats['wins']} W  |  💀 {stats['losses']} L  | 🎯 {stats['win_rate']:.0f}%\n"
        msg += "━━━━━━━━━━━━━━━━━━━\n"

        # 3. Active Bets
        msg += f"🎲 **ACTIVE BETS ({open_count})**\n\n"
        msg += active_bets_msg
        
        # 4. Recent History (Closed)
        if history_rows:
            msg += "📜 **RECENT HISTORY**\n"
            for row in history_rows:
                sym, log = row
                try:
                    logs = json.loads(log)
                    final_pnl = sum([float(x.get('pnl',0)) for x in logs])
                    # status = logs[-1].get("action", "CLOSED")
                    icon = "✅" if final_pnl > 0 else "❌"
                    msg += f"{icon} **{sym}**: `${final_pnl:+.2f}`\n"
                except: pass

        return msg

    def reset_portfolio(self, initial_balance=200.0):
        """
        Resets the portfolio balance and clears all trade history.
        """
        conn = self._get_conn()
        c = conn.cursor()
        try:
            # Clear Trades
            c.execute("DELETE FROM trades")
            
            # Reset Portfolio
            c.execute("UPDATE portfolio SET balance = ?, realized_pnl = 0.0, fees_paid = 0.0 WHERE id=1", (initial_balance,))
            
            conn.commit()
            logger.info(f"Portfolio reset to ${initial_balance}")
        except Exception as e:
            logger.error(f"Failed to reset portfolio: {e}")
        finally:
            conn.close()
