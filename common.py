"""
common.py
---------
Reusable functions for the project:

    set_db        -> open (or create) the SQLite database
    get_data      -> download candlestick data for one ticker via yfinance
    to_asset_rows -> convert a yfinance DataFrame into a list of AssetClass rows
    create_table  -> create a table from a dataclass or a dictionary
    insert_data   -> insert a list of dataclasses / dicts / tuples / lists
    table_name    -> build a table name such as raw_stk_1d
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import asdict, dataclass, fields, is_dataclass
from pathlib import Path
from typing import Any, Sequence, get_type_hints

import pandas as pd
import yfinance as yf

import config


@dataclass
class AssetClass:
    """
    One candlestick (one row of price data) for one asset.

    Every column is named and typed explicitly, which makes the data
    self-describing and lets create_table() build a matching SQL table.
    """

    ticker: str     # e.g. "AAPL"
    date: str       # ISO date string, e.g. "2024-03-15"
    open: float     # opening price
    high: float     # highest price in the period
    low: float      # lowest price in the period
    close: float    # closing price (adjusted for splits/dividends by yfinance)
    volume: int     # number of shares traded


_SQL_TYPES: dict[type, str] = {
    int: "INTEGER",
    float: "REAL",
    str: "TEXT",
    bool: "INTEGER",  
    bytes: "BLOB",
}

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _check_identifier(name: str) -> str:
    """Raise ValueError if `name` is not a safe SQL identifier; else return it."""
    if not _IDENTIFIER.match(name):
        raise ValueError(f"Invalid table/column name: {name!r}")
    return name



def set_db(db_path: str | Path = config.DB_PATH) -> sqlite3.Connection:
    """
    Opens a connection to the SQLite database at `db_path`.

    SQLite creates the file automatically if it does not exist yet,
    so this function doubles as "create database".

    Returns an open sqlite3.Connection.
    """
    
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    return conn



def get_data(
    ticker: str,
    start: str = config.DEFAULT_START_DATE,
    end: str = config.DEFAULT_END_DATE,
    interval: str = config.DEFAULT_INTERVAL,
) -> pd.DataFrame:
    """
    Downloads candlestick (OHLCV) data for a single ticker from Yahoo Finance.

    Returns:
        A pandas DataFrame indexed by date with columns
        Empty if the ticker is invalid or has no data in the range.
    """
    df = yf.Ticker(ticker).history(start=start, end=end, interval=interval)
    return df


def to_asset_rows(df: pd.DataFrame, ticker: str) -> list[AssetClass]:
    """
    Convert a yfinance DataFrame into a list of AssetClass dataclasses.

    Returns one AssetClass per row of the DataFrame.
    """
    rows: list[AssetClass] = []
    # Loops over each row; `date` is the index, `row` holds that day's prices.
    for date, row in df.iterrows():
        rows.append(
            AssetClass(
                ticker=ticker,
                date=date.strftime("%Y-%m-%d"),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]),
            )
        )
    return rows

def create_table(conn: sqlite3.Connection, table: str, schema, primary_key=None) -> None:
    """
    Create a table whose columns match a dataclass or a dictionary.

    """
    columns = [] 

    if is_dataclass(schema):
        # Loop over the dataclass fields, e.g. ticker: str, close: float
        for f in fields(schema):
            type_name = f.type if isinstance(f.type, str) else f.type.__name__
            columns.append(f"{f.name} {SQL_TYPES.get(type_name, 'TEXT')}")

    elif isinstance(schema, dict):
        for name, value in schema.items():
            type_name = type(value).__name__  # e.g. 101.2 -> "float"
            columns.append(f"{name} {SQL_TYPES.get(type_name, 'TEXT')}")

    else:
        raise TypeError("schema must be a dataclass or a dict")

    if primary_key:
        columns.append(f"PRIMARY KEY ({', '.join(primary_key)})")

    sql = f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(columns)})"
    conn.execute(sql)
    conn.commit()


def insert_data(conn: sqlite3.Connection, table: str, rows: list) -> int:
    """
    Insert a list of rows into `table`.

    Returns number of rows actually inserted.
    """
    if not rows:
        return 0

    values = []
    for row in rows:
        if is_dataclass(row):
            values.append(astuple(row))          # AssetClass(...) -> ("AAPL", "2024-01-02", ...)
        elif isinstance(row, dict):
            values.append(tuple(row.values()))   # {"ticker": "AAPL", ...} -> ("AAPL", ...)
        elif isinstance(row, (tuple, list)):
            values.append(tuple(row))            # already in order
        else:
            raise TypeError("each row must be a dataclass, dict, tuple or list")

    placeholders = ", ".join(["?"] * len(values[0]))
    sql = f"INSERT OR IGNORE INTO {table} VALUES ({placeholders})"

    before = conn.total_changes
    conn.executemany(sql, values)
    conn.commit()
    return conn.total_changes - before


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def table_name(asset_type: str = "stock", interval: str = "1d") -> str:
    """Build a table name, e.g. table_name("stock", "1d") -> "raw_stk_1d"."""
    code = config.ASSET_TYPE_CODES[asset_type]
    return f"raw_{code}_{interval}"


def read_table(conn: sqlite3.Connection, table: str, ticker: str) -> pd.DataFrame:
    """Load one ticker's prices from the database as a DataFrame, sorted by date."""
    sql = f"SELECT * FROM {table} WHERE ticker = ? ORDER BY date"
    return pd.read_sql_query(sql, conn, params=(ticker,))