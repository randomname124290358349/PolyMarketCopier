
import os
import logging
import sys

class ConfigValidator:
    def __init__(self):
        # Logging setup similar to PolyMarketController
        self.logger = logging.getLogger("ConfigValidator")
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('[%(asctime)s] [%(name)s] [%(funcName)s] %(message)s')
        handler.setFormatter(formatter)
        
        # Avoid adding duplicate handlers if instantiated multiple times
        if not self.logger.handlers:
            self.logger.addHandler(handler)
            
        self.logger.info("Initializing ConfigValidator...")

    def validate(self) -> bool:
        """
        Validates the configuration environment variables.
        Returns True if all checks pass, False otherwise.
        """
        self.logger.info("Starting configuration validation...")
        is_valid = True

        # 1. Check Credentials
        private_key = os.getenv("PRIVATE_KEY")
        if not private_key:
            self.logger.error("CRITICAL: PRIVATE_KEY is missing or empty in .env")
            is_valid = False
        
        funder_address = os.getenv("FUNDER_ADDRESS")
        if not funder_address:
            self.logger.error("CRITICAL: FUNDER_ADDRESS is missing or empty in .env")
            is_valid = False

        # 2. Check Wallets File
        wallets_path = os.getenv("WALLETS_TXT_PATH")
        if not wallets_path:
            self.logger.error("CRITICAL: WALLETS_TXT_PATH is missing in .env")
            is_valid = False
        elif not os.path.exists(wallets_path):
            self.logger.error(f"CRITICAL: Wallets file not found at path: {wallets_path}")
            is_valid = False
        else:
            self.logger.info(f"Wallets file found at: {wallets_path}")

        # 3. Check Order Type
        order_type = os.getenv("ORDER_TYPE")
        if order_type not in ["limit", "market"]:
            self.logger.error(f"CRITICAL: Invalid ORDER_TYPE '{order_type}'. Must be 'limit' or 'market'.")
            is_valid = False
        else:
            self.logger.info(f"Order type set to: {order_type}")

        # 4. Check Type-Specific Configs
        if order_type == "limit":
            timeout = os.getenv("LIMIT_ORDER_TIMEOUT")
            if not timeout:
                self.logger.warning("LIMIT_ORDER_TIMEOUT not set, defaulting to 10s (as per main.py logic).")
            elif not timeout.isdigit():
                self.logger.error(f"CRITICAL: LIMIT_ORDER_TIMEOUT '{timeout}' is not a valid integer.")
                is_valid = False
        
        elif order_type == "market":
            fixed_amount = os.getenv("MARKET_ORDER_FIXED_AMMOUNT")
            if not fixed_amount:
                self.logger.warning("MARKET_ORDER_FIXED_AMMOUNT not set, defaulting to 1 (as per main.py logic).")
            else:
                try:
                    float(fixed_amount)
                except ValueError:
                    self.logger.error(f"CRITICAL: MARKET_ORDER_FIXED_AMMOUNT '{fixed_amount}' is not a valid number.")
                    is_valid = False

        # 5. Check Global logic flags (Just informational/warning if missing)
        min_share = os.getenv("MIN_SHARE_POSSIBLE")
        if min_share is None:
             self.logger.warning("MIN_SHARE_POSSIBLE not set, defaulting to False.")
        
        if is_valid:
            self.logger.info("Configuration validation passed.")
        else:
            self.logger.error("Configuration validation FAILED. Please fix the errors above.")

        return is_valid
