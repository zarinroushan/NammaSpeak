"""Explicit legacy SQLite export/import utility.

This tool never modifies the SQLite source and never drops PostgreSQL rows.

Export:
    python tools/migrate_sqlite.py export --sqlite instance/nammaspeak.db --output backup.json

Import after `alembic upgrade head`:
    DATABASE_URL=postgresql+psycopg://... \
      python tools/migrate_sqlite.py import --input backup.json
"""
import argparse
import json
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import create_engine, text

TABLES = (
    "phrases",
    "scenarios",
    "users",
    "saved_phrases",
    "user_progress",
    "phrase_learning_stats",
    "translation_cache",
    "phrase_translations",
    "scenario_translations",
)


def json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def export_sqlite(sqlite_path, output_path):
    source = Path(sqlite_path).resolve()
    if not source.exists():
        raise FileNotFoundError(f"SQLite source does not exist: {source}")
    connection = sqlite3.connect(source)
    connection.row_factory = sqlite3.Row
    try:
        payload = {"format": 1, "source": str(source), "tables": {}}
        for table in TABLES:
            rows = connection.execute(f"SELECT * FROM {table}").fetchall()
            payload["tables"][table] = [
                {key: json_value(row[key]) for key in row.keys()} for row in rows
            ]
    finally:
        connection.close()
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {table: len(rows) for table, rows in payload["tables"].items()}


def import_snapshot(input_path, database_url):
    if not database_url or not database_url.startswith("postgresql"):
        raise RuntimeError("Import requires a PostgreSQL DATABASE_URL")
    payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    if payload.get("format") != 1:
        raise ValueError("Unsupported snapshot format")
    engine = create_engine(database_url, future=True, pool_pre_ping=True)
    imported = {}
    with engine.begin() as connection:
        for table in TABLES:
            rows = payload.get("tables", {}).get(table, [])
            if not rows:
                imported[table] = 0
                continue
            columns = list(rows[0].keys())
            names = ", ".join(columns)
            parameters = ", ".join(f":p{i}" for i in range(len(columns)))
            query = text(
                f"INSERT INTO {table} ({names}) VALUES ({parameters}) ON CONFLICT DO NOTHING"
            )
            count = 0
            for row in rows:
                result = connection.execute(
                    query, {f"p{i}": row.get(column) for i, column in enumerate(columns)}
                )
                count += max(result.rowcount, 0)
            imported[table] = count
    return imported


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("--sqlite", required=True)
    export_parser.add_argument("--output", required=True)
    import_parser = subparsers.add_parser("import")
    import_parser.add_argument("--input", required=True)
    args = parser.parse_args()

    if args.command == "export":
        print(json.dumps(export_sqlite(args.sqlite, args.output), indent=2))
    else:
        print(json.dumps(import_snapshot(args.input, os.getenv("DATABASE_URL", "")), indent=2))


if __name__ == "__main__":
    main()
