/**
 * chat.js — reusable chat logic for the career interview + advisor follow-up.
 *
 * The conversation has two phases:
 *   1. INTERVIEW — the AI asks questions to build the user's profile.
 *   2. ADVISOR   — once the interview is done, the chat stays OPEN: the user
 *                  can ask follow-up questions about careers, their matches,
 *                  study paths, etc. The backend handles the mode switch; this
 *                  file just keeps the input usable and adjusts the UI.
 *
 * Exposes window.Nova.createChat(options) which returns an object with:
 *   - start()          → fetches the first AI message
 *   - send()           → reads the input box and posts the user message
 *   - onDone(callback) → fired ONCE, when the interview finishes
 *
 * Options:
 *   chatBoxId   — id of the scrollable bubbles container       (required)
 *   inputId     — id of the user input <input>                 (required)
 *   sendBtnId   — id of the send button                        (required)
 *   onDone      — optional callback, fired once on interview end (optional)
 *   advisorPlaceholder — input placeholder text for advisor mode (optional)
 */
(function () {
  window.Nova = window.Nova || {};

  function createChat(opts) {
    const chatBox = document.getElementById(opts.chatBoxId);
    const input = document.getElementById(opts.inputId);
    const sendBtn = document.getElementById(opts.sendBtnId);
    const advisorPlaceholder = opts.advisorPlaceholder ||
      "Ask me anything about careers, your matches, or next steps…";
    let onDoneCb = opts.onDone || null;
    let started = false;
    let advisorMode = false;   // true once the interview has finished

    function addBubble(text, role) {
      const d = document.createElement("div");
      d.className = "bubble " + (role === "user" ? "bubble-user" : "bubble-ai");
      d.textContent = text;
      chatBox.appendChild(d);
      chatBox.scrollTop = chatBox.scrollHeight;
    }

    function showTyping() {
      const d = document.createElement("div");
      d.className = "typing-dot";
      d.id = "typing";
      d.innerHTML = "<span></span><span></span><span></span>";
      chatBox.appendChild(d);
      chatBox.scrollTop = chatBox.scrollHeight;
    }

    function removeTyping() {
      const el = document.getElementById("typing");
      if (el) el.remove();
    }

    async function start() {
      if (started) return;

      // Try to restore an existing conversation first (e.g. after navigating
      // away to the strategy game or results page and pressing Back).
      try {
        const histRes = await fetch("/chat-history");
        const histData = await histRes.json();
        if (histData.messages && histData.messages.length > 0) {
          started = true;
          histData.messages.forEach(m => addBubble(m.text, m.role));
          if (histData.done) {
            advisorMode = true;
            input.placeholder = advisorPlaceholder;
            if (onDoneCb) onDoneCb(histData);
          }
          return;
        }
      } catch (e) {
        // Network error or unexpected response — fall through to fresh start.
        console.warn("Could not fetch chat history, starting fresh.", e);
      }

      // No existing conversation — start a fresh interview.
      started = true;
      showTyping();
      try {
        const res = await fetch("/start", { method: "POST" });
        const data = await res.json();
        removeTyping();
        addBubble(data.message, "ai");
      } catch (e) {
        removeTyping();
        addBubble("Sorry — couldn't reach the server. Please refresh.", "ai");
        console.error(e);
      }
    }

    async function send() {
      const text = input.value.trim();
      if (!text) return;
      addBubble(text, "user");
      input.value = "";
      sendBtn.disabled = true;
      showTyping();
      try {
        const res = await fetch("/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text })
        });
        const data = await res.json();
        removeTyping();
        sendBtn.disabled = false;
        if (data.message) addBubble(data.message, "ai");

        // `done` marks the end of the INTERVIEW — but the chat stays open so
        // the user can keep asking the advisor follow-up questions. We only
        // run the onDone callback (and switch the placeholder) the first time.
        if (data.done && !advisorMode) {
          advisorMode = true;
          input.placeholder = advisorPlaceholder;
          if (onDoneCb) onDoneCb(data);
        }
        input.focus();
      } catch (e) {
        removeTyping();
        sendBtn.disabled = false;
        addBubble("Sorry — something went wrong. Please try again.", "ai");
        console.error(e);
      }
    }

    function onDone(cb) { onDoneCb = cb; }

    // Wire Enter key on the input
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") send();
    });
    sendBtn.addEventListener("click", send);

    return { start, send, onDone };
  }

  window.Nova.createChat = createChat;
})();
