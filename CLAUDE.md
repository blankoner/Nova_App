# Career Advisor App — CLAUDE.md

Aplikacja webowa pomagająca młodym ludziom w odkryciu ścieżki kariery.
Łączy wywiad z AI, mini-gry oceniające umiejętności oraz dopasowywanie ofert pracy.

---

## Stack

- **Backend:** Python 3 · Flask · SQLite (przez `sqlite3`) · Groq API (LLM: `llama-3.3-70b-versatile`)
- **Frontend:** Vanilla JS + HTML/CSS (bez frameworka) · Bootstrap 5 · Google Fonts
- **Baza ofert:** LinkedIn job postings 2024 (Kaggle) · zasilana przez `import_data.py`
- **LLM fallback:** `MOCK_MODE` gdy brak `GROQ_API_KEY` — korzysta ze skryptowanych odpowiedzi

---

## Struktura plików

```
app.py              # Główna aplikacja Flask — wszystkie trasy HTTP
matcher.py          # Algorytm dopasowywania ofert pracy do profilu użytkownika
skills.py           # Model umiejętności, profil użytkownika, obsługa bazy SQLite (profiles.db)
import_data.py      # Jednorazowy skrypt: CSV → jobs.db (SQLite)
social_scenes.py    # Scenariusze i scoring gry społecznej

# Szablony HTML (Jinja2)
index.html          # Strona startowa / logowanie
dashboard.html      # Główny panel użytkownika (wywiad + mini-apki)
wyniki.html         # Wyniki dopasowania ofert
skills.html         # Przegląd umiejętności użytkownika
game_strategy.html  # Gra strategiczna (Risk-like)
game_social.html    # Gra społeczna (Life is Strange-like)

# JavaScript (vanilla)
chat.js             # Moduł czatu / wywiadu z AI (window.Nova.createChat)
dashboard.js        # Inicjalizacja dashboardu, przełączanie widoków
game-strategy.js    # Logika gry strategicznej
game-social.js      # Logika gry społecznej
todo.js / pomodoro.js / journal.js  # Mini-apki dashboardu

# CSS
index.css / dashboard.css / skills.css
game-strategy.css / game-social.css / wyniki.css
```

---

## Komendy

```bash
# Instalacja zależności
pip install flask groq python-dotenv pandas

# Zasilenie bazy ofert (tylko raz, wymaga plików CSV z Kaggle)
python import_data.py --jobs job_postings.csv --skills job_skills.csv

# Uruchomienie lokalne
GROQ_API_KEY=sk-... python app.py

# Uruchomienie w trybie mock (bez klucza API)
python app.py
```

---

## Trasy Flask (`app.py`)

| Metoda | Ścieżka | Opis |
|--------|---------|------|
| GET | `/` | Strona startowa, czyści sesję |
| GET | `/dashboard?name=...` | Panel użytkownika, tworzy profil |
| POST | `/start` | Inicjuje wywiad AI (resetuje historię) |
| POST | `/chat` | Kolejna wiadomość w wywiadzie lub tryb doradcy |
| GET | `/wyniki` | Wyniki dopasowania ofert (wymaga skończonego wywiadu) |
| GET | `/skills` | Przegląd umiejętności |
| GET | `/game/strategy` | Gra strategiczna |
| GET | `/game/social` | Gra społeczna |
| GET | `/api/social/scenes` | Scenariusze gry społecznej (bez scoringu) |
| POST | `/api/social/score` | Oblicz wynik gry społecznej |
| POST | `/api/game-result` | Zapisz wynik gry do profilu użytkownika |
| GET/POST | `/api/apps` | Pobierz/zapisz stan mini-apek (todo, journal, pomodoro) |
| GET | `/api/profile` | Pełny profil użytkownika jako JSON |

---

## Model danych użytkownika (`skills.py`)

Profil przechowywany w `profiles.db` (SQLite), klucz: znormalizowana nazwa użytkownika.

```python
{
  "name": str,
  "interview": dict | None,      # Wypełniony po zakończeniu wywiadu
  "skills": {
    "strategy": {"level": 0–100, "samples": int},
    "logical_thinking": {...},
    "decision_making": {...},
    "patience": {...},
    "empathy": {...},
    "emotional_support": {...},
    "assertiveness": {...},
  },
  "game_history": [...],
  "apps": {
    "todos": [...],
    "journal": {...},
    "pomodoro": {"settings": {...}},
  },
  "chat": {
    "interview_history": [...],  # Historia rozmowy z LLM
    "advisor_history": [...],    # Historia trybu doradcy
  }
}
```

---

## Ważne zasady

- **Nie modyfikuj `profiles.db` ręcznie** — zawsze używaj `skills_mod.load_profile()` / `save_profile()`
- **Nie commituj kluczy API** — trzymaj je wyłącznie w `.env` (plik `.env` powinien być w `.gitignore`)
- **`MOCK_MODE`** włącza się automatycznie gdy `GROQ_API_KEY` nie jest ustawiony — przydatny do testów UI
- **Scoring gier odbywa się server-side** — wagi odpowiedzi w `social_scenes.py` nie są wysyłane do klienta
- Sesja Flask przechowuje tylko `user_name` — reszta danych żyje w SQLite
- `import_data.py` uruchamiamy **tylko raz** przed startem (lub po zmianie datasetu)

---

## Przepływ użytkownika

```
index.html → wpisuje imię → /dashboard
  → wywiad czatowy (/start → /chat × N)
  → po zakończeniu: tryb doradcy + banner
  → /wyniki  (top 5 dopasowanych ofert)
  → /skills  (poziomy umiejętności)
  → /game/strategy lub /game/social  (mini-gry)
```
