"""
config.py
---------
Project-wide settings. Anything that is reused in more than one place
(database name, tickers, dates, naming patterns) lives here so it only
has to be changed once.
"""

from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parent

DB_NAME: str = "market_data.db"

DATA_DIR: Path = PROJECT_ROOT / "data"

DB_PATH: Path = DATA_DIR / DB_NAME

DEFAULT_TICKERS: list[str] = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]

DEFAULT_INTERVAL: str = "1d"

DEFAULT_START_DATE: str = "2020-01-01"
DEFAULT_END_DATE: str = "2026-01-01"

TABLE_NAME_PATTERN: str = "raw_{asset_type}_{interval}"

ASSET_TYPE_CODES: dict[str, str] = {
    "stock": "stk",
    "etf": "etf",
    "crypto": "cry",
    "fx": "fx",
    "index": "idx",
    "commodity": "cmd",
}