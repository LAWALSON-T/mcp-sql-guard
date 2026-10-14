import json
from pathlib import Path

import pytest

from guard import MAX_ROWS, validate


def ok(sql):
    v = validate(sql)
    assert v.allowed, v.reason
    return v.sql


def blocked(sql, fragment=None):
    v = validate(sql)
    assert not v.allowed, f"should have been blocked: {sql}"
    if fragment:
        assert fragment in v.reason


def test_simple_select_gets_limit():
    assert f"LIMIT {MAX_ROWS}" in ok("SELECT title FROM opportunities")


def test_large_limit_is_clamped():
    assert f"LIMIT {MAX_ROWS}" in ok("SELECT title FROM opportunities LIMIT 5000")


def test_small_limit_is_kept():
    assert "LIMIT 5" in ok("SELECT title FROM opportunities LIMIT 5")


def test_count_star_is_allowed():
    ok("SELECT COUNT(*) FROM opportunities WHERE status = 'open'")


def test_join_group_order_alias():
    ok("SELECT f.name, COUNT(*) AS n FROM funders f JOIN opportunities o ON o.funder_id = f.id "
       "GROUP BY f.name ORDER BY n DESC")


def test_subquery_is_allowed():
    ok("SELECT title FROM opportunities WHERE funder_id IN (SELECT id FROM funders WHERE country = 'Kenya')")


@pytest.mark.parametrize("sql", [
    "DELETE FROM opportunities",
    "DROP TABLE funders",
    "UPDATE opportunities SET status = 'open'",
    "INSERT INTO funders (id, name) VALUES (99, 'x')",
    "TRUNCATE TABLE funders",
])
def test_writes_and_ddl_blocked(sql):
    blocked(sql)


def test_multiple_statements_blocked():
    blocked("SELECT id FROM funders; DROP TABLE funders", "exactly one")


def test_select_star_blocked():
    blocked("SELECT * FROM funders", "SELECT *")
    blocked("SELECT f.* FROM funders f", "SELECT *")


def test_owner_column_blocked():
    blocked("SELECT owner FROM applications", "owner")
    blocked("SELECT a.owner FROM applications a", "owner")


def test_unknown_and_system_tables_blocked():
    blocked("SELECT user FROM mysql.user")
    blocked("SELECT table_name FROM information_schema.tables")
    blocked("SELECT id FROM secrets")


def test_dangerous_functions_blocked():
    blocked("SELECT SLEEP(10)", "SLEEP")
    blocked("SELECT BENCHMARK(1000000, MD5('x'))", "BENCHMARK")
    blocked("SELECT LOAD_FILE('/etc/passwd')", "LOAD_FILE")


def test_into_outfile_blocked():
    blocked("SELECT title FROM opportunities INTO OUTFILE '/tmp/x'")


def test_union_and_cte_blocked():
    blocked("SELECT id FROM funders UNION SELECT id FROM opportunities")
    blocked("WITH x AS (SELECT id FROM funders) SELECT id FROM x")


def test_locking_read_blocked():
    blocked("SELECT id FROM funders FOR UPDATE")


def test_empty_and_garbage_blocked():
    blocked("")
    blocked("   ")
    blocked("this is not sql")


def test_gold_queries_pass_the_guard():
    path = Path(__file__).resolve().parent.parent / "evals" / "questions.jsonl"
    for line in path.read_text().splitlines():
        q = json.loads(line)
        if q["kind"] == "answer":
            assert validate(q["gold_sql"]).allowed, q["id"]
