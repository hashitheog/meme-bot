import asyncio
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot.analyzer.goplus import GoPlusClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Test")

async def test_goplus():
    client = GoPlusClient()
    
    # Test Case 1: USDC on Ethereum (Should be Safe)
    usdc_eth = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    logger.info(f"Testing USDC (ETH): {usdc_eth}")
    result = await client.check_token_security(usdc_eth, "ethereum")
    print(f"USDC LP Holders: {len(result.get('lp_holders', []))}")
    print(f"USDC Top Holder %: {[h.get('percent') for h in result.get('holders', [])[:3]]}")

    # Test Case 2: PEPE on Ethereum
    pepe_eth = "0x6982508145454ce325ddbe47a25d4ec3d2311933"
    logger.info(f"Testing PEPE (ETH): {pepe_eth}")
    result_pepe = await client.check_token_security(pepe_eth, "ethereum")
    # print("PEPE Result:", result_pepe)
    print(f"PEPE LP Holders: {len(result_pepe.get('lp_holders', []))}")
    print(f"PEPE Top Holder %: {[h.get('percent') for h in result_pepe.get('holders', [])[:3]]}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_goplus())
