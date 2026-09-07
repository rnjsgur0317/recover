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
    renderCatSide();
    renderShop();
    renderProfile();
  } catch (e) {
    $("#gameList").innerHTML = '<div class="empty">목록을 불러올 수 없어요.</div>';
  }
}

let selectedCat = "전체";

function saleGames() {
  const out = [];
  for (const c of shopCache.categories) {
    for (const g of c.games) if (g.sale_price != null) out.push(g);
  }
  return out;
}

function bestGames() {
  const out = [];
  for (const c of shopCache.categories) {
    for (const g of c.games) if (g.best) out.push(g);
  }
  return out;
}

function renderCatSide() {
  const side = $("#catSide");
  const total = shopCache.categories.reduce((n, c) => n + c.games.length, 0);
  const sales = saleGames();
  const bests = bestGames();
  const cats = [{ name: "전체", n: total }];
  if (bests.length) cats.push({ name: "⭐ BEST", n: bests.length });
  if (sales.length) cats.push({ name: "🔥 할인", n: sales.length });
  cats.push(...shopCache.categories.map((c) => ({ name: c.name, n: c.games.length })));
  if (!cats.some((c) => c.name === selectedCat)) selectedCat = "전체";
  side.innerHTML = cats.map((c) =>
    `<button class="${c.name === selectedCat ? "active" : ""}${c.name === "⭐ BEST" ? " best-cat" : ""}" data-cat="${esc(c.name)}">${esc(c.name)} <span class="n">${c.n}</span></button>`).join("");
  side.querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => {
      selectedCat = b.dataset.cat;
      renderCatSide();
      renderShop();
    }));
}

function mediaTag(g, cls) {
  const src = `/api/shop/image?name=${encodeURIComponent(g.name)}`;
  if (!g.img) return `<div class="${cls} placeholder">H</div>`;
  if (g.media === "video") {
    return `<video class="${cls}" src="${src}" preload="metadata" muted playsinline></video>`;
  }
  return `<img class="${cls}" loading="lazy" src="${src}" alt="${esc(g.name)}">`;
}

function priceBlock(g) {
  // 정가(취소선) → 판매가 → 할인% / 사이트 할인 중이면 할인가 기준
  const nowPrice = g.sale_price ?? g.price;
  const base = g.sale_price != null ? g.price : (g.official || 0);
  let html = "";
  if (base && base > nowPrice) {
    const off = Math.round((1 - nowPrice / base) * 100);
    html += `<div class="price-was">${g.sale_price != null ? "판매가" : "정가"} ${fmtWon(base)}원</div>`;
    html += `<div class="game-price">${fmtWon(nowPrice)}원 <span class="off-chip${g.sale_price != null ? " hot" : ""}">${off}%↓</span></div>`;
  } else {
    html += `<div class="game-price">${fmtWon(nowPrice)}원</div>`;
  }
  if (g.sale_price != null) html += "";
  return html;
}

function gameCard(g) {
  return `
    <div class="game-card${g.best ? " best" : ""}" data-open="${esc(g.name)}" role="button" tabindex="0">
      ${g.best ? '<span class="best-ribbon">BEST</span>' : ""}
      ${mediaTag(g, "game-img")}
      <div class="game-info">
        <div class="game-name">${esc(g.name)}${g.is_subscription ? ' <span class="game-tag">정기결제</span>' : ""}${g.sale_price != null ? ' <span class="game-tag hot">할인중</span>' : ""}</div>
        ${priceBlock(g)}
      </div>
    </div>`;
}

function renderShop() {
  if (!shopCache) return;
  const q = $("#gameSearch").value.trim().toLowerCase();
  const box = $("#gameList");
  let html = "";
  let total = 0;
  if (selectedCat === "🔥 할인") {
    const games = saleGames().filter((g) => !q || g.name.toLowerCase().includes(q));
    total = games.length;
    html = `<div class="cat-title">🔥 할인 중인 게임 <span class="cat-count">${games.length}</span></div>
      <div class="game-grid">` + games.map(gameCard).join("") + `</div>`;
  } else if (selectedCat === "⭐ BEST") {
    const games = bestGames().filter((g) => !q || g.name.toLowerCase().includes(q));
    total = games.length;
    html = `<div class="cat-title best-title">⭐ BEST <span class="cat-count best-count">${games.length}</span></div>
      <div class="game-grid">` + games.map(gameCard).join("") + `</div>`;
  } else {
    if (selectedCat === "전체") {
      const bests = bestGames().filter((g) => !q || g.name.toLowerCase().includes(q));
      if (bests.length) {
        total += bests.length;
        html += `<div class="cat-title best-title">⭐ BEST <span class="cat-count best-count">${bests.length}</span></div>
          <div class="game-grid">` + bests.map(gameCard).join("") + `</div>`;
      }
    }
    for (const cat of shopCache.categories) {
      if (selectedCat !== "전체" && cat.name !== selectedCat) continue;
      const games = cat.games.filter((g) => !q || g.name.toLowerCase().includes(q));
      if (!games.length) continue;
      total += games.length;
      html += `<div class="cat-title">${esc(cat.name)} <span class="cat-count">${games.length}</span></div>
        <div class="game-grid">` + games.map(gameCard).join("") + `</div>`;
    }
  }
  box.innerHTML = total ? html
    : `<div class="card"><div class="empty">${q ? "검색 결과가 없어요." : "이 카테고리에 게임이 없어요."}</div></div>`;
  box.querySelectorAll("[data-open]").forEach((card) =>
    card.addEventListener("click", () => openDetail(card.dataset.open)));
  renderUpcoming();
}

// ---- 신작(출시 예정) 예약
function renderUpcoming() {
  const box = $("#upcomingSection");
  const ups = shopCache.upcoming || [];
  if (!ups.length) { box.innerHTML = ""; return; }
  box.innerHTML = `
    <div class="upcoming-sep"></div>
    <div class="cat-title">🚀 출시 예정 · 예약 구매 <span class="cat-count">${ups.length}</span></div>
    <p class="hint" style="margin:-4px 2px 10px">예약 구매하면 출시가보다 저렴하게! 출시되면 링크가 DM과 [내 정보]로 발송됩니다.</p>
    <div class="game-grid">` + ups.map((u) => {
      const off = u.price > u.discount_price ? Math.round((1 - u.discount_price / u.price) * 100) : 0;
      return `
      <div class="game-card upcoming-card">
        ${u.img ? `<img class="game-img" loading="lazy" src="/api/shop/upcimg?id=${u.id}" alt="${esc(u.name)}">`
                : `<div class="game-img placeholder">🚀</div>`}
        <div class="game-info">
          <div class="game-name">${esc(u.name)} <span class="game-tag">출시 예정</span></div>
          ${u.price > u.discount_price ? `<div class="price-was">출시가 ${fmtWon(u.price)}원</div>` : ""}
          <div class="game-price">예약가 ${fmtWon(u.discount_price)}원 ${off ? `<span class="off-chip hot">${off}%↓</span>` : ""}</div>
          ${u.note ? `<div class="sub" style="font-size:.78rem;color:#71717a;margin-top:4px">${esc(u.note)}</div>` : ""}
          <button class="small good buy-btn" data-reserve="${u.id}" data-rname="${esc(u.name)}" data-rprice="${u.discount_price}">예약 구매</button>
        </div>
      </div>`;
    }).join("") + `</div>`;
  box.querySelectorAll("[data-reserve]").forEach((b) =>
    b.addEventListener("click", async () => {
      const price = Number(b.dataset.rprice);
      if ((shopCache?.balance ?? 0) < price) {
        return toast(`잔액이 부족해요. (내 잔액 ${fmtWon(shopCache.balance)}원) [잔액 충전] 탭에서 충전해주세요.`, true);
      }
      if (!confirm(`'${b.dataset.rname}'을(를) 예약가 ${fmtWon(price)}원에 예약 구매할까요?\n\n지금 잔액에서 차감되고, 출시되면 링크가 발송됩니다.`)) return;
      try {
        b.disabled = true;
        await api("/api/reserve", { id: Number(b.dataset.reserve) });
        toast("예약 완료! 출시되면 디스코드 DM과 [내 정보]에서 링크를 받을 수 있어요.");
        loadMy();
      } catch (e) {
        toast(e.message, true);
        b.disabled = false;
      }
    }));
}

// ---- 공지사항
async function loadNotices() {
  try {
    const data = await api("/api/notices");
    const box = $("#noticeList");
    box.innerHTML = data.notices.length
      ? data.notices.map((n) => `
        <div class="card">
          <h2>${esc(n.title)}</h2>
          <p class="desc" style="margin:0;white-space:pre-wrap">${esc(n.body)}</p>
          <p class="hint" style="margin-top:10px">${fmtDate(n.created_at)}</p>
        </div>`).join("")
      : '<div class="card"><div class="empty">등록된 공지가 없어요.</div></div>';
  } catch (e) { /* 무시 */ }
}
loadNotices();

// ---- 게임 상세 모달
function closeDetail() {
  $("#detailOverlay").hidden = true;
}
$("#detailClose").addEventListener("click", closeDetail);
$("#detailOverlay").addEventListener("click", (e) => { if (e.target === $("#detailOverlay")) closeDetail(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDetail(); });

async function openDetail(name) {
  const body = $("#detailBody");
  body.innerHTML = '<div class="empty">불러오는 중...</div>';
  $("#detailOverlay").hidden = false;
  let d;
  try {
    d = await api("/api/shop/detail?name=" + encodeURIComponent(name));
  } catch (e) {
    body.innerHTML = `<div class="empty">${esc(e.message)}</div>`;
    return;
  }
  const dt = d.detail || {};
  const nowPrice = d.sale_price ?? d.price;
  const base = d.sale_price != null ? d.price : (dt.official || 0);
  const off = base && base > nowPrice ? Math.round((1 - nowPrice / base) * 100) : 0;
  const mediaList = d.media_list || (d.img ? [d.media || "img"] : []);
  const gallery = mediaList.length ? `
    <div class="gallery">
      <div class="gallery-view" id="galleryView"></div>
      ${mediaList.length > 1 ? `
        <button class="gal-btn prev" id="galPrev">‹</button>
        <button class="gal-btn next" id="galNext">›</button>
        <div class="gal-dots" id="galDots">${mediaList.map((_, i) => `<span data-dot="${i}"></span>`).join("")}</div>` : ""}
    </div>` : "";
  body.innerHTML = `
    ${gallery}
    <div class="detail-name">${d.best ? '<span class="game-tag best-tag">BEST</span> ' : ""}${esc(d.name)}${d.sale_price != null ? ' <span class="game-tag hot">할인중</span>' : ""}</div>
    <div class="detail-prices">
      <span class="now">${fmtWon(nowPrice)}원</span>
      ${base && base > nowPrice ? `<span class="was">${d.sale_price != null ? "판매가" : "정가"} ${fmtWon(base)}원</span>` : ""}
      ${dt.official && d.sale_price != null && dt.official > d.price ? `<span class="was">정가 ${fmtWon(dt.official)}원</span>` : ""}
      ${off > 0 ? `<span class="off">${off}% 할인</span>` : ""}
    </div>
    <div class="detail-row">카테고리 <b>${esc(d.category)}</b>${d.is_subscription ? ' · <span class="game-tag">정기결제</span>' : ""}</div>
    ${dt.rating ? `<div class="detail-row">수위 <b>${esc(dt.rating)}</b></div>` : ""}
    ${dt.seller ? `<div class="detail-row">공식 판매처 <a href="${esc(dt.seller)}" target="_blank" rel="noopener">바로가기 ↗</a></div>` : ""}
    ${(dt.comments || []).length ? `
      <div class="detail-comments">
        <div class="ttl">코멘트</div>
        <ul>${dt.comments.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>
      </div>` : ""}
    ${d.is_subscription
      ? '<button class="primary" disabled style="opacity:.5">정기결제는 디스코드 자판기에서</button>'
      : `<div class="detail-actions">
           <button class="primary" id="detailBuy" style="margin-top:0">${fmtWon(nowPrice)}원 바로 구매</button>
           <button class="primary ghost" id="detailCart" style="margin-top:0">🛒 장바구니</button>
         </div>`}
    <p class="hint" style="text-align:center">구매 시 잔액에서 차감되고, 링크는 디스코드 DM과 [내 정보]에서 7일간 받을 수 있어요.</p>`;

  // 갤러리
  if (mediaList.length) {
    let gi = 0;
    const view = $("#galleryView");
    const show = () => {
      const src = `/api/shop/image?name=${encodeURIComponent(d.name)}&i=${gi}`;
      view.innerHTML = mediaList[gi] === "video"
        ? `<video class="detail-img" src="${src}" controls muted playsinline loop></video>`
        : `<img class="detail-img" src="${src}" alt="${esc(d.name)}">`;
      document.querySelectorAll("[data-dot]").forEach((el, i) => el.classList.toggle("on", i === gi));
    };
    show();
    if (mediaList.length > 1) {
      $("#galPrev").addEventListener("click", () => { gi = (gi - 1 + mediaList.length) % mediaList.length; show(); });
      $("#galNext").addEventListener("click", () => { gi = (gi + 1) % mediaList.length; show(); });
      document.querySelectorAll("[data-dot]").forEach((el, i) =>
        el.addEventListener("click", () => { gi = i; show(); }));
    }
  }

  const buyBtn = $("#detailBuy");
  if (buyBtn) {
    buyBtn.addEventListener("click", async () => {
      if ((shopCache?.balance ?? 0) < nowPrice) {
        return toast(`잔액이 부족해요. (내 잔액 ${fmtWon(shopCache.balance)}원) [잔액 충전] 탭에서 충전해주세요.`, true);
      }
      if (!confirm(`'${d.name}'을(를) ${fmtWon(nowPrice)}원에 구매할까요?`)) return;
      try {
        buyBtn.disabled = true;
        await api("/api/order", { game: d.name });
        closeDetail();
        toast("주문 완료! 봇이 곧 처리하고 디스코드 DM으로 링크를 보내드려요. (최대 1분)");
        loadMy();
      } catch (e) {
        toast(e.message, true);
        buyBtn.disabled = false;
      }
    });
    $("#detailCart").addEventListener("click", () => {
      addToCart(d.name);
      closeDetail();
    });
  }
}

// ---- 장바구니 (이 브라우저에 저장)
function getCart() {
  try { return JSON.parse(localStorage.getItem("cart") || "[]"); } catch (e) { return []; }
}
function setCart(items) {
  try { localStorage.setItem("cart", JSON.stringify(items)); } catch (e) {}
  const cnt = $("#cartCount");
  cnt.hidden = items.length === 0;
  cnt.textContent = items.length;
}
function addToCart(name) {
  const items = getCart();
  if (items.includes(name)) return toast("이미 장바구니에 있어요.");
  if (items.length >= 10) return toast("장바구니는 최대 10개까지 담을 수 있어요.", true);
  items.push(name);
  setCart(items);
  toast(`'${name}' 장바구니에 담았어요.`);
}
function findGame(name) {
  for (const c of (shopCache?.categories || [])) {
    for (const g of c.games) if (g.name === name) return g;
  }
  return null;
}
function renderCart() {
  const items = getCart().filter((n) => findGame(n));  // 판매 종료된 건 제거
  setCart(items);
  const box = $("#cartBody");
  if (!items.length) {
    box.innerHTML = '<div class="empty">장바구니가 비어 있어요.<br>게임 상세에서 [🛒 장바구니]를 눌러 담아보세요.</div>';
    return;
  }
  let total = 0;
  box.innerHTML = items.map((n) => {
    const g = findGame(n);
    const p = g.sale_price ?? g.price;
    total += p;
    return `
      <div class="item-row">
        <div><div class="name">${esc(n)}</div>
        ${g.sale_price != null ? '<div class="sub">🔥 할인가 적용</div>' : ""}</div>
        <div style="display:flex;align-items:center;gap:10px">
          <span class="price">${fmtWon(p)}원</span>
          <button class="small danger" data-rm="${esc(n)}">빼기</button>
        </div>
      </div>`;
  }).join("") + `
    <div class="cart-total">합계 <b>${fmtWon(total)}원</b> <span class="hint" style="margin:0">(내 잔액 ${fmtWon(shopCache?.balance ?? 0)}원)</span></div>
    <button class="primary" id="cartBuyAll">일괄 구매 (${items.length}개)</button>`;
  box.querySelectorAll("[data-rm]").forEach((b) =>
    b.addEventListener("click", () => {
      setCart(getCart().filter((n) => n !== b.dataset.rm));
      renderCart();
    }));
  $("#cartBuyAll").addEventListener("click", async () => {
    if ((shopCache?.balance ?? 0) < total) {
      return toast(`잔액이 부족해요. (필요 ${fmtWon(total)}원 / 보유 ${fmtWon(shopCache.balance)}원)`, true);
    }
    if (!confirm(`${items.length}개 게임을 총 ${fmtWon(total)}원에 일괄 구매할까요?\n\n각 게임의 링크가 디스코드 DM으로 발송됩니다.`)) return;
    try {
      $("#cartBuyAll").disabled = true;
      await api("/api/order", { games: items });
      setCart([]);
      $("#cartOverlay").hidden = true;
      toast("일괄 주문 완료! 봇이 곧 처리하고 게임마다 DM으로 링크를 보내드려요.");
      loadMy();
    } catch (e) {
      toast(e.message, true);
      renderCart();
    }
  });
}
$("#cartBtn").addEventListener("click", () => { $("#cartOverlay").hidden = false; renderCart(); });
$("#cartClose").addEventListener("click", () => { $("#cartOverlay").hidden = true; });
$("#cartOverlay").addEventListener("click", (e) => { if (e.target === $("#cartOverlay")) $("#cartOverlay").hidden = true; });
setCart(getCart());

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
              <div class="name">${esc(o.game)} · ${fmtWon(o.price)}원${o.kind === "reserve" ? ' <span class="game-tag">예약</span>' : ""}</div>
              <div class="sub">${fmtDate(o.created_at)}${o.result ? " · " + esc(o.result) : (o.status === "대기" || o.status === "처리중" ? " · 봇이 처리 중이에요 (최대 1분)" : "")}</div>
              ${o.kind === "reserve" && o.status === "완료" && !o.link_sent ? '<div class="sub">출시되면 링크가 발송돼요.</div>' : ""}
              <div class="link-slot" id="linkSlot${o.id}"></div>
            </div>
            <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px">
              <span class="badge ${esc(o.status)}">${esc(o.status)}</span>
              ${o.link_ok ? `<button class="small good" data-getlink="${o.id}">링크 받기</button>` : ""}
            </div>
          </div>
        </div>`).join("")
      : '<div class="empty">구매 내역이 없어요.</div>';
    obox.querySelectorAll("[data-getlink]").forEach((b) =>
      b.addEventListener("click", async () => {
        try {
          const r = await api("/api/my/link?id=" + b.dataset.getlink);
          const slot = $("#linkSlot" + b.dataset.getlink);
          slot.innerHTML = `<div class="link-box"><a href="${esc(r.link)}" target="_blank" rel="noopener">${esc(r.link)}</a>
            <button class="small" data-copy="${esc(r.link)}">복사</button></div>`;
          slot.querySelector("[data-copy]").addEventListener("click", async (ev) => {
            try { await navigator.clipboard.writeText(ev.target.dataset.copy); toast("링크 복사 완료!"); }
            catch (e) { toast("복사 실패 — 길게 눌러 복사해주세요.", true); }
          });
        } catch (e) { toast(e.message, true); }
      }));

    const cbox = $("#myCharges");
    cbox.innerHTML = data.charges.length
      ? data.charges.map((c) => `
        <div class="req-card">
          <div class="head">
            <div>
              <div class="name">${fmtWon(c.amount)}원 충전</div>
              <div class="sub">${fmtDate(c.created_at)} · ${
                { "대기": "곧 관리자에게 전달돼요",
                  "전달됨": "관리자 확인 중 · 결과는 디스코드 DM",
                  "승인처리중": "승인됨 · 잔액 반영 중 (약 1분)",
                  "승인": "충전 완료!",
                  "거절": "거절됨 · 사유는 디스코드 DM 확인" }[c.status] || ""}</div>
            </div>
            <span class="badge ${esc(c.status)}">${esc(c.status)}</span>
          </div>
        </div>`).join("")
      : '<div class="empty">충전 신청 내역이 없어요.</div>';
  } catch (e) { /* 무시 */ }
}
loadMy();
setInterval(loadMy, 30000);
