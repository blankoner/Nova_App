/**
 * chat.js — reusable chat logic for the career interview.
 *
 * Exposes window.Nova.createChat(options) which returns an object with:
 *   - start()          → fetches the first AI message
 *   - send()           → reads the input box and posts user message
 *   - onDone(callback) → registers a callback fired when the interview ends
 *
 * Options:
 *   chatBoxId   — id of the scrollable bubbles container       (required)
 *   inputId     — id of the user input <input>                 (required)
 *   sendBtnId   — id of the send button                        (required)
 *   onDone      — optional callback when the interview ends    (optional)
 *   disableOnDone — if true, disable input + button on done    (default false)
 */
(function () {
  window.Nova = window.Nova || {};

  function createChat(opts) {
    const chatBox = document.getElementById(opts.chatBoxId);
    const input = document.getElementById(opts.inputId);
    const sendBtn = document.getElementById(opts.sendBtnId);
    const disableOnDone = !!opts.disableOnDone;
    let onDoneCb = opts.onDone || null;
    let started = false;

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
        if (data.done) {
          if (disableOnDone) {
            sendBtn.disabled = true;
            input.disabled = true;
          }
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
