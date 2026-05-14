import os
import re
import json
from flask import Flask, render_template, request, session, jsonify
from dotenv import load_dotenv
from groq import Groq
from matcher import find_top_offers
import skills as skills_mod

load_dotenv()

app = Flask(__name__)
app.secret_key = "zmien_na_losowy_string"  # np. os.urandom(24)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# ── System prompt ─────────────────────────────────────────────────────────────
INTERVIEW_SYSTEM_PROMPT = """You are a friendly career advisor helping young people figure out
their future path. You conduct a short, warm conversation in English.

Your goal is to collect the following information by asking ONE question at a time:

1. AGE — how old the user is
2. SITUATION — current status:
   - still in school (which level: primary / middle / high school / vocational)
   - at university (bachelor / master)
   - already working (part-time or full-time)
   - none of the above
   If working: also ask whether they want to CHANGE jobs or STAY in the same field.
3. FIELD OR ROLE — depending on situation:
   - If at UNIVERSITY or VOCATIONAL school: ask what field/major they study
     (e.g. "computer science", "nursing", "graphic design")
   - If WORKING: ask what their current job or role is
     (e.g. "marketing assistant", "junior developer", "barista")
   - If in primary / middle / high school or NONE: SKIP this question entirely
     and move on to interests. Do not invent a value.
4. INTERESTS — up to 3 hobbies or main interests
5. FIELD IDEA — does the user have an idea which field they want to work in?
   (yes — ask what field / vague — ask for a hint / no_clue — move on)
6. SUCCESS VISION — what success looks like in 5 years:
   money / impact / creativity / stability / freedom / or their own answer
7. WORK STYLE — prefer working alone, with others, or mixed
8. PROUD CREATION — have they ever built or created something they're proud of?
   If yes, briefly what was it?
9. FAVORITE SUBJECTS — up to 2 favorite school subjects
10. WORK TYPE — prefer hands-on (doing, building) or conceptual (thinking, planning) work,
    or mixed

Rules:
- Ask ONE question at a time, keep it short and conversational
- Be encouraging and friendly — this person may be unsure about their future
- Once you have ALL required information, write a brief warm closing sentence,
  then on a NEW LINE output ONLY the following JSON (no markdown, no backticks,
  no extra text before or after the JSON on that line):
  {"age": 20, "situation": {"status": "university", "detail": "bachelor", "field_or_role": "computer science"}, "job_change": null, "interests": ["music", "coding"], "field_idea": {"clarity": "vague", "field": "something creative"}, "success_vision": {"primary": "creativity", "secondary": "freedom", "custom": null}, "work_style": "mixed", "proud_creation": {"has_created": true, "description": "built a small website"}, "favorite_subjects": ["math", "art"], "work_type": "hands-on"}

Allowed values:
  situation.status        : "student" | "university" | "working" | "none"
  situation.detail        : "primary" | "middle" | "high_school" | "vocational" | "bachelor" | "master" | "part_time" | "full_time" | null
  situation.field_or_role : a short string (e.g. "computer science", "nursing", "barista") for university/vocational/working users; null otherwise
  job_change              : "change" | "stay" | "open" | null
  field_idea.clarity      : "yes" | "vague" | "no_clue"
  success_vision.primary  : "money" | "impact" | "creativity" | "stability" | "freedom" | "custom"
  work_style              : "alone" | "team" | "mixed"
  work_type               : "hands-on" | "conceptual" | "mixed"
"""


def chat_with_groq(messages):
    """Sends messages to Groq and returns the response."""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=600,
        temperature=0.7,
    )
    return response.choices[0].message.content


def parse_profile_from_response(text):
    """
    Extracts the JSON profile from the AI response.
    Looks for a line that starts with '{' and contains the key 'age'.
    Robust against missing markers or formatting variations.
    """
    for line in reversed(text.strip().splitlines()):
        line = line.strip()
        if line.startswith("{") and '"age"' in line:
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                pass

    # Fallback: find any JSON object with 'age' anywhere in the text
    match = re.search(r'\{[^{}]*"age"[^{}]*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def clean_response_for_display(text):
    """Removes the JSON line from the AI response before showing it to the user."""
    lines = text.strip().splitlines()
    cleaned = [l for l in lines if not (l.strip().startswith("{") and '"age"' in l)]
    return "\n".join(cleaned).strip()


# ── Trasy Flask ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    session.clear()
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message", "").strip()
    if not user_message:
        return jsonify({"error": "Pusta wiadomość"}), 400

    # Inicjalizuj historię rozmowy jeśli pusta
    if "history" not in session:
        session["history"] = [
            {"role": "system", "content": INTERVIEW_SYSTEM_PROMPT}
        ]

    # Dodaj wiadomość użytkownika do historii
    history = session["history"]
    history.append({"role": "user", "content": user_message})

    # Zapytaj Groq
    ai_response = chat_with_groq(history)

    # Dodaj odpowiedź AI do historii
    history.append({"role": "assistant", "content": ai_response})
    session["history"] = history
    session.modified = True

    # Sprawdź czy wywiad się zakończył
    profile = parse_profile_from_response(ai_response)
    if profile:
        session["profile"] = profile
        # Persist the interview into the user's on-disk profile, alongside
        # any skills they've already built up through games.
        name = session.get("user_name", "Guest")
        user_profile = skills_mod.load_profile(name)
        user_profile["interview"] = profile
        skills_mod.save_profile(user_profile)

        display_text = clean_response_for_display(ai_response)
        return jsonify({
            "message": display_text or "Thank you! I have everything I need.",
            "done": True,
            "profile": profile
        })

    return jsonify({"message": ai_response, "done": False})


@app.route("/start", methods=["POST"])
def start():
    """Inicjuje rozmowę — AI zadaje pierwsze pytanie."""
    session.clear()
    history = [{"role": "system", "content": INTERVIEW_SYSTEM_PROMPT}]
    history.append({"role": "user", "content": "Hi, I want to find a job or school that suits me."})

    ai_response = chat_with_groq(history)
    history.append({"role": "assistant", "content": str(ai_response)})

    session["history"] = history
    session.modified = True

    return jsonify({"message": ai_response})


@app.route("/dashboard")
def dashboard():
    # The signup / "continue as guest" flow passes the name as ?name=...
    # Persist it in the session so later API calls know whose profile to load.
    name = request.args.get("name", "Guest").strip() or "Guest"
    session["user_name"] = name
    # Make sure a profile file exists from the first visit, so the skills page
    # and game endpoints always have something to read.
    profile = skills_mod.load_profile(name)
    skills_mod.save_profile(profile)
    return render_template("dashboard.html")


@app.route("/wyniki")
def wyniki():
    # Prefer the persistent on-disk profile (interview + skills from games).
    # Fall back to the session-only profile if the user hasn't been saved yet.
    name = session.get("user_name", "Guest")
    user_profile = skills_mod.load_profile(name)
    interview = user_profile.get("interview") or session.get("profile")

    if not interview:
        return render_template("index.html")

    # Build the dict the matcher expects: the interview fields, plus the
    # skill levels folded in under a "skills" key (rule 7 in matcher.py).
    match_input = dict(interview)
    match_input["skills"] = user_profile.get("skills", {})

    offers = find_top_offers(match_input, top_n=5)
    return render_template("wyniki.html", profile=interview, offers=offers)


@app.route("/skills")
def skills_page():
    """The skills overview page — shows each skill and its current level."""
    name = session.get("user_name", "Guest")
    user_profile = skills_mod.load_profile(name)
    skill_list = skills_mod.skills_for_display(user_profile)
    has_interview = user_profile.get("interview") is not None
    games_played = len(user_profile.get("game_history", []))
    return render_template(
        "skills.html",
        skills=skill_list,
        name=name,
        has_interview=has_interview,
        games_played=games_played,
    )


@app.route("/game/strategy")
def game_strategy():
    """The Strategy game — a Risk-style conquest game played in the browser."""
    name = session.get("user_name", "Guest")
    # Ensure a profile exists so the game's result POST has somewhere to land.
    profile = skills_mod.load_profile(name)
    skills_mod.save_profile(profile)
    return render_template("game_strategy.html", name=name)


@app.route("/api/profile")
def api_profile():
    """Return the current user's full persistent profile as JSON."""
    name = session.get("user_name", "Guest")
    return jsonify(skills_mod.load_profile(name))


@app.route("/api/game-result", methods=["POST"])
def api_game_result():
    """
    Receive a game's result, fold it into the user's skills, and persist.

    Expected JSON body:
      { "game": "strategy", "result": { "strategy": 72, "patience": 40, ... } }

    `result` values are scores 0–100 per skill key. Unknown keys are ignored
    and values are clamped server-side (see skills.apply_game_result).
    """
    data = request.get_json(silent=True) or {}
    game_id = str(data.get("game", "")).strip()
    result = data.get("result", {})

    if not game_id:
        return jsonify({"error": "Missing 'game' field"}), 400
    if not isinstance(result, dict):
        return jsonify({"error": "'result' must be an object"}), 400

    name = session.get("user_name", "Guest")
    user_profile = skills_mod.load_profile(name)
    skills_mod.apply_game_result(user_profile, game_id, result)
    skills_mod.save_profile(user_profile)

    # Return the updated skills so the client can show progress immediately.
    return jsonify({
        "ok": True,
        "skills": skills_mod.skills_for_display(user_profile),
    })


if __name__ == "__main__":
    app.run(debug=True)
