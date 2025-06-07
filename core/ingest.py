import pandas as pd
import sqlite3
from core.db import get_connection

TABLE_COLUMNS = {
    "customers": ["customer_id", "first_name", "last_name", "email", "phone"],
    "employees": ["emp_id", "first_name", "last_name", "email", "hire_date", "salary"],
    "orders": ["order_id", "customer_id", "order_date", "amount"]
}

def insert_dataframe_to_table(df: pd.DataFrame, table_name: str) -> str:
    """
    Inserts a DataFrame into a specific table in the database.
    Assumes the DataFrame matches the schema of the table.
    Returns a message indicating success or failure.
    """
    if table_name not in TABLE_COLUMNS:
        return f" Error: Unsupported table '{table_name}'."

    expected_columns = TABLE_COLUMNS[table_name]
    if list(df.columns) != expected_columns:
        return f" Error: Column mismatch. Expected columns: {expected_columns}"

    try:
        conn = get_connection()
        df.to_sql(table_name, conn, if_exists='append', index=False)
        conn.commit()
        conn.close()
        return f" Successfully inserted {len(df)} rows into '{table_name}'."
    except Exception as e:
        return f" Error inserting into '{table_name}': {str(e)}"

def read_csv_and_insert(filepath: str, table_name: str) -> str:
    """
    Reads a CSV file and inserts its content into the specified table.
    """
    try:
        df = pd.read_csv(filepath)
        return insert_dataframe_to_table(df, table_name)
    except Exception as e:
        return f" Error reading CSV file: {str(e)}"
