import pyodbc
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()

def get_connection():
    return pyodbc.connect(
        f"DRIVER={{SQL Server}};"
        f"SERVER={os.getenv('JDE_SERVER')};"
        f"DATABASE={os.getenv('JDE_DATABASE')};"
        f"UID={os.getenv('JDE_USER')};"
        f"PWD={os.getenv('JDE_PASSWORD')}"
    )

def query(sql: str) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql(sql, conn)
