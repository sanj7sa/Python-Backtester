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


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
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


# Maps Python types to SQLite column types.
_SQL_TYPES: dict[type, str] = {
    int: "INTEGER",
    float: "REAL",
    str: "TEXT",
    bool: "INTEGER",   # SQLite has no boolean; stored as 0/1
    bytes: "BLOB",
}

# Table/column names must be simple identifiers. SQL placeholders (?) cannot
# be used for names, so we validate them to prevent SQL injection.
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _check_identifier(name: str) -> str:
    """Raise ValueError if `name` is not a safe SQL identifier; else return it."""
    if not _IDENTIFIER.match(name):
        raise ValueError(f"Invalid table/column name: {name!r}")
    return name


# ---------------------------------------------------------------------------
# 1) Database connection
# ---------------------------------------------------------------------------
def set_db(db_path: str | Path = config.DB_PATH) -> sqlite3.Connection:
    """
    Open a connection to the SQLite database at `db_path`.

    SQLite creates the file automatically if it does not exist yet,
    so this function doubles as "create database".

    Args:
        db_path: Path to the .db file. Defaults to config.DB_PATH.

    Returns:
        An open sqlite3.Connection. Close it with conn.close() when done.
    """
    # SQLite creates the file but not missing folders, so make sure the
    # parent folder (e.g. data/) exists first.
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    return conn


# ---------------------------------------------------------------------------
# 2) Data extraction
# ---------------------------------------------------------------------------
def get_data(
    ticker: str,
    start: str = config.DEFAULT_START_DATE,
    end: str = config.DEFAULT_END_DATE,
    interval: str = config.DEFAULT_INTERVAL,
) -> pd.DataFrame:
    """
    Download candlestick (OHLCV) data for a single ticker from Yahoo Finance.

    Args:
        ticker:   Yahoo Finance symbol, e.g. "AAPL" or "BTC-USD".
        start:    Start date "YYYY-MM-DD" (inclusive).
        end:      End date "YYYY-MM-DD" (exclusive).
        interval: Candle size, e.g. "1d", "1wk", "1h".

    Returns:
        A pandas DataFrame indexed by date with columns
        Open, High, Low, Close, Volume (plus Dividends, Stock Splits).
        Empty if the ticker is invalid or has no data in the range.
    """
    # Ticker.history() returns single-level columns, which is simpler to work
    # with than yf.download() (that one returns multi-level columns).
    df = yf.Ticker(ticker).history(start=start, end=end, interval=interval)
    return df


def to_asset_rows(df: pd.DataFrame, ticker: str) -> list[AssetClass]:
    """
    Convert a yfinance DataFrame into a list of AssetClass dataclasses.

    Values are cast to plain Python int/float/str because sqlite3 cannot
    store numpy types (e.g. numpy.int64) directly.

    Args:
        df:     DataFrame returned by get_data().
        ticker: Symbol to attach to every row.

    Returns:
        One AssetClass per row of the DataFrame.
    """
    rows: list[AssetClass] = []
    # itertuples() yields one namedtuple per row; row.Index is the date.
    for row in df.itertuples():
        rows.append(
            AssetClass(
                ticker=ticker,
                date=row.Index.strftime("%Y-%m-%d"),
                open=float(row.Open),
                high=float(row.High),
                low=float(row.Low),
                close=float(row.Close),
                volume=int(row.Volume),
            )
        )
    return rows


# ---------------------------------------------------------------------------
# 3) Table creation
# ---------------------------------------------------------------------------
def create_table(
    conn: sqlite3.Connection,
    table: str,
    schema: type | dict[str, Any] | Any,
    primary_key: Sequence[str] | None = None,
) -> None:
    """
    Create a table (if it does not already exist) whose columns match
    a dataclass or a dictionary.

    Args:
        conn:        Open database connection.
        table:       Table name, e.g. "raw_stk_1d".
        schema:      One of:
                     - a dataclass class, e.g. AssetClass
                     - a dataclass instance
                     - a dict mapping column name -> Python type,
                       e.g. {"ticker": str, "close": float}
                     - a dict of example values,
                       e.g. {"ticker": "AAPL", "close": 101.2}
        primary_key: Columns that uniquely identify a row, e.g.
                     ("ticker", "date"). Stops the same candle being
                     stored twice.

    Example:
        create_table(conn, "raw_stk_1d", AssetClass, primary_key=("ticker", "date"))
    """
    _check_identifier(table)

    # Work out {column name: python type} from whatever we were given.
    if is_dataclass(schema):
        cls = schema if isinstance(schema, type) else type(schema)
        hints = get_type_hints(cls)
        columns = {f.name: hints[f.name] for f in fields(cls)}
    elif isinstance(schema, dict):
        columns = {
            name: (value if isinstance(value, type) else type(value))
            for name, value in schema.items()
        }
    else:
        raise TypeError("schema must be a dataclass (class or instance) or a dict")

    # Build "name TYPE" for each column; unknown types default to TEXT.
    col_defs = [
        f"{_check_identifier(name)} {_SQL_TYPES.get(py_type, 'TEXT')}"
        for name, py_type in columns.items()
    ]

    if primary_key:
        pk = ", ".join(_check_identifier(c) for c in primary_key)
        col_defs.append(f"PRIMARY KEY ({pk})")

    sql = f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(col_defs)})"
    conn.execute(sql)
    conn.commit()


# ---------------------------------------------------------------------------
# 4) Insertion
# ---------------------------------------------------------------------------
def insert_data(
    conn: sqlite3.Connection,
    table: str,
    rows: Sequence[Any],
    ignore_duplicates: bool = True,
) -> int:
    """
    Insert many rows into `table` in one go.

    Accepts a list of any ONE of these row types:
        - dataclasses  -> columns taken from the field names
        - dicts        -> columns taken from the keys
        - tuples/lists -> values inserted in the table's column order

    Args:
        conn:              Open database connection.
        table:             Name of an existing table.
        rows:              The rows to insert (all the same type).
        ignore_duplicates: If True, rows that clash with the primary key
                           are skipped instead of raising an error, so the
                           same download can be run twice safely.

    Returns:
        Number of rows actually inserted.
    """
    _check_identifier(table)
    if not rows:
        return 0

    first = rows[0]
    verb = "INSERT OR IGNORE" if ignore_duplicates else "INSERT"

    # Dataclasses are turned into dicts, then handled like dicts.
    if is_dataclass(first):
        rows = [asdict(r) for r in rows]
        first = rows[0]

    if isinstance(first, dict):
        # Named placeholders (:ticker, :date, ...) so key order doesn't matter.
        cols = [_check_identifier(c) for c in first.keys()]
        placeholders = ", ".join(f":{c}" for c in cols)
        sql = f"{verb} INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
    elif isinstance(first, (tuple, list)):
        # Positional placeholders (?, ?, ...) in the table's column order.
        placeholders = ", ".join("?" for _ in first)
        sql = f"{verb} INTO {table} VALUES ({placeholders})"
    else:
        raise TypeError(
            "rows must be a list of dataclasses, dicts, tuples or lists; "
            f"got {type(first).__name__}"
        )

    before = conn.total_changes
    conn.executemany(sql, rows)
    conn.commit()
    return conn.total_changes - before


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def table_name(asset_type: str = "stock", interval: str = config.DEFAULT_INTERVAL) -> str:
    """
    Build a table name following the project pattern, e.g. raw_stk_1d.

    Args:
        asset_type: A key of config.ASSET_TYPE_CODES ("stock", "crypto", ...).
        interval:   Candle interval, e.g. "1d".

    Returns:
        The table name as a string.
    """
    code = config.ASSET_TYPE_CODES[asset_type]
    return config.TABLE_NAME_PATTERN.format(asset_type=code, interval=interval)


def read_table(conn: sqlite3.Connection, table: str, ticker: str | None = None) -> pd.DataFrame:
    """
    Read a table (optionally one ticker only) back into a DataFrame.
    Useful for checking what was stored, and for Part Two.
    """
    _check_identifier(table)
    if ticker is None:
        return pd.read_sql_query(f"SELECT * FROM {table} ORDER BY ticker, date", conn)
    return pd.read_sql_query(
        f"SELECT * FROM {table} WHERE ticker = ? ORDER BY date", conn, params=(ticker,)
    )