import re
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


class DatabaseRow(dict):
    """Compatibility row with the existing sqlite3.Row string-key behavior."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class DatabaseResult:
    def __init__(self, result):
        self._result = result
        self.rowcount = result.rowcount

    def fetchone(self):
        row = self._result.fetchone()
        return DatabaseRow(row._mapping) if row else None

    def fetchall(self):
        return [DatabaseRow(row._mapping) for row in self._result.fetchall()]


class DatabaseConnection:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.connection = engine.connect()
        self.transaction = None

    def _parameters(self, query, params):
        values = tuple(params or ())
        index = 0

        def replace(_match):
            nonlocal index
            name = f"p{index}"
            index += 1
            return f":{name}"

        converted = re.sub(r"\?", replace, query)
        return converted, {f"p{i}": value for i, value in enumerate(values)}

    def execute(self, query, params=None):
        query = query.strip().rstrip(";")
        if query.upper().startswith("PRAGMA"):
            return DatabaseResult(self.connection.execute(text("SELECT 1")))
        if query.upper().startswith("INSERT OR IGNORE INTO"):
            query = re.sub(r"^INSERT OR IGNORE INTO", "INSERT INTO", query, flags=re.IGNORECASE)
            query += " ON CONFLICT DO NOTHING"
        converted, values = self._parameters(query, params)
        return DatabaseResult(self.connection.execute(text(converted), values))

    def __enter__(self):
        # SQLAlchemy starts an implicit transaction on the first statement.
        # Reuse it when a caller performs a write before entering the context.
        if not self.connection.in_transaction():
            self.transaction = self.connection.begin()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type:
                self.connection.rollback()
            elif self.transaction:
                self.transaction.commit()
            elif self.connection.in_transaction():
                self.connection.commit()
        finally:
            self.close()

    def close(self):
        if not self.connection.closed:
            if self.connection.in_transaction():
                self.connection.commit()
            self.connection.close()


def create_database_engine(database_url):
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is required for runtime database access. "
            "Use an explicit sqlite test URL only in tests or the legacy migration utility."
        )
    return create_engine(database_url, future=True, pool_pre_ping=True)


def get_database_connection(database_url):
    return DatabaseConnection(create_database_engine(database_url))


@contextmanager
def database_transaction(database_url):
    connection = get_database_connection(database_url)
    try:
        with connection:
            yield connection
    except Exception:
        connection.close()
        raise
