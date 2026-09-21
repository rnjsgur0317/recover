// 컷씬 공용 WebGL2 도우미 — 셰이더 컴파일, HDR 렌더타깃, 전체화면 패스, 듀얼필터 블룸, 지터 갓레이, 파티클 시드
// 사용: const X = CSGL.create(canvas); X.resize(w, h); X.pass(prog, target|null, (u) => {...}); const bloomTex = X.bloom(sceneTex, .7);
"use strict";
window.CSGL = (function () {
  const VS_FULL = `#version 300 es
out vec2 vUv; void main(){ vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2)); vUv = p; gl_Position = vec4(p * 2. - 1., 0., 1.); }`;
  const NOISE = `
float hash(vec2 p){ p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float noise(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3. - 2. * f);
  return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y); }
float fbm(vec2 p){ float a = .5, s = 0.; for (int i = 0; i < 5; i++){ s += a * noise(p); p = p * 2.03 + vec2(17., 9.); a *= .5; } return s; }`;
  const FS_BRIGHT = `#version 300 es
precision highp float; in vec2 vUv; out vec4 o; uniform sampler2D uTex; uniform float uThr;
void main(){ vec3 c = texture(uTex, vUv).rgb; float l = max(c.r, max(c.g, c.b)); float k = clamp((l - uThr) / .55, 0., 1.); o = vec4(c * k * k, 1.); }`;
  const FS_DOWN = `#version 300 es
precision highp float; in vec2 vUv; out vec4 o; uniform sampler2D uTex; uniform vec2 uTexel;
void main(){ vec4 s = texture(uTex, vUv) * 4.; s += texture(uTex, vUv - uTexel); s += texture(uTex, vUv + uTexel); s += texture(uTex, vUv + vec2(uTexel.x, -uTexel.y)); s += texture(uTex, vUv - vec2(uTexel.x, -uTexel.y)); o = s / 8.; }`;
  const FS_UP = `#version 300 es
precision highp float; in vec2 vUv; out vec4 o; uniform sampler2D uTex, uAdd; uniform vec2 uTexel;
void main(){ vec4 s = texture(uTex, vUv + vec2(-uTexel.x * 2., 0.)); s += texture(uTex, vUv + vec2(-uTexel.x, uTexel.y)) * 2.; s += texture(uTex, vUv + vec2(0., uTexel.y * 2.)); s += texture(uTex, vUv + uTexel) * 2.;
  s += texture(uTex, vUv + vec2(uTexel.x * 2., 0.)); s += texture(uTex, vUv + vec2(uTexel.x, -uTexel.y)) * 2.; s += texture(uTex, vUv + vec2(0., -uTexel.y * 2.)); s += texture(uTex, vUv - uTexel) * 2.;
  o = s / 12. + texture(uAdd, vUv); }`;
  const FS_RAYS = `#version 300 es
precision highp float; in vec2 vUv; out vec4 o; uniform sampler2D uTex; uniform vec2 uLight; uniform float uK;
${NOISE}
void main(){ vec2 d = (vUv - uLight) * (1. / 64.) * .92; vec2 uv = vUv - d * hash(gl_FragCoord.xy); vec3 acc = vec3(0.); float decay = 1.;
  for (int i = 0; i < 64; i++){ uv -= d; acc += texture(uTex, uv).rgb * decay; decay *= .972; } o = vec4(acc / 64. * uK, 1.); }`;

  function create(canvas) {
    const gl = canvas.getContext("webgl2", { antialias: false, alpha: false, preserveDrawingBuffer: true, powerPreference: "high-performance" });
    if (!gl) throw new Error("이 브라우저는 WebGL2를 지원하지 않습니다.");
    const HDR = !!gl.getExtension("EXT_color_buffer_float") || !!gl.getExtension("EXT_color_buffer_half_float");
    function compile(vs, fs) {
      const mk = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)); return s; };
      const p = gl.createProgram(); gl.attachShader(p, mk(gl.VERTEX_SHADER, vs)); gl.attachShader(p, mk(gl.FRAGMENT_SHADER, fs)); gl.linkProgram(p);
      if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
      const u = {}, n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS); for (let i = 0; i < n; i++) { const name = gl.getActiveUniform(p, i).name.replace(/\[0\]$/, ""); u[name] = gl.getUniformLocation(p, name); }
      return { p, u };
    }
    function target(w, h) {
      const tex = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, tex);
      if (HDR) gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA16F, w, h, 0, gl.RGBA, gl.HALF_FLOAT, null); else gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
      for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_2D, k, v);
      const fbo = gl.createFramebuffer(); gl.bindFramebuffer(gl.FRAMEBUFFER, fbo); gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
      return { tex, fbo, w, h };
    }
    function free(t) { if (!t) return; (Array.isArray(t) ? t : [t]).forEach((x) => { gl.deleteTexture(x.tex); gl.deleteFramebuffer(x.fbo); }); }
    function bind(dst) { gl.bindFramebuffer(gl.FRAMEBUFFER, dst ? dst.fbo : null); gl.viewport(0, 0, dst ? dst.w : canvas.width, dst ? dst.h : canvas.height); }
    function pass(prog, dst, setup) { bind(dst); gl.useProgram(prog.p); setup(prog.u); gl.bindVertexArray(null); gl.drawArrays(gl.TRIANGLES, 0, 3); }
    function bindTex(unit, tex, loc) { gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_2D, tex); gl.uniform1i(loc, unit); }
    function canvasTexture() { const tex = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, tex); for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_2D, k, v); return tex; }
    function upload(tex, src, premultiply) { gl.bindTexture(gl.TEXTURE_2D, tex); gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true); gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, !!premultiply); gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, src); gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false); gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false); }
    function seeds(n, seedFn) { const data = new Float32Array(n * 4); for (let i = 0; i < data.length; i++) data[i] = seedFn(); const vao = gl.createVertexArray(); gl.bindVertexArray(vao); const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW); gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 4, gl.FLOAT, false, 0, 0); gl.bindVertexArray(null); return vao; }

    const P = { bright: compile(VS_FULL, FS_BRIGHT), down: compile(VS_FULL, FS_DOWN), up: compile(VS_FULL, FS_UP), rays: compile(VS_FULL, FS_RAYS) };
    let R = { bright: null, rays: null, down: [], up: [] };
    function resize(w, h) {
      free(R.bright); free(R.rays); free(R.down); free(R.up);
      R = { bright: target(w >> 1, h >> 1), rays: target(w >> 1, h >> 1), down: [], up: [] };
      let cw = w >> 1, ch = h >> 1; for (let i = 0; i < 5; i++) { cw = Math.max(2, cw >> 1); ch = Math.max(2, ch >> 1); R.down.push(target(cw, ch)); R.up.push(target(cw, ch)); }
    }
    function bloom(srcTex, thr) {                       // 밝은 부분 추출 → 5단 다운/업 → 블룸 텍스처
      pass(P.bright, R.bright, (u) => { bindTex(0, srcTex, u.uTex); gl.uniform1f(u.uThr, thr); });
      let src = R.bright; for (const d of R.down) { pass(P.down, d, (u) => { bindTex(0, src.tex, u.uTex); gl.uniform2f(u.uTexel, .5 / d.w, .5 / d.h); }); src = d; }
      let acc = R.down[R.down.length - 1]; for (let i = R.down.length - 2; i >= 0; i--) { const dst = R.up[i], add = R.down[i]; pass(P.up, dst, (u) => { bindTex(0, acc.tex, u.uTex); bindTex(1, add.tex, u.uAdd); gl.uniform2f(u.uTexel, .5 / dst.w, .5 / dst.h); }); acc = dst; }
      return acc.tex;
    }
    function rays(lightU, lightV, k) {                  // bloom() 직후 호출 — 밝은 부분을 광원에서 바깥으로 번지게
      pass(P.rays, R.rays, (u) => { bindTex(0, R.bright.tex, u.uTex); gl.uniform2f(u.uLight, lightU, lightV); gl.uniform1f(u.uK, k); });
      return R.rays.tex;
    }
    return { gl, HDR, compile, target, free, bind, pass, bindTex, canvasTexture, upload, seeds, resize, bloom, rays };
  }
  return { create, VS_FULL, NOISE };
})();
