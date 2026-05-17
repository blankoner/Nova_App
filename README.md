Nova\_App that helps young people find their educational path in life.
Also makes studying easier and more organized.

## Local development

### Prerequisites

- Python 3.10 or newer
- `pip`

### 1. Install dependencies

```bash
pip install flask python-dotenv pandas groq
```

> The bundled `requirements.txt` lists some stdlib names that `pip` can't
> install. The line above is the practical install command.

### 2. Prepare the SQLite database

Pick one:

**(a) Quick start — recommended for frontend / design work.** Generate a
small `jobs.db` with ~35 hand-crafted sample offers:

```bash
python seed_stub_db.py
```

**(b) Real data.** Follow the docstring in `import_data.py` to load the
Kaggle LinkedIn jobs CSV into `jobs.db`.

### 3. Run the Flask dev server

```bash
python app.py
```

The app serves at <http://127.0.0.1:5000> with auto-reload on file
changes (Flask debug mode).

#### Mock LLM mode (default — no API key required)

If `GROQ_API_KEY` is not set, the app starts in **mock mode** and prints:

```
[MOCK MODE] GROQ_API_KEY not set — using scripted mock responses.
```

The interview replays a fixed 9-question script and writes a hard-coded
mock profile when finished. Useful for working on the UI without
hitting the LLM.

#### Real LLM mode (Groq)

Create a `.env` file in the project root:

```
GROQ_API_KEY=your_groq_api_key_here
```

Restart `python app.py` — the mock banner won't appear and `/chat` will
talk to Groq's `llama-3.3-70b-versatile`.

### Routes

| Path        | Purpose                                              |
| ----------- | ---------------------------------------------------- |
| `/`         | Sign-up + interview entry                            |
| `/dashboard`| Dashboard: interview, to-do, pomodoro, journal       |
| `/wyniki`   | Career match results (visible after the interview)   |
