import os
import re
import json
from collections import Counter
from flask import Flask, render_template, request, session, jsonify
from dotenv import load_dotenv
from groq import Groq
from groq import AuthenticationError as GroqAuthError, RateLimitError as GroqRateLimitError
from matcher import find_top_offers
import skills as skills_mod
import social_scenes

load_dotenv()

app = Flask(__name__)
app.secret_key = "zmien_na_losowy_string"  # np. os.urandom(24)

# When GROQ_API_KEY is not set we run a scripted mock conversation so the
# frontend flow can be exercised without hitting the real LLM.
MOCK_MODE = not os.environ.get("GROQ_API_KEY")

if MOCK_MODE:
    print("[MOCK MODE] GROQ_API_KEY not set — using scripted mock responses.")
    client = None
else:
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


def _fallback_to_mock(reason: str):
    global MOCK_MODE, client
    MOCK_MODE = True
    client = None
    print(f"[MOCK MODE] {reason} — falling back to scripted responses.")


MOCK_QUESTIONS = [
    "Hey there! I'm so glad you're here. Let's get to know each other — first things first, how old are you?",
    "Nice to meet you! What's your current situation — are you still in school, at university, working, or none of those?",
    "Got it. Now tell me — what are some of your hobbies or main interests? You can share up to 3.",
    "Cool. Do you already have an idea about which field you'd like to work in? It's totally fine if you're not sure yet!",
    "Let's picture 5 years from now. What does success look like to you — money, impact, creativity, stability, freedom, or something else?",
    "Do you usually prefer working alone, with others, or a mix of both?",
    "Have you ever built or created something you're proud of? If yes, what was it briefly?",
    "What are your favorite school subjects? (Up to 2)",
    "Last one! Do you prefer hands-on work like building and doing, or more conceptual work like thinking and planning — or a mix?",
]

MOCK_PROFILE = {
    "age": 17,
    "situation": {"status": "student", "detail": "high_school"},
    "job_change": None,
    "interests": ["music", "coding", "design"],
    "field_idea": {"clarity": "vague", "field": "something creative with technology"},
    "success_vision": {"primary": "creativity", "secondary": "freedom", "custom": None},
    "work_style": "mixed",
    "proud_creation": {"has_created": True, "description": "built a small personal website"},
    "favorite_subjects": ["math", "art"],
    "work_type": "hands-on",
}


def mock_chat_response(messages):
    """Return the next scripted question, or the final wrap-up + profile JSON."""
    user_count = sum(1 for m in messages if m.get("role") == "user")
    if 1 <= user_count <= len(MOCK_QUESTIONS):
        return MOCK_QUESTIONS[user_count - 1]
    closing = "Thanks for sharing all of that — you've given me a great picture of who you are."
    return f"{closing}\n{json.dumps(MOCK_PROFILE)}"

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


# ── Advisor prompt (used AFTER the interview is complete) ──────────────────────
# Once we have the user's profile, the chat switches into a free-form Q&A mode.
# The user can ask about careers, specific roles, what their matches mean, how to
# build skills, study paths, etc. The AI is no longer collecting data and must
# NOT emit any JSON — that phase is over.
#
# The {profile_summary} placeholder is filled in per-request with a readable
# summary of what we learned in the interview, so answers stay personal.
ADVISOR_SYSTEM_PROMPT = """You are a warm, encouraging career advisor for a young person who has
just finished a career-discovery interview. You already know their profile —
here is a summary of what they told you:

{profile_summary}

The interview is OVER. Your job now is to answer their follow-up questions and
help them think things through. They might ask about:
- specific jobs, roles, or industries (what the work is like, typical paths in)
- what their job matches mean or why something was suggested
- study options, courses, or whether university is right for them
- how to build the skills a career needs
- their own doubts and uncertainties about the future

Rules:
- Stay focused on careers, study, work, and skills — that's what this tool is for.
  If they ask about something clearly unrelated, gently steer back, e.g.
  "That's a bit outside what I can help with here — but speaking of your future…"
- Topics around their career are fair game even if broad (e.g. "I don't know if
  I should go to university" is absolutely something to help with).
- Be concrete and honest. If something is hard or uncertain, say so kindly.
  Don't over-promise or give generic platitudes.
- Keep answers conversational and reasonably short — a few sentences to a short
  paragraph. They can always ask for more.
- Use what you know about them. Reference their interests, situation, or goals
  when it makes the answer more useful.
- NEVER output JSON or any structured data block. The interview is finished.
- You are not a substitute for a real careers counsellor for major decisions —
  if something needs professional guidance, you can say so.
"""


def build_profile_summary(profile: dict) -> str:
    """
    Turn the interview profile dict into a short human-readable summary for the
    advisor prompt. Defensive against missing keys — the interview JSON can vary.
    """
    if not profile:
        return "(No interview details available.)"

    parts = []
    age = profile.get("age")
    if age:
        parts.append(f"- Age: {age}")

    situation = profile.get("situation", {}) or {}
    status = situation.get("status")
    detail = situation.get("detail")
    field_or_role = situation.get("field_or_role")
    if status:
        line = f"- Situation: {status}"
        if detail:
            line += f" ({detail})"
        if field_or_role:
            line += f", field/role: {field_or_role}"
        parts.append(line)

    job_change = profile.get("job_change")
    if job_change:
        parts.append(f"- Regarding their current job: wants to {job_change}")

    interests = profile.get("interests") or []
    if interests:
        parts.append(f"- Interests: {', '.join(str(i) for i in interests)}")

    field_idea = profile.get("field_idea", {}) or {}
    if field_idea.get("field"):
        clarity = field_idea.get("clarity", "")
        parts.append(f"- Field idea ({clarity}): {field_idea['field']}")

    vision = profile.get("success_vision", {}) or {}
    if vision.get("primary"):
        line = f"- Vision of success: {vision['primary']}"
        if vision.get("custom"):
            line += f" — \"{vision['custom']}\""
        parts.append(line)

    if profile.get("work_style"):
        parts.append(f"- Preferred work style: {profile['work_style']}")
    if profile.get("work_type"):
        parts.append(f"- Preferred work type: {profile['work_type']}")

    subjects = profile.get("favorite_subjects") or []
    if subjects:
        parts.append(f"- Favourite subjects: {', '.join(str(s) for s in subjects)}")

    creation = profile.get("proud_creation", {}) or {}
    if creation.get("has_created") and creation.get("description"):
        parts.append(f"- Proud of creating: {creation['description']}")

    return "\n".join(parts) if parts else "(No interview details available.)"


def chat_with_groq(messages):
    """Sends messages to Groq and returns the response (or a scripted mock)."""
    if MOCK_MODE:
        return mock_chat_response(messages)
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=600,
            temperature=0.7,
        )
        return response.choices[0].message.content
    except GroqAuthError:
        _fallback_to_mock("Groq API returned 403 — invalid or expired API key")
        return mock_chat_response(messages)
    except GroqRateLimitError:
        _fallback_to_mock("Groq rate limit reached")
        return mock_chat_response(messages)
    except Exception as exc:
        _fallback_to_mock(f"Groq API error: {exc}")
        return mock_chat_response(messages)


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

    # The whole conversation now lives in the user's profile (SQLite), not in
    # the Flask session cookie — so it survives page reloads and never risks
    # overflowing the ~4 KB cookie limit.
    name = session.get("user_name", "Guest")
    user_profile = skills_mod.load_profile(name)
    chat_state = user_profile["chat"]

    # ── ADVISOR MODE ──────────────────────────────────────────────────────────
    # If the interview is already finished, we're in free-form Q&A mode. The
    # user can keep asking about careers, their matches, study paths, etc.
    if user_profile.get("interview") is not None:
        advisor_history = chat_state.get("advisor_history") or []
        if not advisor_history:
            # First advisor message — build the history with the advisor prompt,
            # seeded with a fresh summary of the user's profile.
            summary = build_profile_summary(user_profile.get("interview"))
            advisor_history = [{
                "role": "system",
                "content": ADVISOR_SYSTEM_PROMPT.format(profile_summary=summary),
            }]

        advisor_history.append({"role": "user", "content": user_message})
        ai_response = chat_with_groq(advisor_history)
        advisor_history.append({"role": "assistant", "content": ai_response})

        chat_state["advisor_history"] = advisor_history
        skills_mod.save_profile(user_profile)

        # `done` stays True so the frontend keeps showing the post-interview
        # state — but the chat box is NOT disabled in this mode.
        return jsonify({"message": ai_response, "done": True, "mode": "advisor"})

    # ── INTERVIEW MODE ────────────────────────────────────────────────────────
    # Initialise the interview history with the system prompt if it's empty.
    history = chat_state.get("interview_history") or []
    if not history:
        history = [{"role": "system", "content": INTERVIEW_SYSTEM_PROMPT}]

    history.append({"role": "user", "content": user_message})
    ai_response = chat_with_groq(history)
    history.append({"role": "assistant", "content": ai_response})
    chat_state["interview_history"] = history

    # Sprawdź czy wywiad się zakończył
    profile = parse_profile_from_response(ai_response)
    if profile:
        # Store the interview result on the profile — this also flips the
        # conversation into advisor mode on the next message.
        user_profile["interview"] = profile
        skills_mod.save_profile(user_profile)

        display_text = clean_response_for_display(ai_response)
        # `done` means "interview finished" — but the chat stays open: the
        # frontend switches into advisor mode rather than disabling input.
        return jsonify({
            "message": display_text or "Thank you! I have everything I need.",
            "done": True,
            "mode": "advisor",
            "profile": profile
        })

    # Interview still going — save progress and return the next question.
    skills_mod.save_profile(user_profile)
    return jsonify({"message": ai_response, "done": False})


@app.route("/chat-history", methods=["GET"])
def chat_history():
    """Returns existing conversation messages for UI restoration — no reset."""
    name = session.get("user_name")
    if not name:
        return jsonify({"messages": [], "done": False})
    user_profile = skills_mod.load_profile(name)
    chat_state = user_profile.get("chat") or {}
    done = user_profile.get("interview") is not None

    messages = []

    # Rebuild visible interview messages:
    # index 0 is the system prompt (skip), index 1 is the fake starter user
    # message "Hi, I want to find a job…" (skip) — everything after is real.
    interview_history = chat_state.get("interview_history") or []
    first_user_seen = False
    for msg in interview_history:
        role = msg.get("role")
        if role == "system":
            continue
        if role == "user" and not first_user_seen:
            first_user_seen = True
            continue  # skip the scripted starter message
        text = msg.get("content", "")
        if role == "assistant":
            # Strip the profile JSON line from the closing interview message.
            cleaned = clean_response_for_display(text)
            if cleaned:
                text = cleaned
        messages.append({"role": "user" if role == "user" else "ai", "text": text})

    # Append advisor messages (after the interview) — skip their system prompt.
    if done:
        for msg in (chat_state.get("advisor_history") or []):
            role = msg.get("role")
            if role == "system":
                continue
            messages.append({"role": "user" if role == "user" else "ai", "text": msg.get("content", "")})

    return jsonify({"messages": messages, "done": done})


@app.route("/start", methods=["POST"])
def start():
    """Inicjuje rozmowę — AI zadaje pierwsze pytanie. Resetuje wywiad."""
    name = session.get("user_name", "Guest")
    user_profile = skills_mod.load_profile(name)

    # Starting a fresh interview wipes the previous conversation and the old
    # interview result, but keeps skills and game history intact.
    user_profile["interview"] = None
    user_profile["chat"] = skills_mod.blank_chat()

    history = [{"role": "system", "content": INTERVIEW_SYSTEM_PROMPT}]
    history.append({"role": "user", "content": "Hi, I want to find a job or school that suits me."})

    ai_response = chat_with_groq(history)
    history.append({"role": "assistant", "content": str(ai_response)})

    user_profile["chat"]["interview_history"] = history
    skills_mod.save_profile(user_profile)

    return jsonify({"message": ai_response})


@app.route("/dashboard")
def dashboard():
    # The signup / "continue as guest" flow passes the name as ?name=...
    # Keep it in the (lightweight) session so later requests know who's logged
    # in — the actual data lives in the database, keyed by this name.
    name = request.args.get("name", "Guest").strip() or "Guest"
    session["user_name"] = name
    # Make sure a profile row exists from the first visit, so the skills page,
    # game endpoints and app-state endpoints always have something to read.
    profile = skills_mod.load_profile(name)
    skills_mod.save_profile(profile)
    return render_template("dashboard.html")


@app.route("/wyniki")
def wyniki():
    # The interview profile and skills both live in the database now.
    name = session.get("user_name", "Guest")
    user_profile = skills_mod.load_profile(name)
    interview = user_profile.get("interview")

    if not interview:
        return render_template("index.html")

    # Build the dict the matcher expects: the interview fields, plus the
    # skill levels folded in under a "skills" key (rule 7 in matcher.py).
    match_input = dict(interview)
    match_input["skills"] = user_profile.get("skills", {})

    offers = find_top_offers(match_input, top_n=5)
    return render_template("wyniki.html", profile=interview, offers=offers, name=name)


@app.route("/skills")
def skills_page():
    """The skills overview page — shows each skill and its current level."""
    name = session.get("user_name", "Guest")
    user_profile = skills_mod.load_profile(name)
    skill_list = skills_mod.skills_for_display(user_profile)
    has_interview = user_profile.get("interview") is not None
    games_played = len(user_profile.get("game_history", []))

    job_offers = []
    top_job_skills = []
    if has_interview:
        match_input = dict(user_profile["interview"])
        match_input["skills"] = user_profile.get("skills", {})
        job_offers = find_top_offers(match_input, top_n=5)
        skill_counts = Counter()
        for offer in job_offers:
            for skill in offer.get("skills_list", []):
                skill_counts[skill] += 1
        top_job_skills = [{"skill": s, "count": c} for s, c in skill_counts.most_common(25)]

    return render_template(
        "skills.html",
        skills=skill_list,
        name=name,
        has_interview=has_interview,
        games_played=games_played,
        job_offers=job_offers,
        top_job_skills=top_job_skills,
    )


@app.route("/game/strategy")
def game_strategy():
    """The Strategy game — a Risk-style conquest game played in the browser."""
    name = session.get("user_name", "Guest")
    # Ensure a profile exists so the game's result POST has somewhere to land.
    profile = skills_mod.load_profile(name)
    skills_mod.save_profile(profile)
    return render_template("game_strategy.html", name=name)


@app.route("/game/social")
def game_social():
    """The Social game — a Life-is-Strange-style social-scenario game."""
    name = session.get("user_name", "Guest")
    # Ensure a profile exists so the game's result POST has somewhere to land.
    profile = skills_mod.load_profile(name)
    skills_mod.save_profile(profile)
    return render_template("game_social.html", name=name)


@app.route("/api/social/scenes")
def api_social_scenes():
    """
    Serve the Social game's scenes to the client — with all scoring data
    (correct emotions, response weights) stripped out.
    """
    return jsonify({"scenes": social_scenes.scenes_for_client()})


@app.route("/api/social/score", methods=["POST"])
def api_social_score():
    """
    Score a completed Social playthrough. The client sends its per-scene
    answers; we compute the skill scores server-side (so weights stay hidden)
    and return them. We do NOT persist here — the client then calls
    /api/game-result with the returned skills, same as the Strategy game.

    Expected JSON body:
      { "answers": [ {"scene": id, "read": emotion_key, "response": resp_id}, ... ] }
    """
    data = request.get_json(silent=True) or {}
    answers = data.get("answers", [])
    if not isinstance(answers, list):
        return jsonify({"error": "'answers' must be a list"}), 400

    scored = social_scenes.score_playthrough(answers)
    return jsonify(scored)


@app.route("/api/profile")
def api_profile():
    """Return the current user's full persistent profile as JSON."""
    name = session.get("user_name", "Guest")
    return jsonify(skills_mod.load_profile(name))


@app.route("/api/apps", methods=["GET"])
def api_apps_get():
    """
    Return the saved state of the dashboard mini-apps (to-do list, journal,
    pomodoro settings) for the current user. The frontend loads this on
    startup so nothing is lost between sessions.
    """
    name = session.get("user_name", "Guest")
    profile = skills_mod.load_profile(name)
    return jsonify(profile.get("apps", skills_mod.blank_apps()))


@app.route("/api/apps", methods=["POST"])
def api_apps_save():
    """
    Save dashboard mini-app state. The body may contain any subset of
    {"todos": [...], "journal": {...}, "pomodoro": {...}} — only the keys
    present are updated, so the to-do list and journal can save independently.
    """
    data = request.get_json(silent=True) or {}
    name = session.get("user_name", "Guest")
    profile = skills_mod.load_profile(name)
    apps = profile.setdefault("apps", skills_mod.blank_apps())

    # Only accept known keys, and only the ones actually sent.
    if "todos" in data and isinstance(data["todos"], list):
        apps["todos"] = data["todos"]
    if "journal" in data and isinstance(data["journal"], dict):
        apps["journal"] = data["journal"]
    if "pomodoro" in data and isinstance(data["pomodoro"], dict):
        apps["pomodoro"] = data["pomodoro"]

    skills_mod.save_profile(profile)
    return jsonify({"ok": True, "apps": apps})


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
