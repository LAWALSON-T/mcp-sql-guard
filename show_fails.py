import json
from pathlib import Path

from core import fetch_rows

gold = {}
for line in Path("evals/questions.jsonl").read_text().splitlines():
    q = json.loads(line)
    gold[q["id"]] = q.get("gold_sql")

data = json.loads(Path("evals/results/latest.json").read_text())
for r in data["results"]:
    if r["status"] == "PASS":
        continue
    print("=" * 60)
    print(r["id"], r["status"], "|", r["question"])
    print("MODEL SQL:", r["model_sql"])
    print("GOLD SQL: ", gold[r["id"]])
    for label, sql in (("MODEL", r["model_sql"]), ("GOLD", gold[r["id"]])):
        try:
            cols, rows = fetch_rows(sql)
            print(label, "->", cols, rows[:10])
        except Exception as e:
            print(label, "-> error:", type(e).__name__)