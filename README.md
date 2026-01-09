# PolyMarketCopier

A Python bot that monitors specified Polymarket wallets and automatically copies their trades to your account (asynchronous).

## Features

| Feature                    | Description                                                                 |
|---------------------------|-----------------------------------------------------------------------------|
| **Wallet Monitoring**     | Track multiple wallets and continuously monitor them for new trades        |
| **Automatic Trade Copying** | Asynchronously execute copy trades whenever a monitored wallet makes a move |
| **Market & Limit Orders** | Full support for both market and limit order execution                      |
| **SQLite Database**       | Local SQLite database to persist seen trades and prevent duplicate actions |
| **Concurrent Execution**  | Asynchronous loops for wallet loading, trade polling, and trade execution  |
| **Same size copying**  | Can copy trades with the same size as the original trade  |
| **Min share possible**  | Can copy trades with the same size as the original trade  |

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python package manager)
- Your Polymarket funder wallet and private key [TUTORIAL](https://www.youtube.com/watch?v=kxexDNb9mHw)
- A list of wallets to monitor  (one per line)

## Installation

### 1. Install uv

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/randomname124290358349/PolyMarketCopier.git

# Navigate to project directory
cd PolyMarketCopier

# Create virtual environment and install dependencies
uv sync
```

### 3. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Credentials Config
FUNDER_ADDRESS=0xYourFunderAddress
PRIVATE_KEY=your_private_key_here

# Wallets file path
WALLETS_TXT_PATH="C:\path\to\wallets.txt"

# Trades Config
ORDER_TYPE="market"              # "limit" or "market"
LIMIT_ORDER_TIMEOUT=10           # Timeout for limit orders (seconds)
MIN_SHARE_POSSIBLE=True          # Use minimum share size
MARKET_ORDER_FIXED_AMMOUNT=1     # Fixed cash amount for market orders
```

### 4. Create Wallets File

Create a `wallets.txt` file with one wallet address per line:

```
0x090a0d3fc9d68d3e16db70e3460e3e4b510801b4
0xanotherwalletaddress123456789
```

## Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `FUNDER_ADDRESS` | Your Polymarket funder public address | Required |
| `PRIVATE_KEY` | Your Polymarket private key | Required |
| `WALLETS_TXT_PATH` | Path to file containing wallet addresses to monitor | Required |
| `ORDER_TYPE` | Order type: `"market"` or `"limit"` | `"market"` |
| `LIMIT_ORDER_TIMEOUT` | Seconds to wait before cancelling unfilled limit orders | `10` |
| `MIN_SHARE_POSSIBLE` | If `True`, uses minimum share size (5 shares, $1 minimum) | `True` |
| `MARKET_ORDER_FIXED_AMMOUNT` | Fixed USD amount for market orders | `1` |

## Running the Bot

```bash
# Activate virtual environment and run
uv run python main.py
```

## How It Works

1. **Wallet Loading** (every 30s): Reads wallet addresses from `wallets.txt`
2. **Trade Checking** (every 5s): Asynchronously fetches recent trades from monitored wallets via Polymarket API
3. **Trade Execution** (every 2s): Asynchronously executes queued trades on your account

When a monitored wallet is first detected, all existing trades are stored in the database to establish a baseline. Only **new** trades after this point are copied.

## Database

The bot uses SQLite (`trades.db`) to track:
- **watched_wallets**: Wallets currently being monitored
- **seen_trades**: Trade hashes to prevent duplicate execution

## Logs

The bot outputs structured logs with timestamps and function names:

```
[2026-01-08 18:45:32] [PMC] [run] Starting concurrent task loops...
[2026-01-08 18:45:32] [PMC] [get_wallets_to_copy] Loaded 3 wallets.
[2026-01-08 18:45:37] [PMC] [check_trades_from_wallets] New trade found...
```

