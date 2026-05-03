"""
import_data.py — one-time script to import LinkedIn Kaggle CSV into SQLite.

Usage:
    python import_data.py --jobs job_postings.csv --skills job_skills.csv

The script:
  1. Reads job_postings.csv and job_skills.csv
  2. Joins them on job_link
  3. Keeps only useful columns
  4. Writes to jobs.db (SQLite)

Run once before starting the Flask app.
"""

import argparse
import sqlite3
import pandas as pd


# ── Column mapping from the Kaggle CSV ───────────────────────────────────────

KEEP_JOBS = [
    "job_link",
    "job_title",
    "company",
    "job_location",
    "job_level",    # e.g. "Entry level", "Mid senior", "Associate", "Director"
    "job_type",     # e.g. "Onsite", "Remote", "Hybrid"
]

# job_level → our work_type / seniority tags
LEVEL_MAP = {
    "entry level":    "entry",
    "associate":      "entry",
    "mid senior":     "mid",
    "director":       "senior",
    "executive":      "senior",
    "internship":     "internship",
    "not applicable": "any",
}


def normalize_level(raw: str) -> str:
    return LEVEL_MAP.get(str(raw).strip().lower(), "any")


def main(jobs_csv: str, skills_csv: str, db_path: str, limit: int):
    print(f"Reading {jobs_csv} ...")
    jobs = pd.read_csv(jobs_csv, usecols=KEEP_JOBS, low_memory=False)
    jobs = jobs.dropna(subset=["job_title", "company", "job_link"])
    jobs = jobs.drop_duplicates(subset="job_link")

    print(f"Reading {skills_csv} ...")
    skills = pd.read_csv(skills_csv, low_memory=False)
    # job_skills.csv columns: job_link, job_skills
    skills_grouped = (
        skills.groupby("job_link")["job_skills"]
        .apply(lambda x: "|".join(x.dropna().astype(str).str.lower()))
        .reset_index()
        .rename(columns={"job_skills": "skills_raw"})
    )

    print("Merging ...")
    df = jobs.merge(skills_grouped, on="job_link", how="left")
    df["skills_raw"] = df["skills_raw"].fillna("")
    df["level_norm"] = df["job_level"].apply(normalize_level)

    if limit:
        df = df.head(limit)

    print(f"Writing {len(df):,} rows to {db_path} ...")
    con = sqlite3.connect(db_path)
    con.execute("DROP TABLE IF EXISTS offers")
    con.execute("""
        CREATE TABLE offers (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            company     TEXT,
            location    TEXT,
            job_type    TEXT,
            level       TEXT,
            skills_raw  TEXT,
            url         TEXT
        )
    """)
    # Create FTS virtual table for fast keyword search
    con.execute("DROP TABLE IF EXISTS offers_fts")
    con.execute("""
        CREATE VIRTUAL TABLE offers_fts USING fts5(
            title, company, skills_raw,
            content='offers', content_rowid='id'
        )
    """)

    rows = [
        (
            row.job_title,
            row.company,
            row.job_location,
            row.job_type,
            row.level_norm,
            row.skills_raw,
            row.job_link,
        )
        for row in df.itertuples()
    ]
    con.executemany(
        "INSERT INTO offers (title, company, location, job_type, level, skills_raw, url) VALUES (?,?,?,?,?,?,?)",
        rows,
    )
    # Populate FTS index
    con.execute("""
        INSERT INTO offers_fts(rowid, title, company, skills_raw)
        SELECT id, title, company, skills_raw FROM offers
    """)
    con.commit()
    con.close()
    print("Done! Database ready: jobs.db")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs",   default="job_postings.csv")
    parser.add_argument("--skills", default="job_skills.csv")
    parser.add_argument("--db",     default="jobs.db")
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Import only first N rows (0 = all). Use 50000 for testing."
    )
    args = parser.parse_args()
    main(args.jobs, args.skills, args.db, args.limit)
