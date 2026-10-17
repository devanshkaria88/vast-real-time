export const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);

async function request(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body ?? {}) }),
};

const PATHS = {
  inbox: '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
  layers: '<path d="M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>',
  ready: '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
  flag: '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" x2="4" y1="22" y2="15"/>',
  cctv: '<path d="M16.75 12h3.632a1 1 0 0 1 .894 1.447l-2.034 4.069a1 1 0 0 1-1.708.134l-2.124-2.97"/><path d="M17.106 9.053a1 1 0 0 1 .447 1.341l-3.106 6.211a1 1 0 0 1-1.342.447L3.61 12.3a2.92 2.92 0 0 1-1.3-3.91L3.69 5.6a2.92 2.92 0 0 1 3.92-1.3z"/><path d="M2 19h3.76a2 2 0 0 0 1.8-1.1L9 15"/><path d="M2 21v-4"/><path d="M7 9h.01"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  chevronRight: '<path d="m9 18 6-6-6-6"/>',
  chevronUp: '<path d="m18 15-6-6-6 6"/>',
  chevronDown: '<path d="m6 9 6 6 6-6"/>',
  play: '<polygon points="7 4 20 12 7 20 7 4" fill="currentColor"/>',
  pause: '<rect x="14" y="4" width="4" height="16" rx="1" fill="currentColor"/><rect x="6" y="4" width="4" height="16" rx="1" fill="currentColor"/>',
  maximize: '<path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/>',
  scan: '<path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/><path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/><rect x="7" y="7" width="10" height="10" rx="1"/>',
  paperclip: '<path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
  shield: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
  shieldAlert: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="M12 8v4"/><path d="M12 16h.01"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  minus: '<path d="M5 12h14"/>',
  pin: '<path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/>',
  clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
  car: '<path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><path d="M9 17h6"/><circle cx="17" cy="17" r="2"/>',
  signal: '<rect x="8" y="2" width="8" height="20" rx="3"/><circle cx="12" cy="7" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="12" cy="17" r="1.4"/>',
  impact: '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>',
  road: '<path d="M12 13v8"/><path d="M12 3v3"/><path d="M4 6a1 1 0 0 0-1 1v5a1 1 0 0 0 1 1h13a2 2 0 0 0 1.152-.365l3.424-2.317a1 1 0 0 0 0-1.635l-3.424-2.318A2 2 0 0 0 17 6z"/>',
  weather: '<path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M16 14v6"/><path d="M8 14v6"/><path d="M12 16v6"/>',
  light: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
  motion: '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
  ask: '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>',
  copy: '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
  menu: '<line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="18" y2="18"/>',
  external: '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  refresh: '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
  keyboard: '<path d="M10 8h.01"/><path d="M12 12h.01"/><path d="M14 8h.01"/><path d="M16 12h.01"/><path d="M18 8h.01"/><path d="M6 8h.01"/><path d="M7 16h10"/><path d="M8 12h.01"/><rect width="20" height="16" x="2" y="4" rx="2"/>',
  eye: '<path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/>',
  user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  doc: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
};

export function icon(name, size = 16, extra = "") {
  return `<svg class="ic ${extra}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${PATHS[name] || ""}</svg>`;
}

export const STATUS = {
  triage: { label: "Triage", order: 0 },
  review: { label: "Needs review", order: 1 },
  ready: { label: "Ready to settle", order: 2 },
  done: { label: "Done", order: 3 },
};

export function statusGlyph(status, size = 14) {
  const s = `width="${size}" height="${size}" viewBox="0 0 14 14" class="glyph" aria-hidden="true"`;
  if (status === "triage") return `<svg ${s}><circle cx="7" cy="7" r="5.5" fill="none" stroke="#8a8f98" stroke-width="1.5" stroke-dasharray="2.2 2"/></svg>`;
  if (status === "review") return `<svg ${s}><circle cx="7" cy="7" r="5.5" fill="none" stroke="#f0bf00" stroke-width="1.5"/><path d="M7 3.5a3.5 3.5 0 0 1 0 7z" fill="#f0bf00"/></svg>`;
  if (status === "ready") return `<svg ${s}><circle cx="7" cy="7" r="5.5" fill="none" stroke="#27a644" stroke-width="1.5"/><path d="M7 3.5A3.5 3.5 0 1 1 3.5 7H7z" fill="#27a644"/></svg>`;
  return `<svg ${s}><circle cx="7" cy="7" r="6.25" fill="#5e6ad2"/><path d="M4.4 7.2l1.8 1.8 3.5-3.7" fill="none" stroke="#fff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}

export const decision = (outcome, label) => `<span class="decision ${esc(outcome)}"><i></i>${esc(label)}</span>`;

const AVATAR_COLOURS = ["#5e6ad2", "#27a644", "#fc7840", "#00b8cc", "#b08a2e", "#d4526e", "#4ea7fc"];

export const POODLE_MARK = `<svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" fill="#f4c39a"/><circle cx="16" cy="8" r="6" fill="#e3a57a"/><circle cx="7" cy="17" r="5" fill="#e3a57a"/><circle cx="25" cy="17" r="5" fill="#e3a57a"/><ellipse cx="16" cy="20" rx="8" ry="7" fill="#ffe8d6"/><circle cx="13" cy="18" r="1.6" fill="#2c2420"/><circle cx="19" cy="18" r="1.6" fill="#2c2420"/><ellipse cx="16" cy="22" rx="2" ry="1.4" fill="#3d2c28"/></svg>`;

export function avatar(name) {
  if (!name || name === "Unassigned") return `<span class="avatar none" title="Unassigned"></span>`;
  if (name === "Poodle") return `<span class="avatar bot" title="Poodle (automatic)">${POODLE_MARK}</span>`;
  const initials = name.split(/\s+/).map((p) => p[0]).join("").slice(0, 2).toUpperCase();
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return `<span class="avatar" style="background:${AVATAR_COLOURS[h % AVATAR_COLOURS.length]}" title="${esc(name)}">${esc(initials)}</span>`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const pad = (n) => String(n).padStart(2, "0");

export const fmt = {
  money: (v) => (v === null || v === undefined ? "—" : `£${Number(v).toLocaleString("en-GB")}`),
  date: (iso) => {
    const d = new Date(iso);
    return `${d.getDate()} ${MONTHS[d.getMonth()]}, ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  },
  time: (iso) => {
    const d = new Date(iso);
    return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  },
  ago: (iso) => {
    const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
    if (s < 60) return "now";
    if (s < 3600) return `${Math.floor(s / 60)}m`;
    if (s < 86400) return `${Math.floor(s / 3600)}h`;
    return `${Math.floor(s / 86400)}d`;
  },
  dist: (m) => (m < 1000 ? `${m} m` : `${(m / 1000).toFixed(1)} km`),
  clock: (sec) => `${pad(Math.floor(sec / 60))}:${pad(Math.floor(sec % 60))}`,
  pct: (v) => `${Math.round(v * 100)}%`,
};

export function conf(value) {
  const low = value < 0.5;
  return `<span class="conf${low ? " low" : ""}" title="${low ? "Below the 0.5 confidence floor" : "Confidence"}"><span class="bar"><i style="width:${Math.round(value * 100)}%"></i></span>${value.toFixed(2)}</span>`;
}

export function toast(text) {
  document.querySelector(".toast")?.remove();
  const el = document.createElement("div");
  el.className = "toast";
  el.setAttribute("role", "status");
  el.innerHTML = `${icon("check", 15)}<span>${esc(text)}</span>`;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 2600);
}

export const POODLE_SVG = `
<svg class="poodle mood-watch" viewBox="0 0 200 180" aria-hidden="true">
  <g class="torso">
    <g class="tail"><circle class="fur" cx="40" cy="124" r="11"/><circle class="fur" cx="28" cy="108" r="16"/><circle class="fur-lite" cx="22" cy="100" r="7"/></g>
    <ellipse class="fur" cx="84" cy="126" rx="38" ry="28"/><circle class="fur" cx="62" cy="120" r="16"/><circle class="fur" cx="108" cy="122" r="22"/>
    <circle class="fur-lite" cx="104" cy="114" r="10"/><path class="curl" d="M70 112c8 6 10 12 4 16"/><path class="curl" d="M92 108c6 8 6 14 0 18"/>
    <ellipse class="fur" cx="98" cy="156" rx="13" ry="8"/><ellipse class="fur" cx="124" cy="158" rx="13" ry="8"/>
    <ellipse class="fur-lite" cx="94" cy="158" rx="5" ry="3"/><ellipse class="fur-lite" cx="120" cy="160" rx="5" ry="3"/>
  </g>
  <g class="head">
    <g class="ear ear-l"><circle class="fur-deep" cx="70" cy="96" r="16"/></g>
    <g class="ear ear-r"><circle class="fur-deep" cx="162" cy="90" r="15"/></g>
    <circle class="fur" cx="116" cy="74" r="38"/><circle class="fur" cx="116" cy="38" r="16"/><circle class="fur-lite" cx="110" cy="32" r="6"/>
    <circle class="bow" cx="132" cy="30" r="6"/><circle class="bow" cx="144" cy="32" r="5.5"/><circle class="bow-knot" cx="138" cy="33" r="3"/>
    <path class="curl" d="M96 58c8 4 12 10 6 16"/><path class="curl" d="M124 50c6 6 8 12 2 16"/>
    <ellipse class="face" cx="128" cy="82" rx="20" ry="15"/>
    <g class="eyes-open"><ellipse fill="#fff" cx="114" cy="72" rx="5.2" ry="6"/><ellipse fill="#fff" cx="136" cy="70" rx="5.2" ry="6"/>
      <circle class="pupil" cx="115.6" cy="73" r="3"/><circle class="pupil" cx="137.6" cy="71" r="3"/>
      <circle class="catch" cx="117" cy="71.4" r="1.1"/><circle class="catch" cx="139" cy="69.4" r="1.1"/></g>
    <g class="eyes-happy"><path class="mouth" d="M108 74c3-5 8-5 11 0"/><path class="mouth" d="M130 72c3-5 8-5 11 0"/></g>
    <ellipse class="cheek" cx="106" cy="88" rx="5" ry="3"/><ellipse class="cheek" cx="148" cy="86" rx="5" ry="3"/>
    <ellipse class="nose" cx="150" cy="82" rx="5" ry="3.6"/>
    <path class="mouth mouth-rest" d="M140 92c4 4 10 4 14-1"/><path class="mouth mouth-happy" d="M134 90c8 10 18 8 24-2"/>
    <path class="collar" d="M96 108c12 12 32 12 46-2"/>
  </g>
</svg>`;
