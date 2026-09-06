// H Company - 유저 페이지 (게임 목록 / 잔액 충전 / 링크 복구 / 내 요청)
"use strict";

const $ = (sel) => document.querySelector(sel);

function toast(msg, isError) {
  const el = $("#toast");
  el.textContent = msg;
  el.className = isError ? "show error" : "show";
  clearTimeout(el._t);
  el._t = setTimeout(() => (el.className = ""), 3200);
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function api(path, body) {
  const opt = body
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    : {};
  const res = await fetch(path, opt);
  const data = await res.json().catch(() => ({}));
  if (res.status === 401) { location.href = "/"; throw new Error("로그인이 필요합니다."); }
  if (!res.ok) throw new Error(data.error || "요청 실패");
  return data;
}

function fmtDate(ts) {
  const d = new Date(ts * 1000);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function fmtWon(n) {
  return Number(n || 0).toLocaleString("ko-KR");
}

// ---- 탭
document.querySelectorAll(".tabs button").forEach((btn) =>
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b === btn));
    document.querySelectorAll(".tab-page").forEach((p) => p.classList.toggle("active", p.id === "page-" + btn.dataset.tab));
  }));

// ---- 프로필
api("/api/me").then((me) => {
  $("#who").textContent = `${me.name} 님`;
  if (me.role === "admin") $("#adminLink").hidden = false;
}).catch(() => {});

// ---- 게임 목록 + 잔액
let shopCache = null;

async function loadShop() {
  try {
    shopCache = await api("/api/shopdata");
    $("#balance").textContent = fmtWon(shopCache.balance);
    $("#balanceChip").hidden = false;
    $("#shopUpdated").textContent = shopCache.updated_at
      ? `목록·잔액은 봇과 자동 동기화됩니다. (마지막 동기화: ${fmtDate(shopCache.updated_at)})`
      : "아직 봇과 동기화 전입니다. 잠시 후 새로고침해주세요.";
    renderShop();
    renderProfile();
  } catch (e) {
    $("#gameList").innerHTML = '<div class="empty">목록을 불러올 수 없어요.</div>';
  }
}

function renderShop() {
  if (!shopCache) return;
  const q = $("#gameSearch").value.trim().toLowerCase();
  const box = $("#gameList");
  let html = "";
  let total = 0;
  for (const cat of shopCache.categories) {
    const games = cat.games.filter((g) => !q || g.name.toLowerCase().includes(q));
    if (!games.length) continue;
    total += games.length;
    html += `<div class="cat-title">${esc(cat.name)} <span class="cat-count">${games.length}</span></div>
      <div class="game-grid">` +
      games.map((g) => `
        <div class="game-card">
          ${g.img
            ? `<img class="game-img" loading="lazy" src="/api/shop/image?name=${encodeURIComponent(g.name)}" alt="${esc(g.name)}">`
            : `<div class="game-img placeholder">H</div>`}
          <div class="game-info">
            <div class="game-name">${esc(g.name)}</div>
            <div class="game-price">${fmtWon(g.price)}원${g.is_subscription ? ' <span class="game-tag">정기결제</span>' : ""}</div>
            ${g.is_subscription
              ? '<button class="small buy-btn" disabled title="정기결제는 디스코드 자판기에서">디스코드에서 구매</button>'
              : `<button class="small good buy-btn" data-buy="${esc(g.name)}" data-price="${g.price}">구매하기</button>`}
          </div>
        </div>`).join("") +
      `</div>`;
  }
  box.innerHTML = total ? html
    : `<div class="card"><div class="empty">${q ? "검색 결과가 없어요." : "아직 등록된 게임이 없어요."}</div></div>`;
  box.querySelectorAll(".game-img:not(.placeholder)").forEach((img) =>
    img.addEventListener("click", () => window.open(img.src, "_blank")));
  box.querySelectorAll("[data-buy]").forEach((b) =>
    b.addEventListener("click", async () => {
      const name = b.dataset.buy;
      const price = Number(b.dataset.price);
      if ((shopCache?.balance ?? 0) < price) {
        return toast(`잔액이 부족해요. (내 잔액 ${fmtWon(shopCache.balance)}원) [잔액 충전] 탭에서 충전해주세요.`, true);
      }
      if (!confirm(`'${name}'을(를) ${fmtWon(price)}원에 구매할까요?\n\n잔액에서 차감되고, 다운로드 링크가 디스코드 DM으로 발송됩니다.`)) return;
      try {
        b.disabled = true;
        await api("/api/order", { game: name });
        toast("주문 완료! 봇이 곧 처리하고 디스코드 DM으로 링크를 보내드려요. (최대 1분)");
        loadMy();
      } catch (e) {
        toast(e.message, true);
        b.disabled = false;
      }
    }));
}

// ---- 구매자 정보 (봇 데이터)
function renderProfile() {
  const p = shopCache && shopCache.profile;
  const rbox = $("#recentBuys");
  if (!p) {
    $("#profileCard").hidden = true;
    rbox.innerHTML = '<div class="empty">아직 구매 정보가 없어요. 디스코드에서 !가입 후 이용해주세요.</div>';
    return;
  }
  $("#profileCard").hidden = false;
  $("#profileStats").innerHTML = `
    <div class="stat"><div class="num">${fmtWon(p.total)}원</div><div class="lbl">누적 구매액</div></div>
    <div class="stat"><div class="num" style="font-size:1.05rem;padding-top:6px">${esc(p.tier)}</div><div class="lbl">현재 등급</div></div>
    <div class="stat"><div class="num">${fmtWon(p.purchase_count)}</div><div class="lbl">총 구매 횟수</div></div>
    <div class="stat"><div class="num">${fmtWon(p.point)}p</div><div class="lbl">보유 포인트</div></div>`;

  if (p.next_tier && p.next_threshold > 0) {
    const pct = Math.max(3, Math.min(100, Math.round(p.total / p.next_threshold * 100)));
    $("#tierProgress").innerHTML = `
      <div class="tier-bar-wrap">
        <div class="tier-bar-label">
          <span>다음 등급 <b>${esc(p.next_tier)}</b>까지 <b>${fmtWon(p.remaining)}원</b> 남음</span>
          <span>${pct}%</span>
        </div>
        <div class="tier-bar"><div class="tier-bar-fill" style="width:${pct}%"></div></div>
      </div>`;
  } else {
    $("#tierProgress").innerHTML = '<p class="hint">최고 등급에 도달했어요! 🎉</p>';
  }

  const extras = [];
  if (p.game_pass) {
    extras.push(`게임패스 <b>${esc(p.game_pass.tier)}</b> 이용 중 (만료 ${fmtDate(p.game_pass.expires_at)})`);
  }
  for (const sb of p.subscriptions || []) {
    extras.push(`정기결제 <b>${esc(sb.name)}</b> 구독 중 (다음 결제 ${fmtDate(sb.next_payment)})`);
  }
  $("#profileExtra").innerHTML = extras.length
    ? `<p class="hint" style="margin-top:12px">${extras.join("<br>")}</p>` : "";

  rbox.innerHTML = (p.recent || []).length
    ? p.recent.map((e) => `
      <div class="item-row">
        <div>
          <div class="name">${esc(e.name)}</div>
          <div class="sub">${fmtDate(e.ts)}${e.type === "subscription" ? " · 정기결제" : (e.type === "renewal" ? " · 자동갱신" : "")}</div>
        </div>
        <span class="price">${fmtWon(e.paid)}원</span>
      </div>`).join("")
    : '<div class="empty">아직 구매한 게임이 없어요.</div>';
}

$("#gameSearch").addEventListener("input", renderShop);
loadShop();
setInterval(loadShop, 60000);

// ---- 잔액 충전
$("#chargeSubmit").addEventListener("click", async () => {
  const body = {
    code1: $("#chargeCode1").value.trim(),
    code2: $("#chargeCode2").value.trim(),
    amount: $("#chargeAmount").value.trim(),
  };
  if (!body.code1) return toast("문화상품권 코드를 입력하세요.", true);
  if (!body.amount) return toast("금액을 입력하세요.", true);
  try {
    $("#chargeSubmit").disabled = true;
    await api("/api/charge", body);
    ["chargeCode1", "chargeCode2", "chargeAmount"].forEach((id) => ($("#" + id).value = ""));
    toast("충전 신청 완료! 관리자 승인 후 잔액이 반영됩니다. (결과는 디스코드 DM)");
    loadMy();
  } catch (e) {
    toast(e.message, true);
  } finally {
    $("#chargeSubmit").disabled = false;
  }
});

// ---- 구매내역 캡쳐 첨부 (링크 복구)
let imageData = "";

async function compressImage(file) {
  const bitmap = await createImageBitmap(file);
  const maxW = 1280;
  const scale = Math.min(1, maxW / bitmap.width);
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.85);
}

function clearImage() {
  imageData = "";
  $("#previewImg").src = "";
  $("#imagePreview").hidden = true;
  $("#dropzone").hidden = false;
  $("#imageFile").value = "";
}

async function handleImageFile(file) {
  if (!file || !file.type.startsWith("image/")) {
    return toast("이미지 파일만 첨부할 수 있어요.", true);
  }
  try {
    imageData = await compressImage(file);
    $("#previewImg").src = imageData;
    $("#imagePreview").hidden = false;
    $("#dropzone").hidden = true;
  } catch (e) {
    toast("이미지를 읽을 수 없어요. 다른 파일로 시도해주세요.", true);
  }
}

$("#dropzone").addEventListener("click", () => $("#imageFile").click());
$("#imageFile").addEventListener("change", (e) => handleImageFile(e.target.files[0]));
$("#removeImage").addEventListener("click", clearImage);
["dragover", "dragleave", "drop"].forEach((evt) =>
  $("#dropzone").addEventListener(evt, (e) => {
    e.preventDefault();
    $("#dropzone").classList.toggle("dragover", evt === "dragover");
    if (evt === "drop") handleImageFile(e.dataTransfer.files[0]);
  }));

$("#submit").addEventListener("click", async () => {
  const game = $("#game").value.trim();
  const note = $("#note").value.trim();
  if (!game) return toast("게임 이름을 입력하세요.", true);
  if (!imageData) return toast("구매내역 캡쳐를 첨부해주세요.", true);
  try {
    $("#submit").disabled = true;
    await api("/api/request", { game, note, image: imageData });
    $("#game").value = "";
    $("#note").value = "";
    clearImage();
    toast("복구요청 완료! 관리자가 확인하면 디스코드 DM으로 링크가 도착합니다.");
    loadMy();
  } catch (e) {
    toast(e.message, true);
  } finally {
    $("#submit").disabled = false;
  }
});

// ---- 내 요청
async function loadMy() {
  try {
    const data = await api("/api/my");
    const box = $("#myList");
    box.innerHTML = data.requests.length
      ? data.requests.map((r) => `
        <div class="req-card">
          <div class="head">
            <div>
              <div class="name">${esc(r.game)}</div>
              <div class="sub">${fmtDate(r.created_at)}${r.note ? " · " + esc(r.note) : ""}</div>
              ${r.status === "완료" ? '<div class="sub">디스코드 DM으로 링크를 보냈어요. 확인해주세요!</div>' : ""}
              ${r.status === "거절" && r.admin_reply ? `<div class="sub">사유: ${esc(r.admin_reply)}</div>` : ""}
            </div>
            <span class="badge ${esc(r.status)}">${esc(r.status)}</span>
          </div>
        </div>`).join("")
      : '<div class="empty">아직 요청이 없어요.</div>';

    const obox = $("#myOrders");
    obox.innerHTML = (data.orders || []).length
      ? data.orders.map((o) => `
        <div class="req-card">
          <div class="head">
            <div>
              <div class="name">${esc(o.game)} · ${fmtWon(o.price)}원</div>
              <div class="sub">${fmtDate(o.created_at)}${o.result ? " · " + esc(o.result) : (o.status === "대기" || o.status === "처리중" ? " · 봇이 처리 중이에요 (최대 1분)" : "")}</div>
            </div>
            <span class="badge ${esc(o.status)}">${esc(o.status)}</span>
          </div>
        </div>`).join("")
      : '<div class="empty">구매 내역이 없어요.</div>';

    const cbox = $("#myCharges");
    cbox.innerHTML = data.charges.length
      ? data.charges.map((c) => `
        <div class="req-card">
          <div class="head">
            <div>
              <div class="name">${fmtWon(c.amount)}원 충전</div>
              <div class="sub">${fmtDate(c.created_at)} · ${c.status === "대기" ? "곧 관리자에게 전달돼요" : "관리자 확인 중 · 결과는 디스코드 DM"}</div>
            </div>
            <span class="badge ${esc(c.status)}">${esc(c.status)}</span>
          </div>
        </div>`).join("")
      : '<div class="empty">충전 신청 내역이 없어요.</div>';
  } catch (e) { /* 무시 */ }
}
loadMy();
setInterval(loadMy, 30000);
