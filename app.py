import os
import re
import json
from flask import Flask, render_template, request, session, jsonify
from dotenv import load_dotenv
from groq import Groq
from matcher import find_top_offers

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
   If working: ask whether they want to CHANGE jobs or STAY in the same field.
3. INTERESTS — up to 3 hobbies or main interests
4. FIELD IDEA — does the user have an idea which field they want to work in?
   (yes — ask what field / vague — ask for a hint / no_clue — move on)
5. SUCCESS VISION — what success looks like in 5 years:
   money / impact / creativity / stability / freedom / or their own answer
6. WORK STYLE — prefer working alone, with others, or mixed
7. PROUD CREATION — have they ever built or created something they're proud of?
   If yes, briefly what was it?
8. FAVORITE SUBJECTS — up to 2 favorite school subjects
9. WORK TYPE — prefer hands-on (doing, building) or conceptual (thinking, planning) work,
   or mixed

Rules:
- Ask ONE question at a time, keep it short and conversational
- Be encouraging and friendly — this person may be unsure about their future
- Once you have ALL 9 pieces of information, write a brief warm closing sentence,
  then on a NEW LINE output ONLY the following JSON (no markdown, no backticks,
  no extra text before or after the JSON on that line):
  {"age": 17, "situation": {"status": "student", "detail": "high_school"}, "job_change": null, "interests": ["music", "coding"], "field_idea": {"clarity": "vague", "field": "something creative"}, "success_vision": {"primary": "creativity", "secondary": "freedom", "custom": null}, "work_style": "mixed", "proud_creation": {"has_created": true, "description": "built a small website"}, "favorite_subjects": ["math", "art"], "work_type": "hands-on"}

Allowed values:
  situation.status  : "student" | "university" | "working" | "none"
  situation.detail  : "primary" | "middle" | "high_school" | "vocational" | "bachelor" | "master" | "part_time" | "full_time" | null
  job_change        : "change" | "stay" | "open" | null
  field_idea.clarity: "yes" | "vague" | "no_clue"
  success_vision.primary: "money" | "impact" | "creativity" | "stability" | "freedom" | "custom"
  work_style        : "alone" | "team" | "mixed"
  work_type         : "hands-on" | "conceptual" | "mixed"
"""


def chat_with_groq(messages):
    """Sends messages to Groq and returns the response (or a scripted mock)."""
    if MOCK_MODE:
        return mock_chat_response(messages)
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
    return render_template("dashboard.html")


@app.route("/wyniki")
def wyniki():
    profile = session.get("profile")
    if not profile:
        return render_template("index.html")
    offers = find_top_offers(profile, top_n=5)
    return render_template("wyniki.html", profile=profile, offers=offers)


if __name__ == "__main__":
    app.run(debug=True)
