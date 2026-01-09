
# Import modules
from modules.PolyClasses import PolyMarketController
import asyncio

# Load environment variables
from dotenv import load_dotenv
import os   
load_dotenv()


if __name__ == "__main__":
    pmc = PolyMarketController(
        private_key                 = os.getenv("PRIVATE_KEY"),
        founder_key                 = os.getenv("FUNDER_ADDRESS"),
        wallets_txt_path            = os.getenv("WALLETS_TXT_PATH"),
        order_type                  = os.getenv("ORDER_TYPE"),
        limit_order_timeout         = int(os.getenv("LIMIT_ORDER_TIMEOUT", "10")),
        market_order_fixed_ammount  = float(os.getenv("MARKET_ORDER_FIXED_AMMOUNT", "1")),
        min_share_possible          = os.getenv("MIN_SHARE_POSSIBLE", "false").lower() == "true"
    )

    asyncio.run(pmc.run())
