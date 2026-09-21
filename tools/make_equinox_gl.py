# -*- coding: utf-8 -*-
"""equinox_preview.html → equinox_gl.html (공용 cs_gl.js 파이프라인 위로 이식)"""
import io

src = r"C:\Users\rnjsg\dev\recover\public\equinox_preview.html"
dst = r"C:\Users\rnjsg\dev\recover\public\equinox_gl.html"
s = io.open(src, encoding="utf-8").read()


def rep(a, b):
    global s
    assert a in s, "NF: " + a[:80]
    s = s.replace(a, b, 1)


# ── 머리말/데모 문구
rep("<title>EQUINOX 컷씬 테스트 — 陰陽</title>", "<title>EQUINOX 컷씬 (WebGL) — 陰陽</title>")
rep("<h1>EQUINOX — 陰陽 컷씬 테스트</h1>", "<h1>EQUINOX — 陰陽 · WebGL 버전</h1>")
rep('''<p>음악(앞 20초)을 분석해서 박자에 맞춘 컷씬입니다. 90BPM · 3/4박, 11.02초에 레이어가 들어오는 지점을 "합일"의 순간으로 잡았어요.</p>''',
    '''<p>같은 연출을 GPU 파이프라인으로 올린 버전입니다. 먹이 번지는 듯한 경계, 바탕을 뒤집는 GPU 입자 수천 개, 블룸 · 갓레이 · 박자마다 출렁이는 충격파 · 색수차 · 필름 그레인, 한지/먹 질감.</p>''')
rep('<canvas id="cv"></canvas>', '<canvas id="glc"></canvas>\n  <canvas id="ui" style="z-index:2;pointer-events:none;mix-blend-mode:difference"></canvas>')
rep('<script src="/equinox_data.js"></script>', '<script src="/equinox_data.js"></script>\n<script src="/cs_gl.js"></script>')

# ── 캔버스: 2D 는 화면 밖 레이어, 화면에는 WebGL
rep('const cv = $("cv"), g = cv.getContext("2d"), bgm = $("bgm");',
    'const glc = $("glc"), ui = $("ui"), ug = ui.getContext("2d"), bgm = $("bgm");\nconst cv = document.createElement("canvas"), g = cv.getContext("2d");      // 2D 레이어 (텍스처로 올라감)')
rep("function resize() { DPR = Math.min(2, window.devicePixelRatio || 1); W = cv.clientWidth; H = cv.clientHeight; U = Math.min(W, H) / 10; cv.width = W * DPR; cv.height = H * DPR; }",
    '''let DPR_CAP = 1.5, slow = 0;
function resize() {
  DPR = Math.min(DPR_CAP, window.devicePixelRatio || 1); W = glc.clientWidth; H = glc.clientHeight; U = Math.min(W, H) / 10;
  const pw = Math.max(2, Math.round(W * DPR)), ph = Math.max(2, Math.round(H * DPR));
  glc.width = cv.width = ui.width = pw; glc.height = cv.height = ui.height = ph;
  initGL(); X.resize(pw, ph); X.free(RT.scene); X.free(RT.mask); RT.scene = X.target(pw, ph); RT.mask = X.target(pw >> 1, ph >> 1);
}''')

# ── draw(): 흔들림·확대·후처리는 셰이더로, 자막은 오버레이로
rep('''  const zoom = 1 + .05 * bar + .28 * pulse(t, DROP, .01, .5) + .12 * pulse(t, TITLE, .01, .4);
  const shake = U * (.35 * pulse(t, DROP, .02, .6) + .05 * bp + .2 * pulse(t, TITLE, .02, .4) + .06 * seg(t, BUILD + 1, DROP));
  const r0 = rng(Math.floor(t * 60));
  g.translate(W / 2 + (r0() - .5) * shake, H / 2 + (r0() - .5) * shake); g.scale(zoom, zoom);''',
    '''  g.translate(W / 2, H / 2);''')
rep('''  // 자막
  for (const c of CAPS) { const a = Math.min(seg(t, c.a, c.a + .6), 1 - seg(t, c.b - .6, c.b)); if (a > 0) text(c.s, 0, 3.35 * U, .44 * U, "", a); }
''', "")
i0 = s.index("  /* 후처리: 드롭 순간 전체 반전(1회)")
i1 = s.index("/* ── 재생 ── */")
s = s[:i0] + "}\n\n" + "@@GL@@\n\n" + s[i1:]

GL = r'''/* ═════════════════ WebGL 합성 ═════════════════ */
let X = null, P = {}, RT = {}, layerTex = null, seedVAO = null;
const FS_SCENE = `#version 300 es
precision highp float; in vec2 vUv; out vec4 o; uniform sampler2D uLayer, uMask; uniform vec2 uRes; uniform float uU, uT, uWarp;
${CSGL.NOISE}
void main(){
  vec2 p = vec2(vUv.x - .5, .5 - vUv.y) * uRes / uU;
  // 먹 번짐: 경계가 살짝 일렁이도록 표본 위치를 노이즈로 밀어 줌
  vec2 w = vec2(fbm(p * 1.3 + vec2(uT * .15, 3.)), fbm(p * 1.3 + vec2(7., -uT * .13))) - .5;
  vec2 uv = vUv + w * uWarp * uU / uRes;
  vec3 c = texture(uLayer, uv).rgb;
  float m = clamp(texture(uMask, vUv).r, 0., 1.);
  c = abs(c - m);                                              // GPU 입자는 바탕을 뒤집는다 (difference)
  float l = dot(c, vec3(.333));
  float paper = .93 + .07 * fbm(p * 2.6 + 11.), ink = fbm(p * .5 + vec2(uT * .02, 0.));
  c = c * mix(1., paper, smoothstep(.5, 1., l)) + vec3(.035, .03, .075) * pow(ink, 2.) * (1. - smoothstep(0., .4, l));   // 흰 곳엔 한지결, 검은 곳엔 먹 안개
  o = vec4(c * 1.2, 1.);
}`;
const VS_PART = `#version 300 es
precision highp float; layout(location = 0) in vec4 aSeed; out float vA;
uniform int uMode; uniform float uT, uT0, uU, uPow, uR0; uniform vec2 uRes, uOrigin;
void main(){
  vec2 pos; float size, a, age = uT - uT0;
  if (uMode == 0){                                                                       // 떠다니는 먹 티끌
    pos = (aSeed.xy * 2. - 1.) * vec2(10.5, 6.2) + vec2(sin(uT * .2 + aSeed.z * 6.28) * .5, cos(uT * .17 + aSeed.w * 6.28) * .4);
    size = .7 + aSeed.z * 1.3; a = (.2 + .4 * (.5 + .5 * sin(uT * (1. + aSeed.w * 2.) + aSeed.x * 30.))) * uPow;
  } else {
    if (age < 0.){ gl_Position = vec4(2., 2., 0., 1.); gl_PointSize = 0.; vA = 0.; return; }
    bool inkMode = uMode == 2;                                                           // 1: 빛살(빠르고 잘게) 2: 먹(느리고 굵게)
    float life = (inkMode ? 1.5 : .9) * (.4 + .6 * aSeed.w) * (uPow > 1.2 ? 1.8 : 1.), k = inkMode ? 2.6 : 1.4;
    float v0 = mix(inkMode ? .5 : 3., inkMode ? 7. : 17., aSeed.z * aSeed.z) * uPow, ang = aSeed.x * 6.2832 + age * (aSeed.y - .5) * (inkMode ? 2.2 : .5);
    float dist = v0 * (1. - exp(-k * age)) / k + (inkMode ? sqrt(aSeed.y) * 2.2 : uR0);
    pos = uOrigin + vec2(cos(ang), sin(ang)) * dist;
    a = clamp(1. - age / life, 0., 1.); size = (inkMode ? 2. + aSeed.y * 4. : .8 + aSeed.y * 1.5) * (.5 + .5 * a); a = inkMode ? smoothstep(0., .25, a) : a;
  }
  vec2 px = pos * uU; gl_Position = vec4(px.x / (uRes.x * .5), -px.y / (uRes.y * .5), 0., 1.); gl_PointSize = max(1., size * uU / 34.); vA = a;
}`;
const FS_PART = `#version 300 es
precision highp float; in float vA; out vec4 o;
void main(){ float d = length(gl_PointCoord - .5); float a = smoothstep(.5, .32, d) * vA; o = vec4(a, a, a, 1.); }`;
const FS_FINAL = `#version 300 es
precision highp float; in vec2 vUv; out vec4 o;
uniform sampler2D uScene, uBloom, uRaysTex; uniform vec2 uRes, uShake; uniform float uU, uT, uZoom, uCA, uBloomK, uFlash, uInvert, uFade; uniform vec4 uWaves[10];
${CSGL.NOISE}
void main(){
  vec2 uv = (vUv - .5) / uZoom + .5 + uShake;
  vec2 p = vec2(uv.x - .5, .5 - uv.y) * uRes / uU;
  for (int i = 0; i < 10; i++){ vec4 w = uWaves[i]; if (w.w == 0.) continue; vec2 dv = p - w.xy; float d = length(dv), wd = .3 + w.z * .07;
    float ring = exp(-pow((d - w.z) / wd, 2.)); vec2 off = dv / max(d, 1e-4) * ring * w.w; uv += vec2(off.x, -off.y) * uU / uRes; }
  vec2 dir = uv - .5; float ca = uCA * (.25 + length(dir) * 1.6);
  vec3 col = vec3(texture(uScene, uv + dir * ca).r, texture(uScene, uv).g, texture(uScene, uv - dir * ca).b);
  vec3 bl = texture(uBloom, uv).rgb; float inWhite = smoothstep(.3, .85, dot(bl, vec3(.333)));              // 블룸 값이 크면 = 넓은 흰 영역 안쪽
  col += (bl * uBloomK + texture(uRaysTex, uv).rgb) * (1. - inWhite);
  col = min(col, vec3(1.));
  col = mix(col, 1. - col, uInvert);                                                     // 드롭 순간 1회 전체 반전
  col = min(col + uFlash, vec3(1.));
  col = mix(vec3(.031, .027, .102), vec3(.965, .937, .875), col);                        // 검정 → 남빛, 흰색 → 상아
  col += (hash(gl_FragCoord.xy + fract(uT) * 91.7) - .5) * .04;
  float v = length((vUv - .5) * vec2(1., .85)); col *= 1. - smoothstep(.4, .98, v) * .6;
  o = vec4(max(col, 0.) * (1. - uFade), 1.);
}`;
function initGL() {
  if (X) return;
  X = CSGL.create(glc);
  P.scene = X.compile(CSGL.VS_FULL, FS_SCENE); P.part = X.compile(VS_PART, FS_PART); P.final = X.compile(CSGL.VS_FULL, FS_FINAL);
  const r = rng(808); seedVAO = X.seeds(12000, r); layerTex = X.canvasTexture();
}
function drawUI(t) {                                            // 자막: 블룸 밖 오버레이 (CSS mix-blend-mode: difference 로 바탕의 반대색)
  ug.setTransform(1, 0, 0, 1, 0, 0); ug.clearRect(0, 0, ui.width, ui.height); ug.setTransform(DPR, 0, 0, DPR, ui.width / 2, ui.height / 2);
  const fade = Math.max(1 - seg(t, 0, .25), seg(t, FADE, END));
  for (const c of CAPS) { const a = Math.min(seg(t, c.a, c.a + .6), 1 - seg(t, c.b - .6, c.b)) * (1 - fade); if (a <= 0) continue;
    ug.globalAlpha = a; ug.fillStyle = "#fff"; ug.font = `${.44 * U}px "Nanum Myeongjo","Batang","바탕",serif`; ug.textAlign = "center"; ug.textBaseline = "middle"; ug.fillText(c.s, 0, 3.35 * U); }
  ug.globalAlpha = 1;
}
let waveList = [];
function buildWaves() {
  waveList = [{ t0: DROP, x: 0, y: 0, r0: .5, sp: 12, dur: 1.5, str: .8 }, { t0: TITLE, x: 0, y: -1.5, r0: .5, sp: 13, dur: 1.4, str: .6 }];
  for (let bt = T0; bt < DROP - .1; bt += 2) waveList.push({ t0: bt, x: 0, y: 0, r0: .6, sp: 10, dur: .9, str: .16 });     // 1막: 마디 첫 박마다 잔물결
  for (let n = 3, bt = DROP + 3 * BEAT; bt < TITLE - .05; n += 3, bt = DROP + n * BEAT) waveList.push({ t0: bt, x: 0, y: 0, r0: 2.4, sp: 9, dur: .9, str: .3 });
  for (let n = 1, bt = DROP + BEAT; bt < TITLE - .05; n++, bt = DROP + n * BEAT) if (n % 3) waveList.push({ t0: bt, x: 0, y: 0, r0: 2.4, sp: 8, dur: .6, str: .12 });
}
function render(t) {
  draw(t); drawUI(t);
  const gl = X.gl, pw = glc.width, ph = glc.height, Ud = U * DPR, bp = beatPulse(t), bar = barPulse(t), cy = centerY(t) / U, titleK = eInOut(seg(t, TITLE, TITLE + .55));
  gl.disable(gl.DEPTH_TEST);
  // ① 입자 마스크 (가산) — 나중에 장면을 뒤집는 데 쓰임
  X.bind(RT.mask); gl.clearColor(0, 0, 0, 1); gl.clear(gl.COLOR_BUFFER_BIT); gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE);
  gl.useProgram(P.part.p); gl.bindVertexArray(seedVAO); const pu = P.part.u;
  gl.uniform2f(pu.uRes, pw, ph); gl.uniform1f(pu.uU, Ud); gl.uniform1f(pu.uT, t);
  const burst = (mode, t0, ox, oy, first, n, pow, life, r0) => { if (t < t0 || t > t0 + life) return; gl.uniform1i(pu.uMode, mode); gl.uniform1f(pu.uT0, t0); gl.uniform1f(pu.uPow, pow); gl.uniform1f(pu.uR0, r0); gl.uniform2f(pu.uOrigin, ox, oy); gl.drawArrays(gl.POINTS, first, n); };
  for (let n = 0, bt = T0; bt < DROP - .05; n++, bt = T0 + n * BEAT) { const [ox, oy] = orbPos(bt, n % 2 === 0); burst(1, bt, ox / U, oy / U, (n * 733) % 10000, 130, .85, .7, .5); }   // 1막: 박마다 음·양 구슬에서 번갈아 튀는 입자
  gl.uniform1i(pu.uMode, 0); gl.uniform1f(pu.uT0, 0); gl.uniform1f(pu.uPow, seg(t, T0, T0 + 1.5) * (1 - titleK * .5)); gl.uniform2f(pu.uOrigin, 0, 0); gl.drawArrays(gl.POINTS, 0, 800);
  burst(1, DROP, 0, 0, 0, 4500, 1.5, 2.2, 2.6);
  for (let n = 1, bt = DROP + BEAT; bt < TITLE - .05; n++, bt = DROP + n * BEAT) { const k = n % 3; if (k === 1) burst(1, bt, 0, 0, (n * 977) % 9000, 1100, 1, 1, 2.6); }
  burst(1, TITLE, 0, centerY(TITLE + .6) / U, 0, 2200, 1.1, 1.4, 1.4);
  gl.bindVertexArray(null); gl.disable(gl.BLEND);
  // ② 장면: 2D 레이어 + 먹 번짐 + 입자 반전 + 한지/먹 질감
  X.upload(layerTex, cv, false);
  X.pass(P.scene, RT.scene, (u) => { X.bindTex(0, layerTex, u.uLayer); X.bindTex(1, RT.mask.tex, u.uMask); gl.uniform2f(u.uRes, pw, ph); gl.uniform1f(u.uU, Ud); gl.uniform1f(u.uT, t); gl.uniform1f(u.uWarp, .05 + .05 * bp); });
  // ③ 블룸 + 갓레이 (광원: 1막 = 양의 구슬, 2막 = 태극 중심)
  const bloomTex = X.bloom(RT.scene.tex, .78);
  const [yx, yy] = t >= T0 ? orbPos(t, true) : [0, 0], act2 = t >= DROP;
  const lx = act2 ? 0 : yx, ly = act2 ? centerY(t) : yy, raysK = (act2 ? .16 + .3 * bp : .5 * seg(t, T0, T0 + 1) * (1 - seg(t, BUILD + 1, DROP))) * (1 - titleK * .6);
  const raysTex = X.rays(.5 + lx / W, .5 - ly / H, raysK);
  // ④ 최종
  const b1 = t >= T0 && t < DROP ? Math.exp(-(((t - T0) / BEAT) % 1) * 5) : 0, bar1 = t >= T0 && t < DROP ? Math.exp(-(((t - T0) / 2) % 1) * 6) : 0;   // 1막의 박·마디 펄스
  const hit = .02 * b1 + .04 * bar1 + .35 * pulse(t, DROP, .02, .6) + .05 * bp + .2 * pulse(t, TITLE, .02, .4) + .06 * seg(t, BUILD + 1, DROP) * (act2 ? 0 : 1);
  const zoom = 1 + .015 * b1 + .035 * bar1 + .04 * bar + .22 * pulse(t, DROP, .01, .5) + .1 * pulse(t, TITLE, .01, .4);
  const flash = Math.max(pulse(t, DROP + .07, .01, .5), .8 * pulse(t, TITLE, .02, .4), .5 * pulse(t, T0, .01, .3)), fade = Math.max(1 - seg(t, 0, .25), seg(t, FADE, END));
  const r0 = rng(Math.floor(t * 60)), wv = new Float32Array(40); let wi = 0;
  for (const w of waveList) { const age = t - w.t0; if (age < 0 || age > w.dur || wi >= 10) continue; const k = 1 - age / w.dur; wv.set([w.x, w.y, w.r0 + w.sp * age, w.str * k * k], wi * 4); wi++; }
  X.pass(P.final, null, (u) => { X.bindTex(0, RT.scene.tex, u.uScene); X.bindTex(1, bloomTex, u.uBloom); X.bindTex(2, raysTex, u.uRaysTex); gl.uniform2f(u.uRes, pw, ph); gl.uniform1f(u.uU, Ud); gl.uniform1f(u.uT, t);
    gl.uniform2f(u.uShake, (r0() - .5) * hit * U / W, (r0() - .5) * hit * U / H); gl.uniform1f(u.uZoom, zoom); gl.uniform1f(u.uCA, .001 + .011 * hit + .004 * bp * (act2 ? 1 : 0)); gl.uniform1f(u.uBloomK, .55 + .25 * bp + .2 * b1);
    gl.uniform1f(u.uFlash, flash * flash * .85); gl.uniform1f(u.uInvert, t >= DROP && t < DROP + .07 ? 1 : 0); gl.uniform1f(u.uFade, fade); gl.uniform4fv(u.uWaves, wv); });
}
'''
s = s.replace("@@GL@@", GL)

# ── 재생 루프: draw → render, 느린 GPU 대응, 초기화 실패 처리
rep("  const dt = Math.min(.05, Math.max(0, t - time)); time = t;\n  update(t, dt); draw(t);",
    "  const raw = t - time, dt = Math.min(.05, Math.max(0, raw)); time = t;\n  slow = raw > .03 ? slow + 1 : Math.max(0, slow - 1); if (slow > 45 && DPR_CAP > 1) { DPR_CAP = 1; slow = 0; resize(); }\n  update(t, dt); render(t);")
rep('  opts = o; $("cs").hidden = false; resize(); init(); time = 0; running = true; anchor = now(); useAudio = o.sound !== false;',
    '  opts = o; $("cs").hidden = false;\n  try { resize(); } catch (e) { console.error(e); $("cs").hidden = true; alert("WebGL 초기화 실패: " + e.message); if (o.onDone) o.onDone(); return; }\n  init(); buildWaves(); time = 0; running = true; anchor = now(); useAudio = o.sound !== false;')
rep('window.addEventListener("resize", () => { if (!$("cs").hidden) resize(); });', 'window.addEventListener("resize", () => { if (!$("cs").hidden) { resize(); init(); buildWaves(); } });')
rep("function renderStill(tt) { init(); for (let t = 0; t < tt; t += 1 / 60) { time = t; update(t, 1 / 60); } time = tt; draw(tt); }",
    "function renderStill(tt) { init(); buildWaves(); for (let t = 0; t < tt; t += 1 / 60) { time = t; update(t, 1 / 60); } time = tt; render(tt); }")

io.open(dst, "w", encoding="utf-8", newline="\n").write(s)
print("written", len(s))
