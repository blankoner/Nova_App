"""
skills.py — skill model + persistent user profile storage.

This module is the single source of truth for:
  - which skills exist (SKILLS)
  - how a game's raw result maps onto skills (games register a mapper)
  - loading / saving a user's persistent profile as JSON on disk

A "user profile" here is broader than the interview profile. It bundles:
  {
    "name":            "alice",
    "interview":       { ...the JSON the AI interview produced... } | null,
    "skills":          { "logical_thinking": {"level": 0-100, "samples": int}, ... },
    "game_history":    [ {"game": "...", "ts": ..., "result": {...}}, ... ]
  }

Storage: one JSON file per user under data/users/<name>.json.
This is deliberately simple — no database, no migrations. Easy to swap for
SQLite later because every read/write goes through load_profile / save_profile.
"""

import os
import json
import time
import re

# ── Where user profiles live ──────────────────────────────────────────────────
# data/users/<name>.json   (created on first save)
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "users")


# ── The skill catalogue ───────────────────────────────────────────────────────
# Each skill has a stable key, a human label, and a short description shown
# on the skills page. Keep keys snake_case — they appear in JSON and templates.
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

# Skill keys in display order
SKILL_ORDER = list(SKILLS.keys())


def blank_skills() -> dict:
    """A fresh skill block — every skill at level 0 with no samples yet."""
    return {key: {"level": 0, "samples": 0} for key in SKILL_ORDER}


def blank_profile(name: str) -> dict:
    """A brand-new user profile with no interview and no skill progress."""
    return {
        "name": _safe_name(name),
        "interview": None,
        "skills": blank_skills(),
        "game_history": [],
    }


# ── Filename safety ───────────────────────────────────────────────────────────
def _safe_name(name: str) -> str:
    """
    Turn an arbitrary display name into a safe filename stem.
    Prevents path traversal (../) and odd characters. Falls back to 'guest'.
    """
    name = (name or "").strip().lower()
    name = re.sub(r"[^a-z0-9_-]", "_", name)
    return name or "guest"


def _profile_path(name: str) -> str:
    return os.path.join(DATA_DIR, _safe_name(name) + ".json")


# ── Load / save ───────────────────────────────────────────────────────────────
def load_profile(name: str) -> dict:
    """
    Load a user's profile from disk. If the file doesn't exist (or is corrupt),
    return a fresh blank profile — callers can always rely on a usable dict.
    Also self-heals: if an older file is missing newer skill keys, they're added.
    """
    path = _profile_path(name)
    if not os.path.exists(path):
        return blank_profile(name)

    try:
        with open(path, "r", encoding="utf-8") as f:
            profile = json.load(f)
    except (json.JSONDecodeError, OSError):
        return blank_profile(name)

    # ── Self-healing for forward compatibility ──
    profile.setdefault("name", _safe_name(name))
    profile.setdefault("interview", None)
    profile.setdefault("game_history", [])
    skills = profile.setdefault("skills", blank_skills())
    # Add any skill keys introduced after this file was written
    for key in SKILL_ORDER:
        skills.setdefault(key, {"level": 0, "samples": 0})

    return profile


def save_profile(profile: dict) -> None:
    """Write a profile back to disk, creating the data directory if needed."""
    os.makedirs(DATA_DIR, exist_ok=True)
    path = _profile_path(profile.get("name", "guest"))
    # Write to a temp file then rename — avoids a half-written file if the
    # process dies mid-write.
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


# ── Applying a game result to a profile ───────────────────────────────────────
# A game result is a dict of { skill_key: score_0_to_100 }. We don't trust the
# client blindly — unknown keys are dropped and values are clamped to 0–100.
#
# Each skill level is a *weighted running average* of all samples ever recorded
# for that skill. New samples are weighted slightly higher than old ones so the
# profile drifts toward recent performance without wild swings.

# How much a brand-new sample pulls the level toward itself, by sample count.
# First sample: level jumps straight to it. Later samples: gentler nudges.
def _blend(old_level: float, old_samples: int, new_score: float) -> float:
    if old_samples <= 0:
        return new_score
    # weight of the new sample shrinks as we gather more history,
    # but never below 0.25 so recent play always matters
    weight = max(0.25, 1.0 / (old_samples + 1))
    return old_level * (1 - weight) + new_score * weight


def apply_game_result(profile: dict, game_id: str, result: dict) -> dict:
    """
    Fold one game's result into the user's skill levels and history.
    Returns the same profile dict (mutated) for convenience.

    `result` is { skill_key: score } — scores outside 0–100 are clamped,
    unknown skill keys are ignored.
    """
    skills = profile.setdefault("skills", blank_skills())
    cleaned = {}

    for key, raw in (result or {}).items():
        if key not in SKILLS:
            continue  # ignore anything not in our catalogue
        try:
            score = float(raw)
        except (TypeError, ValueError):
            continue
        score = max(0.0, min(100.0, score))
        cleaned[key] = score

        entry = skills.setdefault(key, {"level": 0, "samples": 0})
        entry["level"] = round(_blend(entry["level"], entry["samples"], score), 1)
        entry["samples"] = entry["samples"] + 1

    # Record history (even if no skills matched — useful for debugging)
    profile.setdefault("game_history", []).append({
        "game": game_id,
        "ts": int(time.time()),
        "result": cleaned,
    })

    return profile


# ── Helper for templates / matcher ────────────────────────────────────────────
def skills_for_display(profile: dict) -> list:
    """
    Return a list of dicts ready for the skills page, in display order:
      [ {key, label, desc, level, samples}, ... ]
    """
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
