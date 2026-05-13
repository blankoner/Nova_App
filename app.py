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
