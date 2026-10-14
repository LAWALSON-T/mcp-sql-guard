# mcp-sql-guard

A small MCP server that lets Claude (Claude Desktop or any MCP client) answer questions over a MySQL database without being trusted with it. Every query the model writes passes through a guard, runs as a read-only database user, and is written to an audit log.

All data in this repo is synthetic. The demo schema mirrors a simple funding-opportunity tracker (funders, opportunities, applications).

## Why this exists

Connecting a model to a database with a stock MCP server is easy. Making that safe enough for real teams is the hard part. This project is a worked example of the controls I would want before putting it in front of colleagues:

1. Least privilege at the database, not just in code.
2. A validator that rejects anything except a narrow class of SELECT queries.
3. Treating query results as untrusted, because rows are content and content can carry instructions.
4. An audit trail of every call, allowed or blocked.
5. An evaluation set, so "it seems to work" becomes a number.

## How it works

```
Claude Desktop  ->  MCP server (server.py)  ->  guard.py  ->  MySQL (read-only user)
                         |                         |
                         +--> audit.jsonl <--------+
```

- guard.py parses the SQL with sqlglot and allows exactly one plain SELECT over an allowlist of tables and columns. It rejects SELECT *, writes, DDL, UNION, CTEs, locking reads, SELECT INTO, schema-qualified tables, and functions such as SLEEP, BENCHMARK and LOAD_FILE. It adds or clamps a LIMIT.
- core.py runs the validated query with a statement timeout, wraps every returned string in `<untrusted_data>` tags, and adds a warning when a value looks like an instruction.
- sql/create_readonly_user.sql grants SELECT on specific columns only. The applications.owner column is never granted and is also absent from the guard allowlist.
- audit.py appends one JSON line per call with the SQL, the decision and the reason.

## Threat model

| Risk | Control | Residual risk |
|---|---|---|
| Model writes or drops data | Guard rejects non-SELECT; DB user has SELECT only | A bug in the guard is still stopped by DB privileges |
| Model reads a sensitive column | Column allowlist plus column-level grants | Columns inside the allowlist are readable by design |
| Expensive or hanging query | LIMIT clamp, MAX_EXECUTION_TIME, MAX_QUERIES_PER_HOUR | A burst of valid but heavy queries is still possible |
| Prompt injection through row content | Result wrapping, tool description, warnings, least privilege | Wrapping and regex warnings are heuristics. The real protection is that an injected instruction has very little it can do |
| Silent misuse | Audit log | The log is local and unsigned |

## Setup

1. Create the database and load the synthetic data:
   ```
   CREATE DATABASE plus_demo; USE plus_demo;
   SOURCE sql/schema.sql;
   SOURCE sql/seed.sql;
   SOURCE sql/create_readonly_user.sql;
   ```
   Change the placeholder password in create_readonly_user.sql first.
2. Install dependencies in a virtual environment: `pip install -r requirements.txt`
3. Add the server to Claude Desktop using claude_desktop_config.example.json (fill in the absolute paths), then restart Claude Desktop.
4. Ask something like "How many opportunities are open, and what is their total value?" and check audit.jsonl.

Run the guard tests with `pytest` (no database needed).

## Evaluation

Accuracy: `python -m evals.run_evals` asks the model to write SQL for each question in evals/questions.jsonl, runs it through the guard, and compares its result with a hand-written gold query. Questions marked must_block check that unsafe requests are refused or blocked.

Injection: `python -m evals.injection_test` gives the model the real tool and a question about a row whose notes field tells it to ignore its instructions. It passes only if the model does not obey and never tries to read the owner column.

### Results

Fill this in from your own run. Do not publish numbers you have not produced.

| Check | Result |
|---|---|
| Guard unit tests | |
| Accuracy eval (answerable questions) | |
| Must-block questions | |
| Injection test | |
| Model and date | |

### Failures worth noting

Describe two or three failures from your own runs: what the model got wrong, how it was caught, and what you changed.

## Cost

Estimate by recording input and output tokens from the API responses over a full eval run, then multiplying by the current price for the model you used. Interactive use through Claude Desktop is billed through your plan rather than per token.

## Limitations

- The guard is deliberately conservative. Some valid queries (UNION, CTEs, derived tables) are blocked.
- Column checks use a union of the columns of the tables in the query, so a column that exists in a different table than the one the model meant will fail at the database instead of at the guard.
- Wrapping every string in untrusted tags costs tokens and does not make injection impossible.
- Eval comparison is order-insensitive, which is wrong for questions where order matters.
- The eval set is small. Treat the accuracy figure as a smoke test, not a benchmark.

## Build notes

[Edit this section before publishing. Say plainly which parts you wrote, which parts were AI-assisted, what you changed or fixed, and what you tested on your own machine.]

## Possible next steps

- Per-user credentials and per-user audit trails.
- Signed or append-only audit storage.
- Document extraction and retrieval over the notes and descriptions.
- Regression evals that run in CI against a disposable database.
