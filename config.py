"""
config.py
---------
Project-wide settings. Anything that is reused in more than one place
(database name, tickers, dates, naming patterns) lives here so it only
has to be changed once.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# Root of the project (the folder this file sits in).
PROJECT_ROOT: Path = Path(__file__).resolve().parent

# Name of the SQLite database file. It is created automatically on first use.
DB_NAME: str = "market_data.db"

# Folder that holds the database (py_backtester/data/).
DATA_DIR: Path = PROJECT_ROOT / "data"

# Full path to the database file, e.g. py_backtester/data/market_data.db
DB_PATH: Path = DATA_DIR / DB_NAME

# ---------------------------------------------------------------------------
# Data extraction settings
# ---------------------------------------------------------------------------
# Tickers to download by default (Yahoo Finance symbols).
DEFAULT_TICKERS: list[str] = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]

# Candle interval. yfinance accepts e.g. "1d", "1wk", "1mo", "1h".
DEFAULT_INTERVAL: str = "1d"

# Default date range (YYYY-MM-DD). END_DATE is exclusive in yfinance.
DEFAULT_START_DATE: str = "2020-01-01"
DEFAULT_END_DATE: str = "2026-01-01"

# ---------------------------------------------------------------------------
# Table naming
# ---------------------------------------------------------------------------
# Tables follow the pattern raw_<asset type>_<interval>, e.g. raw_stk_1d.
TABLE_NAME_PATTERN: str = "raw_{asset_type}_{interval}"

# Short codes for each asset type used in table names.
ASSET_TYPE_CODES: dict[str, str] = {
    "stock": "stk",
    "etf": "etf",
    "crypto": "cry",
    "fx": "fx",
    "index": "idx",
    "commodity": "cmd",
}