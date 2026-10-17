import { incidentDialog, incidentsView, mountIncidentDialog, mountIncidents } from "./incidents.js";
import { api, esc, fmt, icon, POODLE_MARK, toast } from "./ui.js";
import { camDialog, camerasView, claimView, FILTERS, listView, mountCamDialog, mountClaim, visibleClaims } from "./views.js";

const state = {
  claims: [],
  health: null,
  watch: null,
  cams: null,
  cache: new Map(),
  selected: {},
  from: "inbox",
  route: null,
  claimCtl: null,
  viewCtl: null,
  camLimit: 48,
};

const app = document.querySelector(".app");
const sidebar = document.querySelector(".sidebar");
const main = document.querySelector("#main");

// ---------------------------------------------------------------- data

async function refreshClaims() {
  state.claims = await api.get("/api/claims");
}

async function loadCams() {
  if (!state.cams) state.cams = await api.get("/api/cams");
  return state.cams;
}

async function loadClaim(id, force = false) {
  if (force || !state.cache.has(id)) state.cache.set(id, await api.get(`/api/claims/${id}`));
  return state.cache.get(id);
}

// ---------------------------------------------------------------- sidebar

function renderSidebar() {
  const count = (f) => visibleClaims(state.claims, f).length;
  const r = state.route || {};
  const here = (name) => ((r.name === "list" && r.filter === name) || (r.name === "claim" && state.from === name) ? 'aria-current="page"' : "");
  const camsHere = r.name === "cameras" ? 'aria-current="page"' : "";
  const libHere = r.name === "incidents" ? 'aria-current="page"' : "";
  const w = state.watch || state.health?.watch;
  const libCount = !w ? ""
    : w.open ? `<span class="count hot" title="${w.open} open now, ${w.incidents} in the library">${w.open}</span>`
    : `<span class="count" title="${w.incidents} in the library">${w.incidents}</span>`;
  const svc = state.health?.services || [];
  const live = state.health?.mode === "live";
  sidebar.innerHTML = `
    <div class="ws"><span class="ws-mark">${POODLE_MARK}</span>Poodle<span class="ws-sub">Claims</span></div>
    <button class="search-btn" data-cmdk>${icon("search", 14)}<span>Search or jump to</span><kbd>⌘K</kbd></button>
    <nav class="nav" aria-label="Views">
      <a class="nav-item" href="#/inbox" ${here("inbox")}>${icon("inbox", 15)}Inbox<span class="count">${count("inbox")}</span></a>
      <a class="nav-item" href="#/ready" ${here("ready")}>${icon("ready", 15)}Ready to settle<span class="count">${count("ready")}</span></a>
      <a class="nav-item" href="#/all" ${here("all")}>${icon("layers", 15)}All claims<span class="count">${count("all")}</span></a>
      <a class="nav-item" href="#/fraud" ${here("fraud")}>${icon("flag", 15)}Fraud flags<span class="count${count("fraud") ? " hot" : ""}">${count("fraud")}</span></a>
      <div class="nav-label">Monitoring</div>
      <a class="nav-item" href="#/cameras" ${camsHere}>${icon("cctv", 15)}Live cameras<span class="live-dot" title="Live TfL feed"></span></a>
      <a class="nav-item" href="#/incidents" ${libHere}>${icon("archive", 15)}Incident library${libCount}</a>
    </nav>
    <div class="services" aria-label="Services">
      <div class="services-h"><span>Services</span><span class="mode-chip${live ? " live" : ""}" title="${live ? "Every service is live" : "Services that are not connected run from recorded data"}">${live ? "Live" : "Replay mode"}</span></div>
      ${svc.map((s) => `<div class="svc" title="${esc(s.role)}: ${esc(s.detail)}"><span class="dot ${s.status}"></span><b>${esc(s.name)}</b><span>${esc(s.detail)}</span></div>`).join("")}
      <div class="attrib">Powered by TfL Open Data</div>
    </div>`;
}

// ---------------------------------------------------------------- router

function parseRoute() {
  const raw = location.hash.replace(/^#\/?/, "");
  const [path, query = ""] = raw.split("?");
  const params = Object.fromEntries(new URLSearchParams(query));
  const [head, id] = path.split("/");
  if (head === "claim" && id) return { name: "claim", id };
  if (head === "cameras") return { name: "cameras", params };
  if (head === "incidents") return { name: "incidents", params };
  if (FILTERS[head]) return { name: "list", filter: head };
  return { name: "list", filter: "inbox" };
}

async function route() {
  state.claimCtl?.destroy();
  state.claimCtl = null;
  state.viewCtl?.destroy();
  state.viewCtl = null;
  app.classList.remove("nav-open");
  const r = parseRoute();
  state.route = r;
  renderSidebar();
  if (r.name === "list") return renderList(r.filter);
  if (r.name === "claim") return renderClaim(r.id);
  if (r.name === "cameras") return renderCameras(r.params);
  if (r.name === "incidents") return renderIncidents(r.params);
}

function renderList(filter) {
  state.from = filter;
  const list = visibleClaims(state.claims, filter);
  if (!list.some((c) => c.id === state.selected[filter])) state.selected[filter] = list[0]?.id;
  main.innerHTML = listView(state.claims, filter, state.selected[filter]);
  document.title = `${FILTERS[filter].title} · Poodle`;
  main.querySelectorAll(".row").forEach((row) => row.addEventListener("mouseenter", () => select(row.dataset.id, false)));
}

function select(id, scroll = true) {
  const filter = state.route.filter;
  state.selected[filter] = id;
  main.querySelectorAll(".row").forEach((row) => {
    const on = row.dataset.id === id;
    row.setAttribute("aria-selected", String(on));
    if (on && scroll) row.scrollIntoView({ block: "nearest" });
  });
}

function navList() {
  const list = visibleClaims(state.claims, state.from);
  return list.length ? list : visibleClaims(state.claims, "all");
}

async function renderClaim(id) {
  main.innerHTML = `<header class="vh"><div class="vh-title"><span class="crumb">${esc(FILTERS[state.from].title)}</span>${icon("chevronRight", 14)}<span>${esc(id)}</span></div></header>
    <div class="view"><div class="claim-main"><div class="skeleton" style="height:28px;width:50%;margin-bottom:16px"></div><div class="skeleton" style="aspect-ratio:16/9;max-width:820px"></div></div></div>`;
  let claim;
  try {
    claim = await loadClaim(id);
  } catch {
    main.innerHTML = `<div class="empty"><b>Claim ${esc(id)} was not found.</b><a class="btn" href="#/inbox">Back to the inbox</a></div>`;
    return;
  }
  if (state.route?.name !== "claim" || state.route.id !== id) return;
  let list = visibleClaims(state.claims, state.from);
  if (!list.some((c) => c.id === id)) {
    state.from = "all";
    list = visibleClaims(state.claims, "all");
  }
  const index = list.findIndex((c) => c.id === id);
  state.selected[state.from] = id;
  main.innerHTML = claimView(claim, { from: state.from, index, total: list.length });
  document.title = `${claim.id} · ${claim.title} · Poodle`;
  state.claimCtl = mountClaim(main, claim, {
    act: (action) => act(claim.id, action),
    step,
    openCam: (cam, claimId) => openCam(cam, claimId),
    showCite,
  });
}

function step(delta) {
  if (state.route?.name !== "claim") return;
  const list = visibleClaims(state.claims, state.from);
  const i = list.findIndex((c) => c.id === state.route.id);
  const next = list[(i + delta + list.length) % list.length];
  if (next) location.hash = `#/claim/${next.id}`;
}

async function renderCameras(params) {
  main.innerHTML = `<header class="vh"><div class="vh-title">${icon("cctv", 15)}Live cameras</div></header>
    <div class="view"><div class="cams-view"><div class="cam-grid">${'<div class="skeleton" style="aspect-ratio:352/288"></div>'.repeat(8)}</div></div></div>`;
  let cams;
  try {
    cams = await loadCams();
  } catch {
    main.innerHTML = `<div class="empty"><b>The TfL camera feed did not respond.</b><span>Check the network, then reload.</span></div>`;
    return;
  }
  if (state.route?.name !== "cameras") return;
  const draw = () => {
    main.innerHTML = camerasView(cams, state.claims, { ...params, limit: state.camLimit });
    document.title = "Live cameras · Poodle";
    const input = main.querySelector("[data-cam-search]");
    let t;
    input.addEventListener("input", () => {
      clearTimeout(t);
      t = setTimeout(() => {
        const q = input.value.trim();
        location.hash = q ? `#/cameras?q=${encodeURIComponent(q)}` : "#/cameras";
      }, 250);
    });
    if (params.q) {
      input.focus();
      input.setSelectionRange(input.value.length, input.value.length);
    }
    main.querySelector("[data-more]")?.addEventListener("click", () => {
      state.camLimit += 48;
      draw();
    });
    main.querySelectorAll("[data-cam]").forEach((b) => b.addEventListener("click", () => {
      openCam(cams.find((c) => c.id === b.dataset.cam), params.near);
    }));
  };
  draw();
}

async function renderIncidents(params) {
  main.innerHTML = `<header class="vh"><div class="vh-title">${icon("archive", 15)}Incident library</div></header>
    <div class="view"><div class="lib-top"><div class="skeleton" style="height:150px"></div></div></div>`;
  let data, watch;
  try {
    [data, watch] = await Promise.all([api.get("/api/incidents"), api.get("/api/watch")]);
  } catch {
    main.innerHTML = `<div class="empty"><b>The incident library did not load.</b><span>Check that the Poodle server is running, then reload.</span></div>`;
    return;
  }
  if (state.route?.name !== "incidents") return;
  state.watch = watch;
  renderSidebar();
  main.innerHTML = incidentsView(data, watch, params);
  document.title = "Incident library · Poodle";
  state.viewCtl = mountIncidents(main, data, watch, params, {
    openIncident,
    onWatch: (w) => {
      state.watch = w;
      renderSidebar();
    },
  });
}

async function openIncident(id) {
  let inc;
  try {
    inc = await api.get(`/api/incidents/${encodeURIComponent(id)}`);
  } catch {
    toast(`Incident ${id} was not found`);
    return;
  }
  openDialog(incidentDialog(inc), (root) => mountIncidentDialog(root, inc, {
    openCam: (cam) => openCam(cam),
    changed: () => state.viewCtl?.refresh?.(),
  }));
}

// ---------------------------------------------------------------- actions

async function act(id, action) {
  const updated = await api.post(`/api/claims/${id}/action`, { action, by: "You" });
  state.cache.set(id, updated);
  await refreshClaims();
  const words = { approve: "Recommendation confirmed", refer: "Referred to the SIU team", reopen: "Claim reopened", assign: "Assigned to you" };
  toast(`${words[action] || "Updated"}: ${id}`);
  route();
}

async function attach(claimId, camId) {
  const updated = await api.post(`/api/claims/${claimId}/attach`, { camId });
  state.cache.set(claimId, updated);
  if (state.route?.name === "claim" && state.route.id === claimId) {
    closeDialog();
    route();
  }
}

// ---------------------------------------------------------------- dialogs

let lastFocus = null;

function openDialog(html, onMount) {
  closeDialog();
  lastFocus = document.activeElement;
  const scrim = document.createElement("div");
  scrim.className = "scrim";
  scrim.innerHTML = html;
  scrim.addEventListener("mousedown", (e) => e.target === scrim && closeDialog());
  scrim.querySelector("[data-close]")?.addEventListener("click", closeDialog);
  document.body.appendChild(scrim);
  onMount?.(scrim);
  (scrim.querySelector("input, [data-close], button") || scrim).focus();
}

function closeDialog() {
  const scrim = document.querySelector(".scrim");
  if (!scrim) return;
  scrim.querySelectorAll("video").forEach((v) => v.pause());
  scrim.remove();
  lastFocus?.focus?.();
}

function openCam(cam, claimId) {
  if (!cam) return;
  openDialog(camDialog(cam, state.claims, claimId), (root) => mountCamDialog(root, cam, { attach }));
}

function showCite(c) {
  if (!c) return;
  openDialog(`<div class="dialog" role="dialog" aria-modal="true" aria-label="${esc(c.title)}" style="width:min(520px,calc(100vw - 32px))">
    <div class="dialog-h">${icon(c.kind === "rule" ? "road" : "doc", 15)}${esc(c.title)}<button class="icon-btn" data-close aria-label="Close (Esc)">${icon("x")}</button></div>
    <p style="margin:0;padding:16px 18px 20px;color:var(--text-1);font-size:14px">${esc(c.text)}</p>
    <p class="faint" style="margin:0;padding:0 18px 16px">${c.kind === "rule" ? "The Highway Code, gov.uk (Open Government Licence)." : "Synthetic demo policy wording."}</p></div>`);
}

function showKeys() {
  const rows = [
    ["Search or jump to", ["⌘", "K"]], ["Move down / up", ["J", "K"]], ["Open the selected claim", ["↵"]],
    ["Back to the list", ["Esc"]], ["Play or pause footage", ["Space"]], ["Show or hide detections", ["D"]],
    ["Approve the recommendation", ["⌘", "↵"]], ["Go to inbox / cameras / all / library", ["G", "I · C · A · L"]], ["Show shortcuts", ["?"]],
  ];
  openDialog(`<div class="dialog" role="dialog" aria-modal="true" aria-label="Keyboard shortcuts" style="width:min(460px,calc(100vw - 32px))">
    <div class="dialog-h">${icon("keyboard", 15)}Keyboard shortcuts<button class="icon-btn" data-close aria-label="Close (Esc)">${icon("x")}</button></div>
    <div class="keys">${rows.map(([l, k]) => `<span>${esc(l)}</span><span>${k.map((x) => `<kbd>${esc(x)}</kbd>`).join("")}</span>`).join("")}</div></div>`);
}

// ---------------------------------------------------------------- command menu

function commands(query) {
  const q = query.trim().toLowerCase();
  const items = [];
  const nav = [
    ["Inbox", "#/inbox", "inbox", "G I"], ["Ready to settle", "#/ready", "ready", "G R"], ["All claims", "#/all", "layers", "G A"],
    ["Fraud flags", "#/fraud", "flag", "G F"], ["Live cameras", "#/cameras", "cctv", "G C"],
    ["Incident library", "#/incidents", "archive", "G L"],
  ];
  nav.forEach(([label, href, ic, hint]) => items.push({ group: "Go to", label, icon: ic, hint, run: () => (location.hash = href) }));
  state.claims.forEach((c) => items.push({ group: "Claims", label: `${c.id}  ${c.title}`, sub: `${c.area} ${c.label}`, icon: "doc", hint: c.label, run: () => (location.hash = `#/claim/${c.id}`) }));
  if (state.route?.name === "claim") {
    const id = state.route.id;
    items.push({ group: "This claim", label: "Approve the recommendation", icon: "check", hint: "⌘↵", run: () => act(id, "approve") });
    items.push({ group: "This claim", label: "Open the evidence pack", icon: "download", run: () => window.open(`/api/claims/${id}/pack`, "_blank") });
    items.push({ group: "This claim", label: "Show or hide detections", icon: "eye", hint: "D", run: () => state.claimCtl?.toggleDets() });
  }
  items.push({ group: "Help", label: "Keyboard shortcuts", icon: "keyboard", hint: "?", run: showKeys });
  let out = q ? items.filter((it) => `${it.label} ${it.sub || ""} ${it.group}`.toLowerCase().includes(q)) : items;
  if (q.length >= 3 && state.cams) {
    state.cams.filter((c) => c.available && c.name.toLowerCase().includes(q)).slice(0, 5)
      .forEach((c) => out.push({ group: "Cameras", label: c.name, icon: "cctv", hint: "Live", run: () => openCam(c, state.route?.id) }));
  }
  return out.slice(0, 40);
}

function openCmdk() {
  loadCams().catch(() => {});
  openDialog(`<div class="cmdk" role="dialog" aria-modal="true" aria-label="Command menu">
    <input type="text" placeholder="Type a command, a claim or a road" aria-label="Command" role="combobox" aria-expanded="true" aria-controls="cmdk-list">
    <ul id="cmdk-list" role="listbox"></ul>
    <div class="foot"><span><kbd>↑</kbd> <kbd>↓</kbd> move</span><span><kbd>↵</kbd> run</span><span><kbd>Esc</kbd> close</span></div></div>`, (root) => {
    const input = root.querySelector("input");
    const ul = root.querySelector("ul");
    let items = [];
    let active = 0;
    const paint = () => {
      items = commands(input.value);
      active = Math.min(active, Math.max(0, items.length - 1));
      let group = "";
      ul.innerHTML = items.map((it, i) => {
        const head = it.group !== group ? `<li class="grp" role="presentation">${esc((group = it.group))}</li>` : "";
        return `${head}<li role="presentation"><button role="option" data-i="${i}" aria-selected="${i === active}">${icon(it.icon, 15)}<span>${esc(it.label)}</span>${it.hint ? `<span class="hint">${esc(it.hint)}</span>` : ""}</button></li>`;
      }).join("") || `<li class="grp">No match</li>`;
      ul.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: "nearest" });
    };
    const run = (i) => {
      const it = items[i];
      if (!it) return;
      closeDialog();
      it.run();
    };
    input.addEventListener("input", () => { active = 0; paint(); });
    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") { e.preventDefault(); active = (active + 1) % items.length; paint(); }
      if (e.key === "ArrowUp") { e.preventDefault(); active = (active - 1 + items.length) % items.length; paint(); }
      if (e.key === "Enter") { e.preventDefault(); run(active); }
    });
    ul.addEventListener("click", (e) => {
      const b = e.target.closest("[data-i]");
      if (b) run(Number(b.dataset.i));
    });
    ul.addEventListener("mousemove", (e) => {
      const b = e.target.closest("[data-i]");
      if (b && Number(b.dataset.i) !== active) { active = Number(b.dataset.i); paint(); }
    });
    paint();
  });
}

// ---------------------------------------------------------------- keyboard

let gPending = 0;

document.addEventListener("keydown", (e) => {
  const mod = e.metaKey || e.ctrlKey;
  if (mod && e.key.toLowerCase() === "k") {
    e.preventDefault();
    document.querySelector(".cmdk") ? closeDialog() : openCmdk();
    return;
  }
  if (document.querySelector(".scrim")) {
    if (e.key === "Escape") closeDialog();
    return;
  }
  const typing = /^(input|textarea|select)$/i.test(e.target.tagName) || e.target.isContentEditable;
  if (typing) {
    if (e.key === "Escape") e.target.blur();
    return;
  }
  const r = state.route;
  if (mod && e.key === "Enter" && r?.name === "claim") {
    e.preventDefault();
    const claim = state.cache.get(r.id);
    if (!claim || claim.status === "done") return;
    if (claim.decision.outcome !== "refer") act(r.id, "approve");
    else if (claim.assignee !== "You") act(r.id, "assign");
    return;
  }
  if (mod || e.altKey) return;
  if (Date.now() - gPending < 1200) {
    gPending = 0;
    const go = { i: "#/inbox", c: "#/cameras", a: "#/all", r: "#/ready", f: "#/fraud", l: "#/incidents" }[e.key.toLowerCase()];
    if (go) location.hash = go;
    return;
  }
  const key = e.key;
  if (key === "g") { gPending = Date.now(); return; }
  if (key === "?") { showKeys(); return; }
  if (r?.name === "list") {
    const list = visibleClaims(state.claims, r.filter);
    const i = list.findIndex((c) => c.id === state.selected[r.filter]);
    if (key === "j" || key === "ArrowDown") { e.preventDefault(); select(list[Math.min(list.length - 1, i + 1)]?.id); }
    if (key === "k" || key === "ArrowUp") { e.preventDefault(); select(list[Math.max(0, i - 1)]?.id); }
    if (key === "Enter" && state.selected[r.filter] && !e.target.closest("a, button")) location.hash = `#/claim/${state.selected[r.filter]}`;
  } else if (r?.name === "claim") {
    if (key === "j") step(1);
    if (key === "k") step(-1);
    if (key === "Escape") location.hash = `#/${state.from}`;
    if (key === " " && !e.target.closest("button, a")) { e.preventDefault(); state.claimCtl?.togglePlay(); }
    if (key === "d") state.claimCtl?.toggleDets();
  } else if (r?.name === "cameras" && key === "/") {
    e.preventDefault();
    main.querySelector("[data-cam-search]")?.focus();
  }
});

document.addEventListener("click", (e) => {
  if (e.target.closest("[data-cmdk]")) openCmdk();
  if (e.target.closest("[data-menu]")) app.classList.toggle("nav-open");
  if (app.classList.contains("nav-open") && !e.target.closest(".sidebar, [data-menu]")) app.classList.remove("nav-open");
});

window.addEventListener("hashchange", route);

// ---------------------------------------------------------------- boot

async function boot() {
  try {
    const [claims, health] = await Promise.all([api.get("/api/claims"), api.get("/api/health").catch(() => null)]);
    state.claims = claims;
    state.health = health;
  } catch {
    main.innerHTML = `<div class="empty"><b>The Poodle server is not running.</b><span>Start it with <code>uvicorn server.app:app --port 8080</code>, then reload.</span></div>`;
    return;
  }
  if (!location.hash) history.replaceState(null, "", "#/inbox");
  route();
  setInterval(async () => {
    state.health = await api.get("/api/health").catch(() => state.health);
    if (state.route?.name !== "incidents") state.watch = null;
    renderSidebar();
  }, 60000);
}

boot();
