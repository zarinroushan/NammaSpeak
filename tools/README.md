# Database migration procedure

The application requires PostgreSQL through `DATABASE_URL`. SQLite is not a
runtime fallback. The existing SQLite database is preserved as a read-only
source for an explicit export/import.

## 1. Create PostgreSQL and configure the URL

Set `DATABASE_URL` in the environment or an untracked `.env` file:

```text
DATABASE_URL=postgresql+psycopg://user:password@host:5432/nammaspeak
```

Do not commit this URL; it contains credentials.

## 2. Create the versioned schema

```powershell
.\venv\Scripts\python.exe -m alembic upgrade head
```

The application refuses to start against PostgreSQL until the migration has
created the required tables.

## 3. Export the existing SQLite data

This does not modify or delete the SQLite file:

```powershell
.\venv\Scripts\python.exe tools\migrate_sqlite.py export `
  --sqlite instance\nammaspeak.db `
  --output instance\nammaspeak-export.json
```

Review the JSON counts and keep the export as a backup.

## 4. Import into PostgreSQL

```powershell
.\venv\Scripts\python.exe tools\migrate_sqlite.py import `
  --input instance\nammaspeak-export.json
```

Imports use `ON CONFLICT DO NOTHING`; existing PostgreSQL rows are never
overwritten or silently reassigned. Any legacy `default` user data remains
owned by the explicit `default` user. Review and reconcile it deliberately
before exposing the database to users.

## 5. Verify before starting the app

Run the complete test suite with a PostgreSQL test URL, then start Flask with
the same verified `DATABASE_URL`. A real PostgreSQL instance is required for
the integration test; SQLite-only tests do not prove PostgreSQL compatibility.
