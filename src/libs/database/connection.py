import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def get_cursor():
    conn = None
    cur = None

    try:
        conn = psycopg2.connect(
            database=os.environ.get("DB"),
            host=os.environ.get("DB_HOST"),
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD"),
        )

        cur = conn.cursor()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        return conn, cur

def execute(query: str):
    conn, cur = get_cursor()

    if cur is not None:
        cur.execute(query)
        cur.close()
    
    if conn is not None:
        conn.close()

def select(query: str):
    conn, cur = get_cursor()
    result = []

    if cur is not None:
        cur.execute(query)
        result = cur.fetchall()

    if conn is not None:
        conn.close()

    return result