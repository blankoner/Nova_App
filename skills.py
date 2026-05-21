"""
skills.py — skill model + persistent user profile storage (SQLite-backed).

This module is the single source of truth for:
  - which skills exist (SKILLS)
  - how a game's raw result maps onto skills (apply_game_result)
  - loading / saving a user's persistent profile

A "user profile" bundles everything we keep for one user:
  {
    "name":         "alice",
    "interview":    { ...the JSON the AI interview produced... } | null,
    "skills":       { "logical_thinking": {"level": 0-100, "samples": int}, ... },
    "game_history": [ {"game": "...", "ts": ..., "result": {...}}, ... ],
    "apps": {
        "todos":   [ {text, done, created, due}, ... ],
        "journal": { "2026-05-09": "note text", ... },
        "pomodoro": { "settings": {focus, short, long, sessions} },
    },
    "chat": {
        "interview_history": [ {role, content}, ... ],   # the Q&A interview
        "advisor_history":   [ {role, content}, ... ],    # post-interview Q&A
    },
  }

── Storage ──
The whole profile is stored as one JSON blob in a SQLite table, keyed by the
user's (sanitised) name. We keep the read/write API — load_profile / save_profile
— identical to the previous file-based version, so the rest of the app does not
need to change. Storing the profile as a single blob (rather than normalised
tables) is a deliberate choice: the profile is always read and written as a
whole, so a blob avoids multi-table joins and migrations while still giving us
durability and atomic writes. It can be normalised later if ever needed.
"""

import os
import json
import time
import re
import sqlite3
import threading

# ── Where the database lives ──────────────────────────────────────────────────
# data/users.db   (created automatically on first use)
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "users.db")

# SQLite + Flask's threaded dev server: each call opens its own short-lived
# connection. A lock serialises writes so two requests can't corrupt each other.
_write_lock = threading.Lock()


# ── The skill catalogue ───────────────────────────────────────────────────────
SKILLS = {
    "logical_thinking": {
        "label": "Logical Thinking",
        "desc": "Breaking problems down and reasoning step by step.",
    },
    "strategy": {
        "label": "Strategic Planning",
        "desc": "Thinking several moves ahead and weighing trade-offs.",
    },
    "decision_making": {
        "label": "Decision Making",
        "desc": "Committing to choices under uncertainty.",
    },
    "patience": {
        "label": "Patience & Composure",
        "desc": "Staying measured instead of rushing headlong.",
    },
    "empathy": {
        "label": "Empathy",
        "desc": "Reading other people's emotions and perspectives.",
    },
    "emotional_support": {
        "label": "Emotional Support",
        "desc": "Responding helpfully when someone is struggling.",
    },
    "assertiveness": {
        "label": "Assertiveness",
        "desc": "Stating your position clearly and standing your ground.",
    },
}

SKILL_ORDER = list(SKILLS.keys())


def blank_skills() -> dict:
    """A fresh skill block — every skill at level 0 with no samples yet."""
    return {key: {"level": 0, "samples": 0} for key in SKILL_ORDER}


def blank_apps() -> dict:
    """Fresh state for the dashboard mini-apps (to-do, journal, pomodoro)."""
    return {
        "todos": [],
        "journal": {},
        "pomodoro": {"settings": {"focus": 25, "short": 5, "long": 15, "sessions": 4}},
    }


def blank_chat() -> dict:
    """Fresh chat state — the interview and advisor conversations."""
    return {
        "interview_history": [],
        "advisor_history": [],
    }


def blank_profile(name: str) -> dict:
    """A brand-new user profile with nothing filled in yet."""
    return {
        "name": _safe_name(name),
        "interview": None,
        "skills": blank_skills(),
        "game_history": [],
        "apps": blank_apps(),
        "chat": blank_chat(),
    }


# ── Name safety ───────────────────────────────────────────────────────────────
def _safe_name(name: str) -> str:
    """
    Normalise an arbitrary display name into a safe storage key.
    Lowercased, only [a-z0-9_-], falls back to 'guest'.
    """
    name = (name or "").strip().lower()
    name = re.sub(r"[^a-z0-9_-]", "_", name)
    return name or "guest"


# ── Database setup ────────────────────────────────────────────────────────────
def _connect() -> sqlite3.Connection:
    """Open a connection to the user database, creating the file/dir if needed."""
    os.makedirs(DATA_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    return con


def _init_db() -> None:
    """Create the profiles table if it doesn't exist. Safe to call repeatedly."""
    con = _connect()
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                name        TEXT PRIMARY KEY,
                data        TEXT NOT NULL,
                updated_at  INTEGER NOT NULL
            )
        """)
        con.commit()
    finally:
        con.close()


# Initialise the schema as soon as the module is imported.
_init_db()


# ── Self-healing ──────────────────────────────────────────────────────────────
def _heal_profile(profile: dict, name: str) -> dict:
    """
    Make sure a loaded profile has every key the current code expects, adding
    missing ones with sensible defaults. This lets old data (saved before a
    feature existed) keep working after an update.
    """
    profile.setdefault("name", _safe_name(name))
    profile.setdefault("interview", None)
    profile.setdefault("game_history", [])

    skills = profile.setdefault("skills", blank_skills())
    for key in SKILL_ORDER:
        skills.setdefault(key, {"level": 0, "samples": 0})

    apps = profile.setdefault("apps", blank_apps())
    apps.setdefault("todos", [])
    apps.setdefault("journal", {})
    pomo = apps.setdefault("pomodoro", {"settings": {}})
    pomo.setdefault("settings", {})
    for k, v in {"focus": 25, "short": 5, "long": 15, "sessions": 4}.items():
        pomo["settings"].setdefault(k, v)

    chat = profile.setdefault("chat", blank_chat())
    chat.setdefault("interview_history", [])
    chat.setdefault("advisor_history", [])

    return profile


# ── Load / save ───────────────────────────────────────────────────────────────
def load_profile(name: str) -> dict:
    """
    Load a user's profile from the database. If there's no row yet (or the
    stored data is somehow corrupt), return a fresh blank profile — callers can
    always rely on getting a complete, usable dict.
    """
    key = _safe_name(name)
    con = _connect()
    try:
        row = con.execute(
            "SELECT data FROM profiles WHERE name = ?", (key,)
        ).fetchone()
    finally:
        con.close()

    if row is None:
        return blank_profile(name)

    try:
        profile = json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return blank_profile(name)

    return _heal_profile(profile, name)


def delete_profile(name: str) -> None:
    """Remove a user's profile row from the database (used to reset guest data)."""
    key = _safe_name(name)
    with _write_lock:
        con = _connect()
        try:
            con.execute("DELETE FROM profiles WHERE name = ?", (key,))
            con.commit()
        finally:
            con.close()


def save_profile(profile: dict) -> None:
    """
    Persist a profile to the database. An UPSERT keyed on the user's name —
    inserts a new row or replaces the existing one. Serialised by a lock so
    concurrent requests can't clobber each other mid-write.
    """
    key = _safe_name(profile.get("name", "guest"))
    profile["name"] = key  # keep the stored name normalised
    blob = json.dumps(profile, ensure_ascii=False)
    now = int(time.time())

    with _write_lock:
        con = _connect()
        try:
            con.execute(
                """
                INSERT INTO profiles (name, data, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    data = excluded.data,
                    updated_at = excluded.updated_at
                """,
                (key, blob, now),
            )
            con.commit()
        finally:
            con.close()


# ── Applying a game result to a profile ───────────────────────────────────────
def _blend(old_level: float, old_samples: int, new_score: float) -> float:
    """Weighted running average — recent samples always keep some weight."""
    if old_samples <= 0:
        return new_score
    weight = max(0.25, 1.0 / (old_samples + 1))
    return old_level * (1 - weight) + new_score * weight


def apply_game_result(profile: dict, game_id: str, result: dict) -> dict:
    """
    Fold one game's result into the user's skill levels and history.
    Returns the same (mutated) profile for convenience.

    `result` is { skill_key: score } — scores outside 0–100 are clamped,
    unknown skill keys are ignored.
    """
    skills = profile.setdefault("skills", blank_skills())
    cleaned = {}

    for key, raw in (result or {}).items():
        if key not in SKILLS:
            continue
        try:
            score = float(raw)
        except (TypeError, ValueError):
            continue
        score = max(0.0, min(100.0, score))
        cleaned[key] = score

        entry = skills.setdefault(key, {"level": 0, "samples": 0})
        entry["level"] = round(_blend(entry["level"], entry["samples"], score), 1)
        entry["samples"] = entry["samples"] + 1

    profile.setdefault("game_history", []).append({
        "game": game_id,
        "ts": int(time.time()),
        "result": cleaned,
    })

    return profile


# ── Helper for templates / matcher ────────────────────────────────────────────
def skills_for_display(profile: dict) -> list:
    """Return a list of dicts ready for the skills page, in display order."""
    skills = profile.get("skills", {})
    out = []
    for key in SKILL_ORDER:
        meta = SKILLS[key]
        entry = skills.get(key, {"level": 0, "samples": 0})
        out.append({
            "key": key,
            "label": meta["label"],
            "desc": meta["desc"],
            "level": entry.get("level", 0),
            "samples": entry.get("samples", 0),
        })
    return out
