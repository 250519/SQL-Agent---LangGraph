import sqlite3
from pathlib import Path

DB_PATH = "data/mydb.db"

def get_connection():
    """
    Establish and return a SQLite database connection.
    Creates the database file if it doesn't exist.
    """
    Path("data").mkdir(exist_ok=True)
    return sqlite3.connect(DB_PATH)

def initialize_db():
    """
    Creates default tables if they do not exist.
    Can be extended to support migrations or versioning later.
    """
    conn = get_connection()
    cursor = conn.cursor()

    table_creation_queries = [
        """
        CREATE TABLE IF NOT EXISTS employees (
            emp_id INTEGER PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            hire_date TEXT NOT NULL,
            salary REAL NOT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS customers (
            customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            amount REAL NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
        );
        """
    ]

    for query in table_creation_queries:
        cursor.execute(query)

    conn.commit()
    conn.close()
