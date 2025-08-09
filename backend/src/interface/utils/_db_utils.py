import os
import psycopg2
from interface.utils._formatting import format_sql_query

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

def execute(query: str, *args):
    """
    Given query is formatted with sanitized arguments.

    For argument **val** with index *i* in the packed tuple, any instances of !p*i* in the query string will be replaced with **val**.  
    Indexing begins at 1.
    ```
    # Equivalent to "SELECT * FROM table WHERE id = 5 AND count = 5"
    select("SELECT * FROM table WHERE id = !p1 AND count = !p1", 5)
    ```
    """
    conn, cur = get_cursor()
    formatted_query = format_sql_query(query, *args)

    if cur is not None:
        cur.execute(formatted_query)
        cur.close()
    
    if conn is not None:
        conn.commit()
        conn.close()

def select(query: str, *args) -> list[tuple[int | str, ...]]:
    """
    Given query is formatted with sanitized arguments.

    For argument **val** with index *i* in the packed tuple, any instances of !p*i* in the query string will be replaced with **val**.  
    Indexing begins at 1.
    ```
    # Equivalent to "SELECT * FROM table WHERE id = 5 AND count = 5"
    select("SELECT * FROM table WHERE id = !p1 AND count = !p1", 5)
    ```
    """
    conn, cur = get_cursor()
    result = []
    formatted_query = format_sql_query(query, *args)

    if cur is not None:
        cur.execute(formatted_query)
        result = cur.fetchall()

    if conn is not None:
        conn.close()

    return result