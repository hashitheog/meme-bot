import logging
from plyer import notification
from bot.models.token import AnalysisResult

logger = logging.getLogger(__name__)

class DesktopNotifier:
    @staticmethod
    def send_notification(result: AnalysisResult):
        """
        Sends a desktop notification for High Priority or Alert tokens.
        """
        token = result.token
        title = f"🚀 Meme Coin Alert: {token.base_token_symbol}"
        
        # Calculate potential text
        potential_text = ""
        if result.predicted_fdv > 0:
            x_potential = result.predicted_fdv / token.fdv if token.fdv > 0 else 0
            potential_text = f"\nPotential: {x_potential:.1f}x (${result.predicted_fdv:,.0f})"
            
        message = (
            f"Score: {result.score:.0f}/100 [{result.action}]\n"
            f"Price: ${token.price_usd:.6f}\n"
            f"Liq: ${token.liquidity_usd:,.0f}{potential_text}"
        )
        
        try:
            notification.notify(
                title=title,
                message=message,
                app_name="Meme Coin Bot",
                timeout=10
            )
        except Exception as e:
            logger.error(f"Desktop notification failed: {e}")
