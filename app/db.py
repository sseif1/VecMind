import psycopg2
from .config import DATABASE_URL


def get_conn():
    """
    Simple Postgres connection helper using psycopg2.
    Autocommit is enabled so we don't have to manage transactions manually
    for this small demo app.
    """
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn