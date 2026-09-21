/* ═══════════════════════════════════════════════════════════════
   컷씬 공용 인터페이스 — 시작 화면 · 재생 시계 · HUD · 자막 · 엔드카드 (cs_ui.css 와 한 쌍)

   const player = CSUI.create({
     stage, audio, volume, duration,                    // 무대 요소(#cs), <audio>(없어도 됨), 음량, 전체 길이(초)
     theme: "ink" | "lumen", no, title, sub, tagline, meta: [[값, 이름]…], hero, variants: [{ label, href, on }],
     chapters: [{ t, name }], captions: [{ a, b, s }], capBlend: true(바탕 반대색) | false(그림자),
     prepare(),            // 재생 직전: 캔버스 크기·리소스 준비 (실패하면 throw)
     simulate(t),          // 상태를 t 시점으로 되감기/빨리감기 (탐색용, 그리지 않음)
     frame(t, dt, raw),    // 한 프레임 그리기
   });
   player.play({ sound, from, onDone })  ·  player.still(t)  ·  player.active()  ·  player.record()
   영상 저장: 1920x1080 녹화 캔버스에 화면 + 레터박스 + 자막 + 워터마크를 합쳐 MediaRecorder 로 실시간 녹화(mp4 우선, 안 되면 webm) → 자동 다운로드
   주소: ?autoplay=1&sound=0|1 (갤러리 iframe — 끝나면 parent 로 { type: "cutscene-done" }), &record=1 (바로 녹화), ?t=12.4 (정지 화면)
   키: Space 일시정지 · ←/→ 2초 탐색 · M 음소거 · F 전체화면 · Esc 닫기
   ═══════════════════════════════════════════════════════════════ */
(function () {
"use strict";
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const seg = (t, a, b) => clamp((t - a) / (b - a));
const eOut = (t) => 1 - Math.pow(1 - t, 3);
const fmt = (t) => { t = Math.max(0, Math.floor(t + 1e-6)); return Math.floor(t / 60) + ":" + String(t % 60).padStart(2, "0"); };
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const now = () => performance.now() / 1000;
const svg = (d) => `<svg viewBox="0 0 24 24" aria-hidden="true">${d}</svg>`;
const ICON = {
  back: svg('<path d="M20 12H5M11 6l-6 6 6 6"/>'),
  play: svg('<path class="f" d="M8 5.2v13.6a.6.6 0 0 0 .92.5l10.4-6.8a.6.6 0 0 0 0-1L8.92 4.7A.6.6 0 0 0 8 5.2z"/>'),
  pause: svg('<path class="f" d="M7 5h3.4v14H7zM13.6 5H17v14h-3.4z"/>'),
  sound: svg('<path d="M4 9.5v5h3.5L12 18.5v-13L7.5 9.5zM15.5 9a4.2 4.2 0 0 1 0 6M18 6.5a7.8 7.8 0 0 1 0 11"/>'),
  mute: svg('<path d="M4 9.5v5h3.5L12 18.5v-13L7.5 9.5zM16 9.5l5 5M21 9.5l-5 5"/>'),
  full: svg('<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>'),
  skip: svg('<path d="M5 5l8 7-8 7zM18 5v14"/>'),
  replay: svg('<path d="M4 12a8 8 0 1 0 2.6-5.9M4 4v4.5h4.5"/>'),
  down: svg('<path d="M12 4v11M7 10.5l5 5 5-5M5 19.5h14"/>'),
};
const ROMAN = ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ", "Ⅶ", "Ⅷ"];
const WATERMARK = "Discord  @sexy_cute__";            // 저장한 영상 왼쪽 아래에 찍히는 글자

function create(cfg) {
  const q = new URLSearchParams(location.search), embedded = !!q.get("autoplay");
  const stage = cfg.stage, audio = cfg.audio || null, DUR = cfg.duration, chapters = cfg.chapters || [], caps = cfg.captions || [];
  const gallery = cfg.gallery || "/cutscenes.html";
  let opts = {}, running = false, paused = false, on = false, time = 0, anchor = 0, raf = 0, useAudio = false, soundOn = true, idleTimer = 0, curCap = null, lastSec = -1, lastChap = -2, dragging = false, rec = null, actx = null, asrc = null;

  /* 음원은 Blob 으로 받아 둔다 — Range 요청을 지원하지 않는 서버(python http.server 등)에서는 <audio> 가 탐색 불가로 잡혀 currentTime 이 0으로 돌아가기 때문 */
  let playToken = 0;
  const audioReady = !audio ? Promise.resolve() : fetch(audio.currentSrc || audio.src).then((r) => { if (!r.ok) throw new Error("no audio"); return r.blob(); }).then((b) => { audio.src = URL.createObjectURL(b); }).catch(() => {});

  document.body.classList.add("csui-body");
  if (document.fonts && document.fonts.load) { document.fonts.load('400 20px "Noto Serif KR"', "陰陽광휘").catch(() => {}); document.fonts.load('800 20px "Pretendard"', "EQUINOX").catch(() => {}); }

  /* ── 시작 화면 ── */
  const land = document.createElement("div");
  land.className = "csui csui-land"; land.dataset.theme = cfg.theme || "ink"; land.style.setProperty("--hero", `url("${cfg.hero}")`);
  land.innerHTML = `
    <div class="csui-hero"></div>
    <div class="csui-top"><a href="${gallery}">${ICON.back}컷씬 목록</a><span>Cutscene ${esc(cfg.no || "")}</span></div>
    <div class="csui-main">
      <div class="csui-intro">
        <div class="csui-kicker">Cutscene — ${esc(cfg.no || "")}</div>
        <h1 class="csui-title">${esc(cfg.title)}</h1>
        <p class="csui-sub">${esc(cfg.sub || "")}</p>
        <p class="csui-tagline">${esc(cfg.tagline || "").replace(/\n/g, "<br>")}</p>
        <ul class="csui-meta">${(cfg.meta || []).map(([v, k]) => `<li><b>${esc(v)}</b>${esc(k)}</li>`).join("")}</ul>
        <div class="csui-actions">
          <button class="csui-play" data-act="start">${ICON.play}재생</button>
          <button class="csui-ghost" data-act="landsound" aria-pressed="true"></button>
          <button class="csui-ghost" data-act="landrec">${ICON.down}영상 저장</button>
          ${(cfg.variants || []).length ? `<div class="csui-seg">${cfg.variants.map((v) => `<a href="${v.href}"${v.on ? ' class="on"' : ""}>${esc(v.label)}</a>`).join("")}</div>` : ""}
        </div>
        <div class="csui-err" hidden></div>
      </div>
      ${chapters.length ? `<div class="csui-chapters"><h2>Chapters</h2>${chapters.map((c, i) => `<button data-from="${c.t}"><time>${fmt(c.t)}</time><span>${ROMAN[i] || i + 1}. ${esc(c.name)}</span><em>PLAY</em></button>`).join("")}</div>` : ""}
    </div>
    <div class="csui-keys"><span><kbd>Space</kbd>일시정지</span><span><kbd>←</kbd><kbd>→</kbd>탐색</span><span><kbd>M</kbd>음소거</span><span><kbd>F</kbd>전체화면</span><span><kbd>Esc</kbd>닫기</span></div>`;
  land.hidden = embedded;                              // 갤러리에서 열 때는 설명 화면을 아예 띄우지 않는다
  document.body.prepend(land);
  const errEl = land.querySelector(".csui-err"), landSound = land.querySelector('[data-act="landsound"]');
  const paintLandSound = () => { landSound.setAttribute("aria-pressed", String(soundOn)); landSound.innerHTML = (soundOn ? ICON.sound : ICON.mute) + (soundOn ? "사운드 켬" : "사운드 끔"); };
  paintLandSound();
  land.addEventListener("click", (e) => {
    const from = e.target.closest("[data-from]"), act = e.target.closest("[data-act]");
    if (from) play({ sound: soundOn, from: parseFloat(from.dataset.from) || 0 });
    else if (act && act.dataset.act === "start") play({ sound: soundOn });
    else if (act && act.dataset.act === "landsound") { soundOn = !soundOn; paintLandSound(); }
    else if (act && act.dataset.act === "landrec") record();
  });

  /* ── 무대: 레터박스 · 자막 · HUD · 엔드카드 ── */
  stage.classList.add("csui", "csui-stage"); stage.dataset.theme = cfg.theme || "ink";
  const wrap = document.createElement("div");
  wrap.innerHTML = `
    <div class="csui-bar top"></div><div class="csui-bar bottom"></div>
    <div class="csui-cap ${cfg.capBlend ? "blend" : "shade"}"><i></i><p></p></div>
    <div class="csui-toast"></div>
    <div class="csui-rec" hidden><i></i><span></span><button data-act="reccancel">취소</button></div>
    <div class="csui-mini"><i></i></div>
    <div class="csui-hud">
      <div class="csui-hud-row top">
        <button class="csui-ic" data-act="back" title="닫기 (Esc)">${ICON.back}</button>
        <div class="csui-id"><b>${esc(cfg.title)}</b><span>${esc(cfg.sub || "")}</span></div>
        <div class="csui-grow"></div>
        <button class="csui-ic" data-act="mute" title="음소거 (M)"></button>
        <button class="csui-ic" data-act="full" title="전체화면 (F)">${ICON.full}</button>
        <button class="csui-skip" data-act="skip">SKIP${ICON.skip}</button>
      </div>
      <div class="csui-hud-row bot">
        <button class="csui-ic" data-act="pause" title="일시정지 (Space)"></button>
        <div class="csui-chap"></div>
        <div class="csui-track"><div class="csui-fill"></div>${chapters.filter((c) => c.t > 0).map((c) => `<div class="csui-tick" style="left:${c.t / DUR * 100}%"></div>`).join("")}<div class="csui-knob"></div><div class="csui-tip"></div></div>
        <div class="csui-time"><b>0:00</b> / ${fmt(DUR)}</div>
      </div>
    </div>
    <div class="csui-end" hidden>
      <div class="csui-kicker">Fin</div><h2>${esc(cfg.title)}</h2><p>${esc(cfg.sub || "")}</p><p class="csui-note" hidden></p>
      <div class="csui-actions"><button class="csui-play" data-act="replay">${ICON.replay}다시 보기</button><button class="csui-ghost" data-act="rec">${ICON.down}영상 저장</button><button class="csui-ghost" data-act="home">처음 화면</button><a class="csui-ghost" href="${gallery}">컷씬 목록</a></div>
    </div>`;
  while (wrap.firstChild) stage.append(wrap.firstChild);
  const el = (s) => stage.querySelector(s);
  const capEl = el(".csui-cap"), capP = el(".csui-cap p"), capRule = el(".csui-cap i"), fill = el(".csui-fill"), knob = el(".csui-knob"), tip = el(".csui-tip"), mini = el(".csui-mini i"),
    timeB = el(".csui-time b"), chapEl = el(".csui-chap"), track = el(".csui-track"), toast = el(".csui-toast"), endEl = el(".csui-end"), btnMute = el('[data-act="mute"]'), btnPause = el('[data-act="pause"]'), recEl = el(".csui-rec"), recTxt = el(".csui-rec span"), noteEl = el(".csui-note");

  function paintIcons() { btnMute.innerHTML = soundOn ? ICON.sound : ICON.mute; btnPause.innerHTML = paused ? ICON.play : ICON.pause; }
  function sync(t) {                                   // HUD·자막을 t 시점에 맞춤 (시간에만 의존 → 탐색·정지 화면에서도 같게 보임)
    const k = clamp(t / DUR); fill.style.transform = mini.style.transform = `scaleX(${k})`; knob.style.left = k * 100 + "%";
    const s = Math.floor(t); if (s !== lastSec) { lastSec = s; timeB.textContent = fmt(Math.min(t, DUR)); }
    let ci = -1; for (let i = 0; i < chapters.length; i++) if (t >= chapters[i].t) ci = i;
    if (ci !== lastChap) { lastChap = ci; chapEl.innerHTML = ci < 0 ? "" : `<small>${ROMAN[ci] || ci + 1}</small>${esc(chapters[ci].name)}`; }
    let c = null; for (const x of caps) if (t >= x.a && t < x.b) { c = x; break; }
    if (c !== curCap) { curCap = c; capP.innerHTML = c ? c.s.split("\n").map((l) => `<span>${esc(l)}</span>`).join("") : ""; }
    if (!c) { capEl.style.opacity = 0; return; }
    const a = Math.min(seg(t, c.a, c.a + .5), 1 - seg(t, c.b - .5, c.b)), r = eOut(seg(t, c.a, c.a + 1.2)), ls = (.36 - .24 * r).toFixed(3) + "em";
    capEl.style.opacity = a.toFixed(3); capP.style.letterSpacing = ls; capP.style.paddingLeft = ls; capP.style.filter = r < .995 ? `blur(${((1 - r) * 5).toFixed(2)}px)` : "none"; capRule.style.transform = `scaleX(${r.toFixed(3)})`;
  }

  /* ── 영상 저장: 녹화 캔버스(1920x1080)에 화면·레터박스·자막·워터마크를 합쳐 실시간 녹화 ── */
  const RW = 1920, RH = 1080, SERIF = '"Noto Serif KR","Nanum Myeongjo","Batang","바탕",serif', SANS = '"Pretendard","Noto Sans KR","Malgun Gothic",system-ui,sans-serif';
  function paintRec(t) {
    const g = rec.rg, cvs = stage.querySelector("canvas"); g.globalCompositeOperation = "source-over"; g.globalAlpha = 1; g.filter = "none"; g.shadowBlur = 0;
    g.fillStyle = "#000"; g.fillRect(0, 0, RW, RH); if (cvs && cvs.width) g.drawImage(cvs, 0, 0, RW, RH);
    let c = null; for (const x of caps) if (t >= x.a && t < x.b) { c = x; break; }
    if (c) { const a = Math.min(seg(t, c.a, c.a + .5), 1 - seg(t, c.b - .5, c.b)), r = eOut(seg(t, c.a, c.a + 1.2)), px = RH * .035, lh = px * 1.7, lines = c.s.split("\n"), bottom = RH * .5 + RH * .37, top = bottom - lines.length * lh;
      if (!cfg.capBlend) { const gr = g.createLinearGradient(0, top - RH * .06, 0, bottom + RH * .07); gr.addColorStop(0, "rgba(0,0,0,0)"); gr.addColorStop(.45, `rgba(0,0,0,${.55 * a})`); gr.addColorStop(.6, `rgba(0,0,0,${.55 * a})`); gr.addColorStop(1, "rgba(0,0,0,0)"); g.fillStyle = gr; g.fillRect(0, top - RH * .06, RW, bottom - top + RH * .13); }
      g.globalAlpha = a; if (cfg.capBlend) g.globalCompositeOperation = "difference"; else { g.shadowColor = "rgba(0,0,0,.95)"; g.shadowBlur = 14; }
      g.fillStyle = cfg.capBlend ? "#fff" : "#f2f6fc"; g.fillRect(RW / 2 - RH * .035 * r, top - RH * .015, RH * .07 * r, 1.5);
      g.font = `400 ${px}px ${SERIF}`; g.textAlign = "center"; g.textBaseline = "middle"; try { g.letterSpacing = ((.36 - .24 * r) * px).toFixed(1) + "px"; } catch (e) { /* 구형 브라우저 */ }
      if (r < .995) g.filter = `blur(${((1 - r) * 5 * RH / 720).toFixed(1)}px)`; lines.forEach((ln, i) => g.fillText(ln, RW / 2 + (.36 - .24 * r) * px / 2, top + lh * (i + .5)));
      g.filter = "none"; g.shadowBlur = 0; g.globalAlpha = 1; g.globalCompositeOperation = "source-over"; try { g.letterSpacing = "0px"; } catch (e) { /* 무시 */ } }
    g.fillStyle = "#000"; g.fillRect(0, 0, RW, RH * .09); g.fillRect(0, RH * .91, RW, RH * .09);                       // 레터박스
    g.font = `600 ${RH * .024}px ${SANS}`; g.textAlign = "left"; g.textBaseline = "middle"; g.fillStyle = "rgba(255,255,255,.86)"; g.fillText(WATERMARK, RH * .04, RH * .955);   // 워터마크(왼쪽 아래)
    recTxt.textContent = `녹화 중 ${fmt(t)} / ${fmt(DUR)} — 이 탭을 계속 켜 두세요`;
  }
  function record() {
    if (rec) return;
    if (!window.MediaRecorder || !HTMLCanvasElement.prototype.captureStream) { errEl.hidden = false; errEl.textContent = "이 브라우저는 영상 저장을 지원하지 않습니다 (크롬·엣지 권장)."; return; }
    const mime = ["video/mp4;codecs=avc1.640028,mp4a.40.2", "video/mp4", "video/webm;codecs=vp9,opus", "video/webm;codecs=vp8,opus", "video/webm"].find((m) => MediaRecorder.isTypeSupported(m));
    const rc = document.createElement("canvas"); rc.width = RW; rc.height = RH; const stream = rc.captureStream(60), chunks = [];
    if (audio) { try { if (!actx) { actx = new (window.AudioContext || window.webkitAudioContext)(); asrc = actx.createMediaElementSource(audio); asrc.connect(actx.destination); }
      const dest = actx.createMediaStreamDestination(); asrc.connect(dest); actx.resume(); dest.stream.getAudioTracks().forEach((tr) => stream.addTrack(tr)); rec = { dest }; } catch (e) { console.warn("오디오 없이 녹화", e); } }
    const mr = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 12e6, audioBitsPerSecond: 192e3 });
    rec = Object.assign(rec || {}, { rc, rg: rc.getContext("2d"), mr, chunks, mime, cancelled: false });
    mr.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
    mr.onstop = () => { const r0 = rec; rec = null; if (r0.dest && asrc) { try { asrc.disconnect(r0.dest); } catch (e) { /* 무시 */ } }
      stage.classList.remove("rec"); recEl.hidden = true; stage.style.cssText = ""; try { if (!stage.hidden) cfg.prepare(); } catch (e) { /* 무시 */ }
      if (!r0.cancelled && chunks.length) { const ext = /mp4/.test(mime) ? "mp4" : "webm", a = document.createElement("a"); a.href = URL.createObjectURL(new Blob(chunks, { type: mime.split(";")[0] })); a.download = `${String(cfg.title).replace(/[^\w가-힣]+/g, "_")}.${ext}`; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 60000);
        noteEl.hidden = false; noteEl.textContent = `영상을 저장했습니다 (${ext.toUpperCase()})`; }
      if (embedded) setTimeout(post, 900); };
    const fit = () => { if (rec) stage.style.cssText = `inset:auto;left:50%;top:50%;width:${RW}px;height:${RH}px;transform:translate(-50%,-50%) scale(${Math.min(innerWidth / RW, innerHeight / RH)})`; };
    fit(); window.addEventListener("resize", fit); stage.classList.add("rec"); recEl.hidden = false; noteEl.hidden = true;
    play({ sound: true });
  }
  function stopRec(cancel) { if (!rec) return; rec.cancelled = !!cancel; if (rec.mr.state !== "inactive") rec.mr.stop(); else rec.mr.onstop(); }

  /* ── 시계 (음악이 있으면 음악 재생 위치에 부드럽게 맞춤) ── */
  function tick() {
    if (!running) return;
    if (useAudio && !audio.paused && audio.currentTime > 0) { const diff = (now() - audio.currentTime) - anchor; anchor += Math.abs(diff) > .25 ? diff : diff * .1; }
    const t = now() - anchor, raw = t - time, dt = clamp(raw, 0, .05); time = t;
    cfg.frame(t, dt, raw); sync(t); if (rec) paintRec(t);
    if (t >= DUR) return finish();
    raf = requestAnimationFrame(tick);
  }
  function startAudio(t) { if (!audio) { useAudio = false; return; } useAudio = true;
    try { audio.muted = !soundOn; audio.volume = cfg.volume == null ? 1 : cfg.volume; audio.currentTime = t; const p = audio.play(); if (p) p.catch(() => { useAudio = false; }); } catch (e) { useAudio = false; } }
  function play(o = {}) {
    opts = o; if (o.sound !== undefined) soundOn = o.sound !== false;
    endEl.hidden = true; errEl.hidden = true; stage.hidden = false; land.hidden = true; on = true;
    try { cfg.prepare(); } catch (e) { console.error(e); stage.hidden = true; land.hidden = embedded; on = false; errEl.hidden = false; errEl.textContent = "재생할 수 없습니다 — " + e.message; if (o.onDone) o.onDone(); if (embedded) post(); return; }
    halt();
    const from = clamp(o.from || 0, 0, DUR - .1), token = ++playToken;
    cfg.simulate(from); time = from; paused = false; lastSec = -1; lastChap = -2; curCap = undefined;
    cfg.frame(from, 0, 0); sync(from); paintIcons(); poke(); toast.className = "csui-toast";
    Promise.race([audioReady, new Promise((r) => setTimeout(r, 2500))]).then(() => {
      if (token !== playToken || !on) return;
      anchor = now() - from; running = true; startAudio(from); if (rec) { paintRec(from); if (rec.mr.state === "inactive") rec.mr.start(250); } cancelAnimationFrame(raf); raf = requestAnimationFrame(tick);
    });
  }
  function halt() { playToken++; running = false; cancelAnimationFrame(raf); if (audio) { try { audio.pause(); } catch (e) { /* 무시 */ } } }
  function finish() {
    halt(); paused = false; capEl.style.opacity = 0; const wasRec = !!rec; if (rec) setTimeout(() => stopRec(false), 120);
    if ((embedded && !wasRec) || opts.onDone) { stage.hidden = true; on = false; if (opts.onDone) opts.onDone(); if (embedded) post(); return; }
    endEl.hidden = false; stage.classList.remove("hud", "idle"); toast.className = "csui-toast";
  }
  function home() { halt(); paused = false; on = false; stage.hidden = true; land.hidden = false; paintLandSound(); if (document.fullscreenElement) document.exitFullscreen().catch(() => {}); }
  function post() { try { parent.postMessage({ type: "cutscene-done" }, location.origin); } catch (e) { /* 단독 실행 */ } }
  function togglePause() {
    if (!on || !endEl.hidden || rec) return;
    if (!paused) { halt(); paused = true; toast.innerHTML = ICON.pause; toast.className = "csui-toast hold"; }
    else { paused = false; running = true; anchor = now() - time; startAudio(time); toast.innerHTML = ICON.play; toast.className = "csui-toast"; void toast.offsetWidth; toast.className = "csui-toast pop"; raf = requestAnimationFrame(tick); }
    paintIcons(); poke();
  }
  function seek(t) {
    if (!on || !endEl.hidden || rec) return;
    t = clamp(t, 0, DUR - .05); cfg.simulate(t); time = t; anchor = now() - t;
    if (useAudio && !paused) { try { audio.currentTime = t; } catch (e) { /* 무시 */ } }
    if (paused) cfg.frame(t, 0, 0);
    sync(t); poke();
  }
  function toggleSound() { soundOn = !soundOn; if (audio) audio.muted = !soundOn; paintIcons(); poke(); }
  function toggleFull() { if (document.fullscreenElement) document.exitFullscreen().catch(() => {}); else if (document.documentElement.requestFullscreen) document.documentElement.requestFullscreen().catch(() => {}); poke(); }
  function close() { if (rec) stopRec(true); if (embedded || opts.onDone) { halt(); stage.hidden = true; on = false; if (opts.onDone) opts.onDone(); if (embedded) post(); } else home(); }

  /* HUD 는 움직임이 있을 때만 보이고 2.4초 뒤 사라짐 (일시정지 중에는 유지) */
  function poke() { if (!on || !endEl.hidden) return; stage.classList.add("hud"); stage.classList.remove("idle"); clearTimeout(idleTimer); idleTimer = setTimeout(() => { if (paused || dragging || stage.querySelector(".csui-hud-row :hover")) return poke(); stage.classList.remove("hud"); stage.classList.add("idle"); }, 2400); }
  stage.addEventListener("pointermove", poke); stage.addEventListener("pointerdown", poke);
  stage.addEventListener("click", (e) => {
    const act = e.target.closest("[data-act]");
    if (!act) { if (e.target.tagName === "CANVAS" || e.target === stage) togglePause(); return; }
    ({ back: close, skip: () => (embedded || opts.onDone ? close() : finish()), mute: toggleSound, full: toggleFull, pause: togglePause, replay: () => play({ sound: soundOn }), home, rec: record, reccancel: () => close() })[act.dataset.act]();
  });
  stage.addEventListener("dblclick", (e) => { if (e.target.tagName === "CANVAS") toggleFull(); });
  const trackT = (e) => { const r = track.getBoundingClientRect(); return clamp((e.clientX - r.left) / r.width) * DUR; };
  let seekRaf = 0, seekTo = 0;
  track.addEventListener("pointerdown", (e) => { dragging = true; track.classList.add("drag"); track.setPointerCapture(e.pointerId); seek(trackT(e)); });
  track.addEventListener("pointermove", (e) => { const t = trackT(e); tip.textContent = fmt(t); tip.style.left = t / DUR * 100 + "%"; if (!dragging) return; seekTo = t; if (!seekRaf) seekRaf = requestAnimationFrame(() => { seekRaf = 0; seek(seekTo); }); });
  const drop = () => { dragging = false; track.classList.remove("drag"); };
  track.addEventListener("pointerup", drop); track.addEventListener("pointercancel", drop);
  window.addEventListener("keydown", (e) => {
    if (!on || e.ctrlKey || e.metaKey || e.altKey) return;
    const k = e.key;
    if (k === " " || k === "k") { e.preventDefault(); togglePause(); }
    else if (k === "ArrowLeft") seek(time - 2); else if (k === "ArrowRight") seek(time + 2);
    else if (k === "m" || k === "M") toggleSound(); else if (k === "f" || k === "F") toggleFull();
    else if (k === "Escape") close(); else if ((k === "Enter" || k === "r") && !endEl.hidden) play({ sound: soundOn });
  });

  function still(t) { stage.hidden = false; land.hidden = true; on = false; cfg.prepare(); cfg.simulate(t); time = t; cfg.frame(t, 0, 0); sync(t); }
  const api = { play, still, seek, close, record, active: () => on, time: () => time, land, stage };

  stage.hidden = true;
  setTimeout(() => {                                   // 페이지 스크립트가 끝난 뒤에 주소 옵션 처리
    const qt = q.get("t");
    if (embedded) { land.hidden = true; if (q.get("record")) record(); else play({ sound: q.get("sound") !== "0" }); }
    else if (qt !== null) still(parseFloat(qt) || 0);
    else if (audio) audioReady.then(() => { const p = audio.play(); if (p) p.then(() => { audio.pause(); if (!on) play({ sound: true }); }).catch(() => { /* 자동 재생이 막힌 브라우저 → 설명 화면에서 시작 */ }); });   // 직접 열었을 때도 가능하면 설명 화면을 건너뛰고 바로 재생
  }, 0);
  return api;
}
window.CSUI = { create };
})();
