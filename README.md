# PolyMarketCopier

1. You must have uv installed (https://docs.astral.sh/uv/getting-started/installation/)
2. You must have a Polymarket funder wallet and private key (https://www.youtube.com/watch?v=kxexDNb9mHw)

## Installation

```bash
git clone https://github.com/randomname124290358349/PolyMarketCopier.git
cd PolyMarketCopier
uv sync
```

## Configuration

Copy `.env.example` to `.env` and fill in your details:

```env
# Credentials Config
FUNDER_ADDRESS=
PRIVATE_KEY=

# Wallets file path
WALLETS_TXT_PATH="F:\path\wallets.txt" # In this file you must have a list of wallets to copy trades from

# Trades Config
ORDER_TYPE="market"              # Type can be "limit" or "market"

LIMIT_ORDER_TIMEOUT=10           # Time out for limit order confirmation in seconds
                                 # If ORDER_TYPE is market, this will be ignored

MIN_SHARE_POSSIBLE=True          # If true, it will try to make the order with the minimum size possible dependind the price
                                 # The minimum size of this type of operation is 5, and de minimum ammount of cash must be $1 
                                 # If false, it will try to make the order equal to the size of the trade copied

MARKET_ORDER_FIXED_AMMOUNT=1     # If ORDER_TYPE is "market", this will be the fixed ammount of cash to be used
                                 # The program will buys or sells the minimum shares possible to reach this ammount
```

Create a `wallets.txt` file with the wallets to monitor (one per line).

## Run

```bash
uv run python main.py
```
