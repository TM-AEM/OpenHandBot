#!/usr/bin/env python3
"""Isolated SQLite persistence canary (H1 validation) — standalone, stdlib only.

Purpose
-------
Prove whether a hosting provider keeps a SQLite file (including its WAL sidecars)
across a process restart, a server/container restart, and a redeployment.

This script is deliberately independent of OpenHandBot:
  * standard library only (argparse, os, sqlite3, uuid, pathlib);
  * no network access, no sockets, no HTTP;
  * no Telegram/OpenHands credentials;
  * never reads application environment variables or a .env file;
  * never deletes a database;
  * never defaults to ``bot_state.sqlite3``.

Commands
--------
  write    Create a disposable database, enable WAL, insert a unique marker, commit.
  read     Reopen the database and print the stored marker(s) and journal mode.
  inspect  Report the resolved path, journal mode, and which files exist
           (database / -wal / -shm). Never creates the database.

The database path must be passed explicitly with ``--db`` and must be absolute.

Exit codes: 0 = success, 1 = usage/verification failure, 2 = argument error.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import uuid
from pathlib import Path

TABLE = "canary"


def _fail(message: str) -> "SystemExit":
    """Print a non-secret diagnostic to stderr and return a non-zero exit."""
    print(f"ERROR: {message}", file=os.sys.stderr)
    return SystemExit(1)


def _find_openhandbot_root(start: Path) -> Path | None:
    """Return the OpenHandBot repository root that contains ``start``, if any.

    Detected by signature files only (no imports from the application):
    ``main.py`` + ``bot/`` + ``AGENTS.md``, or a ``.git`` directory next to ``main.py``.
    """
    current: Path | None = start
    while current is not None:
        if (current / "main.py").is_file() and (current / "bot").is_dir() and (
            current / "AGENTS.md"
        ).is_file():
            return current
        if (current / ".git").is_dir() and (current / "main.py").is_file():
            return current
        parent = current.parent
        current = None if parent == current else parent
    return None


def resolve_db_path(raw: str) -> Path:
    """Validate and resolve the operator-supplied database path.

    Rules: must be provided, must be absolute, must not be a directory, and must
    not live inside the OpenHandBot repository.
    """
    if not raw:
        raise _fail("--db is required (an explicit absolute path, e.g. /home/container/h1_canary.sqlite3)")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise _fail(f"--db must be an absolute path (got {raw!r}); relative paths are rejected")
    resolved = path.resolve()
    if resolved.name == "bot_state.sqlite3":
        raise _fail("refusing to use 'bot_state.sqlite3' — the canary never touches application data")
    if resolved.is_dir():
        raise _fail(f"--db points at a directory, not a file: {resolved}")

    root = _find_openhandbot_root(resolved.parent)
    if root is not None and (resolved == root or root in resolved.parents):
        raise _fail(f"--db must not be inside the OpenHandBot repository ({root}); use a disposable path")
    return resolved


def _require_writable_parent(db_path: Path) -> None:
    """The parent directory must already exist and be writable.

    We do NOT create missing directories: a missing directory usually means the
    persistent volume is not mounted, and silently creating it would test the
    wrong (non-persistent) location.
    """
    parent = db_path.parent
    if not parent.is_dir():
        raise _fail(
            f"parent directory does not exist: {parent} — confirm the persistent volume is mounted "
            "at this path before running the canary"
        )
    if not os.access(parent, os.W_OK):
        raise _fail(f"parent directory is not writable: {parent} (read-only or insufficient permissions)")


def _connect(db_path: Path, *, read_only: bool = False) -> sqlite3.Connection:
    """Open the database, enabling WAL and a busy timeout for write/read modes."""
    if read_only:
        uri = f"file:{db_path}?mode=ro"
        con = sqlite3.connect(uri, uri=True)
    else:
        con = sqlite3.connect(str(db_path), check_same_thread=False)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA busy_timeout=5000")
    return con


def _sidecars(db_path: Path) -> dict[str, bool]:
    return {
        "db": db_path.exists(),
        "wal": db_path.with_name(db_path.name + "-wal").exists(),
        "shm": db_path.with_name(db_path.name + "-shm").exists(),
    }


def cmd_write(db_path: Path, confirm_overwrite: bool) -> int:
    _require_writable_parent(db_path)
    existed = db_path.exists()
    if existed and not confirm_overwrite:
        return int(
            _fail(
                f"database already exists: {db_path} — refusing to touch existing data. "
                "Re-run with --confirm-overwrite only if you intend to add a new marker row."
            ).code
        )

    marker = uuid.uuid4().hex
    try:
        con = _connect(db_path)
        with con:  # committed transaction
            con.execute(
                f"CREATE TABLE IF NOT EXISTS {TABLE} (marker TEXT PRIMARY KEY, kind TEXT NOT NULL)"
            )
            con.execute(f"INSERT INTO {TABLE} (marker, kind) VALUES (?, ?)", (marker, "canary"))
        mode = con.execute("PRAGMA journal_mode").fetchone()[0]
        con.close()
    except sqlite3.OperationalError as exc:
        return int(_fail(f"cannot write to {db_path}: {exc}").code)

    if str(mode).lower() != "wal":
        return int(_fail(f"WAL not enabled on this filesystem (journal_mode={mode!r})").code)

    files = _sidecars(db_path)
    print(f"OK wrote marker={marker} journal_mode={mode}")
    print(f"PATH {db_path}")
    print(f"FILES db={files['db']} wal={files['wal']} shm={files['shm']}")
    return 0


def cmd_read(db_path: Path) -> int:
    if not db_path.exists():
        return int(_fail(f"database not found: {db_path} — run 'write' first").code)
    try:
        con = _connect(db_path, read_only=True)
        try:
            rows = con.execute(f"SELECT marker, kind FROM {TABLE} ORDER BY marker").fetchall()
            mode = con.execute("PRAGMA journal_mode").fetchone()[0]
        finally:
            con.close()
    except sqlite3.OperationalError as exc:
        return int(_fail(f"cannot read {db_path}: {exc}").code)

    if not rows:
        return int(_fail(f"no canary rows found in {db_path} — the record did not persist").code)

    files = _sidecars(db_path)
    print(f"OK read {len(rows)} marker(s) journal_mode={mode}")
    print(f"PATH {db_path}")
    print(f"FILES db={files['db']} wal={files['wal']} shm={files['shm']}")
    for marker, kind in rows:
        print(f"MARKER {marker} kind={kind}")
    return 0


def cmd_inspect(db_path: Path) -> int:
    files = _sidecars(db_path)
    mode = "unknown"
    if files["db"]:
        try:
            con = _connect(db_path, read_only=True)
            try:
                mode = con.execute("PRAGMA journal_mode").fetchone()[0]
            finally:
                con.close()
        except sqlite3.OperationalError as exc:
            mode = f"unreadable ({exc})"
    print(f"PATH {db_path}")
    print(f"PARENT {db_path.parent} writable={os.access(db_path.parent, os.W_OK) if db_path.parent.exists() else False}")
    print(f"JOURNAL_MODE {mode}")
    print(f"FILES db={files['db']} wal={files['wal']} shm={files['shm']}")
    if not files["db"]:
        print("NOTE database does not exist yet (inspect never creates it)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="canary.py",
        description="Isolated SQLite persistence canary (stdlib only, no network, no secrets).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_write = sub.add_parser("write", help="create the DB (WAL) and insert a unique marker")
    p_write.add_argument("--db", required=True, help="absolute path to the disposable canary database")
    p_write.add_argument(
        "--confirm-overwrite",
        action="store_true",
        help="allow adding a marker to an existing database (off by default)",
    )

    p_read = sub.add_parser("read", help="reopen the DB and verify the stored marker")
    p_read.add_argument("--db", required=True, help="absolute path to the disposable canary database")

    p_inspect = sub.add_parser("inspect", help="report path, journal mode, and existing files")
    p_inspect.add_argument("--db", required=True, help="absolute path to the disposable canary database")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    db_path = resolve_db_path(args.db)

    if args.command == "write":
        return cmd_write(db_path, args.confirm_overwrite)
    if args.command == "read":
        return cmd_read(db_path)
    if args.command == "inspect":
        return cmd_inspect(db_path)
    return int(_fail(f"unknown command: {args.command}").code)


if __name__ == "__main__":
    raise SystemExit(main())
