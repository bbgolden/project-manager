import re

def sanitize(arg: int | str) -> str:
    """
    Sanitizes argument for use in Postgres SQL queries.
    - Converts falsy values to NULL
    - Escapes forbidden sequences
    - Formats single quotes
    """
    if isinstance(arg, int):
        return str(arg)
    if not arg:
        return "NULL"
    
    return "'" + arg.replace("'", "''") + "'"

def format_sql_query(query: str, *args) -> str:
    """
    Formats given query with sanitized arguments.

    For argument **val** with index *i* in the packed tuple, any instances of !p*i* in the query string will be replaced with **val**.  
    Indexing begins at 1.
    ```
    # Equivalent to "SELECT * FROM table WHERE id = 5 AND count = 5"
    format_sql_query("SELECT * FROM table WHERE id = !p1 AND count = !p1", 5)
    ```
    """
    param_count = len(set(re.findall(r"!p[0-9]+", query)))
    arg_count = len(args)
    if param_count != arg_count:
        raise TypeError(f"Expected {param_count} query arguments but received {arg_count}")
    
    formatted_query = query
    for i, arg in enumerate(args):
        formatted_query = formatted_query.replace(f"!p{i + 1}", sanitize(arg))

    return formatted_query