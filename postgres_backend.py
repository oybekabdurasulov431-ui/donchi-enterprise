"""Small DB-API compatibility layer for DONCHI's PostgreSQL migration.

Activate only with DONCHI_DB_ENGINE=postgres and DATABASE_URL. Nothing in this
module connects to, modifies, or resets the existing SQLite database.
"""
from __future__ import annotations

import re


def _convert_placeholders(sql: str) -> str:
    """Translate sqlite qmark binds without changing quoted question marks."""
    out = []
    quote = None
    i = 0
    while i < len(sql):
        ch = sql[i]
        if quote:
            out.append(ch)
            if ch == quote:
                if i + 1 < len(sql) and sql[i + 1] == quote:
                    out.append(sql[i + 1]); i += 1
                else:
                    quote = None
        elif ch in ("'", '"'):
            quote = ch; out.append(ch)
        elif ch == '?':
            out.append('%s')
        else:
            out.append(ch)
        i += 1
    return ''.join(out)


def _create_order(statements: list[str]) -> list[str]:
    """PostgreSQL needs referenced tables to exist before FK declarations."""
    tables = {}
    others = []
    for stmt in statements:
        match = re.match(r'CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+(\w+)', stmt, re.I)
        if match: tables[match.group(1)] = stmt
        else: others.append(stmt)
    ordered = []
    while tables:
        ready = [name for name, stmt in tables.items()
                 if not any(dep in tables and dep != name
                            for dep in re.findall(r'REFERENCES\s+(\w+)\s*\(', stmt, re.I))]
        if not ready:
            raise ValueError('Cyclic PostgreSQL foreign-key schema')
        for name in ready:
            ordered.append(tables.pop(name))
    return ordered + others


class _Row(dict):
    """Support sqlite-style row['field'] and row[0] access."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class PgConnection:
    def __init__(self, url: str):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError('Install psycopg[binary] to enable PostgreSQL') from exc
        self.conn = psycopg.connect(url, autocommit=True, row_factory=dict_row,
                                    connect_timeout=10)

    def execute(self, statement: str, params=()):
        query = statement.strip()
        if re.match(r'^INSERT\s+OR\s+IGNORE\s+INTO\b', query, re.I):
            query = re.sub(r'^INSERT\s+OR\s+IGNORE\s+INTO\b', 'INSERT INTO', query, flags=re.I)
            query += ' ON CONFLICT DO NOTHING'
        cursor = self.conn.execute(_convert_placeholders(query), params)
        return _Cursor(cursor)

    def executescript(self, script: str):
        # DONCHI schemas contain no semicolons within SQL string literals.
        statements = [s.strip() for s in script.split(';') if s.strip()]
        for stmt in _create_order(statements):
            self.execute(stmt)

    def has_column(self, table: str, column: str) -> bool:
        return bool(self.execute('SELECT 1 FROM information_schema.columns '
                                 'WHERE table_schema=current_schema() AND table_name=? '
                                 'AND column_name=?', (table, column)).fetchone())

    def close(self):
        self.conn.close()


class _Cursor:
    def __init__(self, cursor): self.cursor = cursor

    def __iter__(self):
        for row in self.cursor:
            yield _Row(row)

    def fetchone(self):
        row = self.cursor.fetchone()
        return _Row(row) if row is not None else None

    def fetchall(self):
        return [_Row(row) for row in self.cursor.fetchall()]

    @property
    def rowcount(self): return self.cursor.rowcount
