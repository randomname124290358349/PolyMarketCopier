
# Import general modules
import requests
import sqlite3
import json
import math
import asyncio
import logging
import threading
from datetime import datetime
from time import sleep

# Import Clob modules
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType, OpenOrderParams, MarketOrderArgs
from py_clob_client.exceptions import PolyApiException

class PolyMarketController:
    '''
    Controller for PolyMarket copier

    Docs:
      - Private key: Your polymarket private key
      - Founder key: Founder public key
      - Wallets txt path: Path to the wallets.txt file
      - Order type: limit or market
      - Limit order timeout: Timeout for limit orders in seconds
      - Market order fixed ammount: Fixed ammount for market orders
      - Min share possible: Whether to grant that price * size >= 1
    '''
    def __init__(self, private_key: str, 
                founder_key: str,
                wallets_txt_path: str,
                order_type: str,
                limit_order_timeout: int,
                market_order_fixed_ammount: int,
                min_share_possible: bool
    ):
        
        # User config
        self.private_key                = private_key
        self.founder_key                = founder_key
        self.wallets_txt_path           = wallets_txt_path
        self.trades_to_copy: list[dict] = []
        self.wallets_to_copy: list[str] = []
        self.order_type                 = order_type
        self.market_order_fixed_ammount = market_order_fixed_ammount
        self.min_share_possible         = min_share_possible

        # Thread-safe locks for shared data
        self._trades_lock = threading.Lock()
        self._wallets_lock = threading.Lock()

        # Logging setup
        self.logger = logging.getLogger("PMC")
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('[%(asctime)s] [%(name)s] [%(funcName)s] %(message)s')
        handler.setFormatter(formatter)
        if not self.logger.handlers:
            self.logger.addHandler(handler)

        self.logger.info("Initializing PolyMarketController...")

        # Database setup
        self.db_path = "trades.db"
        self._init_db()

        # Constants
        self.DATA_API_POLYMARKET = "https://data-api.polymarket.com/trades"
        self.CLOB_CLIENT = ClobClient(
            host="https://clob.polymarket.com",
            key=self.private_key,
            chain_id=137,
            signature_type=1,
            funder=self.founder_key
        )
        self.CLOB_CLIENT.set_api_creds(self.CLOB_CLIENT.create_or_derive_api_creds())
        self.logger.info("PolyMarketController initialized.")

    def _init_db(self):
        self.logger.info("Initializing database...")
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.cursor = self.conn.cursor()
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS watched_wallets (
                address TEXT PRIMARY KEY
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS seen_trades (
                transactionHash TEXT PRIMARY KEY,
                wallet TEXT,
                data TEXT
            )
        ''')
        self.conn.commit()
        self.logger.info("Database initialized.")

    def get_wallets_to_copy(self) -> list[str]:
        '''
        This must return a list of wallets
        
        Example:
        
        ['0x090a0d3fc9d68d3e16db70e3460e3e4b510801b4', '0x090a0d3fc9d68d3e16db70e3460e3e4b510801b4']
        '''
        self.logger.info("Reading wallets file...")
        try:
            with open(self.wallets_txt_path, 'r') as f:
                wallets = f.read().splitlines()
            with self._wallets_lock:
                self.wallets_to_copy = wallets
            self.logger.info(f"Loaded {len(self.wallets_to_copy)} wallets.")
        except Exception as e:
            self.logger.error(f"Error reading wallets file: {e}")
            with self._wallets_lock:
                self.wallets_to_copy = []
        return self.wallets_to_copy
    
    async def get_trades_from_wallet(self, wallet: str, limit: int = 5) -> list[dict]:
        '''
        This must return a list of trades (async version).
        '''
        self.logger.info(f"Fetching trades for wallet {wallet[:10]}...")
        try:
            response = await asyncio.to_thread(
                requests.get,
                self.DATA_API_POLYMARKET,
                params={"user": wallet,
                "limit": limit,
                "offset": 0,
                "sortDirection": "DESC"}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Error fetching trades for {wallet}: {e}")
            return []

    async def check_trades_from_wallets(self):
        self.logger.info("Checking trades from wallets...")
        with self._wallets_lock:
            wallets = list(self.wallets_to_copy)
        for wallet in wallets:
            trades = await self.get_trades_from_wallet(wallet)
            if not trades:
                continue

            # Check if wallet is tracked
            res = self.cursor.execute("SELECT 1 FROM watched_wallets WHERE address = ?", (wallet,))
            is_new = res.fetchone() is None

            if is_new:
                self.logger.info(f"New wallet detected: {wallet[:10]}...")
                # Mark wallet as watched
                self.cursor.execute("INSERT INTO watched_wallets (address) VALUES (?)", (wallet,))
                
                # Add existing trades to DB but don't copy (historical)
                for trade in trades:
                    t_hash = trade.get('transactionHash')
                    if t_hash:
                        self.cursor.execute("INSERT OR IGNORE INTO seen_trades (transactionHash, wallet, data) VALUES (?, ?, ?)", 
                                            (t_hash, wallet, json.dumps(trade)))
                self.conn.commit()
            else:
                # Wallet already watched, check for new trades
                for trade in trades:
                    t_hash = trade.get('transactionHash')
                    if t_hash:
                        # Check if trade is seen
                        res = self.cursor.execute("SELECT 1 FROM seen_trades WHERE transactionHash = ?", (t_hash,))
                        if res.fetchone() is None:
                            # New trade detected
                            self.logger.info(f"New trade found for {wallet[:10]}...: {t_hash[:10]}...")
                            with self._trades_lock:
                                self.trades_to_copy.append(trade)
                            self.cursor.execute("INSERT INTO seen_trades (transactionHash, wallet, data) VALUES (?, ?, ?)", 
                                                (t_hash, wallet, json.dumps(trade)))
                self.conn.commit()
        self.logger.info("Finished checking trades from wallets.")
            
    async def execute_queued_trades(self):
        """
        Executes all trades in the trades_to_copy list.
        """
        # Create a copy of the list to iterate over safely
        with self._trades_lock:
            trades = list(self.trades_to_copy)
        
        if trades:
            self.logger.info(f"Executing {len(trades)} queued trades...")

        for trade in trades:
            self.logger.info(f"Processing trade for asset {trade.get('asset')[:20]}...")
            await self.make_order_and_wait_confirmation(trade)
            with self._trades_lock:
                if trade in self.trades_to_copy:
                    self.trades_to_copy.remove(trade)
            
    async def make_order_and_wait_confirmation(self, trade: dict) -> None:
        if self.order_type == "limit":
            if self.min_share_possible:
                # Grant that price * size >= 1
                price    = trade["price"]
                size     = trade["size"]
                min_size = math.ceil(1 / price)
            else:
                min_size = trade["size"]

            try:
                # Mount order
                order = OrderArgs(
                    token_id=trade["asset"], 
                    price=price, 
                    size=5 if min_size < 5 else min_size, 
                    side=trade["side"]
                )

                # Execute order
                self.logger.info(f"Placing LIMIT order: token={trade['asset'][:20]}..., price={price}, side={trade['side']}")
                signed = await asyncio.to_thread(self.CLOB_CLIENT.create_order, order)
                resp   = await asyncio.to_thread(self.CLOB_CLIENT.post_order, signed, OrderType.GTC)
                
                self.logger.info(f"Order placed. ID: {resp.get('orderID')}. Waiting {self.limit_order_timeout}s...")
                await asyncio.sleep(self.limit_order_timeout)

                open_orders = await asyncio.to_thread(self.CLOB_CLIENT.get_orders, OpenOrderParams())
                for order in open_orders:
                    if order["id"] == resp["orderID"]:
                        self.logger.info(f"Cancelling order {order['id']}...")
                        await asyncio.to_thread(self.CLOB_CLIENT.cancel, order["id"])
            except PolyApiException as e:
                self.logger.error(f"PolyApiException in limit order: {e}")
            except Exception as e:
                self.logger.error(f"Error in limit order: {e}")
    
        try:    
            if self.order_type == "market":
                order = MarketOrderArgs(
                    token_id=trade["asset"], 
                    amount=self.market_order_fixed_ammount, 
                    side=trade["side"], 
                    order_type=OrderType.FOK
                )
                self.logger.info(f"Placing MARKET order: token={trade['asset'][:20]}..., side={trade['side']}")
                signed = await asyncio.to_thread(self.CLOB_CLIENT.create_market_order, order)
                resp   = await asyncio.to_thread(self.CLOB_CLIENT.post_order, signed, OrderType.FOK)
                self.logger.info(f"Market order response: {resp}")
        except PolyApiException as e:
            self.logger.error(f"PolyApiException in market order: {e}")
        except Exception as e:
            self.logger.error(f"Error in market order: {e}")

    async def _wallet_loader_loop(self, interval: int = 30):
        """
        Periodically reloads wallets from file.
        Interval: 30s (local file, no API rate limit)
        """
        while True:
            try:
                self.get_wallets_to_copy()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                self.logger.info("Wallet loader loop cancelled.")
                break
            except Exception as e:
                self.logger.error(f"Error in wallet loader loop: {e}")
                await asyncio.sleep(5)

    async def _trade_checker_loop(self, interval: int = 5):
        """
        Periodically checks for new trades from watched wallets.
        Interval: 5s (respects Data API /trades 200 req/10s limit)
        """
        while True:
            try:
                await self.check_trades_from_wallets()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                self.logger.info("Trade checker loop cancelled.")
                break
            except Exception as e:
                self.logger.error(f"Error in trade checker loop: {e}")
                await asyncio.sleep(5)

    async def _trade_executor_loop(self, interval: int = 2):
        """
        Periodically executes queued trades.
        Interval: 2s (respects CLOB POST /order 60/s avg limit)
        """
        while True:
            try:
                await self.execute_queued_trades()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                self.logger.info("Trade executor loop cancelled.")
                break
            except Exception as e:
                self.logger.error(f"Error in trade executor loop: {e}")
                await asyncio.sleep(5)

    async def run(self):
        """
        Main entry point that launches all concurrent task loops.
        Each function runs independently at its own interval.
        """
        self.logger.info("Starting concurrent task loops...")
        
        # Initial wallet load before starting loops
        self.get_wallets_to_copy()
        
        # Create concurrent tasks
        tasks = [
            asyncio.create_task(self._wallet_loader_loop(30), name="wallet_loader"),
            asyncio.create_task(self._trade_checker_loop(5), name="trade_checker"),
            asyncio.create_task(self._trade_executor_loop(2), name="trade_executor"),
        ]
        
        self.logger.info(f"Launched {len(tasks)} concurrent tasks: wallet_loader(30s), trade_checker(5s), trade_executor(2s)")
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            self.logger.info("Shutting down all tasks...")
            for task in tasks:
                task.cancel()
            # Wait for all tasks to complete cancellation
            await asyncio.gather(*tasks, return_exceptions=True)
            self.logger.info("All tasks shut down.")
