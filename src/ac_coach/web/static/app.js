"use strict";

// --- állapot ------------------------------------------------------------------

const state = {
  connected: false,      // WebSocket
  game: "waiting",       // waiting | connected
  session: null,         // {car, track, length, map}
  ref: null,             // referencia-kör vagy null
  tick: null,            // utolsó élő adat
  trail: [],             // az elmúlt ~30 s: {d, speed, thr, brk}
};

const TRAIL_MAX = 600;
const TRACE_BACK_M = 300;
const TRACE_AHEAD_M = 700;
const $ = (id) => document.getElementById(id);

// --- segédfüggvények ----------------------------------------------------------

function fmtMs(ms) {
  if (!ms || ms <= 0 || ms >= 2147483647) return "–";
  const m = Math.floor(ms / 60000);
  const s = ((ms % 60000) / 1000).toFixed(3).padStart(6, "0");
  return `${m}:${s}`;
}

function signed(v, digits = 2) {
  return (v > 0 ? "+" : v < 0 ? "−" : "±") + Math.abs(v).toFixed(digits);
}

// p távolsága a d ponttól a pálya mentén, -L/2..L/2
function rel(p, d, L) {
  return ((p - d + 1.5 * L) % L) - L / 2;
}

function refAt(channel, d) {
  const r = state.ref;
  if (!r) return null;
  const arr = r[channel];
  const f = d / r.step;
  const i = Math.floor(f);
  if (i < 0) return arr[0];
  if (i >= arr.length - 1) return arr[arr.length - 1];
  return arr[i] + (arr[i + 1] - arr[i]) * (f - i);
}

function trackLength() {
  return state.session ? state.session.length : 0;
}

// --- WebSocket ----------------------------------------------------------------

function connect() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onopen = () => { state.connected = true; renderHeader(); };
  ws.onclose = () => {
    state.connected = false;
    renderHeader();
    setTimeout(connect, 1000);
  };
  ws.onmessage = (ev) => handle(JSON.parse(ev.data));
}

function handle(msg) {
  switch (msg.type) {
    case "status":
      state.game = msg.state;
      renderHeader();
      break;
    case "session":
      state.session = msg;
      state.trail = [];
      $("results").innerHTML = "";
      $("laps").innerHTML = "";
      renderHeader();
      mapDirty = true;
      break;
    case "reference":
      state.ref = msg.ref;
      renderHeader();
      mapDirty = true;
      break;
    case "tick":
      onTick(msg);
      break;
    case "lap":
      addLap(msg);
      break;
    case "zone":
      addZoneResult(msg);
      break;
  }
}

// --- élő adatok ---------------------------------------------------------------

function onTick(t) {
  state.tick = t;
  if (t.live && !t.pit) {
    state.trail.push({ d: t.d, speed: t.speed, thr: t.thr, brk: t.brk });
    if (state.trail.length > TRAIL_MAX) state.trail.shift();
  }
  renderTick();
  requestDraw();
}

function renderHeader() {
  const dot = $("conn");
  dot.className = "dot " + (!state.connected ? "" : state.game === "connected" ? "ok" : "waiting");
  const s = state.session;
  if (!state.connected) $("session").textContent = "Nincs kapcsolat a szerverrel...";
  else if (state.game !== "connected" || !s) $("session").textContent = "Várakozás az Assetto Corsára...";
  else $("session").textContent = `${s.car} @ ${s.track} (${Math.round(s.length)} m)`;

  const r = state.ref;
  $("ref-info").textContent = r
    ? `legjobb ${fmtMs(r.best_ms)} · elméleti ${fmtMs(r.theo_ms)} · ${r.zones.length} féktáv`
    : s ? "még nincs érvényes kör – rögzítés" : "";
}

function renderTick() {
  const t = state.tick;

  const delta = $("delta");
  if (t.delta === null) {
    delta.textContent = "–";
    delta.className = "delta";
  } else {
    delta.textContent = signed(t.delta);
    delta.className = "delta " + (t.delta <= 0 ? "good" : "bad");
  }
  $("lap").textContent = t.lap;
  $("lap-time").textContent = fmtMs(t.lap_ms);
  $("last-time").textContent = fmtMs(t.last_ms);
  $("best-time").textContent = fmtMs(t.best_ms);
  $("invalid").classList.toggle("hidden", !t.invalid);

  $("speed").textContent = Math.round(t.speed);
  $("gear").textContent = t.gear === -1 ? "R" : t.gear === 0 ? "N" : t.gear;
  $("thr").style.width = `${t.thr * 100}%`;
  $("brk").style.width = `${t.brk * 100}%`;

  const showRef = state.ref && t.live && !t.pit;
  const rs = showRef ? refAt("speed", t.d) : null;
  if (rs !== null) {
    const diff = t.speed - rs;
    $("ref-speed").innerHTML =
      `ref ${Math.round(rs)} km/h <span class="${diff >= 0 ? "good" : "bad"}">(${signed(diff, 0)})</span>`;
  } else {
    $("ref-speed").innerHTML = "&nbsp;";
  }
  setRefMark("thr-ref", showRef ? refAt("throttle", t.d) : null);
  setRefMark("brk-ref", showRef ? refAt("brake", t.d) : null);

  renderNext(t);
}

function setRefMark(id, v) {
  const el = $(id);
  if (v === null) { el.style.display = "none"; return; }
  el.style.display = "block";
  el.style.left = `calc(${v * 100}% - 1px)`;
}

function renderNext(t) {
  const title = $("next-title"), dist = $("next-dist"), bar = $("next-bar"), targets = $("next-targets");
  if (!t.next || !state.ref) {
    title.textContent = "–";
    dist.textContent = "–";
    dist.className = "big";
    bar.style.width = "0";
    targets.innerHTML = "";
    return;
  }
  const z = state.ref.zones[t.next.index - 1];
  const m = t.next.dist;
  title.textContent = `${z.index}. féktáv`;
  dist.textContent = `${Math.round(m)} m`;
  dist.className = "big" + (m < 30 ? " now" : m < 120 ? " near" : "");
  bar.style.width = `${Math.max(0, Math.min(1, 1 - m / 400)) * 100}%`;
  targets.innerHTML =
    `Fékerő <b>${Math.round(z.peak_brake * 100)}%</b> · ` +
    `<b>${Math.round(z.entry_speed_kmh)}</b> → <b>${Math.round(z.min_speed_kmh)}</b> km/h<br>` +
    `gáz a fékponttól <b>${Math.round(z.throttle_m - z.brake_m)} m</b>-re`;
}

// --- listák ---------------------------------------------------------------------

function prepend(listId, html, max) {
  const li = document.createElement("li");
  li.innerHTML = html;
  const list = $(listId);
  list.prepend(li);
  while (list.children.length > max) list.lastChild.remove();
}

function addZoneResult(r) {
  const t = r.time_diff === null ? "?" :
    `<span class="${r.time_diff <= 0 ? "good" : "bad"}">${signed(r.time_diff)} s</span>`;
  let brake;
  if (r.brake_diff === null) brake = "nem fékeztél";
  else if (Math.abs(r.brake_diff) < 3) brake = "fékpont pontos";
  else brake = `${Math.round(Math.abs(r.brake_diff))} m-rel ${r.brake_diff > 0 ? "később" : "korábban"}`;
  const speedCls = r.min_speed_diff >= 0 ? "good" : "bad";
  prepend("results",
    `<b>${r.index}.</b> ${t} · ${brake} · fék ${Math.round(r.peak * 100)}% ` +
    `<span class="muted">(${Math.round(r.ref_peak * 100)}%)</span> · min ${Math.round(r.min_speed)} ` +
    `<span class="${speedCls}">(${signed(r.min_speed_diff, 0)})</span>`, 14);
}

function addLap(l) {
  prepend("laps", `${fmtMs(l.ms)} ${l.valid ? "" : '<span class="bad">érvénytelen</span>'}`, 14);
}

// --- rajzolás ------------------------------------------------------------------

let drawPending = false;
let mapDirty = true;
let mapCache = null;   // {canvas, project}

function requestDraw() {
  if (drawPending) return;
  drawPending = true;
  requestAnimationFrame(() => {
    drawPending = false;
    drawTrace();
    drawMap();
  });
}

function fitCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    mapDirty = true;
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w, h };
}

// Pontsor rajzolása a sávban; a távolság-ugrásoknál megszakítja a vonalat.
function plotSeries(ctx, points, d, L, xOf, yOf, color, width, fill = null) {
  let prev = null;
  const segs = [];
  let seg = [];
  for (const p of points) {
    const r = rel(p.d, d, L);
    if (r < -TRACE_BACK_M || r > TRACE_AHEAD_M) { prev = null; if (seg.length) { segs.push(seg); seg = []; } continue; }
    if (prev !== null && (r < prev || r - prev > 50)) { if (seg.length) segs.push(seg); seg = []; }
    seg.push([xOf(r), yOf(p.v)]);
    prev = r;
  }
  if (seg.length) segs.push(seg);
  for (const s of segs) {
    if (fill !== null) {
      ctx.beginPath();
      ctx.moveTo(s[0][0], fill);
      for (const [x, y] of s) ctx.lineTo(x, y);
      ctx.lineTo(s[s.length - 1][0], fill);
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();
    } else {
      ctx.beginPath();
      s.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.stroke();
    }
  }
}

function refPoints(channel) {
  const r = state.ref;
  return r[channel].map((v, i) => ({ d: i * r.step, v }));
}

function drawTrace() {
  const { ctx, w, h } = fitCanvas($("trace"));
  ctx.clearRect(0, 0, w, h);
  const t = state.tick, L = trackLength();
  if (!t || !L) return;
  const d = t.d;

  const span = TRACE_BACK_M + TRACE_AHEAD_M;
  const xOf = (r) => ((r + TRACE_BACK_M) / span) * w;
  const speedH = h * 0.62, pedTop = speedH + 8, pedH = h - pedTop - 4;
  const maxSpeed = state.ref ? Math.max(...state.ref.speed) * 1.08 : 300;
  const ySpeed = (v) => speedH - (v / maxSpeed) * (speedH - 14);
  const yPed = (v) => pedTop + pedH - v * pedH;

  // rács
  ctx.strokeStyle = "#2a2f37";
  ctx.lineWidth = 1;
  ctx.fillStyle = "#8a919c";
  ctx.font = "11px system-ui";
  for (let v = 50; v < maxSpeed; v += 50) {
    ctx.beginPath(); ctx.moveTo(0, ySpeed(v)); ctx.lineTo(w, ySpeed(v)); ctx.stroke();
    ctx.fillText(v, 4, ySpeed(v) - 2);
  }
  ctx.beginPath(); ctx.moveTo(0, pedTop - 4); ctx.lineTo(w, pedTop - 4); ctx.stroke();

  // referencia
  if (state.ref) {
    plotSeries(ctx, refPoints("brake"), d, L, xOf, yPed, "rgba(255,77,77,0.25)", 0, yPed(0));
    plotSeries(ctx, refPoints("throttle"), d, L, xOf, yPed, "rgba(62,207,110,0.45)", 1.5);
    plotSeries(ctx, refPoints("speed"), d, L, xOf, ySpeed, "#9aa3ad", 2);

    // fékpontok
    for (const z of state.ref.zones) {
      const r = rel(z.brake_m, d, L);
      if (r < -TRACE_BACK_M || r > TRACE_AHEAD_M) continue;
      const x = xOf(r);
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = "rgba(255,176,32,0.8)";
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "#ffb020";
      ctx.font = "bold 13px system-ui";
      ctx.fillText(`${z.index}.`, x + 4, 14);
    }
  }

  // saját nyomvonal
  const trail = (key) => state.trail.map((p) => ({ d: p.d, v: p[key] }));
  plotSeries(ctx, trail("thr"), d, L, xOf, yPed, "#3ecf6e", 2);
  plotSeries(ctx, trail("brk"), d, L, xOf, yPed, "#ff4d4d", 2.5);
  plotSeries(ctx, trail("speed"), d, L, xOf, ySpeed, "#4fc3ff", 2.5);

  // autó
  const xc = xOf(0);
  ctx.strokeStyle = "#ffffff";
  ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.moveTo(xc, 0); ctx.lineTo(xc, h); ctx.stroke();
}

function buildMap(w, h) {
  const s = state.session;
  let xs = null, zs = null;
  if (s && s.map) { xs = s.map.x; zs = s.map.z; }
  else if (state.ref) { xs = state.ref.x; zs = state.ref.z; }
  if (!xs || !xs.length) return null;

  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minZ = Math.min(...zs), maxZ = Math.max(...zs);
  const pad = 18;
  const scale = Math.min((w - 2 * pad) / (maxX - minX || 1), (h - 2 * pad) / (maxZ - minZ || 1));
  const ox = (w - (maxX - minX) * scale) / 2, oz = (h - (maxZ - minZ) * scale) / 2;
  const project = (x, z) => [ox + (x - minX) * scale, oz + (z - minZ) * scale];

  const dpr = window.devicePixelRatio || 1;
  const c = document.createElement("canvas");
  c.width = Math.round(w * dpr);
  c.height = Math.round(h * dpr);
  const ctx = c.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.lineJoin = "round";
  ctx.lineCap = "round";

  ctx.beginPath();
  xs.forEach((x, i) => { const [px, pz] = project(x, zs[i]); i ? ctx.lineTo(px, pz) : ctx.moveTo(px, pz); });
  ctx.closePath();
  ctx.strokeStyle = "#3a4049";
  ctx.lineWidth = 7;
  ctx.stroke();

  // féktávok a referencia nyomvonalán
  const r = state.ref;
  if (r) {
    ctx.strokeStyle = "#ff4d4d";
    ctx.lineWidth = 4;
    ctx.fillStyle = "#ffb020";
    ctx.font = "bold 13px system-ui";
    for (const z of r.zones) {
      const i0 = Math.floor(z.brake_m / r.step), i1 = Math.min(r.x.length - 1, Math.ceil(z.brake_end_m / r.step));
      ctx.beginPath();
      for (let i = i0; i <= i1; i++) {
        const [px, pz] = project(r.x[i], r.z[i]);
        i === i0 ? ctx.moveTo(px, pz) : ctx.lineTo(px, pz);
      }
      ctx.stroke();
      const [lx, lz] = project(r.x[i0], r.z[i0]);
      ctx.fillText(`${z.index}`, lx + 7, lz - 7);
    }
  }
  return { canvas: c, project };
}

function drawMap() {
  const { ctx, w, h } = fitCanvas($("map"));
  if (mapDirty) {
    mapCache = buildMap(w, h);
    mapDirty = false;
  }
  ctx.clearRect(0, 0, w, h);
  if (!mapCache) return;
  ctx.drawImage(mapCache.canvas, 0, 0, w, h);
  const t = state.tick;
  if (t && t.live) {
    const [px, pz] = mapCache.project(t.x, t.z);
    ctx.beginPath();
    ctx.arc(px, pz, 7, 0, 2 * Math.PI);
    ctx.fillStyle = "#4fc3ff";
    ctx.fill();
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 2;
    ctx.stroke();
  }
}

window.addEventListener("resize", () => { mapDirty = true; requestDraw(); });
connect();
