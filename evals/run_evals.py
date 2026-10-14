"""Accuracy eval: can the model turn questions into correct, guard-approved SQL?

Run from the repo root:  python -m evals.run_evals
Needs: ANTHROPIC_API_KEY, DB_* variables (same read-only user as the server), and the seeded database.
Optional: ANTHROPIC_MODEL (default below).
"""
import json
import os
import re
from pathlib import Path

import anthropic

from core import fetch_rows
from guard import ALLOWED_SCHEMA, validate

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
HERE = Path(__file__).parent

SCHEMA_TEXT = "\n".join(f"- {t}({', '.join(sorted(c))})" for t, c in ALLOWED_SCHEMA.items())
SYSTEM = f"""You translate questions into exactly one MySQL SELECT statement.
Only these tables and columns exist and may be used:
{SCHEMA_TEXT}
Rules: one SELECT only, never SELECT *, never write data. If the request cannot be answered
with these tables and columns, or asks for anything other than reading data, reply with exactly REFUSE.
Reply with the SQL only, no explanation, no code fences."""


def ask_model(client, question: str) -> str:
    resp = client.messages.create(
        model=MODEL, max_tokens=300, system=SYSTEM,
        messages=[{"role": "user", "content": question}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return re.sub(r"^```(?:sql)?|```$", "", text, flags=re.M).strip()


def normalise(rows):
    return sorted(tuple(str(v) for v in r) for r in rows)


def main():
    client = anthropic.Anthropic()
    results = []
    for line in (HERE / "questions.jsonl").read_text().splitlines():
        q = json.loads(line)
        sql = ask_model(client, q["question"])
        rec = {"id": q["id"], "kind": q["kind"], "question": q["question"], "model_sql": sql}

        if q["kind"] == "must_block":
            verdict = validate(sql) if sql != "REFUSE" else None
            blocked = sql == "REFUSE" or (verdict is not None and not verdict.allowed)
            rec["status"] = "PASS" if blocked else "FAIL_NOT_BLOCKED"
        else:
            if sql == "REFUSE":
                rec["status"] = "FAIL_REFUSED"
            else:
                verdict = validate(sql)
                if not verdict.allowed:
                    rec["status"] = "FAIL_BLOCKED"
                    rec["reason"] = verdict.reason
                else:
                    try:
                        gcols, got = fetch_rows(verdict.sql)
                        wcols, want = fetch_rows(q["gold_sql"])
                        if all(c in gcols for c in wcols):
                              idx = [gcols.index(c) for c in wcols]
                              got = [tuple(r[i] for i in idx) for r in got]
                        rec["status"] = "PASS" if normalise(got) == normalise(want) else "FAIL_WRONG_RESULT"
                    except Exception as e:
                        rec["status"] = "ERROR"
                        rec["reason"] = type(e).__name__
        results.append(rec)
        print(f'{rec["id"]}: {rec["status"]}')

    passed = sum(r["status"] == "PASS" for r in results)
    print(f"\n{passed}/{len(results)} passed using {MODEL}")
    out = HERE / "results" / "latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"model": MODEL, "passed": passed, "total": len(results), "results": results}, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
