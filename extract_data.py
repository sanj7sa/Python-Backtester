"""
extract_data.py
---------------
Part One: download daily price data for each ticker in config.py
and save it into the SQLite database.

Run from the project root:  python extract_data.py
"""

import config
from common import AssetClass, create_table, get_data, insert_data, set_db, table_name, to_asset_rows


def inspect_data(ticker: str) -> None:
    """Download one ticker and print what type of object the data is in."""
    df = get_data(ticker)
    print(type(df))      # <class 'pandas.core.frame.DataFrame'>
    print(df.head())     # first 5 rows

    # Print the first 3 rows one at a time
    for date, row in df.head(3).iterrows():
        print(date, row["Close"])


def extract(tickers: list[str]) -> None:
    """Download each ticker and insert its rows into the raw_stk_1d table."""
    conn = set_db()
    table = table_name("stock", "1d")   # "raw_stk_1d"

    # Create the table from the AssetClass dataclass (does nothing if it already exists)
    create_table(conn, table, AssetClass, primary_key=("ticker", "date"))

    for ticker in tickers:
        df = get_data(ticker)                     # download prices
        rows = to_asset_rows(df, ticker)          # turn each row into an AssetClass
        added = insert_data(conn, table, rows)    # save to the database
        print(f"{ticker}: {added} new rows added")

    conn.close()


if __name__ == "__main__":
    inspect_data("AAPL")
    extract(config.DEFAULT_TICKERS)