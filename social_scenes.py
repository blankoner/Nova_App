"""
social_scenes.py — content and scoring for the Social game.

The Social game (inspired by Life is Strange / Detroit: Become Human) puts the
player through a series of social situations. Each scene has two steps:

  1. READ  — the player is shown the other person's behaviour/posture and picks
             which emotion that person is actually feeling. This measures EMPATHY:
             reading people correctly.

  2. RESPOND — the player picks how to react. There is NO "correct" answer — the
             screenshot brief is explicit about this. Each response option simply
             carries weights for EMOTIONAL_SUPPORT and LOGIC. Different players
             build different profiles.

Why this lives server-side: the response weights and the "correct" emotion must
not be visible to the client, or players would game the system instead of
reacting honestly. The client only ever sees text + option labels.

Scoring produces three skill scores (0–100):
  empathy           ← share of scenes where the player read the emotion right
  emotional_support ← average support weight of the responses they chose
  logical_thinking  ← average logic weight of the responses they chose

── Pronouns ──
Each scene is about ONE specific person, so the text uses "he"/"she" rather than
the generic "they". To keep this maintainable, scene text is written with
placeholders ({they}, {their}, {them}, {theyre}, {theyve}) and each scene
declares a `pronoun` ("he" or "she"). scenes_for_client() substitutes the
placeholders before sending text to the browser — so adding a new scene only
means setting `pronoun`, not hand-writing every "he"/"she".

── Replayability ──
There are more scenes than one playthrough uses. scenes_for_client() returns a
random subset (SCENES_PER_GAME), so repeat plays feel fresh. Scoring still
works because score_playthrough looks scenes up by id in the full SCENES list.
"""

import random

# How many scenes one playthrough presents (a random subset of all SCENES).
SCENES_PER_GAME = 5

# ── The scenes ────────────────────────────────────────────────────────────────
# Each scene:
#   id            stable id
#   pronoun       "he" or "she" — the single person this scene is about
#   situation     what's happening (shown to the player)
#   person        who they're facing
#   posture       observable behaviour — the clue for the READ step
#   emotion_key   the emotion the person is *actually* feeling (the READ answer)
#   emotion_label human label for that emotion (used by the result screen)
#   read_options  list of {key, label} — one key matches emotion_key
#   responses     list of {id, text, support, logic} — support/logic are 0..3
#
# Scene TEXT uses pronoun placeholders, substituted per `pronoun`:
#   {they}  → he / she        {their} → his / her
#   {them}  → him / her       {theyre} → he's / she's
#   {theyve} → he's / she's   (as in "he's been quiet" — "has" form)
# Capitalised forms work too: {They}, {Their}, {Theyre}.
#
# support/logic guide:
#   support 3 = deeply validating / comforting; 0 = dismissive of feelings
#   logic   3 = reasoned, problem-solving, fact-based; 0 = no reasoning at all
# A response can be high on both, low on both, or trade off — that's the point.

SCENES = [
    {
        "id": "grief",
        "pronoun": "she",
        "situation": (
            "A classmate you don't know well is sitting alone after class. "
            "{They} just found out a grandparent passed away. {They} {look} up "
            "when you sit down nearby."
        ),
        "person": "Classmate",
        "posture": (
            "Shoulders curled inward, eyes red and fixed on the desk. {Theyre} "
            "holding {their} phone but not looking at it. When you sit down "
            "{they} {give} a small, automatic nod but {dont} speak."
        ),
        "emotion_key": "grief",
        "emotion_label": "Grief",
        "read_options": [
            {"key": "grief",     "label": "Grief — {theyre} overwhelmed by loss"},
            {"key": "annoyance", "label": "Annoyance — {they} {want} to be left alone"},
            {"key": "boredom",   "label": "Boredom — {theyre} just tired after class"},
            {"key": "anxiety",   "label": "Anxiety — {theyre} worried about schoolwork"},
        ],
        "responses": [
            {"id": "sit_with",
             "text": "\"I'm really sorry. I'm here if you want to talk — or we can just sit.\"",
             "support": 3, "logic": 1},
            {"id": "practical",
             "text": "\"Do you need anything sorted — notes from class, telling a teacher?\"",
             "support": 1, "logic": 3},
            {"id": "distract",
             "text": "\"Want to come grab food? Might help to get out of here.\"",
             "support": 2, "logic": 1},
            {"id": "minimise",
             "text": "\"{They} lived a long life though, right? Try not to dwell on it.\"",
             "support": 0, "logic": 1},
        ],
    },
    {
        "id": "group_conflict",
        "pronoun": "he",
        "situation": (
            "Your group project is due in two days. Two teammates just had a "
            "loud disagreement about who isn't pulling their weight. One of them "
            "turns to you: \"You've seen it. Tell them I'm right.\""
        ),
        "person": "Teammate",
        "posture": (
            "Jaw tight, arms crossed, leaning toward you. {Their} voice is louder "
            "than the room needs. {They} {keep} glancing at the other teammate, "
            "waiting for a reaction."
        ),
        "emotion_key": "frustration",
        "emotion_label": "Frustration",
        "read_options": [
            {"key": "frustration", "label": "Frustration — {they} {feel} unsupported and {want} backup"},
            {"key": "calm",        "label": "Calm — {theyre} just stating facts neutrally"},
            {"key": "amusement",   "label": "Amusement — {theyre} not taking it seriously"},
            {"key": "fear",        "label": "Fear — {theyre} scared of the other person"},
        ],
        "responses": [
            {"id": "mediate",
             "text": "\"I can see you're both stressed. Let's list what's left and split it fairly.\"",
             "support": 2, "logic": 3},
            {"id": "take_side",
             "text": "\"Yeah, you've done more. They need to step up.\"",
             "support": 1, "logic": 1},
            {"id": "validate_first",
             "text": "\"It's frustrating to feel like you're carrying it. Can we talk it through calmly?\"",
             "support": 3, "logic": 2},
            {"id": "deflect",
             "text": "\"I don't want to get in the middle of this.\"",
             "support": 0, "logic": 0},
        ],
    },
    {
        "id": "debate",
        "pronoun": "he",
        "situation": (
            "In class, a friend argues passionately for a position you think is "
            "based on a clear factual mistake. {They} {finish} and look at you: "
            "\"Back me up here.\""
        ),
        "person": "Friend",
        "posture": (
            "Animated, fast hand gestures, a bright confident smile. {Theyre} "
            "energised by the discussion and clearly expect you to agree. {Their} "
            "tone is warm, not aggressive."
        ),
        "emotion_key": "enthusiasm",
        "emotion_label": "Enthusiasm",
        "read_options": [
            {"key": "enthusiasm", "label": "Enthusiasm — {theyre} excited and confident"},
            {"key": "anger",      "label": "Anger — {theyre} spoiling for a fight"},
            {"key": "insecurity", "label": "Insecurity — {theyre} desperate for approval"},
            {"key": "sadness",    "label": "Sadness — something is upsetting {them}"},
        ],
        "responses": [
            {"id": "gentle_correct",
             "text": "\"I love the energy — but I think one fact's off. Can I show you?\"",
             "support": 2, "logic": 3},
            {"id": "agree_to_please",
             "text": "\"Yeah, totally, you're right.\"",
             "support": 1, "logic": 0},
            {"id": "blunt_correct",
             "text": "\"That's just wrong. Here's why.\"",
             "support": 0, "logic": 3},
            {"id": "private_later",
             "text": "\"Let's not do this in front of everyone — I'll catch you after.\"",
             "support": 3, "logic": 2},
        ],
    },
    {
        "id": "withdrawn_friend",
        "pronoun": "she",
        "situation": (
            "A close friend has been quiet and distant for a week. {They} {have} "
            "cancelled plans twice. Today {they} {say} \"I'm fine, really\" — but "
            "{they} said it before you even asked."
        ),
        "person": "Close friend",
        "posture": (
            "A quick, practised smile that doesn't reach {their} eyes. {They} "
            "{answer} before you finish your sentence and immediately change the "
            "subject. {Their} foot is tapping under the table."
        ),
        "emotion_key": "distress",
        "emotion_label": "Hidden distress",
        "read_options": [
            {"key": "distress",    "label": "Hidden distress — {theyre} struggling but masking it"},
            {"key": "contentment", "label": "Contentment — {they} really are fine"},
            {"key": "irritation",  "label": "Irritation — {theyre} annoyed you keep asking"},
            {"key": "excitement",  "label": "Excitement — {they} {have} good news {theyre} hiding"},
        ],
        "responses": [
            {"id": "name_it_gently",
             "text": "\"You don't have to talk, but I've noticed you're not yourself. I'm here.\"",
             "support": 3, "logic": 2},
            {"id": "respect_space",
             "text": "\"Okay — just know the door's open whenever you want.\"",
             "support": 2, "logic": 2},
            {"id": "press_for_facts",
             "text": "\"Fine isn't an answer. What specifically is going on?\"",
             "support": 1, "logic": 2},
            {"id": "take_at_word",
             "text": "\"Cool, glad you're fine!\" — and move on.",
             "support": 0, "logic": 0},
        ],
    },
    {
        "id": "harsh_feedback",
        "pronoun": "he",
        "situation": (
            "A teammate shows you work {theyre} proud of. You can see real "
            "problems with it. {They} {ask}, beaming: \"So — what do you think?\""
        ),
        "person": "Teammate",
        "posture": (
            "Standing a little taller than usual, a hopeful open expression, "
            "watching your face closely. {Theyve} clearly put a lot of "
            "{themselves} into this and are bracing slightly for your reaction."
        ),
        "emotion_key": "pride",
        "emotion_label": "Hopeful pride",
        "read_options": [
            {"key": "pride",        "label": "Hopeful pride — {theyre} invested and want it to land well"},
            {"key": "indifference", "label": "Indifference — {they} {dont} really care what you say"},
            {"key": "dread",        "label": "Dread — {they} already know it's bad"},
            {"key": "suspicion",    "label": "Suspicion — {they} think you'll be unfair"},
        ],
        "responses": [
            {"id": "honest_kind",
             "text": "\"There's a lot of you in this — and I think a couple of parts need work. Want to go through them?\"",
             "support": 3, "logic": 3},
            {"id": "only_praise",
             "text": "\"It's great, really well done!\"",
             "support": 2, "logic": 0},
            {"id": "only_problems",
             "text": "\"Honestly, there are some real issues here.\" — and list them.",
             "support": 0, "logic": 3},
            {"id": "vague_dodge",
             "text": "\"Yeah, it's... interesting. Not bad.\"",
             "support": 1, "logic": 0},
        ],
    },
    {
        "id": "left_out",
        "pronoun": "she",
        "situation": (
            "A friend finds out the rest of your group went out at the weekend "
            "without inviting {them}. {They} {bring} it up with you, trying to keep "
            "it light: \"Looked like fun, anyway.\""
        ),
        "person": "Friend",
        "posture": (
            "{Theyre} smiling, but it fades a beat too fast. {They} {look} at the "
            "floor when {they} {mention} the weekend, and {their} arms are wrapped "
            "loosely around {themselves}."
        ),
        "emotion_key": "hurt",
        "emotion_label": "Feeling left out",
        "read_options": [
            {"key": "hurt",        "label": "Hurt — {theyre} stung at being excluded"},
            {"key": "indifference","label": "Indifference — {they} genuinely don't mind"},
            {"key": "anger",       "label": "Anger — {theyre} furious and want a confrontation"},
            {"key": "relief",      "label": "Relief — {theyre} glad {they} weren't dragged along"},
        ],
        "responses": [
            {"id": "acknowledge",
             "text": "\"That must have stung. For what it's worth, I'd have wanted you there.\"",
             "support": 3, "logic": 1},
            {"id": "explain",
             "text": "\"It was a last-minute thing — honestly no one planned it properly.\"",
             "support": 1, "logic": 3},
            {"id": "fix_forward",
             "text": "\"Let's get something in the calendar this week, just us.\"",
             "support": 2, "logic": 2},
            {"id": "brush_off",
             "text": "\"It wasn't even that fun, don't worry about it.\"",
             "support": 0, "logic": 1},
        ],
    },
    {
        "id": "new_student",
        "pronoun": "he",
        "situation": (
            "A new student joined this week and has spent every break alone. "
            "At lunch {theyre} sitting at the end of a table near you, "
            "pretending to be busy on {their} phone."
        ),
        "person": "New student",
        "posture": (
            "{They} {keep} glancing up at groups of people, then quickly back down. "
            "{Their} food is barely touched. When someone laughs nearby, {they} "
            "half-smile as if {theyre} part of it, then catch {themselves}."
        ),
        "emotion_key": "loneliness",
        "emotion_label": "Loneliness",
        "read_options": [
            {"key": "loneliness", "label": "Loneliness — {they} {want} to be included but can't break in"},
            {"key": "contentment","label": "Contentment — {theyre} happy keeping to {themselves}"},
            {"key": "arrogance",  "label": "Arrogance — {they} think {theyre} above the others"},
            {"key": "focus",      "label": "Focus — {theyre} genuinely just busy"},
        ],
        "responses": [
            {"id": "invite_in",
             "text": "\"Hey, we're sitting over there if you want to join — no pressure.\"",
             "support": 3, "logic": 2},
            {"id": "small_talk",
             "text": "\"How are you finding it here so far?\"",
             "support": 2, "logic": 2},
            {"id": "practical_help",
             "text": "\"Want me to walk you through where everything is?\"",
             "support": 2, "logic": 3},
            {"id": "ignore",
             "text": "Decide {theyre} probably fine and leave {them} to it.",
             "support": 0, "logic": 0},
        ],
    },
    {
        "id": "anxious_presenter",
        "pronoun": "she",
        "situation": (
            "A friend is about to present to the class and {theyve} pulled you "
            "aside in the corridor. \"I think I'm going to mess this up,\" "
            "{they} {say}."
        ),
        "person": "Friend",
        "posture": (
            "{Their} hands won't stay still — gripping notes, then {their} "
            "sleeve, then nothing. {Theyre} breathing shallowly and keep "
            "glancing at the classroom door."
        ),
        "emotion_key": "anxiety",
        "emotion_label": "Performance anxiety",
        "read_options": [
            {"key": "anxiety",     "label": "Performance anxiety — {theyre} scared of failing publicly"},
            {"key": "boredom",     "label": "Boredom — {they} just don't want to do it"},
            {"key": "anger",       "label": "Anger — {theyre} annoyed at being made to present"},
            {"key": "overconfidence","label": "Overconfidence — {theyre} fishing for a compliment"},
        ],
        "responses": [
            {"id": "reassure",
             "text": "\"It's normal to feel this. You know your stuff — I've heard you talk about it.\"",
             "support": 3, "logic": 1},
            {"id": "practical_tip",
             "text": "\"Pick one friendly face and talk to them. Slow down on the first slide.\"",
             "support": 2, "logic": 3},
            {"id": "reframe",
             "text": "\"Even if one bit goes wrong, no one will remember by tomorrow.\"",
             "support": 2, "logic": 2},
            {"id": "dismiss",
             "text": "\"You'll be fine, don't overthink it.\"",
             "support": 0, "logic": 0},
        ],
    },
    {
        "id": "broke_promise",
        "pronoun": "he",
        "situation": (
            "A friend promised to help you with something and forgot completely. "
            "When you mention it, {their} face falls. \"I can't believe I did "
            "that,\" {they} {say} quietly."
        ),
        "person": "Friend",
        "posture": (
            "{They} won't quite meet your eyes. One hand rubs the back of {their} "
            "neck. {Theyre} already half-apologising before you've said how you "
            "feel about it."
        ),
        "emotion_key": "guilt",
        "emotion_label": "Guilt",
        "read_options": [
            {"key": "guilt",        "label": "Guilt — {they} {feel} genuinely bad about letting you down"},
            {"key": "defensiveness","label": "Defensiveness — {theyre} about to make excuses"},
            {"key": "indifference", "label": "Indifference — {they} {dont} really care"},
            {"key": "irritation",   "label": "Irritation — {theyre} annoyed you brought it up"},
        ],
        "responses": [
            {"id": "reassure_repair",
             "text": "\"It happens — I know you didn't mean to. Can we sort it now?\"",
             "support": 3, "logic": 2},
            {"id": "honest_impact",
             "text": "\"It did put me in a tough spot. I'd just like to know you'll remember next time.\"",
             "support": 2, "logic": 3},
            {"id": "let_off",
             "text": "\"Don't worry about it at all, totally fine.\"",
             "support": 1, "logic": 0},
            {"id": "guilt_trip",
             "text": "\"I really needed you and you weren't there.\"",
             "support": 0, "logic": 1},
        ],
    },
    {
        "id": "rivals_success",
        "pronoun": "she",
        "situation": (
            "Someone you don't get along with just got a result you'd hoped for "
            "yourself. {They} {mention} it to you directly — not unkindly — "
            "\"Did you hear? I got it.\""
        ),
        "person": "Classmate",
        "posture": (
            "{Theyre} clearly pleased — a real smile — but {they} watch your "
            "reaction carefully, as if {theyre} not sure whether {theyll} get a "
            "genuine response from you."
        ),
        "emotion_key": "pride",
        "emotion_label": "Genuine pride",
        "read_options": [
            {"key": "pride",      "label": "Genuine pride — {theyre} happy and hoping you'll be decent about it"},
            {"key": "gloating",   "label": "Gloating — {theyre} rubbing it in"},
            {"key": "anxiety",    "label": "Anxiety — {theyre} worried you'll be upset"},
            {"key": "contempt",   "label": "Contempt — {they} think you didn't deserve it"},
        ],
        "responses": [
            {"id": "genuine_congrats",
             "text": "\"That's a real achievement — well done, honestly.\"",
             "support": 3, "logic": 2},
            {"id": "polite_brief",
             "text": "\"Congrats.\" — short, but you mean it.",
             "support": 2, "logic": 1},
            {"id": "ask_how",
             "text": "\"Nice — how did you approach it? I'm curious what worked.\"",
             "support": 2, "logic": 3},
            {"id": "cold",
             "text": "\"Good for you.\" — and turn away.",
             "support": 0, "logic": 0},
        ],
    },
]

# Max raw weight a response can carry on each axis (used for normalising)
_MAX_WEIGHT = 3


# ── Pronoun substitution ──────────────────────────────────────────────────────
def _pronoun_map(pronoun: str) -> dict:
    """
    Build the placeholder → word map for a scene's pronoun.
    `pronoun` is "he" or "she" (anything else falls back to "they" forms).

    As well as pronouns, this maps a few VERB placeholders. With "they" a verb
    stays plural ("they look"); with "he"/"she" it must take the -s form
    ("she looks"). Writing {look}/{have}/{keep} etc. in scene text lets the
    substitution stay grammatically correct for every pronoun.
    """
    is_singular = pronoun in ("he", "she")

    if pronoun == "he":
        forms = {
            "they": "he", "their": "his", "them": "him",
            "theyre": "he's", "theyve": "he's", "theyll": "he'll",
            "themselves": "himself", "dont": "doesn't",
        }
    elif pronoun == "she":
        forms = {
            "they": "she", "their": "her", "them": "her",
            "theyre": "she's", "theyve": "she's", "theyll": "she'll",
            "themselves": "herself", "dont": "doesn't",
        }
    else:
        # Fallback — keep the generic plural forms
        forms = {
            "they": "they", "their": "their", "them": "them",
            "theyre": "they're", "theyve": "they've", "theyll": "they'll",
            "themselves": "themselves", "dont": "don't",
        }

    # Verb placeholders: plural form for "they", -s form for "he"/"she".
    verbs = {
        "look": "looks", "give": "gives", "keep": "keeps", "have": "has",
        "want": "wants", "feel": "feels", "bring": "brings", "finish": "finishes",
        "say": "says", "ask": "asks", "mention": "mentions", "answer": "answers",
        "argue": "argues",
    }
    for base, singular in verbs.items():
        forms[base] = singular if is_singular else base

    # Add capitalised variants for sentence starts: {They} → "He" etc.
    full = {}
    for key, word in forms.items():
        full[key] = word
        full[key.capitalize()] = word[0].upper() + word[1:]
    return full


def _apply_pronouns(text: str, mapping: dict) -> str:
    """Replace every {placeholder} in `text` using `mapping`."""
    for placeholder, word in mapping.items():
        text = text.replace("{" + placeholder + "}", word)
    return text


# ── Public helpers ────────────────────────────────────────────────────────────
def scenes_for_client(count: int = SCENES_PER_GAME) -> list:
    """
    Return a random subset of scenes with all scoring information stripped out
    and pronoun placeholders resolved — safe to send to the browser.

    The client never sees emotion_key or response weights. Scenes are shuffled
    and trimmed to `count` so repeat playthroughs differ; scoring still works
    because score_playthrough looks scenes up by id in the full SCENES list.
    """
    pool = list(SCENES)
    random.shuffle(pool)
    chosen = pool[:max(1, min(count, len(pool)))]

    safe = []
    for scene in chosen:
        pron = _pronoun_map(scene.get("pronoun", "they"))
        safe.append({
            "id": scene["id"],
            "situation": _apply_pronouns(scene["situation"], pron),
            "person": scene["person"],
            "posture": _apply_pronouns(scene["posture"], pron),
            "emotion_label": scene["emotion_label"],  # shown only on result screen
            "read_options": [
                {"key": o["key"], "label": _apply_pronouns(o["label"], pron)}
                for o in scene["read_options"]
            ],
            "responses": [
                {"id": r["id"], "text": _apply_pronouns(r["text"], pron)}
                for r in scene["responses"]
            ],
        })
    return safe


def _scene_by_id(scene_id: str):
    for scene in SCENES:
        if scene["id"] == scene_id:
            return scene
    return None


def score_playthrough(answers: list) -> dict:
    """
    Turn a list of per-scene answers into three skill scores (0–100).

    `answers` is a list of:
      { "scene": scene_id, "read": emotion_key_chosen, "response": response_id }

    Unknown scene ids, missing fields, and bad option ids are skipped defensively
    so a malformed payload can't crash scoring — it just contributes nothing.

    Returns:
      {
        "skills": { "empathy": int, "emotional_support": int, "logical_thinking": int },
        "detail": [ per-scene breakdown for the result screen ],
        "scenes_counted": int
      }
    """
    read_correct = 0
    support_sum = 0.0
    logic_sum = 0.0
    counted = 0
    detail = []

    for ans in answers or []:
        if not isinstance(ans, dict):
            continue
        scene = _scene_by_id(ans.get("scene"))
        if scene is None:
            continue

        # ── READ step → empathy ──
        chosen_emotion = ans.get("read")
        valid_emotion = any(o["key"] == chosen_emotion for o in scene["read_options"])
        got_emotion_right = valid_emotion and chosen_emotion == scene["emotion_key"]

        # ── RESPOND step → support / logic ──
        response = None
        for r in scene["responses"]:
            if r["id"] == ans.get("response"):
                response = r
                break
        if response is None:
            # No valid response → this scene can't be scored at all
            continue

        counted += 1
        if got_emotion_right:
            read_correct += 1
        support_sum += response["support"]
        logic_sum += response["logic"]

        detail.append({
            "scene": scene["id"],
            "read_correct": got_emotion_right,
            "correct_emotion": scene["emotion_label"],
            "response_support": response["support"],
            "response_logic": response["logic"],
        })

    if counted == 0:
        # Nothing scoreable — return zeros rather than dividing by zero
        return {
            "skills": {"empathy": 0, "emotional_support": 0, "logical_thinking": 0},
            "detail": [],
            "scenes_counted": 0,
        }

    empathy = round(read_correct / counted * 100)
    emotional_support = round(support_sum / (counted * _MAX_WEIGHT) * 100)
    logical_thinking = round(logic_sum / (counted * _MAX_WEIGHT) * 100)

    return {
        "skills": {
            "empathy": empathy,
            "emotional_support": emotional_support,
            "logical_thinking": logical_thinking,
        },
        "detail": detail,
        "scenes_counted": counted,
    }
