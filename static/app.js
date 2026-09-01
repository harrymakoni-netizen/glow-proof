/* GlowProof front end.
   Talks to the existing FastAPI backend: /api/health, /api/analyze,
   /api/routine/{id}. No framework, no build step.

   Two things worth knowing before reading:

   1. The mask overlay is the signature moment. Perfect Corp returns mask
      image URLs on live responses, but not on fixtures - so synthMask()
      draws a plausible region bloom as an inline SVG when none is supplied.
      The whole flow is therefore demoable with no API calls, and swaps to
      real masks automatically the moment they appear.

   2. On arriving at the results view the overlay sequence AUTO-PLAYS once
      and settles on the worst concern. That is a demo decision, not an
      aesthetic one: scroll- or hover-driven reveals are hard to hit
      repeatably on camera, so the money shot happens identically every take
      while staying fully clickable.
*/

const $ = (id) => document.getElementById(id);
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;

const VIEWS = ["landing", "capture", "working", "results", "report"];
let stream = null, shotURL = null, stepTimer = null, clockTimer = null;
let current = null;      // latest analysis payload
let currentRoutine = null;
let cycleTimer = null;

function show(v) {
  VIEWS.forEach((n) => $("v-" + n).classList.toggle("on", n === v));
  window.scrollTo({ top: 0, behavior: "auto" });
}

/* ─────────── status ─────────── */

async function loadStatus() {
  try {
    const h = await (await fetch("/api/health")).json();
    const el = $("status");
    el.dataset.live = h.skin_live;
    $("status-text").textContent = h.skin_live
      ? "live analysis"
      : "sample data";
  } catch {
    $("status-text").textContent = "offline";
  }
}

/* ─────────── capture ─────────── */

async function openCamera() {
  $("cam-err").hidden = true;
  show("capture");
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 1440 }, height: { ideal: 1440 } },
      audio: false,
    });
    $("video").srcObject = stream;
  } catch (e) {
    $("cam-err").hidden = false;
    $("cam-err").textContent =
      "Camera unavailable (" + e.name + "). Browsers only allow camera access " +
      "over https or on localhost — use “Upload a photo” instead.";
  }
}

function closeCamera() {
  if (stream) stream.getTracks().forEach((t) => t.stop());
  stream = null;
}

/* Perfect Corp wants short side ≥480px, long side ≤4096, under 10MB. */
function toBlob(src, w, h) {
  const scale = Math.min(1, 1000 / Math.min(w, h));
  const c = document.createElement("canvas");
  c.width = Math.round(w * scale);
  c.height = Math.round(h * scale);
  c.getContext("2d").drawImage(src, 0, 0, c.width, c.height);
  return new Promise((r) => c.toBlob(r, "image/jpeg", 0.93));
}

/* ─────────── working ─────────── */

const STAGES = [["upload", 0], ["detect", 1100], ["measure", 3400], ["score", 6800]];

function runStages() {
  const t0 = performance.now();
  document.querySelectorAll(".stage-row").forEach((s) => (s.className = "stage-row"));
  clockTimer = setInterval(() => {
    const s = (performance.now() - t0) / 1000;
    $("clock").innerHTML = s.toFixed(1) + '<span style="font-size:1rem">s</span>';
  }, 80);

  let i = 0;
  (function advance() {
    if (i > 0) {
      const p = document.querySelector(`.stage-row[data-k="${STAGES[i - 1][0]}"]`);
      if (p) p.className = "stage-row done";
    }
    if (i >= STAGES.length) return;
    const c = document.querySelector(`.stage-row[data-k="${STAGES[i][0]}"]`);
    if (c) c.className = "stage-row active";
    const next = i + 1 < STAGES.length ? STAGES[i + 1][1] - STAGES[i][1] : 5000;
    i++;
    stepTimer = setTimeout(advance, next);
  })();
}

function stopStages() {
  clearTimeout(stepTimer);
  clearInterval(clockTimer);
  document.querySelectorAll(".stage-row").forEach((s) => (s.className = "stage-row done"));
}

async function begin(blob) {
  if (shotURL) URL.revokeObjectURL(shotURL);
  shotURL = URL.createObjectURL(blob);
  $("preview-working").src = shotURL;
  $("face-img").src = shotURL;
  $("work-err").hidden = true;
  show("working");
  runStages();

  const fd = new FormData();
  fd.append("file", blob, "selfie.jpg");

  let data;
  try {
    const r = await fetch("/api/analyze", { method: "POST", body: fd });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || "HTTP " + r.status);
    data = await r.json();
  } catch (e) {
    stopStages();
    $("work-err").hidden = false;
    $("work-err").textContent = "Analysis failed: " + e.message;
    return;
  }

  stopStages();
  current = data;
  $("split").classList.remove("no-photo");
  renderResults(data);
  show("results");
  playOverlays();
  loadRoutine(data.id);
}

/* ─────────── history ─────────── */

async function loadHistory() {
  try {
    const h = await (await fetch("/api/history")).json();
    if (!h.live || !h.scans.length) return;
    const list = $("recent-list");
    list.innerHTML = "";
    h.scans.forEach((s) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "recent-item";
      const when = s.created_at
        ? new Date(s.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })
        : "scan #" + s.id;
      b.innerHTML = `<span></span><span class="score"></span>`;
      b.querySelector("span").textContent = when;
      b.querySelector(".score").textContent = (s.overall ?? "—") + "/100";
      b.onclick = () => openPastScan(s.id);
      list.appendChild(b);
    });
    $("recent").hidden = false;
  } catch {
    /* history is additive to the core flow - fail silently */
  }
}

async function openPastScan(id) {
  let data;
  try {
    const r = await fetch("/api/scan/" + id);
    if (!r.ok) throw new Error("HTTP " + r.status);
    data = await r.json();
  } catch {
    return;
  }
  current = data;
  $("split").classList.add("no-photo");
  renderResults(data);
  show("results");
  loadRoutine(id);
}

/* ─────────── synthetic mask overlays ─────────── */

/* Face-relative regions, as fractions of the frame. Rough on purpose: they
   read as "this area was measured", which is what the overlay communicates. */
const REGIONS = {
  wrinkle:     [[.50, .26, .30, .09], [.29, .40, .11, .05], [.71, .40, .11, .05]],
  pore:        [[.50, .50, .10, .12], [.28, .52, .14, .11], [.72, .52, .14, .11]],
  texture:     [[.28, .54, .16, .14], [.72, .54, .16, .14]],
  acne:        [[.50, .72, .17, .09], [.30, .56, .13, .10], [.70, .56, .13, .10]],
  redness:     [[.50, .52, .12, .09], [.27, .55, .15, .11], [.73, .55, .15, .11]],
  dark_circle: [[.32, .44, .13, .06], [.68, .44, .13, .06]],
  oiliness:    [[.50, .30, .26, .08], [.50, .50, .11, .13]],
  age_spot:    [[.30, .50, .15, .12], [.70, .50, .15, .12]],
  radiance:    [[.50, .46, .52, .34]],
  moisture:    [[.50, .48, .48, .32]],
};

const RAMP = { attn: "#ff3b1d", watch: "#ff9a3c", good: "#5ddba4" };

function synthMask(key, band) {
  const spots = REGIONS[key] || REGIONS.radiance;
  const colour = RAMP[band] || RAMP.attn;
  const blobs = spots.map(([cx, cy, rx, ry], i) =>
    `<ellipse cx="${cx * 400}" cy="${cy * 520}" rx="${rx * 400}" ry="${ry * 520}" fill="url(#g${i})"/>`
  ).join("");
  const defs = spots.map((_, i) =>
    `<radialGradient id="g${i}"><stop offset="0%" stop-color="${colour}" stop-opacity=".85"/>` +
    `<stop offset="60%" stop-color="${colour}" stop-opacity=".35"/>` +
    `<stop offset="100%" stop-color="${colour}" stop-opacity="0"/></radialGradient>`
  ).join("");
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 520" preserveAspectRatio="xMidYMid slice">` +
    `<defs>${defs}</defs>${blobs}</svg>`;
  return "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
}

function band(v) { return v >= 75 ? "good" : v >= 60 ? "watch" : "attn"; }

function setOverlay(idx) {
  if (!current) return;
  const c = current.concerns[idx];
  if (!c) return;
  const src = (c.mask_urls && c.mask_urls[0]) || synthMask(c.key, band(c.ui_score));
  const mask = $("mask");
  mask.classList.remove("on");
  // let the fade-out land before swapping, so it cross-dissolves
  setTimeout(() => {
    $("mask-sharp").src = src;
    $("mask-soft").src = src;
    mask.classList.add("on");
    $("tint").style.background =
      `radial-gradient(60% 50% at 50% 45%, ${RAMP[band(c.ui_score)]}44, transparent 70%)`;
    $("tint").classList.add("on");
  }, REDUCED ? 0 : 220);

  document.querySelectorAll("#dots button").forEach((b, i) =>
    b.setAttribute("aria-current", String(i === idx)));
  document.querySelectorAll(".concern").forEach((b, i) =>
    b.setAttribute("aria-current", String(i === idx)));
}

/* Auto-play once through every concern, then rest on the worst one. */
function playOverlays() {
  clearTimeout(cycleTimer);
  if (!current || !current.concerns.length) return;

  const worst = current.concerns
    .map((c, i) => [c.ui_score, i])
    .sort((a, b) => a[0] - b[0])[0][1];

  if (REDUCED) { setOverlay(worst); return; }

  let i = 0;
  (function step() {
    setOverlay(i);
    i++;
    if (i < current.concerns.length) cycleTimer = setTimeout(step, 900);
    else cycleTimer = setTimeout(() => setOverlay(worst), 900);
  })();
}

/* ─────────── results ─────────── */

function countTo(el, target, suffix = "") {
  if (REDUCED) { el.textContent = target + suffix; return; }
  const t0 = performance.now(), dur = 1100;
  let settled = false;
  const settle = () => { if (!settled) { settled = true; el.textContent = target + suffix; } };
  // rAF is paused while the page is hidden, so a backgrounded tab would
  // otherwise leave the score frozen at 0 forever. Guarantee the end state.
  setTimeout(settle, dur + 120);
  (function tick(now) {
    if (settled) return;
    const p = Math.min(1, ((now || t0) - t0) / dur);
    el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3))) + suffix;
    if (p < 1) requestAnimationFrame(tick); else settle();
  })(t0);
}

function renderResults(d) {
  countTo($("overall"), d.overall || 0);
  $("skin-age").textContent = d.skin_age ? d.skin_age + " yrs" : "—";
  $("overall-note").textContent = d.overall_derived ? "averaged from concerns" : "";

  const wrap = $("concerns");
  wrap.innerHTML = "";
  d.concerns.forEach((c, i) => {
    const b = band(c.ui_score);
    const el = document.createElement("button");
    el.className = "concern";
    el.type = "button";
    el.setAttribute("aria-current", "false");
    el.innerHTML =
      `<div class="concern-top"><span class="concern-name"></span>` +
      `<span class="concern-score s-${b}"></span></div>` +
      `<div class="track"><i class="f-${b}"></i></div>` +
      `<div class="concern-blurb"></div>`;
    el.querySelector(".concern-name").textContent = c.label;
    el.querySelector(".concern-score").textContent = c.ui_score;
    el.querySelector(".concern-blurb").textContent = c.blurb;
    el.onclick = () => { clearTimeout(cycleTimer); setOverlay(i); };
    wrap.appendChild(el);
    setTimeout(() => { el.querySelector(".track i").style.width = c.ui_score + "%"; }, 120 + i * 90);
  });

  const dots = $("dots");
  dots.innerHTML = "";
  d.concerns.forEach((c, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.setAttribute("role", "tab");
    b.setAttribute("aria-label", c.label);
    b.setAttribute("aria-current", "false");
    b.onclick = () => { clearTimeout(cycleTimer); setOverlay(i); };
    dots.appendChild(b);
  });
}

/* ─────────── routine ─────────── */

function stepEl(s) {
  const el = document.createElement("div");
  el.className = "rstep";
  el.innerHTML =
    `<div class="rstep-top"><span class="n"></span><div style="flex:1;min-width:0">` +
    `<div class="act"></div><div class="kind"></div><div class="note"></div></div></div>`;
  el.querySelector(".n").textContent = String(s.order).padStart(2, "0");
  el.querySelector(".act").textContent = s.action;
  const kind = el.querySelector(".kind");
  if (s.product_type) kind.textContent = s.product_type; else kind.remove();
  el.querySelector(".note").textContent = s.note;

  if (s.product) {
    const a = document.createElement("a");
    a.className = "buy";
    a.href = s.product.link || "#";
    a.target = "_blank"; a.rel = "noopener noreferrer";
    a.innerHTML = `${s.product.thumbnail ? '<img alt="">' : ""}<div style="min-width:0">` +
                  `<div class="t"></div><div class="p"></div></div>`;
    if (s.product.thumbnail) a.querySelector("img").src = s.product.thumbnail;
    a.querySelector(".t").textContent = s.product.title;
    a.querySelector(".p").textContent =
      [s.product.price != null ? "$" + s.product.price.toFixed(2) : null, s.product.source]
        .filter(Boolean).join("  ·  ");
    el.appendChild(a);
  }
  return el;
}

async function loadRoutine(id) {
  let out;
  try {
    const r = await fetch("/api/routine/" + id);
    if (!r.ok) throw new Error("HTTP " + r.status);
    out = await r.json();
  } catch (e) {
    $("greeting").textContent = "Your routine could not be generated just now.";
    $("priorities").innerHTML = `<div class="err">${e.message}</div>`;
    return;
  }
  currentRoutine = out.routine;
  const rt = out.routine;

  $("greeting").textContent = rt.greeting;

  $("priorities").innerHTML = "";
  rt.priorities.forEach((p, i) => {
    const el = document.createElement("div");
    el.className = "prio";
    el.innerHTML = `<div class="mono rank"></div><h3></h3><p></p>`;
    el.querySelector(".rank").textContent = "Priority " + String(i + 1).padStart(2, "0");
    el.querySelector("h3").textContent = p.headline;
    el.querySelector("p").textContent = p.what_it_means;
    $("priorities").appendChild(el);
  });

  ["am", "pm"].forEach((k) => {
    const host = $(k);
    host.innerHTML = "";
    rt[k].forEach((s) => host.appendChild(stepEl(s)));
  });

  const rl = rt.red_light;
  const pr = $("protocol");
  pr.innerHTML = `<span class="mono">Red light</span>`;
  if (rl && rl.applicable) {
    pr.insertAdjacentHTML("beforeend",
      `<div class="lamp"><b></b></div>
       <div class="pmetrics">
         <div class="pmetric"><b class="m1"></b><span class="mono">minutes</span></div>
         <div class="pmetric"><b class="m2"></b><span class="mono">per week</span></div>
       </div>
       <p class="note" style="color:var(--lit-faint);font-size:.84rem;margin-top:16px"></p>`);
    pr.querySelector(".lamp b").textContent = rl.wavelength_nm || "633 nm";
    pr.querySelector(".m1").textContent = rl.minutes_per_session;
    pr.querySelector(".m2").textContent = rl.sessions_per_week;
    pr.querySelector(".note").textContent = rl.guidance;
  } else {
    pr.insertAdjacentHTML("beforeend",
      `<p style="color:var(--lit-faint);font-size:.9rem">Light therapy is not a
       priority for these results. The routine above does the work.</p>`);
  }

  if (!out.live) {
    $("priorities").insertAdjacentHTML("beforeend",
      `<div class="prio" style="opacity:.6"><div class="mono rank">Note</div>
       <p>Consultation generated offline${out.error ? " (" + out.error + ")" : ""}.</p></div>`);
  }
}

/* ─────────── report ─────────── */

function buildReport() {
  if (!current) return;
  $("rep-date").textContent = new Date().toLocaleDateString(undefined,
    { year: "numeric", month: "long", day: "numeric" });
  $("rep-overall").textContent = current.overall || "—";
  $("rep-age").textContent = current.skin_age ? current.skin_age : "—";
  $("rep-count").textContent = current.concerns.length;

  $("rep-rows").innerHTML = "";
  current.concerns.forEach((c) => {
    const row = document.createElement("div");
    row.className = "sheet-row";
    row.innerHTML = `<span></span><b></b>`;
    row.querySelector("span").textContent = c.label;
    row.querySelector("b").textContent = c.ui_score + " / 100";
    $("rep-rows").appendChild(row);
  });

  const rl = currentRoutine && currentRoutine.red_light;
  $("rep-protocol").innerHTML = rl && rl.applicable
    ? `<div class="sheet-row"><span>Wavelength</span><b>${rl.wavelength_nm}</b></div>
       <div class="sheet-row"><span>Session length</span><b>${rl.minutes_per_session} min</b></div>
       <div class="sheet-row"><span>Frequency</span><b>${rl.sessions_per_week} × per week</b></div>`
    : `<div class="sheet-row"><span>Light therapy</span><b>not indicated</b></div>`;
}

/* ─────────── wiring ─────────── */

$("go-camera").onclick = openCamera;
$("go-upload").onclick = () => $("file").click();
$("file").onchange = (e) => {
  const f = e.target.files[0];
  if (!f) return;
  const img = new Image();
  img.onload = async () => begin(await toBlob(img, img.naturalWidth, img.naturalHeight));
  img.src = URL.createObjectURL(f);
};
$("shoot").onclick = async () => {
  const v = $("video");
  if (!v.videoWidth) return;
  const b = await toBlob(v, v.videoWidth, v.videoHeight);
  closeCamera();
  begin(b);
};
$("cancel-camera").onclick = () => { closeCamera(); show("landing"); };
$("restart").onclick = () => { clearTimeout(cycleTimer); show("landing"); };
$("go-report").onclick = () => { buildReport(); show("report"); };
$("back-results").onclick = () => show("results");
$("print").onclick = () => window.print();

loadStatus();
loadHistory();
