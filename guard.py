"""SQL guard: validates model-written SQL before it gets anywhere near the database.

This is one layer of defence. The database user is also read-only with column-level
grants (see sql/create_readonly_user.sql), so a bug in this file cannot be turned
into a write or a read of a column the user was never granted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

MAX_ROWS = 100
MAX_SQL_CHARS = 2000

# Data minimisation: only these tables and columns can ever be read through the MCP server.
# applications.owner is deliberately absent.
ALLOWED_SCHEMA: dict[str, set[str]] = {
    "funders": {"id", "name", "country", "type", "focus_area", "website"},
    "opportunities": {
        "id", "funder_id", "title", "description", "amount_usd",
        "deadline", "region", "status", "notes",
    },
    "applications": {"id", "opportunity_id", "stage", "submitted_on"},
}

FORBIDDEN_FUNCTIONS = {
    "SLEEP", "BENCHMARK", "LOAD_FILE", "GET_LOCK", "RELEASE_LOCK",
    "SYS_EXEC", "SYS_EVAL", "MASTER_POS_WAIT",
}

# Heuristic only. It adds a warning to the tool result; it is not the main defence.
_INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) (instructions|prompts)",
    r"disregard (all |any )?(previous|prior|above)",
    r"system (notice|prompt|message)",
    r"you must (now )?(reply|respond|run|call|execute)",
    r"run_query",
    r"reply only with",
]


@dataclass
class Verdict:
    allowed: bool
    sql: str | None
    reason: str


def _block(reason: str) -> Verdict:
    return Verdict(False, None, reason)


def validate(sql: str) -> Verdict:
    if not sql or not sql.strip():
        return _block("empty query")
    if len(sql) > MAX_SQL_CHARS:
        return _block("query too long")

    try:
        statements = sqlglot.parse(sql, read="mysql")
    except SqlglotError as e:
        return _block(f"could not parse SQL ({type(e).__name__})")

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        return _block("exactly one statement is allowed")

    tree = statements[0]
    if not isinstance(tree, exp.Select):
        return _block("only plain SELECT statements are allowed")

    if tree.find(exp.Into):
        return _block("SELECT ... INTO is not allowed")
    if tree.find(exp.Lock):
        return _block("locking reads are not allowed")
    if tree.find(exp.With):
        return _block("CTEs are not supported")
    if tree.find(exp.Union) or tree.find(exp.Intersect) or tree.find(exp.Except):
        return _block("set operations are not supported")

    for node in tree.find_all(exp.Func):
        name = node.name if isinstance(node, exp.Anonymous) else node.sql_name()
        if name.upper() in FORBIDDEN_FUNCTIONS:
            return _block(f"function {name.upper()} is not allowed")

    tables = set()
    for t in tree.find_all(exp.Table):
        if t.args.get("db") or t.args.get("catalog"):
            return _block("schema-qualified tables are not allowed")
        name = t.name.lower()
        if name not in ALLOWED_SCHEMA:
            return _block(f"table '{name}' is not allowed")
        tables.add(name)

    for star in tree.find_all(exp.Star):
        if not isinstance(star.parent, exp.Count):
            return _block("SELECT * is not allowed; name the columns you need")

    allowed_cols = set().union(*(ALLOWED_SCHEMA[t] for t in tables)) if tables else set()
    aliases = {a.alias.lower() for a in tree.find_all(exp.Alias) if a.alias}
    for col in tree.find_all(exp.Column):
        cname = col.name.lower()
        if cname not in allowed_cols and cname not in aliases:
            return _block(f"column '{cname}' is not allowed")

    limit = tree.args.get("limit")
    if limit is None:
        tree = tree.limit(MAX_ROWS)
    else:
        try:
            n = int(limit.expression.name)
        except (ValueError, AttributeError):
            return _block("LIMIT must be a plain number")
        if n > MAX_ROWS:
            tree = tree.limit(MAX_ROWS)

    return Verdict(True, tree.sql(dialect="mysql", comments=False), "ok")


def flag_injection(text: str) -> bool:
    low = text.lower()
    return any(re.search(p, low) for p in _INJECTION_PATTERNS)
