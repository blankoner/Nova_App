import { useState } from 'react'

/* ---------- Inline SVG marks ---------- */

function StarMark({ size = 18 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M12 0 L13.6 9.4 L23 11 L13.6 12.6 L12 22 L10.4 12.6 L1 11 L10.4 9.4 Z" />
    </svg>
  )
}

function ArrowRight({ size = 14 }) {
  return (
    <svg
      className="arrow"
      width={size}
      height={size}
      viewBox="0 0 14 14"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M2 7 H12" />
      <path d="M8 3 L12 7 L8 11" />
    </svg>
  )
}

function BrandMark({ tone = 'ink' }) {
  return (
    <span className="brand-mark" style={{ color: tone === 'light' ? '#fff' : 'var(--ink)' }}>
      <StarMark size={18} />
      Nova
    </span>
  )
}

/* ---------- Question definitions ---------- */

const QUESTIONS = [
  { id: 'name',      type: 'text',     prompt: "What's your name?",                                       placeholder: 'Type your name…' },
  { id: 'age',       type: 'number',   prompt: 'How old are you?',                                        placeholder: 'e.g. 17' },
  { id: 'education', type: 'select',   prompt: 'What is your current education level?',                   options: ['Secondary school', 'University', 'Other'] },
  { id: 'freetime',  type: 'textarea', prompt: 'What do you enjoy doing in your free time?',              placeholder: 'Tell us a little about what you love…' },
  { id: 'persona',   type: 'select',   prompt: 'Which of these sounds most like you?',                    options: [
    'I like working with people',
    'I like solving problems',
    'I like creating things',
    'I like organizing and planning',
  ] },
  { id: 'goal',      type: 'text',     prompt: "What's one thing you'd like to learn or get better at?",  placeholder: 'e.g. public speaking, coding, drawing…' },
]

const pad2 = (n) => String(n).padStart(2, '0')

/* ============================================================
   SCREEN 1 — Sign-up
   ============================================================ */

function SignUp({ onSubmit }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    onSubmit()
  }

  return (
    <div className="signup-page">
      {/* --- Left: editorial purple panel --- */}
      <aside className="signup-hero">
        <BrandMark tone="light" />

        <div className="hero-body">
          <p className="hero-eyebrow">A career compass for students</p>
          <h1 className="hero-title">
            Find your<br />
            <em>path.</em>
          </h1>
          <p className="hero-tagline">
            Discover the studies and careers that match who you are — through
            short interviews, playful tests, and real-world matches.
          </p>
        </div>

        <ol className="hero-journey">
          <li className="current"><span>01</span> Create your account</li>
          <li><span>02</span> Tell us about you</li>
          <li><span>03</span> See your matches</li>
        </ol>
      </aside>

      {/* --- Right: form --- */}
      <main className="signup-form-wrap">
        <form className="form-shell" onSubmit={handleSubmit}>
          <p className="eyebrow">Step 01 — Account</p>
          <h2 className="form-title">Create your account.</h2>
          <p className="form-subtitle">
            Let's get you set up. It takes about two minutes.
          </p>

          <div className="field-group">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
            />
          </div>

          <div className="field-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              autoComplete="new-password"
            />
          </div>

          <div className="field-group">
            <label htmlFor="confirm">Confirm password</label>
            <input
              id="confirm"
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="Type it again"
              autoComplete="new-password"
            />
          </div>

          <button type="submit" className="btn-action">
            Sign up <ArrowRight />
          </button>

          <p className="signup-footer">
            Already have an account?
            <a href="#login" onClick={(e) => e.preventDefault()}>Log in</a>
          </p>
        </form>
      </main>
    </div>
  )
}

/* ============================================================
   SCREEN 2 — Interview
   ============================================================ */

function Interview({ onFinish }) {
  const [step, setStep] = useState(0)
  const [answers, setAnswers] = useState({})

  const total = QUESTIONS.length
  const q = QUESTIONS[step]
  const value = answers[q.id] ?? ''
  const isLast = step === total - 1
  const canAdvance = String(value).trim().length > 0
  const progressPct = ((step + 1) / total) * 100

  const setValue = (v) => setAnswers((prev) => ({ ...prev, [q.id]: v }))

  const next = () => {
    if (!canAdvance) return
    if (isLast) onFinish(answers)
    else setStep((s) => s + 1)
  }

  return (
    <div className="interview-page">
      <header className="interview-topbar">
        <BrandMark />
        <span className="progress-numbers">
          <strong>{pad2(step + 1)}</strong> &nbsp;/&nbsp; {pad2(total)}
        </span>
      </header>

      <div className="progress-line" style={{ '--progress': `${progressPct}%` }} />

      <section className="interview-content">
        <div className="question-grid q-anim" key={q.id}>
          {/* Left: numeral + question */}
          <div className="question-side">
            <div className="big-numeral" aria-hidden="true">{pad2(step + 1)}</div>
            <p className="question-eyebrow">Question {pad2(step + 1)} of {pad2(total)}</p>
            <h2 className="question-text">{q.prompt}</h2>
          </div>

          {/* Right: answer */}
          <div className="answer-side">
            {q.type === 'text' && (
              <input
                className="journal-input"
                type="text"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder={q.placeholder}
                autoFocus
              />
            )}

            {q.type === 'number' && (
              <input
                className="journal-input"
                type="number"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder={q.placeholder}
                min="0"
                autoFocus
              />
            )}

            {q.type === 'textarea' && (
              <textarea
                className="journal-textarea"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder={q.placeholder}
                autoFocus
              />
            )}

            {q.type === 'select' && (
              <div className="option-list">
                {q.options.map((opt) => (
                  <button
                    type="button"
                    key={opt}
                    className={`option ${value === opt ? 'selected' : ''}`}
                    onClick={() => setValue(opt)}
                  >
                    <span className="option-dot" aria-hidden="true" />
                    {opt}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </section>

      <footer className="interview-footer">
        <button
          type="button"
          className="btn-next"
          onClick={next}
          disabled={!canAdvance}
        >
          {isLast ? 'Finish' : 'Next'} <ArrowRight />
        </button>
      </footer>
    </div>
  )
}

/* ============================================================
   SCREEN 3 — Done
   ============================================================ */

function Done({ onRestart }) {
  return (
    <div className="done-page">
      <header className="interview-topbar">
        <BrandMark />
        <span className="progress-numbers">
          <strong>06</strong> &nbsp;/&nbsp; 06
        </span>
      </header>

      <div className="done-content">
        <div className="done-star">
          <StarMark size={48} />
        </div>
        <p className="done-eyebrow">All done</p>
        <h1 className="done-title">
          You're all <em>set.</em>
        </h1>
        <p className="done-sub">
          Thanks for sharing. We'll use what you told us to find the studies
          and careers that fit who you are.
        </p>
        <button type="button" className="btn-action" onClick={onRestart}>
          Get started <ArrowRight />
        </button>
      </div>
    </div>
  )
}

/* ============================================================
   App shell
   ============================================================ */

export default function App() {
  const [screen, setScreen] = useState('signup')

  if (screen === 'signup') {
    return <SignUp onSubmit={() => setScreen('interview')} />
  }
  if (screen === 'interview') {
    return <Interview onFinish={() => setScreen('done')} />
  }
  return <Done onRestart={() => setScreen('signup')} />
}
