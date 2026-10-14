-- Create the database first:  CREATE DATABASE plus_demo; USE plus_demo;
-- All data in this repo is synthetic. No real funders, people or records.

CREATE TABLE funders (
  id INT PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  country VARCHAR(60),
  type VARCHAR(40),
  focus_area VARCHAR(80),
  website VARCHAR(120)
);

CREATE TABLE opportunities (
  id INT PRIMARY KEY,
  funder_id INT NOT NULL,
  title VARCHAR(160) NOT NULL,
  description TEXT,
  amount_usd INT,
  deadline DATE,
  region VARCHAR(60),
  status VARCHAR(20),
  notes TEXT,
  FOREIGN KEY (funder_id) REFERENCES funders(id)
);

CREATE TABLE applications (
  id INT PRIMARY KEY,
  opportunity_id INT NOT NULL,
  owner VARCHAR(80),          -- never exposed through the MCP server
  stage VARCHAR(30),
  submitted_on DATE,
  FOREIGN KEY (opportunity_id) REFERENCES opportunities(id)
);
