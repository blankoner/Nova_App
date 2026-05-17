"""
seed_stub_db.py — populate jobs.db with sample job offers for local development.

Used while the Kaggle CSV is not imported. Creates the same schema matcher.py
expects (offers + offers_fts FTS5 virtual table) and inserts hand-crafted rows
covering a range of fields and levels, so the matching scores show a clear
gradient on the results page.

Usage:
    py -3.13 seed_stub_db.py
"""

import sqlite3

DB_PATH = "jobs.db"


# (title, company, location, job_type, level, skills_raw, url)
OFFERS = [
    # ── Design / creative — strong match for "design", "art", "creative" ──
    ("Junior UX Designer", "PixelStudio", "Remote", "Remote", "entry",
     "ux design figma prototyping creative user research wireframes art",
     "https://example.com/job/1"),
    ("Graphic Design Intern", "BrightInk Agency", "Lisbon, PT", "Onsite", "internship",
     "graphic design adobe illustrator photoshop creative art branding",
     "https://example.com/job/2"),
    ("Product Designer", "Northwind Labs", "Amsterdam, NL", "Hybrid", "mid",
     "product design ux ui figma sketch prototyping creative",
     "https://example.com/job/3"),
    ("Multimedia Artist", "Aurora Media", "Berlin, DE", "Hybrid", "entry",
     "art illustration animation creative media content design",
     "https://example.com/job/4"),
    ("Junior Motion Designer", "Loopframe", "Remote", "Remote", "entry",
     "motion design after effects animation creative art video",
     "https://example.com/job/5"),

    # ── Code / tech — strong match for "coding", "technology" ──
    ("Frontend Developer Intern", "Bitsmith", "Warsaw, PL", "Hybrid", "internship",
     "html css javascript react frontend coding web design technology",
     "https://example.com/job/6"),
    ("Junior Software Engineer", "Cobalt Systems", "Krakow, PL", "Onsite", "entry",
     "python javascript coding software engineering technology git",
     "https://example.com/job/7"),
    ("Web Developer Apprentice", "Nimbus Web", "Remote", "Remote", "internship",
     "html css javascript coding web design frontend technology",
     "https://example.com/job/8"),
    ("Mobile App Developer", "TapForge", "Lisbon, PT", "Hybrid", "mid",
     "android ios coding mobile development technology kotlin swift",
     "https://example.com/job/9"),
    ("Backend Engineer", "Stackhaven", "Remote", "Remote", "mid",
     "python sql backend coding api engineering technology",
     "https://example.com/job/10"),

    # ── Creative tech (design + coding hybrid) — should score very high ──
    ("Creative Technologist", "Studio Echo", "Berlin, DE", "Hybrid", "entry",
     "creative coding design technology art interactive installations javascript",
     "https://example.com/job/11"),
    ("Junior Game Developer", "Pixelloom", "Remote", "Remote", "entry",
     "game development unity c# coding design creative art technology",
     "https://example.com/job/12"),
    ("Web Designer & Coder", "Atelier Mosaic", "Porto, PT", "Onsite", "entry",
     "web design html css javascript creative coding art",
     "https://example.com/job/13"),

    # ── Music / audio — for "music" interest ──
    ("Audio Engineer Intern", "SoundHaus", "London, UK", "Onsite", "internship",
     "audio engineering music production sound recording creative",
     "https://example.com/job/14"),
    ("Junior Music Producer", "Vinyl Loop Records", "Remote", "Remote", "entry",
     "music production audio creative sound engineering",
     "https://example.com/job/15"),
    ("Sound Designer", "Echo Chamber Studio", "Berlin, DE", "Hybrid", "mid",
     "sound design audio music creative engineering",
     "https://example.com/job/16"),

    # ── Math / data — for "math" subject ──
    ("Data Analyst Intern", "Quantra Insight", "Lisbon, PT", "Hybrid", "internship",
     "data analyst math statistics sql excel research",
     "https://example.com/job/17"),
    ("Junior Data Scientist", "Helix Data", "Remote", "Remote", "entry",
     "python data science math statistics machine learning analyst",
     "https://example.com/job/18"),
    ("Quantitative Analyst", "Bridgemark Capital", "London, UK", "Onsite", "mid",
     "math statistics finance analyst quantitative research",
     "https://example.com/job/19"),

    # ── Hands-on / engineering — for work_type="hands-on" ──
    ("Lab Technician", "Meridian BioLabs", "Porto, PT", "Onsite", "entry",
     "lab technician science engineering hands-on research",
     "https://example.com/job/20"),
    ("Junior Mechanical Engineer", "Forgeworks", "Lyon, FR", "Onsite", "entry",
     "mechanical engineering hands-on construction manufacturing math",
     "https://example.com/job/21"),
    ("Field Service Technician", "Northgate Industrial", "Rotterdam, NL", "Onsite", "entry",
     "field engineering technician hands-on repair manufacturing",
     "https://example.com/job/22"),
    ("Workshop Assistant", "Brassroot Makerspace", "Berlin, DE", "Onsite", "entry",
     "hands-on workshop craft making engineering assembly",
     "https://example.com/job/23"),

    # ── Conceptual / strategy / business — distractors ──
    ("Marketing Coordinator", "Halcyon Media", "Lisbon, PT", "Hybrid", "entry",
     "marketing content strategy creative media communication",
     "https://example.com/job/24"),
    ("Junior Business Analyst", "Crestwood Consulting", "London, UK", "Hybrid", "entry",
     "business analyst strategy research consulting planning",
     "https://example.com/job/25"),
    ("Project Coordinator", "Northpath Group", "Warsaw, PL", "Onsite", "entry",
     "project planning coordination strategy management",
     "https://example.com/job/26"),

    # ── Stability / public sector ──
    ("Administrative Assistant", "City of Porto", "Porto, PT", "Onsite", "entry",
     "administration public government office support",
     "https://example.com/job/27"),
    ("Insurance Claims Trainee", "Sentinel Mutual", "Madrid, ES", "Onsite", "entry",
     "insurance administration claims accounting stability",
     "https://example.com/job/28"),

    # ── Sales / finance — for "money" success vision ──
    ("Sales Development Rep", "Brightline SaaS", "Remote", "Remote", "entry",
     "sales business development outreach communication",
     "https://example.com/job/29"),
    ("Junior Finance Associate", "Pinecrest Bank", "Frankfurt, DE", "Onsite", "entry",
     "finance banking accounting math analyst investment",
     "https://example.com/job/30"),

    # ── Education / impact — for "impact" success vision ──
    ("Tutor — STEM Subjects", "BrightFutures Education", "Remote", "Remote", "entry",
     "education tutoring teaching math science impact",
     "https://example.com/job/31"),
    ("NGO Program Assistant", "GreenSprout Foundation", "Lisbon, PT", "Hybrid", "entry",
     "nonprofit ngo social impact education sustainability",
     "https://example.com/job/32"),

    # ── Senior roles (probably filtered out for high_school students) ──
    ("Senior UX Designer", "Northwind Labs", "Amsterdam, NL", "Hybrid", "senior",
     "ux design lead figma strategy creative team management",
     "https://example.com/job/33"),
    ("Engineering Director", "Forgeworks", "Lyon, FR", "Onsite", "senior",
     "engineering director management strategy planning leadership",
     "https://example.com/job/34"),

    # ── "any" level — should always surface ──
    ("Creative Generalist", "Open Studio Collective", "Remote", "Remote", "any",
     "creative design coding art music multimedia freelance",
     "https://example.com/job/35"),
]


SCHEMA = [
    "DROP TABLE IF EXISTS offers_fts",
    "DROP TABLE IF EXISTS offers",
    """
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
    """,
    """
    CREATE VIRTUAL TABLE offers_fts USING fts5(
        title,
        skills_raw,
        content='offers',
        content_rowid='id'
    )
    """,
]


def main():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    for stmt in SCHEMA:
        cur.execute(stmt)

    cur.executemany(
        "INSERT INTO offers (title, company, location, job_type, level, skills_raw, url) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        OFFERS,
    )

    # Populate the FTS index from the base table.
    cur.execute(
        "INSERT INTO offers_fts (rowid, title, skills_raw) "
        "SELECT id, title, skills_raw FROM offers"
    )

    con.commit()
    print(f"Seeded {DB_PATH} with {len(OFFERS)} offers.")
    con.close()


if __name__ == "__main__":
    main()
