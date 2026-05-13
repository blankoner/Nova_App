"""
matcher.py — matches a user profile JSON to the top-N job offers from SQLite.

Each offer starts at 0 points. Points are added for:
  - Profile interests matching skills_raw keywords        (+2 per match)
  - Profile field_idea matching title/skills keywords     (+3 per match)
  - Current field_or_role matching title/skills keywords  (+4 per match if "stay"/open,
                                                           +1 if user wants to "change")
  - Profile favorite_subjects matching skills/title       (+1 per match)
  - proud_creation keywords matching skills               (+1 per match)
  - work_type preference matching job characteristics     (+2 if match)
  - success_vision matching job type/level hints          (+1 if match)

Final score is normalised to 0–100 %.
"""

import sqlite3
import re
from typing import Any


DB_PATH = "jobs.db"

# ── Keyword maps ──────────────────────────────────────────────────────────────

# success_vision primary → keywords to look for in title/skills
SUCCESS_KEYWORDS = {
    "money":      ["finance", "banking", "investment", "sales", "trading"],
    "impact":     ["nonprofit", "social", "education", "health", "sustainability", "ngo"],
    "creativity": ["design", "art", "creative", "marketing", "ux", "media", "content"],
    "stability":  ["government", "public", "administration", "insurance", "accounting"],
    "freedom":    ["remote", "freelance", "startup", "entrepreneur", "consulting"],
    "custom":     [],
}

# work_type → keywords hinting at that style in the title/skills
WORKTYPE_KEYWORDS = {
    "hands-on":    ["engineering", "technician", "mechanic", "lab", "construction",
                    "manufacturing", "repair", "field", "assembly", "craft"],
    "conceptual":  ["analyst", "strategy", "research", "consulting", "planning",
                    "advisory", "policy", "management", "director"],
    "mixed":       [],
}

# job_level → normalised level tag in our DB
LEVEL_FOR_SITUATION = {
    "high_school":  ["entry", "internship", "any"],
    "vocational":   ["entry", "internship", "any"],
    "bachelor":     ["entry", "mid", "any"],
    "master":       ["mid", "senior", "any"],
    "part_time":    ["mid", "senior", "any"],
    "full_time":    ["mid", "senior", "any"],
    None:           ["entry", "any"],
}


def _tokens(text: str) -> list[str]:
    """Lowercase word tokens from any string."""
    return re.findall(r"[a-z]+", text.lower())


def _kw_hits(keywords: list[str], haystack: str) -> int:
    """Count how many keywords appear in haystack."""
    return sum(1 for kw in keywords if kw in haystack)


def score_offer(offer: dict, profile: dict) -> int:
    """Return a raw match score for one offer against the user profile."""
    score = 0
    haystack = (offer["title"] + " " + (offer["skills_raw"] or "")).lower()

    # 1. Interests → skills match (+2 each)
    for interest in profile.get("interests", []):
        score += _kw_hits(_tokens(interest), haystack) * 2

    # 2. Field idea → title/skills match (+3 each keyword)
    field_idea = profile.get("field_idea", {})
    if field_idea.get("clarity") in ("yes", "vague") and field_idea.get("field"):
        for tok in _tokens(field_idea["field"]):
            if len(tok) > 3 and tok in haystack:
                score += 3

    # 2b. Current field of study or job role → title/skills match
    # Strong signal: this is what the user already does/studies.
    # If they want to CHANGE jobs, weight it down so we don't recommend the same field.
    situation = profile.get("situation", {})
    field_or_role = situation.get("field_or_role")
    if field_or_role:
        weight = 1 if profile.get("job_change") == "change" else 4
        for tok in _tokens(field_or_role):
            if len(tok) > 3 and tok in haystack:
                score += weight

    # 3. Favorite subjects → skills (+1 each)
    for subj in profile.get("favorite_subjects", []):
        score += _kw_hits(_tokens(subj), haystack)

    # 4. Proud creation description → skills (+1 each)
    creation = profile.get("proud_creation", {})
    if creation.get("has_created") and creation.get("description"):
        for tok in _tokens(creation["description"]):
            if len(tok) > 4 and tok in haystack:
                score += 1

    # 5. Work type preference (+2 if matching keywords found)
    work_type = profile.get("work_type", "mixed")
    if work_type in WORKTYPE_KEYWORDS:
        if _kw_hits(WORKTYPE_KEYWORDS[work_type], haystack):
            score += 2

    # 6. Success vision (+1 per matching keyword)
    vision = profile.get("success_vision", {})
    primary = vision.get("primary", "")
    if primary in SUCCESS_KEYWORDS:
        score += _kw_hits(SUCCESS_KEYWORDS[primary], haystack)

    return score


def find_top_offers(profile: dict, top_n: int = 5) -> list[dict]:
    """
    Query SQLite, score all candidates, return top_n as list of dicts.
    Uses FTS pre-filter to limit candidates to ~500 rows before Python scoring.
    """
    # Build FTS query from profile keywords
    fts_terms = []
    for interest in profile.get("interests", []):
        fts_terms.extend(_tokens(interest))
    field = profile.get("field_idea", {}).get("field") or ""
    fts_terms.extend(t for t in _tokens(field) if len(t) > 3)
    for subj in profile.get("favorite_subjects", []):
        fts_terms.extend(_tokens(subj))

    # Current field/role — include in pre-filter unless the user wants to change.
    # If they want to change, we still allow scoring against it (with low weight),
    # but we don't bias the candidate pool toward their current field.
    situation = profile.get("situation", {})
    field_or_role = situation.get("field_or_role") or ""
    if field_or_role and profile.get("job_change") != "change":
        fts_terms.extend(t for t in _tokens(field_or_role) if len(t) > 3)

    # Allowed levels for this user
    detail = situation.get("detail")
    allowed_levels = LEVEL_FOR_SITUATION.get(detail, ["entry", "any"])
    level_placeholders = ",".join("?" * len(allowed_levels))

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    if fts_terms:
        # Use FTS to pre-filter up to 500 candidates matching any keyword
        fts_query = " OR ".join(set(fts_terms))
        sql = f"""
            SELECT o.id, o.title, o.company, o.location, o.job_type,
                   o.level, o.skills_raw, o.url
            FROM offers o
            JOIN offers_fts f ON o.id = f.rowid
            WHERE offers_fts MATCH ?
              AND o.level IN ({level_placeholders})
            LIMIT 500
        """
        rows = con.execute(sql, [fts_query] + allowed_levels).fetchall()
    else:
        # No keywords → just filter by level
        sql = f"""
            SELECT id, title, company, location, job_type, level, skills_raw, url
            FROM offers
            WHERE level IN ({level_placeholders})
            LIMIT 500
        """
        rows = con.execute(sql, allowed_levels).fetchall()

    con.close()

    if not rows:
        # Fallback: no level filter
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT id, title, company, location, job_type, level, skills_raw, url FROM offers LIMIT 200"
        ).fetchall()
        con.close()

    # Score each candidate
    scored = []
    for row in rows:
        offer = dict(row)
        offer["score"] = score_offer(offer, profile)
        scored.append(offer)

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:top_n]

    # Normalise score to 0–100 %
    max_score = top[0]["score"] if top and top[0]["score"] > 0 else 1
    for offer in top:
        offer["match_pct"] = min(100, round(offer["score"] / max_score * 100))
        # Clean up fields for template
        offer.pop("skills_raw", None)
        offer.pop("score", None)

    return top
