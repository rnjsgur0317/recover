// H Company - [뽑기] 탭 (상자 열기 → 1차 등급 룰렛 → 2차 내용물 룰렛 → 결과)
// user.js 의 $ / api / toast / esc / fmtWon / fmtDate 를 그대로 사용한다.
"use strict";

let gcData = null;          // /api/gacha 응답
let gcBox = "normal";       // 선택된 상자
let gcBusy = false;
const GC_DISPLAY_W = [50, 28, 14, 6, 2];   // 룰렛 띠 장식 비율 (실제 확률과 무관 — 역산 방지)
const GC_TILE = 124, GC_TOTAL = 64, GC_TARGET = 52;
const gcStage = () => $("#gcStage");

function gcUnit(kind) { return kind === "point" ? "P" : "원"; }

async function loadGacha() {
  try {
    gcData = await api("/api/gacha");
  } catch (e) {
    $("#gcRewards").innerHTML = `<div class="empty">${esc(e.message)}</div>`;
    return;
  }
  renderGachaBox();
  renderGachaSide();
}

function gcCurrent() {
  return (gcData?.boxes || []).find((b) => b.key === gcBox) || null;
}

function renderGachaBox() {
  const b = gcCurrent();
  if (!b) return;
  const w = gcData.wallet || {};
  $("#gcTabNormal").className = gcBox === "normal" ? "on" : "";
  $("#gcTabPremium").className = gcBox === "premium" ? "on prem" : "";
  gcData.boxes.forEach((bx) => {
    $(bx.key === "normal" ? "#gcTabNormal" : "#gcTabPremium").textContent =
      `${bx.name} · ${fmtWon(bx.cost)}${gcUnit(bx.cost_kind)}`;
  });
  gcStage().classList.toggle("prem", gcBox === "premium");
  $("#gcBoxName").textContent = gcBox === "premium" ? "PREMIUM BOX" : "NORMAL BOX";
  const have = w[b.cost_kind] ?? 0;
  $("#gcBtn").textContent = `🎁 ${fmtWon(b.cost)}${gcUnit(b.cost_kind)} 뽑기`;
  $("#gcBtn").disabled = gcBusy || !w.registered || have < b.cost || (b.daily_limit && b.today >= b.daily_limit);
  const hints = [];
  hints.push(b.cost_kind === "point"
    ? `내 포인트 <b>${fmtWon(w.point ?? 0)}P</b>`
    : `내 잔액 <b>${fmtWon(w.cash ?? 0)}원</b>`);
  if (b.daily_limit) hints.push(`오늘 ${b.today}/${b.daily_limit}회`);
  if (!w.registered) hints.push("디스코드에서 !가입 후 이용할 수 있어요");
  else if (have < b.cost) hints.push(b.cost_kind === "point" ? "포인트가 부족해요 (후기 작성으로 적립)" : "잔액이 부족해요 ([잔액 충전] 탭)");
  $("#gcWallet").innerHTML = hints.join(" · ");
  $("#gcRewards").innerHTML = b.tiers.map((t) =>
    `<div class="gc-rw-tier" style="--c:${t.color}"><span class="gc-rw-badge">${esc(t.label)}</span><div class="gc-rw-items">${
      t.items.map((n) => `<span>${esc(n)}</span>`).join("")}</div></div>`).join("");
}

function renderGachaSide() {
  const cbox = $("#gcCoupons");
  const cs = gcData.coupons || [];
  cbox.innerHTML = cs.length
    ? cs.map((c) => `
      <div class="item-row">
        <div><div class="name">🎟️ 게임 ${c.pct}% 할인쿠폰</div>
        <div class="sub">${fmtDate(c.expires_at)}까지 · 게임 구매 시 선택 적용${c.ready ? "" : " · <b>지급 처리 중</b>"}</div></div>
        <span class="badge ${c.ready ? "완료" : "대기"}">${c.ready ? "사용 가능" : "처리 중"}</span>
      </div>`).join("")
    : '<div class="empty">보유한 할인쿠폰이 없어요. 뽑기에서 얻을 수 있어요!</div>';
  const rbox = $("#gcRecent");
  const rs = gcData.recent || [];
  rbox.innerHTML = rs.length
    ? rs.map((r) => `
      <div class="item-row">
        <div><div class="name"><span class="gc-tier-chip" style="--c:${r.color}">${esc(r.tier)}</span> ${esc(r.item)}</div>
        <div class="sub">${esc(r.box_name)} · ${fmtDate(r.created_at)}${r.result ? " · " + esc(r.result) : (r.status === "완료" ? "" : " · 봇이 처리 중 (최대 1분)")}</div></div>
        <span class="badge ${esc(r.status)}">${esc(r.status)}</span>
      </div>`).join("")
    : '<div class="empty">아직 뽑기 기록이 없어요.</div>';
}

function selectGachaBox(k) {
  if (gcBusy) return;
  gcBox = k;
  gcReset();
  renderGachaBox();
}

function gcReset() {
  const st = gcStage();
  st.classList.remove("open", "shake");
  st.style.setProperty("--rare", "#8b8f98");
  for (const id of ["gcWrap1", "gcWrap2"]) $("#" + id).classList.remove("show");
  for (const id of ["gcStrip1", "gcStrip2"]) {
    const s = $("#" + id);
    s.style.transition = "none"; s.style.transform = "translateX(0)"; s.innerHTML = "";
    s.parentElement.classList.remove("landed");
  }
  $("#gcResult").className = "gc-result";
  st.querySelectorAll(".gc-spark").forEach((e) => e.remove());
}

function gcPickIdx(weights) {
  const total = weights.reduce((a, b) => a + b, 0);
  let r = Math.random() * total;
  for (let i = 0; i < weights.length; i++) { r -= weights[i]; if (r < 0) return i; }
  return weights.length - 1;
}

/* 룰렛: entries[resultIdx] 가 화살표에 걸리도록. 띠는 장식 가중치로만 채운다 */
function gcSpin(stripId, entries, resultIdx, duration, displayW) {
  const strip = $("#" + stripId);
  const wrap = strip.parentElement;
  wrap.classList.remove("landed");
  strip.innerHTML = "";
  const dw = entries.map((_, i) => (displayW ? (displayW[i] ?? 1) : 1));
  for (let i = 0; i < GC_TOTAL; i++) {
    let idx = gcPickIdx(dw);
    if (i === GC_TARGET) idx = resultIdx;
    else if (i === GC_TARGET - 1 || i === GC_TARGET + 1) {   // 바로 옆칸은 결과와 다르게
      let guard = 0;
      while (idx === resultIdx && entries.length > 1 && guard++ < 10) idx = gcPickIdx(dw);
    }
    const e = entries[idx];
    const d = document.createElement("div");
    d.className = "gc-tile"; d.style.setProperty("--c", e.color);
    d.innerHTML = `${esc(e.label)}${e.sub ? `<small>${esc(e.sub)}</small>` : ""}`;
    strip.append(d);
  }
  const width = wrap.getBoundingClientRect().width;
  const offset = (Math.random() - .5) * (GC_TILE - 30);
  const target = GC_TARGET * GC_TILE + GC_TILE / 2 - width / 2 + offset;
  strip.style.transition = "none";
  strip.style.transform = "translateX(0)";
  void strip.offsetWidth;
  strip.style.transition = `transform ${duration}ms cubic-bezier(.1,.75,.1,1)`;
  strip.style.transform = `translateX(${-target}px)`;
  return new Promise((res) => setTimeout(() => {
    wrap.classList.add("landed");
    strip.children[GC_TARGET].classList.add("hit");
    res();
  }, duration + 80));
}

const gcWait = (ms) => new Promise((r) => setTimeout(r, ms));

async function gachaPull() {
  if (gcBusy) return;
  const b = gcCurrent();
  if (!b) return;
  const w = gcData.wallet || {};
  if (!confirm(`${b.name}를 ${fmtWon(b.cost)}${gcUnit(b.cost_kind)}에 뽑을까요?\n(${b.cost_kind === "point" ? "포인트" : "잔액"}에서 차감됩니다)`)) return;
  gcBusy = true;
  $("#gcBtn").disabled = true;
  document.querySelectorAll(".gc-tabs button").forEach((t) => (t.disabled = true));
  gcReset();
  let res;
  try {
    res = await api("/api/gacha/pull", { box: b.key });          // 서버가 추첨 — 연출은 결과에 맞춰 멈춤
  } catch (e) {
    toast(e.message, true);
    gcBusy = false;
    document.querySelectorAll(".gc-tabs button").forEach((t) => (t.disabled = false));
    renderGachaBox();
    return;
  }
  gcData.wallet = res.wallet;
  b.today = res.today;
  renderGachaBox();
  $("#gcBtn").disabled = true;
  const st = gcStage();
  const pull = res.pull;

  // 1) 상자 흔들림 → 뚜껑 열림
  st.classList.add("shake");
  await gcWait(600);
  st.classList.add("open");
  await gcWait(700);

  // 2) 1차 룰렛: 등급
  const tiers = b.tiers.map((t) => ({ label: t.label, color: t.color }));
  let tierIdx = tiers.findIndex((t) => t.label === pull.tier);
  if (tierIdx < 0) { tiers.push({ label: pull.tier, color: pull.color }); tierIdx = tiers.length - 1; }
  $("#gcWrap1").classList.add("show");
  await gcWait(550);
  await gcSpin("gcStrip1", tiers, tierIdx, 5200, GC_DISPLAY_W);
  st.style.setProperty("--rare", pull.color);
  await gcWait(700);

  // 3) 2차 룰렛: 그 등급의 내용물 (꽝은 목록에 없으므로 결과가 꽝이면 끼워 넣음)
  const names = [...(b.tiers[tierIdx]?.items || [])];
  if (!names.includes(pull.item)) names.push(pull.item);
  const items = names.map((n) => ({ label: n, color: n === "꽝" ? "#3f3f46" : pull.color, sub: pull.tier }));
  const itemIdx = names.indexOf(pull.item);
  $("#gcWrap2").classList.add("show");
  await gcWait(550);
  await gcSpin("gcStrip2", items, itemIdx, 3600);
  await gcWait(300);

  // 4) 결과
  const r = $("#gcResult");
  r.innerHTML = `<span class="gc-tier">${esc(pull.tier)}</span><div class="gc-name">${esc(pull.item)}</div>
    <div class="gc-sub">${esc(pull.desc || "")}</div>`;
  r.classList.add("show");
  for (let i = 0; i < 10; i++) {
    const s = document.createElement("div");
    s.className = "gc-spark"; s.textContent = "✦"; s.style.color = pull.color;
    s.style.setProperty("--dx", (Math.cos(i / 10 * 6.283) * 150) + "px");
    s.style.setProperty("--dy", (Math.sin(i / 10 * 6.283) * 110) + "px");
    st.append(s);
  }
  await gcWait(900);
  gcBusy = false;
  document.querySelectorAll(".gc-tabs button").forEach((t) => (t.disabled = false));
  renderGachaBox();
  loadGacha();          // 최근 기록·쿠폰 갱신
  if (typeof loadShop === "function") loadShop();
}

$("#gcTabNormal").addEventListener("click", () => selectGachaBox("normal"));
$("#gcTabPremium").addEventListener("click", () => selectGachaBox("premium"));
$("#gcBtn").addEventListener("click", gachaPull);
loadGacha();
setInterval(() => { if (!gcBusy) loadGacha(); }, 60000);
