-- Least privilege: SELECT on specific columns only. The owner column is never granted.
CREATE USER IF NOT EXISTS 'mcp_ro'@'127.0.0.1' IDENTIFIED BY 'password';

GRANT SELECT (id, name, country, type, focus_area, website)
  ON plus_demo.funders TO 'mcp_ro'@'127.0.0.1';
GRANT SELECT (id, funder_id, title, description, amount_usd, deadline, region, status, notes)
  ON plus_demo.opportunities TO 'mcp_ro'@'127.0.0.1';
GRANT SELECT (id, opportunity_id, stage, submitted_on)
  ON plus_demo.applications TO 'mcp_ro'@'127.0.0.1';

ALTER USER 'mcp_ro'@'127.0.0.1' WITH MAX_QUERIES_PER_HOUR 500 MAX_USER_CONNECTIONS 3;
