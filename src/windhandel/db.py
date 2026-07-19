import logging, os
import psycopg
from psycopg.rows import dict_row
from typing import Optional, Union, List, Dict, Any, Literal
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

logger = logging.getLogger(__name__)

def _build_where(
    filters: Optional[Dict[str, Dict[str, Any]]]
) -> tuple[str, dict]:
    """
    Convert a filter dict into a SQL WHERE clause + params dict.
    Returns ("", {}) when filters is None or empty.
    """

    if not filters:
        return "", {}

    conditions = []
    params: Dict[str, Any] = {}
    _OPERATOR_MAP = {
        "eq": "=",
        "neq": "!=",
        "gt": ">",
        "gte": ">=",
        "lt": "<",
        "lte": "<=",
        "like": "LIKE",
        "ilike": "ILIKE",
        "is_": "IS",
    }

    for op, conds in filters.items():
        sql_op = _OPERATOR_MAP.get(op)
        if not sql_op:
            raise ValueError(f"Unsupported filter operator: '{op}'")
        for field, value in conds.items():
            param_key = f"_f_{field}_{op}"
            conditions.append(f"{field} {sql_op} %({param_key})s")
            params[param_key] = value

    where = " WHERE " + " AND ".join(conditions)
    return where, params

class PostgresWrapper:
    def __init__(self, host: str, port: str | int, dbname: str, user: str, password: str) -> None:
        self.host = host
        self.port = port
        self.dbname = dbname
        self.user = user
        self.password = password

    def _connect(self) -> psycopg.Connection:
        conninfo = (
            f"host={self.host} port={self.port} dbname={self.dbname} "
            f"user={self.user} password={self.password} connect_timeout=3"
        )
        try:
            conn = psycopg.connect(conninfo, row_factory=dict_row)
            logger.debug(f"Connected to PostgreSQL at {self.host}")
            return conn
        except psycopg.OperationalError as e:
            logger.warning(f"Could not connect to {self.host}: {e}")
            raise RuntimeError(f"Could not reach PostgreSQL on {self.host}.") from e


    def gen_fetch(
        self,
        table: str,
        select: Optional[List[str]] = None,
        filters: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch rows from a table with optional column selection and filters.

        Supported filter operators: eq, neq, gt, gte, lt, lte, like, ilike, is_

        Example:
            gen_fetch(
                "trades",
                select=["id", "account", "date"],
                filters={
                    "eq":  {"universe": "crypto"},
                    "gte": {"date": "2025-01-01"},
                }
            )
        """
        columns = ", ".join(select) if select else "*"
        where_clause, params = _build_where(filters)
        sql = f"SELECT {columns} FROM {table}{where_clause}"

        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error fetching from {table}: {e}")
            return []

    def gen_insert(
        self,
        table: str,
        rows: List[Dict[str, Any]],
    ) -> int:
        """
        Insert rows into a table. Attempts bulk insert first, then falls back
        to row-by-row on failure (e.g. unique constraint violations).
        """
        if not rows:
            logger.warning("No rows provided for insert.")
            return 0

        columns = list(rows[0].keys())
        col_str = ", ".join(columns)
        placeholders = ", ".join(f"%({c})s" for c in columns)
        sql = f"INSERT INTO {table} ({col_str}) VALUES ({placeholders})"

        # Bulk attempt
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.executemany(sql, rows)
                conn.commit()
                return len(rows)
        except Exception as e:
            logger.error(f"Bulk insert failed on {table}: {e} — falling back to row-by-row.")

        # Row-by-row fallback
        for row in rows:
            try:
                with self._connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute(sql, row)
                    conn.commit()
            except Exception as e:
                logger.error(f"Failed to insert row into {table}: {row} | {e}")

        return len(rows)

    def call_function(
        self,
        func_name: str,
        params: Optional[Dict[str, Any]] = None,
        filters: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Optional[Union[List[Dict[str, Any]], Dict[str, Any]]]:
        """
        Call a PostgreSQL function and return its results, with optional filters
        applied as a WHERE clause on the result set.

        Example:
            call_function(
                "get_positions_as_of",
                params={"as_of_date": "2026-03-26"},
                filters={"eq": {"pocket": "core"}}
            )
        """
        if params:
            args = ", ".join(f"%({k})s" for k in params.keys())
            base_sql = f"SELECT * FROM {func_name}({args})"
        else:
            base_sql = f"SELECT * FROM {func_name}()"

        where_clause, where_params = _build_where(filters)
        sql = f"SELECT * FROM ({base_sql}) AS _fn{where_clause}"
        merged_params = {**(params or {}), **where_params}

        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, merged_params)
                    data = cur.fetchall()
                    logger.debug(f"Function {func_name} returned {len(data)} rows.")
                    return data
        except Exception as e:
            logger.error(f"Error calling function '{func_name}': {e}")
            return None


