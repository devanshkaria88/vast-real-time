import { api, conf, esc, fmt, icon, toast } from "./ui.js";

const KINDS = {
  collision: ["Collision", "impact"],
  breakdown: ["Breakdown", "alert"],
  emergency_response: ["Emergency response", "siren"],
  obstruction: ["Obstruction", "road"],
  flooding: ["Flooding", "weather"],
  fire_or_smoke: ["Fire or smoke", "flame"],
  person_in_road: ["Person in the road", "user"],
  other: ["Something unusual", "eye"],
  roadworks: ["Roadworks", "road"],
  congestion: ["Congestion", "car"],
  normal: ["Normal traffic", "car"],
  unclear: ["Cannot tell", "eye"],
};
const kindLabel = (k) => KINDS[k]?.[0] || k || "Unknown";
const kindIcon = (k) => KINDS[k]?.[1] || "eye";
const SEVERITY = ["Nothing to act on", "Worth noting", "Act now", "Major"];
const sevLevel = (s) => Math.max(0, Math.min(3, Math.round(s || 0)));
const SURFACE = { dry: "Dry road", wet: "Wet road", snow_or_ice: "Snow or ice", unclear: "Surface unclear" };
const LIGHT = { daylight: "Daylight", dusk: "Dusk or dawn", night_lit: "Night, street lights", dark: "Dark" };
const TRAFFIC = ["Empty road", "Light traffic", "Busy", "Queuing"];
const STATE_LABEL = { scanning: "Scanning", paused: "Paused", budget: "Budget reached", backoff: "Waiting for Jev", starting: "Starting", off: "Off" };

export const TABS = {
  all: { label: "All", test: (i) => i.review?.label !== "dismissed" },
  confirmed: { label: "Confirmed", test: (i) => i.confirmed && i.review?.label !== "dismissed" },
  dismissed: { label: "Dismissed", test: (i) => i.review?.label === "dismissed" },
};

const menuBtn = `<button class="icon-btn menu-btn" data-menu aria-label="Open navigation">${icon("menu")}</button>`;
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

function href(tab, kind) {
  const q = new URLSearchParams();
  if (tab && tab !== "all") q.set("tab", tab);
  if (kind) q.set("kind", kind);
  const query = q.toString();
  return `#/incidents${query ? `?${query}` : ""}`;
}

function conditions(c) {
  if (!c || !c.surface) return "Not recorded";
  return [SURFACE[c.surface], LIGHT[c.light], TRAFFIC[sevLevel(c.traffic)]].filter(Boolean).join(" · ");
}

const statusDot = (status) => status === "open"
  ? `<span class="inc-dot" title="Open now"></span>`
  : `<svg width="14" height="14" viewBox="0 0 14 14" class="glyph" aria-hidden="true"><circle cx="7" cy="7" r="5.5" fill="none" stroke="#62666d" stroke-width="1.5"/><path d="M4.6 7.1l1.6 1.6 3.2-3.3" fill="none" stroke="#8a8f98" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

// ---------------------------------------------------------------- library view

function tabs(data, tab) {
  return Object.entries(TABS).map(([k, t]) =>
    `<a class="tab" role="tab" href="${href(k)}" aria-selected="${k === tab}">${t.label}<span class="n">${data.items.filter(t.test).length}</span></a>`).join("");
}

export function incidentsView(data, watch, opts) {
  const tab = TABS[opts.tab] ? opts.tab : "all";
  return `
    <header class="vh">${menuBtn}
      <div class="vh-title">${icon("archive", 15)}<span>Incident library</span><span class="faint num" data-total>${data.items.length}</span></div>
      <div class="tabs" role="tablist" data-tabs>${tabs(data, tab)}</div>
      <div class="vh-actions"><a class="btn btn-ghost" href="/library/incidents.json" download="poodle-incidents.json" title="Every incident with its frames, clips and Jev answers">${icon("download", 14)}<span class="label">Export</span></a></div>
    </header>
    <div class="view">
      <div class="lib-top"><section class="scanner" data-scanner aria-label="Background scanner">${scannerPanel(watch)}</section></div>
      <div data-lib-list>${libraryList(data, watch, opts)}</div>
    </div>`;
}

export function scannerPanel(w) {
  if (w.state === "off") {
    return `<div class="scan-off">${icon("cctv", 18)}<div><b>The background scanner is off.</b><span>${esc(w.reason)}</span></div></div>`;
  }
  const paused = w.state === "paused";
  const open = w.rules.thresholds.open;
  const tiles = w.recent.map((r) => {
    const hot = r.incident >= open && w.rules.kinds.includes(r.kind);
    const dim = r.usable < w.rules.thresholds.usable;
    return `<div class="scan-tile${hot ? " hot" : ""}${dim ? " dim" : ""}" title="${esc(r.name)}: ${esc(kindLabel(r.kind))}, incident ${r.incident.toFixed(2)}, judged ${esc(fmt.time(r.at))}">
      <img src="/api/watch/frames/${esc(r.sha)}" alt="" onerror="this.style.visibility='hidden'">
      <span class="meta"><b>${esc(r.name)}</b><span class="k">${esc(kindLabel(r.kind))}</span><span class="p num">${r.incident.toFixed(2)}</span></span></div>`;
  }).join("");
  return `
    <div class="scan-h">
      <span class="scan-state ${esc(w.state)}"><i></i>${esc(STATE_LABEL[w.state] || w.state)}</span>
      <span class="scan-stats"><b class="num">${w.watching}</b> cameras · <b class="num">${w.perMinute}</b> frames a minute · <b class="num">${w.judgedToday.toLocaleString("en-GB")}</b> judged today · <b class="num">$${w.costToday.toFixed(2)}</b> of Jev today${w.budget ? ` of $${w.budget.toFixed(2)}` : ""}</span>
      <button class="btn" data-watch="${paused ? "resume" : "pause"}">${icon(paused ? "play" : "pause", 12)}${paused ? "Resume" : "Pause"}</button>
    </div>
    ${w.reason ? `<p class="scan-note">${esc(w.reason)}${w.lastError && w.state === "backoff" ? ` ${esc(w.lastError.text)}` : ""}</p>` : ""}
    <div class="scan-strip">${tiles || `<span class="faint">Waiting for the first frames.</span>`}</div>
    <p class="scan-rule">Jev (${esc(w.model || "jev")}) judges each new still once. An incident opens at <code>incident</code> ≥ ${open} with an incident kind, is confirmed by ${w.rules.confirmFrames} frames and clears after ${w.rules.clearFrames} quiet frames. Powered by TfL Open Data.</p>`;
}

function row(i) {
  const lvl = sevLevel(i.severity);
  const review = i.review?.label === "verified" ? `<span class="chip ok">${icon("check", 11)}Verified</span>`
    : i.review?.label === "dismissed" ? `<span class="chip">${icon("x", 11)}Dismissed</span>` : "";
  return `
    <button class="row inc-row" data-inc="${esc(i.id)}">
      ${statusDot(i.status)}
      <span class="id">${esc(i.id)}</span>
      <span class="t">${i.thumb ? `<img class="thumb" src="/library/frames/${esc(i.thumb)}" alt="" loading="lazy">` : `<span class="thumb"></span>`}
        ${icon(kindIcon(i.kind), 14)}<b>${esc(kindLabel(i.kind))}</b><span class="where">${esc(i.cam.name)}</span>${i.confirmed ? "" : `<span class="chip quiet">Unconfirmed</span>`}${review}</span>
      <span class="ev" title="${plural(i.frames, "still")}, ${plural(i.clips, "clip")}">${icon("eye", 12)}${i.frames}${i.clips ? `${icon("film", 12)}${i.clips}` : ""}</span>
      <span class="sev s${lvl}">${esc(SEVERITY[lvl])}</span>
      ${conf(i.peak)}
      <span class="age" title="First seen ${esc(fmt.date(i.openedAt))}">${fmt.ago(i.openedAt)}</span>
    </button>`;
}

function emptyState(w, tab) {
  if (tab === "dismissed") {
    return `<div class="empty">${icon("x", 22)}<b>Nothing dismissed.</b><span>Incidents you mark as not an incident land here. They are labelled examples for tuning the thresholds.</span></div>`;
  }
  if (w.state === "off") return `<div class="empty">${icon("archive", 22)}<b>No incidents yet.</b><span>Turn the scanner on to start filling the library.</span></div>`;
  return `<div class="empty">${icon("archive", 22)}<b>No incidents yet.</b><span>Jev has judged ${w.judgedToday.toLocaleString("en-GB")} frames from ${w.watching} cameras today. Anything it flags lands here.</span></div>`;
}

export function libraryList(data, w, opts) {
  const tab = TABS[opts.tab] ? opts.tab : "all";
  const inTab = data.items.filter(TABS[tab].test);
  const counts = {};
  inTab.forEach((i) => (counts[i.kind] = (counts[i.kind] || 0) + 1));
  const kinds = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const items = opts.kind ? inTab.filter((i) => i.kind === opts.kind) : inTab;
  const chips = kinds.length ? `<div class="kind-chips" aria-label="Filter by kind">${kinds.map(([k, n]) =>
    `<a class="kchip" href="${href(tab, opts.kind === k ? null : k)}" aria-pressed="${opts.kind === k}">${icon(kindIcon(k), 12)}${esc(kindLabel(k))}<span class="num">${n}</span></a>`).join("")}</div>` : "";
  if (!items.length) return chips + emptyState(w, tab);
  let body = "";
  for (const [status, title] of [["open", "Open now"], ["cleared", "Cleared"]]) {
    const group = items.filter((i) => i.status === status);
    if (!group.length) continue;
    body += `<div class="group-h">${statusDot(status)}<span>${title}</span><span class="n">${group.length}</span></div>`;
    body += group.map(row).join("");
  }
  return `${chips}<div class="list inc-list" role="list" aria-label="Incidents">${body}</div>`;
}

export function mountIncidents(root, data, watch, opts, handlers) {
  let version = watch.version;
  const scanner = root.querySelector("[data-scanner]");
  const list = root.querySelector("[data-lib-list]");
  const paint = (w) => {
    handlers.onWatch(w);
    scanner.innerHTML = scannerPanel(w);
  };
  const reload = async (w) => {
    const fresh = await api.get("/api/incidents");
    if (!root.isConnected) return;
    version = w.version;
    list.innerHTML = libraryList(fresh, w, opts);
    root.querySelector("[data-tabs]").innerHTML = tabs(fresh, TABS[opts.tab] ? opts.tab : "all");
    root.querySelector("[data-total]").textContent = fresh.items.length;
  };
  const refresh = async (force = false) => {
    try {
      const w = await api.get("/api/watch");
      if (!root.isConnected) return;
      paint(w);
      if (force || w.version !== version) await reload(w);
    } catch {
      // keep the last good view; the next tick retries
    }
  };
  root.addEventListener("click", async (e) => {
    const r = e.target.closest("[data-inc]");
    if (r) handlers.openIncident(r.dataset.inc);
    const ctl = e.target.closest("[data-watch]");
    if (ctl) {
      ctl.disabled = true;
      try {
        const w = await api.post("/api/watch", { action: ctl.dataset.watch });
        paint(w);
        toast(w.state === "paused" ? "Scanner paused. No Jev calls until you resume." : "Scanner resumed");
      } catch {
        ctl.disabled = false;
        toast("The scanner did not respond");
      }
    }
  });
  const timer = setInterval(refresh, 5000);
  return { destroy: () => clearInterval(timer), refresh: () => refresh(true) };
}

// ---------------------------------------------------------------- incident dialog

function bar(label, v, hot = false) {
  return `<div class="bar-row${hot ? " hot" : ""}"><span>${esc(label)}</span><span class="track"><i style="width:${Math.round(v * 100)}%"></i></span><span class="v num">${v.toFixed(2)}</span></div>`;
}

function answersPanel(f, rules) {
  const lvl = sevLevel(f.severity);
  const kinds = Object.entries(f.kinds || {}).slice(0, 3);
  return `
    <div class="answers-h">Jev on this frame</div>
    <div class="bars">
      ${bar("Incident", f.incident, f.incident >= rules.thresholds.open)}
      ${kinds.map(([k, p], n) => bar(kindLabel(k), p, n === 0 && rules.kinds.includes(k))).join("")}
    </div>
    <div class="bars">${bar("Damaged vehicle", f.damaged)}${bar("Lane blocked", f.blocked)}${bar("Emergency vehicle", f.emergency)}${bar("People in the road", f.people)}</div>
    <div class="kv"><span>Severity</span><b><span class="sev s${lvl}">${esc(SEVERITY[lvl])}</span> <span class="faint num">${f.severity.toFixed(2)}</span></b></div>
    <div class="kv"><span>Conditions</span><b>${esc(conditions(f))}</b></div>
    <div class="kv"><span>View usable</span><b class="num">${f.usable.toFixed(2)}</b></div>
    <div class="hash"><div><b>Still SHA-256</b><code title="${esc(f.sha256)}">${esc(f.sha256.slice(0, 12))}…${esc(f.sha256.slice(-6))}</code></div>
      <button class="icon-btn" data-copy="${esc(f.sha256)}" aria-label="Copy SHA-256">${icon("copy", 14)}</button></div>`;
}

function frameView(f, inc, rules) {
  const showBox = f.box && (f.boxConf ?? 0) >= rules.thresholds.box && f.incident >= rules.thresholds.keep;
  const b = f.box;
  const box = showBox
    ? `<svg class="overlay" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><rect class="jev-box" x="${(b.left * 100).toFixed(2)}" y="${(b.top * 100).toFixed(2)}" width="${((b.right - b.left) * 100).toFixed(2)}" height="${((b.bottom - b.top) * 100).toFixed(2)}" rx="1"/></svg>
       <div class="player-badges"><span class="chip">${icon("scan", 11)}Jev box ${f.boxConf.toFixed(2)}</span></div>`
    : "";
  return `<img src="/library/frames/${esc(f.file)}" alt="Still from ${esc(inc.cam.name)} at ${esc(fmt.time(f.takenAt))}">${box}`;
}

const frameCaption = (f) => `Still taken by TfL at ${fmt.time(f.takenAt)}, judged by Jev at ${fmt.time(f.judgedAt)}. Shown uncropped. Powered by TfL Open Data.`;
const clipCaption = (c) => `10 s clip from TfL${c.takenAt ? `, published ${fmt.time(c.takenAt)}` : ""}, saved ${fmt.time(c.savedAt)}. SHA-256 ${c.sha256.slice(0, 12)}…. Powered by TfL Open Data.`;

function props(inc) {
  const rows = [
    ["Status", inc.status === "open" ? `Open, last seen ${fmt.time(inc.lastSeenAt)}` : `Cleared at ${fmt.time(inc.clearedAt)}`],
    ["Confirmed", inc.confirmed ? `Yes, at ${fmt.time(inc.confirmedAt)}` : `Not yet: ${plural(inc.flagged, "flagged frame")}`],
    ["First seen", fmt.date(inc.openedAt)],
    ["Frames", `${inc.seen} seen, ${inc.frames.length} kept`],
    ...(inc.clearReason ? [["Why cleared", inc.clearReason]] : []),
    ["Camera", `${inc.cam.id}${inc.cam.view ? `, ${inc.cam.view}` : ""}`],
    ["Model", inc.model || "jev"],
  ];
  return rows.map(([k, v]) => `<div class="kv"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join("");
}

export function incidentDialog(inc) {
  const rules = inc.rules;
  const peak = inc.frames[inc.peakFrame] || inc.frames[0];
  const strip = [...inc.frames.map((f) => [f, fmt.time(f.takenAt)]), ...(inc.after ? [[inc.after, "After"]] : [])];
  const label = inc.review?.label;
  return `
  <div class="dialog inc-dialog" role="dialog" aria-modal="true" aria-label="${esc(kindLabel(inc.kind))} at ${esc(inc.cam.name)}">
    <div class="dialog-h">${icon(kindIcon(inc.kind), 15)}${esc(kindLabel(inc.kind))} <span class="muted trunc">${esc(inc.cam.name)} · ${esc(inc.id)}</span>
      <button class="icon-btn" data-close aria-label="Close (Esc)">${icon("x")}</button></div>
    <div class="dialog-body">
      <div>
        <div class="player" id="inc-player">${frameView(peak, inc, rules)}</div>
        <div class="filmstrip" aria-label="Frames and clips">
          ${strip.map(([f, text], n) => `<button class="film-frame" data-frame="${n}" aria-pressed="${f === peak}" aria-label="Show the still from ${esc(text)}"><img src="/library/frames/${esc(f.file)}" alt=""><span>${esc(text)}</span></button>`).join("")}
          ${inc.clips.map((c, n) => `<button class="film-frame clip" data-clip="${n}" aria-pressed="false" aria-label="Play clip ${n + 1}"><span class="film-ic">${icon("film", 16)}</span><span>Clip ${esc(c.takenAt ? fmt.time(c.takenAt) : String(n + 1))}</span></button>`).join("")}
        </div>
        <p class="faint" style="margin:8px 0 0" data-caption>${esc(frameCaption(peak))}</p>
      </div>
      <div class="cam-side">
        ${props(inc)}
        <div data-answers>${answersPanel(peak, rules)}</div>
        <div class="review-btns">
          <button class="btn" data-review="verified" aria-pressed="${label === "verified"}">${icon("check", 14)}Real incident</button>
          <button class="btn" data-review="dismissed" aria-pressed="${label === "dismissed"}">${icon("x", 14)}Not an incident</button>
        </div>
        <button class="btn" data-live>${icon("cctv", 14)}Open the live camera</button>
        <p class="faint" style="margin:0">Your review is stored with the incident and becomes a labelled example for tuning the thresholds.</p>
      </div>
    </div>
  </div>`;
}

export function mountIncidentDialog(root, inc, handlers) {
  const rules = inc.rules;
  const player = root.querySelector("#inc-player");
  const caption = root.querySelector("[data-caption]");
  const answers = root.querySelector("[data-answers]");
  const frames = [...inc.frames, ...(inc.after ? [inc.after] : [])];
  const pick = (btn) => root.querySelectorAll(".film-frame").forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
  root.addEventListener("click", async (e) => {
    const fb = e.target.closest("[data-frame]");
    if (fb) {
      const f = frames[Number(fb.dataset.frame)];
      player.innerHTML = frameView(f, inc, rules);
      caption.textContent = frameCaption(f);
      answers.innerHTML = answersPanel(f, rules);
      pick(fb);
    }
    const cb = e.target.closest("[data-clip]");
    if (cb) {
      const c = inc.clips[Number(cb.dataset.clip)];
      player.innerHTML = `<video src="/library/clips/${esc(c.file)}" muted playsinline autoplay loop controls></video>`;
      caption.textContent = clipCaption(c);
      pick(cb);
    }
    const copy = e.target.closest("[data-copy]");
    if (copy) navigator.clipboard?.writeText(copy.dataset.copy).then(() => toast("SHA-256 copied"));
    if (e.target.closest("[data-live]")) handlers.openCam(inc.cam);
    const rb = e.target.closest("[data-review]");
    if (rb) {
      const label = rb.getAttribute("aria-pressed") === "true" ? null : rb.dataset.review;
      try {
        const updated = await api.post(`/api/incidents/${inc.id}/review`, { label, by: "You" });
        inc.review = updated.review;
        root.querySelectorAll("[data-review]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.review === updated.review?.label)));
        toast(label === "verified" ? `${inc.id} marked as a real incident` : label === "dismissed" ? `${inc.id} marked as not an incident` : `Review cleared on ${inc.id}`);
        handlers.changed?.();
      } catch {
        toast("The review did not save. Try again.");
      }
    }
  });
}
