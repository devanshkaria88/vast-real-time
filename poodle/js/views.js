import { api, avatar, conf, decision, esc, fmt, icon, POODLE_SVG, STATUS, statusGlyph, toast } from "./ui.js";

export const FILTERS = {
  inbox: { title: "Inbox", icon: "inbox", test: (c) => c.status === "triage" || c.status === "review", empty: "Nothing needs a person right now." },
  ready: { title: "Ready to settle", icon: "ready", test: (c) => c.status === "ready", empty: "No claims are ready to settle." },
  all: { title: "All claims", icon: "layers", test: () => true, empty: "No claims yet." },
  fraud: { title: "Fraud flags", icon: "flag", test: (c) => c.fraud, empty: "No fraud signals on open claims." },
};

const KIND_ICON = { vehicle: "car", signal: "signal", impact: "impact", road: "road", weather: "weather", light: "light", motion: "motion" };

export function visibleClaims(claims, filter) {
  return claims
    .filter(FILTERS[filter].test)
    .sort((a, b) => STATUS[a.status].order - STATUS[b.status].order || new Date(b.reportedAt) - new Date(a.reportedAt));
}

const menuBtn = `<button class="icon-btn menu-btn" data-menu aria-label="Open navigation">${icon("menu")}</button>`;

function citeLabel(title) {
  return title
    .replace(/^Section (\d+):.*/, "Section $1")
    .replace(/^General exclusion (\d+):.*/, "Exclusion $1")
    .replace(/^Add-on: (.*)/, "$1 add-on")
    .replace(/^Highway Code rule (\d+)/, "Highway Code $1");
}

function cite(claim, key) {
  const c = key && claim.citations[key];
  if (!c) return "";
  return `<button class="cite" data-cite="${esc(key)}" title="${esc(c.title)}: ${esc(c.text)}">${icon(c.kind === "rule" ? "road" : "doc", 11)}${esc(citeLabel(c.title))}</button>`;
}

// ---------------------------------------------------------------- list

export function listView(claims, filter, selectedId) {
  const f = FILTERS[filter];
  const list = visibleClaims(claims, filter);
  const header = `
    <header class="vh">${menuBtn}
      <div class="vh-title">${icon(f.icon, 15)}<span>${esc(f.title)}</span><span class="faint num">${list.length}</span></div>
      <div class="vh-actions faint"><kbd>J</kbd><kbd>K</kbd><span>&nbsp;move&nbsp;&nbsp;</span><kbd>↵</kbd><span>&nbsp;open</span></div>
    </header>`;
  if (!list.length) {
    return `${header}<div class="view"><div class="empty">${icon(f.icon, 22)}<b>${esc(f.empty)}</b><span>New claims and camera alerts land in the inbox.</span></div></div>`;
  }
  let body = "";
  for (const status of Object.keys(STATUS)) {
    const group = list.filter((c) => c.status === status);
    if (!group.length) continue;
    body += `<div class="group-h">${statusGlyph(status)}<span>${STATUS[status].label}</span><span class="n">${group.length}</span></div>`;
    body += group.map((c) => `
      <a class="row" href="#/claim/${esc(c.id)}" data-id="${esc(c.id)}" aria-selected="${c.id === selectedId}">
        ${statusGlyph(c.status)}
        <span class="id">${esc(c.id)}</span>
        <span class="t"><img class="thumb" src="${esc(c.thumb)}" alt="" loading="lazy"><b>${esc(c.title)}</b><span class="where">${esc(c.area)}</span></span>
        <span class="fraud-col">${c.fraud ? `<span class="chip fraud">${icon("flag", 11)}Fraud signal</span>` : ""}</span>
        ${decision(c.outcome, c.label)}
        <span class="money">${fmt.money(c.estimate)}</span>
        ${avatar(c.assignee)}
        <span class="age" title="Reported ${esc(fmt.date(c.reportedAt))}">${fmt.ago(c.reportedAt)}</span>
      </a>`).join("");
  }
  return `${header}<div class="view"><div class="list" role="listbox" aria-label="${esc(f.title)}">${body}</div></div>`;
}

// ---------------------------------------------------------------- claim

function mood(claim) {
  if (claim.status === "done" || claim.status === "ready" || claim.outcome === "accept") return ["happy", "Poodle is happy: this claim can settle."];
  if (claim.fraud || claim.outcome === "reject" || claim.outcome === "refer") return ["alert", "Poodle is alert: a person needs to look at this claim."];
  return ["watch", "Poodle is watching this claim."];
}

function overlay(claim) {
  const { width: W, height: H, detections } = claim.detections;
  const used = new Set(claim.findings.flatMap((f) => f.det));
  const items = detections
    .map((d, i) => ({ ...d, i }))
    .filter((d) => used.has(d.i))
    .map((d) => {
      const [x, y, w, h] = [d.box[0] * W, d.box[1] * H, d.box[2] * W, d.box[3] * H];
      const name = d.label === "traffic light" ? `signal ${d.state === "not_visible" ? "?" : d.state}` : d.label;
      const text = `${name} ${d.conf.toFixed(2)}`;
      const fs = Math.round(W * 0.021);
      const th = Math.round(fs * 1.45);
      const tw = text.length * fs * 0.6 + fs * 0.7;
      const ty = y > th + 2 ? y - th - 2 : y + 2;
      return `<g class="det${d.state === "red" ? " signal-red" : ""}" data-det="${d.i}" data-t="${d.t}">
        <rect class="box" x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}" rx="4"/>
        <rect class="tag" x="${x.toFixed(1)}" y="${ty.toFixed(1)}" width="${tw.toFixed(0)}" height="${th}" rx="4"/>
        <text x="${(x + fs * 0.35).toFixed(1)}" y="${(ty + th * 0.72).toFixed(1)}" style="font-size:${fs}px">${esc(text)}</text></g>`;
    })
    .join("");
  return `<svg class="overlay" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">${items}</svg>`;
}

function mapTiles(lat, lon, z = 16) {
  const n = 2 ** z;
  const xf = ((lon + 180) / 360) * n;
  const r = (lat * Math.PI) / 180;
  const yf = ((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * n;
  const xt = Math.floor(xf);
  const yt = Math.floor(yf);
  const px = 256 + (xf - xt) * 256;
  const py = 256 + (yf - yt) * 256;
  let imgs = "";
  for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) imgs += `<img src="https://tile.openstreetmap.org/${z}/${xt + dx}/${yt + dy}.png" alt="" loading="lazy">`;
  return `<div class="tiles" style="left:calc(50% - ${px.toFixed(0)}px);top:${(64 - py).toFixed(0)}px">${imgs}</div><span class="pin"></span><span class="osm">© OpenStreetMap</span>`;
}

const SUGGEST = ["What colour was the light?", "Where was the point of impact?", "Was the road wet?", "How fast was the other car going?"];

export function claimView(claim, nav) {
  const d = claim.decision;
  const st = d.settlement;
  const [moodName, moodText] = mood(claim);
  const insurer = claim.thirdParty?.insurer;
  const reasons = d.reasons.map((r) => `<li>${esc(r.text).replace(/`([^`]+)`/g, "<code>$1</code>")}${cite(claim, r.cite)}</li>`).join("");
  const cov = [
    ...d.covered.map((x) => `<div class="cov yes">${icon("check", 15)}<div><b>${esc(x.name)}</b> <span class="muted">${esc(x.detail)}</span>${cite(claim, x.cite)}</div></div>`),
    ...d.notCovered.map((x) => `<div class="cov no">${icon("x", 15)}<div><b>${esc(x.name)}</b> <span class="muted">${esc(x.detail)}</span>${cite(claim, x.cite)}</div></div>`),
  ].join("") || `<div class="cov no">${icon("minus", 15)}<div><b>Held for a person</b> <span class="muted">Cover is not decided until a handler reviews it.</span></div></div>`;
  const settle = st.payable !== null
    ? `<div><span>Repair estimate</span><b>${fmt.money(st.estimate)}</b></div>
       <div><span>Cover limit</span><b>${fmt.money(st.limit)}</b></div>
       <div><span>Excess</span><b>−${fmt.money(st.excess)}</b></div>
       <div class="total"><span>Payable now</span><b>${fmt.money(st.payable)}</b></div>
       ${st.recovery ? `<div><span>Recover from ${esc(insurer || "third party")}</span><b>${fmt.money(st.recovery)}</b></div>` : ""}`
    : `<div><span>Repair estimate</span><b>${fmt.money(st.estimate)}</b></div><div><span>Excess</span><b>${fmt.money(st.excess)}</b></div>
       <div class="total"><span>Payable now</span><b>—</b></div><div><span class="faint">Nothing is paid until a person decides.</span></div>`;
  const findings = claim.findings.map((f) => `
    <button class="finding" data-fid="${esc(f.id)}" data-det="${f.det.join(",")}" data-t="${f.t}">
      ${icon(KIND_ICON[f.kind] || "eye", 15)}<span class="txt">${esc(f.text)}</span><span class="src">${esc(f.source)}</span>${conf(f.conf)}
    </button>`).join("");
  const VERDICT_ICON = { supported: "check", contradicted: "x", unverifiable: "minus" };
  const stmt = claim.statement.claims.length
    ? `<blockquote class="quote"><span>${esc(claim.statement.by)}</span>“${esc(claim.statement.text)}”</blockquote>
       <div class="stmt">${claim.statement.claims.map((s) => `
         <div class="stmt-row">
           <span class="verdict ${esc(s.verdict)}">${icon(VERDICT_ICON[s.verdict], 14)}${esc(s.verdict[0].toUpperCase() + s.verdict.slice(1))}</span>
           <span><span class="claim-text">${esc(s.text)}</span>${s.note ? ` <span class="note">${esc(s.note)}</span>` : ""}</span>
           ${s.finding ? `<button class="cite" data-locate="${esc(s.finding)}">${icon("eye", 11)}Show in footage · ${s.conf.toFixed(2)}</button>` : `<span class="faint num">${s.conf.toFixed(2)}</span>`}
         </div>`).join("")}</div>`
    : `<div class="empty" style="padding:24px">${icon("ask", 20)}<span>No statement yet. Poodle opened this claim from a camera alert at ${esc(fmt.time(claim.incidentAt))}.</span></div>`;
  const activity = claim.activity.map((a) => `
    <div class="act">${a.actor.endsWith("agent") || a.actor === "Poodle" ? avatar("Poodle") : avatar(a.actor)}
      <p><b>${esc(a.actor)}</b> ${esc(a.text)}</p><time title="${esc(fmt.date(a.at))}">${fmt.ago(a.at)} ago</time></div>`).join("");
  const p = claim.policy;
  const checks = d.checks.map((c) => `<div class="check ${c.pass ? "pass" : "fail"}">${icon(c.pass ? "check" : "x", 14)}<div>${esc(c.label)}<small>${esc(c.detail)}</small></div></div>`).join("");
  const hashes = [...claim.evidence, ...claim.attachments].map((h) => `
    <div class="hash"><div><b>${esc(h.label)}</b><code title="${esc(h.sha256)}">${h.sha256.slice(0, 12)}…${h.sha256.slice(-6)}</code></div>
      <button class="icon-btn" data-copy="${esc(h.sha256)}" aria-label="Copy SHA-256 of ${esc(h.label)}">${icon("copy", 14)}</button></div>`).join("");
  const addOns = p.addOns.length ? p.addOns.map((a) => a.replace(/_/g, " ").replace("ncd", "NCD")).join(", ") : "None";
  const done = claim.status === "done";
  const dets = claim.detections.detections.length;

  return `
  <header class="vh">${menuBtn}
    <div class="vh-title"><a class="crumb" href="#/${esc(nav.from)}">${esc(FILTERS[nav.from].title)}</a>${icon("chevronRight", 14)}<span class="num">${esc(claim.id)}</span></div>
    <div class="vh-actions">
      <span class="pager"><span>${nav.index + 1} / ${nav.total}</span>
        <button class="icon-btn" data-nav="-1" aria-label="Previous claim (K)">${icon("chevronUp")}</button>
        <button class="icon-btn" data-nav="1" aria-label="Next claim (J)">${icon("chevronDown")}</button></span>
      <a class="btn" href="/api/claims/${esc(claim.id)}/pack" target="_blank" rel="noopener">${icon("download", 14)}<span class="label">Evidence pack</span></a>
      ${claim.fraud && !done ? `<button class="btn" data-act="refer">${icon("shieldAlert", 14)}<span class="label">Refer to SIU</span></button>` : ""}
      ${done ? `<button class="btn" data-act="reopen">${icon("refresh", 14)}<span class="label">Reopen</span></button>`
             : d.outcome === "refer"
               ? (claim.assignee === "You" ? "" : `<button class="btn btn-primary" data-act="assign">${icon("user", 14)}<span class="label">Take the case</span><kbd>⌘↵</kbd></button>`)
               : `<button class="btn btn-primary" data-act="approve">${icon("check", 14)}<span class="label">Approve</span><kbd>⌘↵</kbd></button>`}
    </div>
  </header>
  <div class="view">
  <div class="claim">
    <div class="claim-main">
      <h1 class="claim-title">${esc(claim.title)}</h1>
      <p class="claim-sub">
        <span>${statusGlyph(claim.status)}${esc(STATUS[claim.status].label)}</span>
        <span>${icon("pin", 14)}${esc(claim.place)}, ${esc(claim.area)}</span>
        <span>${icon("clock", 14)}${esc(fmt.date(claim.incidentAt))}</span>
        ${decision(d.outcome, d.label)}
        ${claim.fraud ? `<span class="chip fraud">${icon("flag", 11)}Fraud signal</span>` : ""}
      </p>

      <div class="console">
        <div class="feed-wrap">
          <div class="mascot">${POODLE_SVG.replace("mood-watch", `mood-${moodName}`)}</div>
          <span class="sr-only" role="status">${esc(moodText)}</span>
          <div class="feed-h">${icon("cctv", 15)}Incident footage <span class="muted trunc">${esc(claim.footage.camera)} · ${esc(claim.footage.source)}</span>
            <span class="right"><span class="chip demo" title="${esc(claim.footage.credit)}">Real footage</span>
              <button class="icon-btn" data-toggle-dets aria-pressed="true" aria-label="Show detections (D)" title="Detections (D)">${icon("eye", 15)}</button></span></div>
          <div class="player" id="incident-player">
            <video src="${esc(claim.footage.clip)}" poster="${esc(claim.footage.poster)}" muted playsinline loop autoplay preload="auto"></video>
            ${overlay(claim)}
            <div class="controls">
              <button class="icon-btn" data-play aria-label="Pause (Space)">${icon("pause", 15)}</button>
              <div class="scrub" data-scrub role="slider" aria-label="Seek" aria-valuemin="0" aria-valuemax="${claim.footage.duration}" tabindex="0"><div class="fill"></div></div>
              <span class="time">00:00 / ${fmt.clock(claim.footage.duration)}</span>
              <span class="det-note">${icon("scan", 12)}YOLO11s, ${dets} objects</span>
              <button class="icon-btn" data-fs aria-label="Full screen">${icon("maximize", 15)}</button>
            </div>
          </div>
        </div>
        <div>
          <div class="feed-h"><span class="live-dot"></span>Nearby live cameras <span class="muted">TfL</span>
            <span class="right"><a class="cams-more" href="#/cameras?near=${esc(claim.id)}">See all</a></span></div>
          <div class="cams-col" id="nearby">${'<div class="skeleton" style="aspect-ratio:352/288"></div>'.repeat(2)}</div>
        </div>
      </div>

      <section class="section" aria-labelledby="rec-h">
        <h2 class="section-h" id="rec-h">Recommendation <span class="muted">${d.record.mode === "live" ? "Jev live" : "Jev answers seeded"}, decision table in code</span></h2>
        <div class="verdict-card">
          <div class="verdict-top"><span class="big decision ${esc(d.outcome)}"><i></i>${esc(d.label)}</span><ul class="why">${reasons}</ul></div>
          <div class="verdict-grid"><div class="coverage">${cov}</div><div class="settle">${settle}</div></div>
          <div class="handoff">${icon("shield", 14)}${d.straightThrough ? "High confidence and low value: this claim can settle without a handler." : "A handler confirms this before the customer is told."}</div>
        </div>
      </section>

      <section class="section" aria-labelledby="find-h">
        <h2 class="section-h" id="find-h">What the footage shows <span class="muted">Click a finding to jump to that moment</span></h2>
        <div class="findings">${findings}</div>
      </section>

      <section class="section" aria-labelledby="stmt-h">
        <h2 class="section-h" id="stmt-h">Statement check</h2>
        ${stmt}
      </section>

      <section class="section" aria-labelledby="ask-h">
        <h2 class="section-h" id="ask-h">Ask the footage <span class="muted">Answers cite a finding, or say “not visible”</span></h2>
        <form class="ask" data-ask><input name="q" autocomplete="off" placeholder="Ask about the signals, the impact, the vehicles or the road" aria-label="Ask a question about the footage"><button class="btn" type="submit">${icon("ask", 14)}Ask</button></form>
        <div class="suggest">${SUGGEST.map((s) => `<button type="button" data-suggest="${esc(s)}">${esc(s)}</button>`).join("")}</div>
        <div class="answers" aria-live="polite"></div>
      </section>

      <section class="section" aria-labelledby="act-h">
        <h2 class="section-h" id="act-h">Activity</h2>
        <div class="activity">${activity}</div>
      </section>
    </div>

    <aside class="props" aria-label="Claim properties">
      <div>
        <h3>Properties</h3>
        <div class="prop"><span>Status</span><span>${statusGlyph(claim.status)}${esc(STATUS[claim.status].label)}</span></div>
        <div class="prop"><span>Decision</span><span>${decision(d.outcome, d.label)}</span></div>
        <div class="prop"><span>Fault</span><span>${esc(d.fault.label)} <span class="faint num">${d.fault.confidence.toFixed(2)}</span></span></div>
        <div class="prop"><span>Assignee</span><span>${avatar(claim.assignee)}<span class="trunc">${esc(claim.assignee)}</span></span></div>
        <div class="prop"><span>Fraud risk</span><span>${claim.fraud ? `<span class="chip fraud">${icon("flag", 11)}High</span>` : esc(claim.jev.fraud_risk.level[0].toUpperCase() + claim.jev.fraud_risk.level.slice(1))}</span></div>
        <div class="prop"><span>Reported</span><span class="trunc">${esc(fmt.date(claim.reportedAt))} via ${esc(claim.channel.toLowerCase())}</span></div>
      </div>
      <div>
        <h3>Policy</h3>
        <div class="prop"><span>Number</span><span class="num">${esc(p.id)}</span></div>
        <div class="prop"><span>Holder</span><span class="trunc">${esc(p.holder)}</span></div>
        <div class="prop"><span>Cover</span><span class="trunc">${esc(p.coverLabel)}</span></div>
        <div class="prop"><span>Vehicle</span><span class="trunc">${esc(p.vehicle.make)}, ${esc(p.vehicle.reg)}</span></div>
        <div class="prop"><span>Driver</span><span class="trunc">${esc(claim.driver)}</span></div>
        <div class="prop"><span>Excess</span><span class="num">${fmt.money(p.excessTotal)}</span></div>
        <div class="prop"><span>Add-ons</span><span class="trunc" title="${esc(addOns)}">${esc(addOns)}</span></div>
      </div>
      <div><h3>Location</h3><div class="map" aria-label="Map of ${esc(claim.place)}">${mapTiles(claim.lat, claim.lon)}</div></div>
      <div><h3>Hard-rule checks</h3><div class="checks">${checks}</div></div>
      <div><h3>Chain of custody</h3><div class="hashes">${hashes}</div></div>
      <div><h3>Decision record</h3>
        <details class="record"><summary>Branch <b>${esc(d.record.branch)}</b>, ${esc(d.record.mode)} answers, floor ${d.record.thresholds.floor} / reject ${d.record.thresholds.reject}</summary>
          <pre>${esc(JSON.stringify(d.record, null, 2))}</pre></details>
      </div>
    </aside>
  </div>
  </div>`;
}

export function mountClaim(root, claim, handlers) {
  const player = root.querySelector("#incident-player");
  const video = player.querySelector("video");
  const svg = player.querySelector(".overlay");
  const playBtn = player.querySelector("[data-play]");
  const fill = player.querySelector(".fill");
  const time = player.querySelector(".time");
  const dur = claim.footage.duration;

  const syncPlay = () => {
    playBtn.innerHTML = icon(video.paused ? "play" : "pause", 15);
    playBtn.setAttribute("aria-label", video.paused ? "Play (Space)" : "Pause (Space)");
  };
  video.addEventListener("play", syncPlay);
  video.addEventListener("pause", syncPlay);
  video.addEventListener("timeupdate", () => {
    fill.style.width = `${(video.currentTime / dur) * 100}%`;
    time.textContent = `${fmt.clock(video.currentTime)} / ${fmt.clock(dur)}`;
  });
  playBtn.addEventListener("click", () => (video.paused ? video.play() : video.pause()));
  player.querySelector("[data-scrub]").addEventListener("click", (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    video.currentTime = ((e.clientX - r.left) / r.width) * dur;
  });
  player.querySelector("[data-fs]").addEventListener("click", () => player.requestFullscreen?.());
  video.play().catch(() => syncPlay());

  const detsBtn = root.querySelector("[data-toggle-dets]");
  detsBtn.addEventListener("click", () => {
    const on = detsBtn.getAttribute("aria-pressed") !== "true";
    detsBtn.setAttribute("aria-pressed", String(on));
    svg.style.display = on ? "" : "none";
  });

  let locked = null;
  const highlight = (ids) => {
    svg.querySelectorAll("g.det").forEach((g) => g.classList.toggle("hot", ids.includes(g.dataset.det)));
    svg.classList.toggle("dim", ids.length > 0);
  };
  // Boxes belong to one frame, so they only show while the video is paused on it.
  const showAt = (t) => svg.querySelectorAll("g.det").forEach((g) => g.classList.toggle("at", t !== null && Math.abs(Number(g.dataset.t) - t) < 0.05));
  video.addEventListener("play", () => showAt(null));
  root.querySelectorAll(".finding").forEach((row) => {
    const ids = row.dataset.det ? row.dataset.det.split(",") : [];
    row.addEventListener("mouseenter", () => highlight(ids));
    row.addEventListener("focus", () => highlight(ids));
    row.addEventListener("mouseleave", () => highlight(locked ? locked.dataset.det.split(",").filter(Boolean) : []));
    row.addEventListener("click", () => {
      locked = locked === row ? null : row;
      root.querySelectorAll(".finding").forEach((r) => r.classList.toggle("is-on", r === locked));
      if (locked) {
        const t = Number(row.dataset.t);
        video.pause();
        video.currentTime = t;
        showAt(t);
      }
      highlight(locked ? ids : []);
    });
  });
  const locate = (fid) => {
    const row = root.querySelector(`.finding[data-fid="${fid}"]`);
    if (!row) return;
    if (locked !== row) row.click();
    player.scrollIntoView({ behavior: "smooth", block: "center" });
  };
  root.addEventListener("click", (e) => {
    const loc = e.target.closest("[data-locate]");
    if (loc) locate(loc.dataset.locate);
    const c = e.target.closest("[data-cite]");
    if (c) handlers.showCite(claim.citations[c.dataset.cite]);
    const copy = e.target.closest("[data-copy]");
    if (copy) navigator.clipboard?.writeText(copy.dataset.copy).then(() => toast("SHA-256 copied"));
    const act = e.target.closest("[data-act]");
    if (act) handlers.act(act.dataset.act);
    const nav = e.target.closest("[data-nav]");
    if (nav) handlers.step(Number(nav.dataset.nav));
  });

  const form = root.querySelector("[data-ask]");
  const answers = root.querySelector(".answers");
  const ask = async (question) => {
    if (!question.trim()) return;
    const item = document.createElement("div");
    item.className = "qa";
    item.innerHTML = `<div class="q">${esc(question)}</div><div class="a"><span class="skeleton" style="display:block;height:14px;width:60%"></span></div>`;
    answers.append(item);
    try {
      const r = await api.post(`/api/claims/${claim.id}/ask`, { question });
      const cites = r.citations.map((c) => `<button class="cite" data-locate="${esc(c.id)}">${icon(KIND_ICON[c.kind] || "eye", 11)}${esc(c.source)} · ${c.conf.toFixed(2)}</button>`).join("");
      item.innerHTML = `<div class="q">${esc(question)}</div><div class="a${r.grounded ? "" : " ungrounded"}">${esc(r.answer)}</div>
        <div class="foot">${esc(r.source)}, ${r.ms} ms${cites ? " · " + cites : ""}</div>`;
    } catch (err) {
      item.innerHTML = `<div class="q">${esc(question)}</div><div class="a ungrounded">The answer service did not respond. Try again.</div>`;
    }
  };
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    ask(form.q.value);
    form.q.value = "";
  });
  root.querySelectorAll("[data-suggest]").forEach((b) => b.addEventListener("click", () => ask(b.dataset.suggest)));

  loadNearby(root.querySelector("#nearby"), claim, handlers);
  return {
    togglePlay: () => (video.paused ? video.play() : video.pause()),
    toggleDets: () => detsBtn.click(),
    destroy: () => video.pause(),
  };
}

const stamp = () => Math.floor(Date.now() / 60000);

export function camTile(cam, distance) {
  return `
    <button class="cam-tile" data-cam="${esc(cam.id)}" aria-label="Open live camera ${esc(cam.name)}">
      <img class="frame" src="${esc(cam.image)}?t=${stamp()}" alt="" loading="lazy">
      <span class="meta"><span class="live-dot"></span><b>${esc(cam.name)}</b><span>${distance !== undefined ? fmt.dist(distance) : esc(cam.view || "TfL")}</span></span>
    </button>`;
}

async function loadNearby(el, claim, handlers) {
  try {
    const cams = await api.get(`/api/cams?near=${claim.lat},${claim.lon}&n=3`);
    if (!el.isConnected) return;
    el.innerHTML = cams.map((c) => camTile(c, c.distance)).join("") || `<p class="muted">No TfL camera nearby.</p>`;
    el.querySelectorAll("[data-cam]").forEach((b) => b.addEventListener("click", () => {
      const cam = cams.find((c) => c.id === b.dataset.cam);
      handlers.openCam(cam, claim.id);
    }));
    const timer = setInterval(() => {
      if (!el.isConnected) return clearInterval(timer);
      el.querySelectorAll("img.frame").forEach((img) => (img.src = img.src.replace(/\?t=\d+/, `?t=${stamp()}`)));
    }, 60000);
  } catch {
    el.innerHTML = `<p class="muted">The TfL camera feed did not respond.</p>`;
  }
}

// ---------------------------------------------------------------- cameras

export function camerasView(cams, claims, opts) {
  const available = cams.filter((c) => c.available);
  const tab = opts.q ? "search" : opts.tab || "near";
  const header = `
    <header class="vh">${menuBtn}
      <div class="vh-title">${icon("cctv", 15)}<span>Live cameras</span><span class="faint num">${available.length}</span></div>
      <div class="tabs" role="tablist">
        <a class="tab" role="tab" href="#/cameras" aria-selected="${tab === "near"}">Near claims</a>
        <a class="tab" role="tab" href="#/cameras?tab=all" aria-selected="${tab === "all"}">All London</a>
      </div>
      <div class="vh-actions"><span class="faint">Powered by TfL Open Data</span></div>
    </header>`;
  let body = "";
  if (tab === "search") {
    const q = opts.q.toLowerCase();
    const hits = available.filter((c) => c.name.toLowerCase().includes(q) || c.view.toLowerCase().includes(q)).slice(0, 48);
    body = hits.length
      ? `<div class="cam-group"><div class="cam-group-h">${hits.length} cameras match “${esc(opts.q)}”</div><div class="cam-grid">${hits.map((c) => camTile(c)).join("")}</div></div>`
      : `<div class="empty"><b>No camera matches “${esc(opts.q)}”.</b><span>Try a road name, such as Euston Rd or A406.</span></div>`;
  } else if (tab === "all") {
    const limit = opts.limit || 48;
    const sorted = [...available].sort((a, b) => a.name.localeCompare(b.name));
    body = `<div class="cam-grid">${sorted.slice(0, limit).map((c) => camTile(c)).join("")}</div>
      ${limit < sorted.length ? `<div style="display:grid;place-items:center;padding:20px"><button class="btn" data-more>Show 48 more of ${sorted.length - limit}</button></div>` : ""}`;
  } else {
    const order = opts.near ? [...claims].sort((a, b) => (a.id === opts.near ? -1 : b.id === opts.near ? 1 : 0)) : claims;
    body = order.map((c) => {
      const near = nearestTo(available, c.lat, c.lon, 4);
      return `<div class="cam-group"><div class="cam-group-h">${statusGlyph(c.status)}<span class="num">${esc(c.id)}</span><span class="muted">${esc(c.place)}, ${esc(c.area)}</span>
        <a href="#/claim/${esc(c.id)}">Open claim</a></div>
        <div class="cam-grid">${near.map((x) => camTile(x, x.distance)).join("")}</div></div>`;
    }).join("");
  }
  return `${header}<div class="view"><div class="cams-view">
    <div class="cams-toolbar"><div class="search-wrap">${icon("search", 14)}<input type="search" data-cam-search placeholder="Search ${available.length} cameras by road" value="${esc(opts.q || "")}" aria-label="Search cameras"></div>
      <span class="note">Stills refresh every 5 to 8 minutes. Each camera has a 10 s clip. Images are shown uncropped.</span></div>
    ${body}</div></div>`;
}

function distanceM(lat1, lon1, lat2, lon2) {
  const r = 6371000;
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dp = p2 - p1;
  const dl = ((lon2 - lon1) * Math.PI) / 180;
  const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return Math.round(2 * r * Math.asin(Math.sqrt(a)));
}

export function nearestTo(cams, lat, lon, n) {
  return cams.map((c) => ({ ...c, distance: distanceM(lat, lon, c.lat, c.lon) })).sort((a, b) => a.distance - b.distance).slice(0, n);
}

export function camDialog(cam, claims, claimId) {
  const claim = claims.find((c) => c.id === claimId);
  const options = claims.map((c) => `<option value="${esc(c.id)}"${c.id === claimId ? " selected" : ""}>${esc(c.id)} · ${esc(c.place)}</option>`).join("");
  return `
  <div class="dialog" role="dialog" aria-modal="true" aria-label="Live camera ${esc(cam.name)}">
    <div class="dialog-h"><span class="live-dot"></span>${esc(cam.name)} <span class="muted">${esc(cam.view)}</span>
      <button class="icon-btn" data-close aria-label="Close (Esc)">${icon("x")}</button></div>
    <div class="dialog-body">
      <div>
        <div class="player" id="cam-player">
          <video src="${esc(cam.video || "")}" poster="${esc(cam.image)}?t=${stamp()}" muted playsinline loop autoplay></video>
        </div>
        <p class="faint" style="margin:8px 0 0" data-cam-caption>Latest 10 s clip from Transport for London, shown uncropped. Powered by TfL Open Data.</p>
      </div>
      <div class="cam-side">
        <div class="kv"><span>Camera</span><b class="num">${esc(cam.id)}</b></div>
        <div class="kv"><span>Refresh</span><b>Every 5 to 8 min</b></div>
        <div class="kv"><span>Position</span><b class="num">${cam.lat.toFixed(4)}, ${cam.lon.toFixed(4)}</b></div>
        ${claim ? `<div class="kv"><span>From ${esc(claim.id)}</span><b>${fmt.dist(distanceM(claim.lat, claim.lon, cam.lat, cam.lon))}</b></div>` : ""}
        <button class="btn" data-scan>${icon("scan", 14)}Scan the latest still</button>
        <div class="counts" data-counts></div>
        <label class="muted" for="attach-to" style="margin-top:6px">Attach the still to a claim</label>
        <select id="attach-to">${options}</select>
        <button class="btn btn-primary" data-attach>${icon("paperclip", 14)}Attach as evidence</button>
        <p class="faint" style="margin:0">The still is hashed with SHA-256 and added to the claim's chain of custody.</p>
      </div>
    </div>
  </div>`;
}

export function mountCamDialog(root, cam, handlers) {
  const player = root.querySelector("#cam-player");
  const counts = root.querySelector("[data-counts]");
  root.querySelector("[data-scan]").addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    btn.innerHTML = `${icon("scan", 14)}Scanning…`;
    try {
      const r = await api.post(`/api/cams/${cam.id}/scan`);
      const boxes = r.detections.map((d) => {
        const [x, y, w, h] = [d.box[0] * 352, d.box[1] * 288, d.box[2] * 352, d.box[3] * 288];
        const text = `${d.label} ${d.conf.toFixed(2)}`;
        return `<g class="det hot"><rect class="box" x="${x}" y="${y}" width="${w}" height="${h}" rx="2"/>
          <rect class="tag" x="${x}" y="${Math.max(0, y - 13)}" width="${text.length * 5.2 + 6}" height="12" rx="2"/>
          <text x="${x + 3}" y="${Math.max(0, y - 13) + 9}" style="font-size:9px">${esc(text)}</text></g>`;
      }).join("");
      player.innerHTML = `<img src="${r.frame}" alt="Scanned still from ${esc(cam.name)}">
        <svg class="overlay" viewBox="0 0 352 288" preserveAspectRatio="none" aria-hidden="true">${boxes}</svg>`;
      root.querySelector("[data-cam-caption]").textContent =
        `Still taken by TfL at ${fmt.time(r.takenAt || r.fetchedAt)}, scanned at ${fmt.time(r.fetchedAt)}. Shown uncropped. Powered by TfL Open Data.`;
      const entries = Object.entries(r.counts);
      counts.innerHTML = r.source
        ? `${entries.length ? entries.map(([k, v]) => `<span class="chip">${v} ${esc(k)}${v > 1 && !k.endsWith("s") ? "s" : ""}</span>`).join("") : `<span class="chip">Nothing detected</span>`}
           <span class="faint" style="width:100%">${esc(r.source)}, ${r.ms} ms · SHA-256 ${r.sha256.slice(0, 10)}…</span>`
        : `<span class="faint">${esc(r.error)}</span>`;
    } catch {
      counts.innerHTML = `<span class="faint">The scan failed. The camera may be offline.</span>`;
    }
    btn.disabled = false;
    btn.innerHTML = `${icon("scan", 14)}Scan again`;
  });
  root.querySelector("[data-attach]").addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    const target = root.querySelector("#attach-to").value;
    btn.disabled = true;
    try {
      await handlers.attach(target, cam.id);
      toast(`Still attached to ${target}`);
    } finally {
      btn.disabled = false;
    }
  });
}
