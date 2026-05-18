/**
 * game-strategy.js — a Risk-style conquest game (player vs AI).
 *
 * The whole game runs client-side. When it ends, we POST a derived skill
 * result to /api/game-result so skills.py can fold it into the user profile.
 *
 * ── How the game maps onto skills ──────────────────────────────────────────
 * The screenshot brief says we analyse: strategy, decision maker, thoughtful,
 * rusher headlong. We turn observed play into four skill scores (0–100):
 *
 *   strategy         ← did they win? how efficiently did they expand?
 *   decision_making  ← did they act, or sit passive? attacks per turn
 *   logical_thinking ← "thoughtful": attacking with a real dice advantage
 *   patience         ← inverse of "rusher headlong": low when they attack
 *                      recklessly (tiny/negative advantage) and lose a lot
 *
 * Everything needed to compute these is tracked in `metrics` during play.
 */
(function () {
  "use strict";

  // ── Map definition ─────────────────────────────────────────────────────────
  // 10 territories on a rough 2D layout. `adj` lists neighbour ids.
  // x/y are percentages used for positioning on the board.
  const MAP = [
    { id: "t0", name: "Norvik",   x: 18, y: 16, adj: ["t1", "t2"] },
    { id: "t1", name: "Drelle",   x: 42, y: 12, adj: ["t0", "t2", "t3"] },
    { id: "t2", name: "Karsk",    x: 30, y: 38, adj: ["t0", "t1", "t4", "t5"] },
    { id: "t3", name: "Estoria",  x: 66, y: 18, adj: ["t1", "t5", "t6"] },
    { id: "t4", name: "Brenmar",  x: 14, y: 62, adj: ["t2", "t5", "t7"] },
    { id: "t5", name: "Velmont",  x: 44, y: 50, adj: ["t2", "t3", "t4", "t6", "t8"] },
    { id: "t6", name: "Ashfen",   x: 74, y: 44, adj: ["t3", "t5", "t9"] },
    { id: "t7", name: "Lowmere",  x: 26, y: 84, adj: ["t4", "t8"] },
    { id: "t8", name: "Tirgate",  x: 52, y: 80, adj: ["t5", "t7", "t9"] },
    { id: "t9", name: "Solhavn",  x: 80, y: 72, adj: ["t6", "t8"] },
  ];

  const MAX_ARMIES = 12;          // cap per territory
  const REINFORCE_PER_TURN = 3;   // armies each side places at end of its turn
  const ROUND_CAP = 30;           // if neither side wins by here, most territory wins

  // ── Game state ─────────────────────────────────────────────────────────────
  let state = null;   // built fresh in newGame()
  let metrics = null; // reset in newGame()
  let selectedId = null;
  let busy = false;   // true while AI is "thinking" — blocks input

  function newGame() {
    // Each territory: { owner: "player"|"ai"|null, armies: int }
    const territories = {};
    MAP.forEach(t => { territories[t.id] = { owner: null, armies: 1 }; });

    // Starting positions: player gets a corner cluster, AI the opposite one,
    // the middle is neutral (owner stays null until someone takes it).
    territories.t0.owner = "player"; territories.t0.armies = 4;
    territories.t2.owner = "player"; territories.t2.armies = 3;
    territories.t4.owner = "player"; territories.t4.armies = 3;

    territories.t9.owner = "ai"; territories.t9.armies = 4;
    territories.t6.owner = "ai"; territories.t6.armies = 3;
    territories.t8.owner = "ai"; territories.t8.armies = 3;

    state = {
      territories,
      turn: "player",      // whose turn it is
      round: 1,
      phase: "attack",     // "attack" | "reinforce" | "over"
      reinforcementsLeft: 0,
      winner: null,
      log: [],
    };

    metrics = {
      playerAttacks: 0,        // total attacks the player launched
      playerWins: 0,           // attacks the player won
      thoughtfulAttacks: 0,    // attacks launched with dice advantage >= 1
      recklessAttacks: 0,      // attacks launched with dice advantage <= 0
      armiesLost: 0,           // player armies lost in combat
      armiesConquered: 0,      // territories captured by the player
      turnsTaken: 0,           // player turns completed
      passedTurns: 0,          // player turns ended with zero attacks
      attacksThisTurn: 0,      // resets each player turn
    };

    selectedId = null;
    busy = false;
    log("Round 1 — your move. Select one of your territories to attack from.");
    render();
  }

  // ── Helpers ────────────────────────────────────────────────────────────────
  function mapNode(id) { return MAP.find(t => t.id === id); }

  function ownedBy(owner) {
    return MAP.filter(t => state.territories[t.id].owner === owner);
  }

  function countArmies(owner) {
    return ownedBy(owner).reduce((sum, t) => sum + state.territories[t.id].armies, 0);
  }

  // A territory can attack if it has > 1 army (must leave one behind)
  function canAttackFrom(id) {
    const t = state.territories[id];
    return t.owner === "player" && t.armies > 1;
  }

  // Valid targets from `id`: adjacent territories not owned by the attacker
  function attackTargets(id) {
    const node = mapNode(id);
    return node.adj.filter(adjId => state.territories[adjId].owner !== state.territories[id].owner);
  }

  function rollDice(n) {
    const rolls = [];
    for (let i = 0; i < n; i++) rolls.push(1 + Math.floor(Math.random() * 6));
    return rolls;
  }

  function diceSum(rolls) { return rolls.reduce((a, b) => a + b, 0); }

  function log(msg) {
    state.log.unshift(msg);
    if (state.log.length > 8) state.log.pop();
  }

  // ── Combat resolution ──────────────────────────────────────────────────────
  // Each side rolls one die per army. Higher sum wins. On a tie, defender holds.
  // Loser of the exchange loses one army; if defender hits 0, attacker moves in.
  function resolveAttack(fromId, toId, attackerIsPlayer) {
    const from = state.territories[fromId];
    const to = state.territories[toId];

    const attackerArmies = from.armies;          // attacker rolls with all but
    const attackDice = Math.max(1, attackerArmies - 1); // the one that stays home
    const defendDice = Math.max(1, to.armies);

    const advantage = attackDice - defendDice;   // used for "thoughtful" metric

    const aRoll = rollDice(attackDice);
    const dRoll = rollDice(defendDice);
    const aSum = diceSum(aRoll);
    const dSum = diceSum(dRoll);

    let captured = false;
    let attackerWon = aSum > dSum;

    if (attackerWon) {
      to.armies -= 1;
      if (to.armies <= 0) {
        // Territory captured — move half the attacking force in (min 1)
        const moving = Math.max(1, Math.floor((from.armies - 1) / 2));
        to.owner = from.owner;
        to.armies = moving;
        from.armies -= moving;
        captured = true;
      }
    } else {
      // Attacker loses one army (the tie-goes-to-defender case lands here too)
      from.armies -= 1;
    }

    // ── Track metrics (only for the player's own attacks) ──
    if (attackerIsPlayer) {
      metrics.playerAttacks += 1;
      metrics.attacksThisTurn += 1;
      if (advantage >= 1) metrics.thoughtfulAttacks += 1;
      if (advantage <= 0) metrics.recklessAttacks += 1;
      if (attackerWon) metrics.playerWins += 1;
      else metrics.armiesLost += 1;
      if (captured) metrics.armiesConquered += 1;
    }

    return { aRoll, dRoll, aSum, dSum, attackerWon, captured, advantage };
  }

  // ── Win / loss check ───────────────────────────────────────────────────────
  function checkGameOver() {
    const playerCount = ownedBy("player").length;
    const aiCount = ownedBy("ai").length;
    if (playerCount === 0) { state.winner = "ai"; state.phase = "over"; return true; }
    if (aiCount === 0)     { state.winner = "player"; state.phase = "over"; return true; }
    return false;
  }

  // ── Player actions ─────────────────────────────────────────────────────────
  // Can the player still place a reinforcement anywhere? (any owned territory
  // below the army cap). If not, the reinforce phase must end automatically —
  // otherwise the game can deadlock with reinforcements left but nowhere to go.
  function playerHasReinforceSpace() {
    return ownedBy("player").some(node => state.territories[node.id].armies < MAX_ARMIES);
  }

  function selectTerritory(id) {
    if (busy || state.phase === "over" || state.turn !== "player") return;

    const t = state.territories[id];

    if (state.phase === "reinforce") {
      // In reinforce phase, clicking your own territory drops an army there
      if (t.owner === "player" && state.reinforcementsLeft > 0 && t.armies < MAX_ARMIES) {
        t.armies += 1;
        state.reinforcementsLeft -= 1;
        log(`Reinforced ${mapNode(id).name}. ${state.reinforcementsLeft} left.`);
        // End the phase if we're out of reinforcements OR every territory is
        // now full (no legal placement remains).
        if (state.reinforcementsLeft === 0 || !playerHasReinforceSpace()) {
          endReinforcePhase();
        }
        render();
      }
      return;
    }

    // Attack phase
    if (selectedId === null) {
      if (canAttackFrom(id)) {
        selectedId = id;
        log(`Selected ${mapNode(id).name}. Pick an adjacent enemy or neutral territory.`);
      } else if (t.owner === "player") {
        log(`${mapNode(id).name} needs more than 1 army to attack from.`);
      }
      render();
      return;
    }

    // We already have an attacker selected
    if (id === selectedId) {
      selectedId = null;             // deselect
      log("Selection cleared.");
      render();
      return;
    }

    if (canAttackFrom(id)) {
      selectedId = id;               // switch attacker
      log(`Selected ${mapNode(id).name}.`);
      render();
      return;
    }

    // Is `id` a valid target of the selected attacker?
    if (attackTargets(selectedId).includes(id)) {
      doPlayerAttack(selectedId, id);
    } else {
      log("Not adjacent — pick a neighbouring territory.");
      render();
    }
  }

  function doPlayerAttack(fromId, toId) {
    const fromName = mapNode(fromId).name;
    const toName = mapNode(toId).name;
    const r = resolveAttack(fromId, toId, true);

    let msg = `${fromName} → ${toName}: you rolled ${r.aSum}, defence ${r.dSum}. `;
    if (r.captured)        msg += `Captured ${toName}!`;
    else if (r.attackerWon) msg += `Defender lost an army.`;
    else                    msg += `Your attack was repelled.`;
    log(msg);

    // Keep the attacker selected if it can still attack, else clear
    if (!canAttackFrom(fromId)) selectedId = null;

    if (checkGameOver()) { render(); finishGame(); return; }
    render();
  }

  // End the player's attack phase → move to reinforce phase
  function endAttackPhase() {
    if (busy || state.phase !== "attack" || state.turn !== "player") return;

    metrics.turnsTaken += 1;
    if (metrics.attacksThisTurn === 0) metrics.passedTurns += 1;
    metrics.attacksThisTurn = 0;

    selectedId = null;
    state.phase = "reinforce";
    state.reinforcementsLeft = Math.min(
      REINFORCE_PER_TURN,
      MAX_ARMIES * ownedBy("player").length - countArmies("player")
    );

    // If there's nothing left to reinforce (no armies to place, or every
    // territory is already at the cap), skip straight to the AI's turn.
    if (state.reinforcementsLeft <= 0 || !playerHasReinforceSpace()) {
      endReinforcePhase();
    } else {
      log(`Place ${state.reinforcementsLeft} reinforcements on your territories.`);
    }
    render();
  }

  function endReinforcePhase() {
    state.phase = "attack";
    state.turn = "ai";
    log("AI's turn…");
    render();
    busy = true;
    setTimeout(runAiTurn, 700);
  }

  // ── AI turn ────────────────────────────────────────────────────────────────
  // "Medium" AI: from each of its territories that has an advantage, it attacks
  // the weakest reachable player/neutral territory. It keeps attacking while it
  // has favourable positions, then reinforces its front line.
  function runAiTurn() {
    let safety = 40;  // hard cap on attacks per AI turn, avoids infinite loops

    function aiStep() {
      if (state.phase === "over") { busy = false; render(); return; }

      // Find the AI's best available attack: largest dice advantage,
      // tie-broken by weakest target.
      let best = null;
      ownedBy("ai").forEach(node => {
        const from = state.territories[node.id];
        if (from.armies <= 1) return;
        const attackDice = from.armies - 1;
        node.adj.forEach(adjId => {
          const to = state.territories[adjId];
          if (to.owner === "ai") return;
          const defendDice = Math.max(1, to.armies);
          const advantage = attackDice - defendDice;
          // Only attack with a real edge (advantage >= 1)
          if (advantage < 1) return;
          if (!best ||
              advantage > best.advantage ||
              (advantage === best.advantage && to.armies < best.targetArmies)) {
            best = { fromId: node.id, toId: adjId, advantage, targetArmies: to.armies };
          }
        });
      });

      if (best && safety-- > 0) {
        const r = resolveAttack(best.fromId, best.toId, false);
        const fromName = mapNode(best.fromId).name;
        const toName = mapNode(best.toId).name;
        if (r.captured) log(`AI captured ${toName} from ${fromName}.`);
        else if (r.attackerWon) log(`AI hit ${toName} — you lost an army.`);
        else log(`AI attacked ${toName} and was repelled.`);

        if (checkGameOver()) { busy = false; render(); finishGame(); return; }
        render();
        setTimeout(aiStep, 550);
      } else {
        // No more good attacks — AI reinforces its front line, then ends turn
        aiReinforce();
        state.turn = "player";
        state.round += 1;
        log(`Round ${state.round} — your move.`);

        // Round cap: some maps can stall (neither side can break through).
        // After 30 rounds, whoever holds more territory wins — ties go to
        // the player, who's the one being assessed.
        if (state.round > ROUND_CAP) {
          const pc = ownedBy("player").length;
          const ac = ownedBy("ai").length;
          state.winner = ac > pc ? "ai" : "player";
          state.phase = "over";
          log(`Round limit reached — ${state.winner === "player" ? "you hold" : "the AI holds"} more territory.`);
          busy = false;
          render();
          finishGame();
          return;
        }

        busy = false;
        render();
      }
    }

    aiStep();
  }

  function aiReinforce() {
    // Drop reinforcements on AI territories that border the player —
    // these are the ones under threat / best for pushing forward.
    let left = REINFORCE_PER_TURN;
    const frontline = ownedBy("ai").filter(node =>
      node.adj.some(adjId => state.territories[adjId].owner === "player")
    );
    const pool = frontline.length ? frontline : ownedBy("ai");

    let i = 0;
    while (left > 0 && pool.length) {
      const node = pool[i % pool.length];
      const terr = state.territories[node.id];
      if (terr.armies < MAX_ARMIES) {
        terr.armies += 1;
        left -= 1;
      }
      i += 1;
      if (i > 100) break; // everything maxed out
    }
  }

  // ── End of game → derive skill scores and submit ───────────────────────────
  function deriveSkills() {
    const m = metrics;
    const won = state.winner === "player";

    // strategy: winning is the core signal, scaled by how efficiently you
    // expanded (territories conquered vs armies lost).
    let strategy;
    if (won) {
      const efficiency = m.armiesLost > 0
        ? m.armiesConquered / m.armiesLost
        : m.armiesConquered;
      // efficiency ~1 is decent, ~2+ is excellent
      strategy = Math.min(100, 60 + efficiency * 20);
    } else {
      // Lost, but partial credit for how much of the map you held / took
      const held = ownedBy("player").length; // 0 if wiped out
      strategy = Math.min(55, 10 + held * 6 + m.armiesConquered * 4);
    }

    // decision_making: did you act decisively? attacks per turn, penalised
    // for turns you passed entirely.
    const avgAttacks = m.turnsTaken > 0 ? m.playerAttacks / m.turnsTaken : 0;
    const passRate = m.turnsTaken > 0 ? m.passedTurns / m.turnsTaken : 1;
    let decision_making = Math.min(100, avgAttacks * 28);
    decision_making = Math.max(0, decision_making - passRate * 40);

    // logical_thinking ("thoughtful"): share of attacks made with a real
    // dice advantage.
    let logical_thinking;
    if (m.playerAttacks === 0) {
      logical_thinking = 20; // never engaged — little to judge, mild score
    } else {
      logical_thinking = (m.thoughtfulAttacks / m.playerAttacks) * 100;
    }

    // patience (inverse of "rusher headlong"): high when few reckless attacks
    // and a healthy win rate; low when you charged in at bad odds.
    let patience;
    if (m.playerAttacks === 0) {
      patience = 55; // didn't rush, but also didn't really play — neutral-ish
    } else {
      const recklessRate = m.recklessAttacks / m.playerAttacks;
      const winRate = m.playerWins / m.playerAttacks;
      patience = Math.max(0, Math.min(100,
        85 - recklessRate * 70 + (winRate - 0.5) * 30
      ));
    }

    return {
      strategy: Math.round(strategy),
      decision_making: Math.round(decision_making),
      logical_thinking: Math.round(logical_thinking),
      patience: Math.round(patience),
    };
  }

  function finishGame() {
    const result = deriveSkills();
    renderGameOver(result);

    // Submit to the backend. We don't block the UI on this — show results
    // immediately, report quietly if the save fails.
    fetch("/api/game-result", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ game: "strategy", result }),
    })
      .then(res => res.json())
      .then(data => {
        if (data && data.ok) {
          const note = document.getElementById("saveNote");
          if (note) note.textContent = "Skills updated and saved to your profile.";
        }
      })
      .catch(() => {
        const note = document.getElementById("saveNote");
        if (note) note.textContent = "Couldn't reach the server — skills not saved.";
      });
  }

  // ── Rendering ──────────────────────────────────────────────────────────────
  function render() {
    renderBoard();
    renderStatus();
    renderLog();
    renderControls();
  }

  function renderBoard() {
    const board = document.getElementById("gameBoard");
    if (!board) return;

    // Draw adjacency lines once (as an SVG layer), territories as buttons.
    let svg = '<svg class="board-lines" viewBox="0 0 100 100" preserveAspectRatio="none">';
    const drawn = new Set();
    MAP.forEach(t => {
      t.adj.forEach(adjId => {
        const key = [t.id, adjId].sort().join("-");
        if (drawn.has(key)) return;
        drawn.add(key);
        const a = t, b = mapNode(adjId);
        svg += `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" />`;
      });
    });
    svg += "</svg>";

    let nodes = "";
    MAP.forEach(t => {
      const terr = state.territories[t.id];
      const cls = ["territory"];
      cls.push("owner-" + (terr.owner || "neutral"));
      if (t.id === selectedId) cls.push("selected");
      // Highlight valid targets when an attacker is selected
      if (selectedId && state.phase === "attack" &&
          attackTargets(selectedId).includes(t.id)) {
        cls.push("targetable");
      }
      // In reinforce phase, highlight where you can drop armies
      if (state.phase === "reinforce" && terr.owner === "player" &&
          state.reinforcementsLeft > 0 && terr.armies < MAX_ARMIES) {
        cls.push("targetable");
      }
      nodes += `
        <button class="${cls.join(" ")}" style="left:${t.x}%; top:${t.y}%"
                data-id="${t.id}" title="${t.name}">
          <span class="terr-name">${t.name}</span>
          <span class="terr-armies">${terr.armies}</span>
        </button>`;
    });

    board.innerHTML = svg + nodes;
  }

  function renderStatus() {
    const set = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    };
    set("statRound", state.round);
    set("statPlayerTerr", ownedBy("player").length);
    set("statAiTerr", ownedBy("ai").length);
    set("statPlayerArmies", countArmies("player"));
    set("statAiArmies", countArmies("ai"));

    const phaseEl = document.getElementById("statPhase");
    if (phaseEl) {
      if (state.phase === "over") phaseEl.textContent = "Game over";
      else if (state.turn === "ai") phaseEl.textContent = "AI thinking…";
      else if (state.phase === "reinforce") phaseEl.textContent = `Reinforce (${state.reinforcementsLeft} left)`;
      else phaseEl.textContent = "Your attack phase";
    }
  }

  function renderLog() {
    const logEl = document.getElementById("gameLog");
    if (!logEl) return;
    logEl.innerHTML = state.log
      .map((line, i) => `<div class="log-line${i === 0 ? " latest" : ""}">${line}</div>`)
      .join("");
  }

  function renderControls() {
    const endBtn = document.getElementById("endTurnBtn");
    if (!endBtn) return;

    if (state.phase === "over") {
      endBtn.style.display = "none";
      return;
    }
    endBtn.style.display = "";

    if (state.turn !== "player" || busy) {
      endBtn.disabled = true;
      endBtn.textContent = "Waiting for AI…";
    } else if (state.phase === "attack") {
      endBtn.disabled = false;
      endBtn.textContent = "End attack phase →";
    } else if (state.phase === "reinforce") {
      endBtn.disabled = false;
      endBtn.textContent = state.reinforcementsLeft > 0
        ? `Skip (${state.reinforcementsLeft} reinforcements left)`
        : "Continue →";
    }
  }

  function renderGameOver(result) {
    const overlay = document.getElementById("gameOverOverlay");
    if (!overlay) return;

    const won = state.winner === "player";
    document.getElementById("gameOverTitle").textContent =
      won ? "Victory!" : "Defeated";
    document.getElementById("gameOverSub").textContent = won
      ? "You conquered the map. Here's what this game revealed about you:"
      : "The AI took the map this time. Here's what the game still revealed:";

    // Skill breakdown bars
    const labels = {
      strategy: "Strategic Planning",
      decision_making: "Decision Making",
      logical_thinking: "Logical Thinking",
      patience: "Patience & Composure",
    };
    let html = "";
    Object.keys(labels).forEach(key => {
      const val = result[key];
      html += `
        <div class="result-skill">
          <div class="result-skill-head">
            <span>${labels[key]}</span><span class="result-skill-val">${val}</span>
          </div>
          <div class="result-bar-track">
            <div class="result-bar-fill" style="width:${val}%"></div>
          </div>
        </div>`;
    });
    document.getElementById("gameOverSkills").innerHTML = html;

    overlay.classList.add("visible");
  }

  // ── Wiring ─────────────────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", () => {
    const board = document.getElementById("gameBoard");
    if (board) {
      // Event delegation — territory buttons are re-rendered constantly
      board.addEventListener("click", (e) => {
        const btn = e.target.closest(".territory");
        if (btn) selectTerritory(btn.dataset.id);
      });
    }

    const endBtn = document.getElementById("endTurnBtn");
    if (endBtn) {
      endBtn.addEventListener("click", () => {
        if (state.phase === "attack") endAttackPhase();
        else if (state.phase === "reinforce") endReinforcePhase();
      });
    }

    const newGameBtn = document.getElementById("newGameBtn");
    if (newGameBtn) {
      newGameBtn.addEventListener("click", () => {
        const overlay = document.getElementById("gameOverOverlay");
        if (overlay) overlay.classList.remove("visible");
        newGame();
      });
    }

    const howToBtn = document.getElementById("howToToggle");
    if (howToBtn) {
      howToBtn.addEventListener("click", () => {
        const panel = document.getElementById("howToPanel");
        if (panel) panel.classList.toggle("open");
      });
    }

    newGame();
  });
})();
