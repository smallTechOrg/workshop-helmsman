"""One-off database bootstrap for Workshop0 (runs as Cloud Run Job `workshop0-dbinit`).

Connects with DATABASE_URL (user workshop0_app) to the `postgres` maintenance
database, creates database `workshop0` owned by workshop0_app if absent, then
probes that workshop0_app can CREATE TABLE in schema public.

Never prints the URL or password. Stdout markers: DBINIT created-database |
DBINIT database-exists | DBINIT schema-ok. Exit non-zero on failure.
"""
import os
import sys
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import sql

DB_NAME = "workshop0"
OWNER = "workshop0_app"


def _conninfo(url: str, dbname: str) -> str:
    # Drop the SQLAlchemy driver suffix; swap the database path.
    parts = urlsplit(url.replace("postgresql+psycopg://", "postgresql://", 1))
    return urlunsplit(parts._replace(path="/" + dbname))


def main() -> int:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("DBINIT error: DATABASE_URL not set")
        return 2

    with psycopg.connect(_conninfo(url, "postgres"), autocommit=True) as conn:
        found = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,)).fetchone()
        if found is None:
            conn.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(DB_NAME), sql.Identifier(OWNER))
            )
            print("DBINIT created-database")
        else:
            owner = conn.execute(
                "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = %s", (DB_NAME,)
            ).fetchone()[0]
            if owner != OWNER:
                conn.execute(
                    sql.SQL("ALTER DATABASE {} OWNER TO {}").format(sql.Identifier(DB_NAME), sql.Identifier(OWNER))
                )
                print("DBINIT owner-fixed")
            print("DBINIT database-exists")

    # Schema privilege probe (rolled back; leaves nothing behind).
    with psycopg.connect(_conninfo(url, DB_NAME)) as conn:
        try:
            conn.execute("CREATE TABLE _workshop0_probe (id int)")
        except psycopg.Error as exc:
            conn.rollback()
            print(f"DBINIT error: cannot CREATE TABLE in public ({type(exc).__name__})")
            return 1
        conn.rollback()
    print("DBINIT schema-ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
