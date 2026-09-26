"""
extract_data.py
---------------
Part One entry point: download candlestick data for a list of tickers and
store it in the local SQLite database.

Run from the project root (with the virtual environment active):

    python extract_data.py                       # uses config.DEFAULT_TICKERS
    python extract_data.py AAPL TSLA BTC-USD     # choose your own tickers
"""

import sys

import config
from common import (
    AssetClass,
    create_table,
    get_data,
    insert_data,
    read_table,
    set_db,
    table_name,
    to_asset_rows,
)


def inspect_data(ticker: str) -> None:
    """
    Task 2 check: download one ticker, print it and report its type.
    """
    df = get_data(ticker)
    print(f"\nget_data('{ticker}') returned an object of type: {type(df)}")
    print(df.head())

    # Looping over rows. iterrows() yields (index, row) tuples where
    # index is a pandas Timestamp and row is a pandas Series.
    print("\nFirst 3 rows via a for loop:")
    for i, (date, row) in enumerate(df.iterrows()):
        print(type(date).__name__, type(row).__name__, date.date(), row["Close"])
        if i == 2:
            break


def extract(tickers: list[str], asset_type: str = "stock") -> None:
    """
    Download each ticker and insert it into raw_<type>_<interval>.

    Args:
        tickers:    Yahoo Finance symbols to add to the database.
        asset_type: Key of config.ASSET_TYPE_CODES; decides the table.
    """
    conn = set_db()
    table = table_name(asset_type, config.DEFAULT_INTERVAL)

    # Build the table from the dataclass; (ticker, date) prevents duplicates.
    create_table(conn, table, AssetClass, primary_key=("ticker", "date"))

    for ticker in tickers:
        df = get_data(ticker)
        if df.empty:
            print(f"{ticker}: no data returned, skipped")
            continue
        rows = to_asset_rows(df, ticker)          # list[AssetClass]
        added = insert_data(conn, table, rows)
        print(f"{ticker}: {len(rows)} rows downloaded, {added} new rows inserted into {table}")

    # Quick check of what is now stored.
    stored = read_table(conn, table)
    print(f"\n{table} now holds {len(stored)} rows across "
          f"{stored['ticker'].nunique()} tickers")
    conn.close()


if __name__ == "__main__":
    chosen = sys.argv[1:] or config.DEFAULT_TICKERS
    inspect_data(chosen[0])
    extract(chosen)