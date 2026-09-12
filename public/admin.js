// H Company - 관리자 페이지
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

let cache = [];        // 복구요청
let chargeCache = [];
let orderCache = [];
let noticeCache = [];
let upcomingCache = [];
let discountCache = [];
let bestCache = [];
let regCache = [];
let giftCache = [];
let categoryList = [];
let shopUpdatedAt = 0;
let filter = "대기";

// ---- 탭
document.querySelectorAll(".tabs button").forEach((btn) =>
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b === btn));
    document.querySelectorAll(".tab-page").forEach((p) => p.classList.toggle("active", p.id === "page-" + btn.dataset.tab));
  }));

document.querySelectorAll(".filter-bar button").forEach((b) =>
  b.addEventListener("click", () => {
    document.querySelectorAll(".filter-bar button").forEach((x) => x.classList.toggle("active", x === b));
    filter = b.dataset.f;
    renderRecover();
  }));

async function refresh() {
  const data = await api("/api/admin/requests");
  cache = data.requests;
  chargeCache = data.charges || [];
  orderCache = data.orders || [];
  noticeCache = data.notices || [];
  upcomingCache = data.upcoming || [];
  discountCache = data.discounts || [];
  bestCache = data.bests || [];
  giftCache = data.gifts || [];
  regCache = data.regs || [];
  categoryList = data.categories || [];
  shopUpdatedAt = data.shop_updated_at || 0;
  $("#dcGameList").innerHTML = (data.product_names || [])
    .map((p) => `<option value="${esc(p.name)}">${fmtWon(p.price)}원</option>`).join("");
  render();
}

function render() {
  const pending = cache.filter((r) => r.status === "대기").length;
  const chargePending = chargeCache.filter((c) => c.status === "대기" || c.status === "전달됨").length;
  const reservePending = orderCache.filter((o) => o.kind === "reserve" && o.status === "완료" && !o.link_sent).length;
  $("#stats").innerHTML = `
    <div class="stat"><div class="num">${pending}</div><div class="lbl">복구 대기</div></div>
    <div class="stat"><div class="num">${chargePending}</div><div class="lbl">충전 대기</div></div>
    <div class="stat"><div class="num">${orderCache.filter((o) => o.status === "대기" || o.status === "처리중").length}</div><div class="lbl">주문 처리중</div></div>
    <div class="stat"><div class="num">${reservePending}</div><div class="lbl">링크 발송 대기</div></div>`;
  setBadge("#cntPending", pending);
  setBadge("#cntCharge", chargePending);
  setBadge("#cntReserve", reservePending);
  renderRecover();
  renderCharges();
  renderOrders();
  renderNotices();
  renderUpcoming();
  renderDiscounts();
  renderBests();
  renderRegs();
  renderGifts();
}

function setBadge(sel, n) {
  const el = $(sel);
  el.hidden = n === 0;
  el.textContent = n;
}

// ---- 복구요청
function renderRecover() {
  const rows = cache.filter((r) => filter === "전체" || r.status === filter);
  const box = $("#list");
  box.innerHTML = rows.length
    ? rows.map((r) => `
      <div class="req-card">
        <div class="head">
          <div>
            <div class="name">${esc(r.game)}</div>
            <div class="sub">${esc(r.username)} (${esc(r.uid)}) · ${fmtDate(r.created_at)}</div>
            ${r.note ? `<div class="sub">메모: ${esc(r.note)}</div>` : ""}
            ${r.status !== "대기" && r.admin_reply ? `<div class="sub">${r.status === "완료" ? "보낸 링크" : "거절 사유"}: ${esc(r.admin_reply)}</div>` : ""}
          </div>
          <span class="badge ${esc(r.status)}">${esc(r.status)}</span>
        </div>
        ${r.image ? `
        <div style="margin-top:10px">
          <div class="sub" style="margin-bottom:4px">구매내역 캡쳐 (클릭하면 크게 보기)</div>
          <a href="/api/admin/image?id=${r.id}" target="_blank"><img class="req-thumb" src="/api/admin/image?id=${r.id}" alt="구매내역 캡쳐"></a>
        </div>` : `<div class="sub" style="margin-top:8px">캡쳐 없음 (구버전 요청)</div>`}
        ${r.status === "대기" ? `
        <div class="controls">
          <input type="text" data-link maxlength="500" placeholder="복구 링크 (https://...)">
          <input type="text" data-msg maxlength="500" placeholder="추가 메시지 / 거절 사유 (선택)">
        </div>
        <div class="controls">
          <button class="small good" data-approve>DM 발송 & 완료</button>
          <button class="small" data-reject>거절 (사유 DM)</button>
          <button class="small danger" data-del>삭제</button>
        </div>` : `
        <div class="controls">
          <button class="small danger" data-del>삭제</button>
        </div>`}
      </div>`).join("")
    : '<div class="empty">표시할 요청이 없어요.</div>';

  box.querySelectorAll(".req-card").forEach((card, i) => {
    const r = rows[i];
    const approveBtn = card.querySelector("[data-approve]");
    if (approveBtn) {
      approveBtn.addEventListener("click", async () => {
        const link = card.querySelector("[data-link]").value.trim();
        const message = card.querySelector("[data-msg]").value.trim();
        if (!link) return toast("복구 링크를 입력하세요.", true);
        try {
          approveBtn.disabled = true;
          await api("/api/admin/respond", { id: r.id, action: "approve", link, message });
          toast("DM 발송 완료!");
          refresh();
        } catch (e) {
          toast(e.message, true);
          approveBtn.disabled = false;
        }
      });
      card.querySelector("[data-reject]").addEventListener("click", async () => {
        const message = card.querySelector("[data-msg]").value.trim();
        if (!confirm(`[${r.game}] 요청을 거절하고 사유를 DM으로 보낼까요?`)) return;
        try {
          await api("/api/admin/respond", { id: r.id, action: "reject", message });
          toast("거절 처리 및 DM 발송 완료");
          refresh();
        } catch (e) { toast(e.message, true); }
      });
    }
    card.querySelector("[data-del]").addEventListener("click", async () => {
      if (!confirm(`[${r.game}] 요청 기록을 삭제할까요?`)) return;
      try {
        await api("/api/admin/delete", { id: r.id });
        toast("삭제 완료");
        refresh();
      } catch (e) { toast(e.message, true); }
    });
  });
}

// ---- 충전 관리
function renderCharges() {
  $("#syncInfo").textContent = shopUpdatedAt
    ? `(마지막 봇 동기화: ${fmtDate(shopUpdatedAt)})`
    : "(아직 봇과 동기화 전 — 봇을 켜야 승인 반영이 됩니다)";
  const box = $("#chargeList");
  box.innerHTML = chargeCache.length
    ? chargeCache.map((c) => `
      <div class="req-card">
        <div class="head">
          <div>
            <div class="name">${fmtWon(c.amount)}원</div>
            <div class="sub">${esc(c.username)} (${esc(c.uid)}) · ${fmtDate(c.created_at)}</div>
            <div class="sub">코드1: ${esc(c.code1)}${c.code2 ? " · 코드2: " + esc(c.code2) : ""}</div>
            ${c.admin_note ? `<div class="sub">거절 사유: ${esc(c.admin_note)}</div>` : ""}
          </div>
          <span class="badge ${esc(c.status)}">${esc(c.status)}</span>
        </div>
        ${(c.status === "대기" || c.status === "전달됨") ? `
        <div class="controls">
          <input type="text" data-reason maxlength="200" placeholder="거절 사유 (거절 시에만)">
        </div>
        <div class="controls">
          <button class="small good" data-capprove>승인 (잔액 충전)</button>
          <button class="small" data-creject>거절 (사유 DM)</button>
        </div>` : ""}
      </div>`).join("")
    : '<div class="empty">충전 신청이 없어요.</div>';

  box.querySelectorAll(".req-card").forEach((card, i) => {
    const c = chargeCache[i];
    const ap = card.querySelector("[data-capprove]");
    if (!ap) return;
    ap.addEventListener("click", async () => {
      if (!confirm(`${esc(c.username)}님에게 ${fmtWon(c.amount)}원을 충전 승인할까요?\n(문상 코드를 먼저 확인하세요!)`)) return;
      try {
        ap.disabled = true;
        const r = await api("/api/admin/charge_action", { id: c.id, action: "approve" });
        toast(r.msg || "승인 완료");
        refresh();
      } catch (e) {
        toast(e.message, true);
        ap.disabled = false;
      }
    });
    card.querySelector("[data-creject]").addEventListener("click", async () => {
      const reason = card.querySelector("[data-reason]").value.trim();
      if (!confirm(`${fmtWon(c.amount)}원 충전을 거절하고 사유를 DM으로 보낼까요?`)) return;
      try {
        await api("/api/admin/charge_action", { id: c.id, action: "reject", reason });
        toast("거절 처리 및 DM 발송 완료");
        refresh();
      } catch (e) { toast(e.message, true); }
    });
  });
}

// ---- 주문·예약
function renderOrders() {
  const box = $("#orderList");
  box.innerHTML = orderCache.length
    ? orderCache.map((o) => `
      <div class="req-card">
        <div class="head">
          <div>
            <div class="name">${esc(o.game)} · ${fmtWon(o.price)}원${
              { reserve: ' <span class="game-tag">예약</span>',
                pass: ' <span class="game-tag pass-tag">게임패스</span>',
                claim: ' <span class="game-tag pass-tag">무료 수령</span>' }[o.kind] || ""}${o.fixed && o.kind === "order" ? ' <span class="game-tag hot">할인가</span>' : ""}</div>
            <div class="sub">${esc(o.username)} (${esc(o.uid)}) · ${fmtDate(o.created_at)}</div>
            ${o.result ? `<div class="sub">${esc(o.result)}</div>` : ""}
            ${o.kind === "reserve" && o.link_sent ? '<div class="sub">✅ 출시 링크 발송됨</div>' : ""}
          </div>
          <span class="badge ${esc(o.status)}">${esc(o.status)}</span>
        </div>
        ${o.kind === "reserve" && o.status === "완료" && !o.link_sent ? `
        <div class="controls">
          <input type="text" data-rmsg maxlength="300" placeholder="추가 메시지 (선택)">
          <button class="small good" data-sendlink="${o.id}">출시 링크 발송</button>
        </div>` : ""}
      </div>`).join("")
    : '<div class="empty">주문이 없어요.</div>';

  box.querySelectorAll("[data-sendlink]").forEach((b) =>
    b.addEventListener("click", async () => {
      const card = b.closest(".req-card");
      const message = card.querySelector("[data-rmsg]").value.trim();
      if (!confirm("판매 목록에 등록된 이 게임의 링크를 예약자 DM으로 보낼까요?")) return;
      try {
        b.disabled = true;
        await api("/api/admin/reservation_send", { id: Number(b.dataset.sendlink), message });
        toast("출시 링크 발송 완료!");
        refresh();
      } catch (e) {
        toast(e.message, true);
        b.disabled = false;
      }
    }));
}

// ---- 공지 관리
function renderNotices() {
  const box = $("#noticeAdminList");
  box.innerHTML = noticeCache.length
    ? noticeCache.map((n) => `
      <div class="req-card">
        <div class="head">
          <div style="flex:1;min-width:0">
            <input type="text" data-nt maxlength="100" value="${esc(n.title)}" style="font-weight:700;margin-bottom:6px">
            <textarea data-nb maxlength="2000" style="min-height:60px;font-size:.86rem">${esc(n.body)}</textarea>
            <div class="sub" style="margin-top:4px">${fmtDate(n.created_at)}</div>
          </div>
        </div>
        <div class="controls">
          <button class="small good" data-nsave="${n.id}">수정 저장</button>
          <button class="small danger" data-ndel="${n.id}">삭제</button>
        </div>
      </div>`).join("")
    : '<div class="empty">공지가 없어요.</div>';

  box.querySelectorAll("[data-nsave]").forEach((b) =>
    b.addEventListener("click", async () => {
      const card = b.closest(".req-card");
      try {
        await api("/api/admin/notice", {
          action: "update", id: Number(b.dataset.nsave),
          title: card.querySelector("[data-nt]").value.trim(),
          body: card.querySelector("[data-nb]").value.trim(),
        });
        toast("공지 수정 완료");
        refresh();
      } catch (e) { toast(e.message, true); }
    }));
  box.querySelectorAll("[data-ndel]").forEach((b) =>
    b.addEventListener("click", async () => {
      if (!confirm("이 공지를 삭제할까요?")) return;
      try {
        await api("/api/admin/notice", { action: "delete", id: Number(b.dataset.ndel) });
        toast("삭제 완료");
        refresh();
      } catch (e) { toast(e.message, true); }
    }));
}

$("#ntAdd").addEventListener("click", async () => {
  const title = $("#ntTitle").value.trim();
  const body = $("#ntBody").value.trim();
  if (!title) return toast("제목을 입력하세요.", true);
  try {
    await api("/api/admin/notice", { action: "add", title, body });
    $("#ntTitle").value = "";
    $("#ntBody").value = "";
    toast("공지 등록 완료");
    refresh();
  } catch (e) { toast(e.message, true); }
});

// ---- 신작 관리
let upImageData = "";

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

function clearUpImage() {
  upImageData = "";
  $("#upPreviewImg").src = "";
  $("#upPreview").hidden = true;
  $("#upDrop").hidden = false;
  $("#upImageFile").value = "";
}

$("#upDrop").addEventListener("click", () => $("#upImageFile").click());
$("#upImageFile").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file || !file.type.startsWith("image/")) return toast("이미지 파일만 첨부할 수 있어요.", true);
  try {
    upImageData = await compressImage(file);
    $("#upPreviewImg").src = upImageData;
    $("#upPreview").hidden = false;
    $("#upDrop").hidden = true;
  } catch (err) { toast("이미지를 읽을 수 없어요.", true); }
});
$("#upRemoveImage").addEventListener("click", clearUpImage);
["dragover", "dragleave", "drop"].forEach((evt) =>
  $("#upDrop").addEventListener(evt, (e) => {
    e.preventDefault();
    $("#upDrop").classList.toggle("dragover", evt === "dragover");
    if (evt === "drop") $("#upImageFile").files = e.dataTransfer.files,
      $("#upImageFile").dispatchEvent(new Event("change"));
  }));

$("#upAdd").addEventListener("click", async () => {
  const body = {
    action: "add",
    name: $("#upName").value.trim(),
    price: $("#upPrice").value.trim(),
    discount_price: $("#upDc").value.trim(),
    note: $("#upNote").value.trim(),
  };
  if (upImageData) body.image = upImageData;
  if (!body.name || !body.price) return toast("이름/출시가를 입력하세요.", true);
  try {
    await api("/api/admin/upcoming", body);
    ["upName", "upPrice", "upDc", "upNote"].forEach((id) => ($("#" + id).value = ""));
    clearUpImage();
    toast("신작 등록 완료 — 유저 목록 하단에 표시됩니다.");
    refresh();
  } catch (e) { toast(e.message, true); }
});

function renderUpcoming() {
  const box = $("#upcomingAdminList");
  box.innerHTML = upcomingCache.length
    ? upcomingCache.map((u) => `
      <div class="req-card">
        <div class="head">
          <div style="display:flex;align-items:center;gap:12px;min-width:0">
            ${u.image ? `<img class="req-thumb" src="/api/shop/upcimg?id=${u.id}" alt="" style="max-height:70px">` : ""}
            <div style="flex:1;min-width:0">
              <input type="text" data-un maxlength="100" value="${esc(u.name)}" style="font-weight:700">
              <div class="controls" style="margin-top:6px">
                <input type="text" data-up value="${u.price}" placeholder="출시가" style="max-width:110px;flex:none">
                <input type="text" data-ud value="${u.discount_price}" placeholder="예약가" style="max-width:110px;flex:none">
                <input type="text" data-uo maxlength="300" value="${esc(u.note)}" placeholder="소개">
              </div>
            </div>
          </div>
        </div>
        <div class="controls">
          <button class="small good" data-usave="${u.id}">수정 저장</button>
          <button class="small danger" data-udel="${u.id}">삭제 (출시 후)</button>
        </div>
      </div>`).join("")
    : '<div class="empty">등록된 신작이 없어요.</div>';

  box.querySelectorAll("[data-usave]").forEach((b) =>
    b.addEventListener("click", async () => {
      const card = b.closest(".req-card");
      try {
        await api("/api/admin/upcoming", {
          action: "update", id: Number(b.dataset.usave),
          name: card.querySelector("[data-un]").value.trim(),
          price: card.querySelector("[data-up]").value.trim(),
          discount_price: card.querySelector("[data-ud]").value.trim(),
          note: card.querySelector("[data-uo]").value.trim(),
        });
        toast("수정 완료");
        refresh();
      } catch (e) { toast(e.message, true); }
    }));
  box.querySelectorAll("[data-udel]").forEach((b) =>
    b.addEventListener("click", async () => {
      if (!confirm("이 신작 항목을 삭제할까요? (예약자 링크 발송을 먼저 확인하세요)")) return;
      try {
        await api("/api/admin/upcoming", { action: "delete", id: Number(b.dataset.udel) });
        toast("삭제 완료");
        refresh();
      } catch (e) { toast(e.message, true); }
    }));
}

// ---- 할인 관리
$("#dcSet").addEventListener("click", async () => {
  const game = $("#dcGame").value.trim();
  const sale_price = $("#dcPrice").value.trim();
  if (!game || !sale_price) return toast("게임 이름과 할인가를 입력하세요.", true);
  try {
    await api("/api/admin/discount", { action: "set", game, sale_price });
    $("#dcGame").value = "";
    $("#dcPrice").value = "";
    toast("할인 시작! 유저 목록 [🔥 할인]에 표시됩니다.");
    refresh();
  } catch (e) { toast(e.message, true); }
});

function renderDiscounts() {
  const box = $("#discountAdminList");
  box.innerHTML = discountCache.length
    ? discountCache.map((d) => `
      <div class="req-card">
        <div class="head">
          <div>
            <div class="name">${esc(d.game)}</div>
            <div class="sub">할인가 ${fmtWon(d.sale_price)}원 · ${fmtDate(d.created_at)}</div>
          </div>
          <button class="small danger" data-dcoff="${esc(d.game)}">할인 종료</button>
        </div>
      </div>`).join("")
    : '<div class="empty">할인 중인 게임이 없어요.</div>';
  box.querySelectorAll("[data-dcoff]").forEach((b) =>
    b.addEventListener("click", async () => {
      if (!confirm(`'${b.dataset.dcoff}' 할인을 종료할까요?`)) return;
      try {
        await api("/api/admin/discount", { action: "unset", game: b.dataset.dcoff });
        toast("할인 종료");
        refresh();
      } catch (e) { toast(e.message, true); }
    }));
}

// ---- 게임 등록 (미디어 첨부)
let rgMedia = [];   // dataURL 목록 (최대 4)

function renderRgPreview() {
  const box = $("#rgPreview");
  box.hidden = rgMedia.length === 0;
  $("#rgDrop").hidden = rgMedia.length >= 4;
  box.innerHTML = rgMedia.map((du, i) => `
    <div style="position:relative">
      ${du.startsWith("data:video")
        ? `<video src="${du}" muted style="height:90px;border:1px solid #d4d4d8;border-radius:8px"></video>`
        : `<img src="${du}" style="height:90px;border:1px solid #d4d4d8;border-radius:8px">`}
      ${i === 0 ? '<span style="position:absolute;top:4px;left:4px;background:#111;color:#fff;font-size:.62rem;font-weight:800;border-radius:5px;padding:1px 6px">대표</span>' : ""}
      <button type="button" data-rgrm="${i}" style="position:absolute;top:4px;right:4px;width:20px;height:20px;border-radius:50%;border:none;background:rgba(0,0,0,.7);color:#fff;font-weight:800;cursor:pointer;line-height:1">×</button>
    </div>`).join("");
  box.querySelectorAll("[data-rgrm]").forEach((b) =>
    b.addEventListener("click", () => {
      rgMedia.splice(Number(b.dataset.rgrm), 1);
      renderRgPreview();
    }));
}

async function addRgFiles(files) {
  for (const file of files) {
    if (rgMedia.length >= 4) return toast("미디어는 최대 4개까지예요.", true);
    if (file.type.startsWith("image/")) {
      try {
        rgMedia.push(await compressImage(file));
      } catch (e) { toast(`이미지를 읽을 수 없어요: ${file.name}`, true); }
    } else if (file.type === "video/mp4" || file.type === "video/webm") {
      if (file.size > 8 * 1024 * 1024) { toast(`영상은 8MB 이하만 가능해요: ${file.name}`, true); continue; }
      rgMedia.push(await new Promise((res, rej) => {
        const r = new FileReader();
        r.onload = () => res(r.result);
        r.onerror = rej;
        r.readAsDataURL(file);
      }));
    } else {
      toast(`지원하지 않는 형식이에요: ${file.name}`, true);
    }
  }
  renderRgPreview();
}

$("#rgDrop").addEventListener("click", () => $("#rgFiles").click());
$("#rgFiles").addEventListener("change", (e) => { addRgFiles([...e.target.files]); e.target.value = ""; });
["dragover", "dragleave", "drop"].forEach((evt) =>
  $("#rgDrop").addEventListener(evt, (e) => {
    e.preventDefault();
    $("#rgDrop").classList.toggle("dragover", evt === "dragover");
    if (evt === "drop") addRgFiles([...e.dataTransfer.files]);
  }));

$("#rgAdd").addEventListener("click", async () => {
  const body = {
    name: $("#rgName").value.trim(),
    category: $("#rgCat").value.trim(),
    price: $("#rgPrice").value.trim(),
    official: $("#rgOfficial").value.trim(),
    link: $("#rgLink").value.trim(),
    rating: $("#rgRating").value.trim(),
    seller: $("#rgSeller").value.trim(),
    comment: $("#rgComment").value,
    images: rgMedia,
  };
  if (!body.name || !body.category || !body.price || !body.link) {
    return toast("이름/카테고리/판매가/링크는 필수입니다.", true);
  }
  if (!confirm(`'${body.name}'을(를) [${body.category}] ${Number(String(body.price).replace(/,/g, "")).toLocaleString("ko-KR")}원으로 등록할까요?${rgMedia.length ? `\n(미디어 ${rgMedia.length}개 + 소개글 게시 포함)` : ""}`)) return;
  try {
    $("#rgAdd").disabled = true;
    const r = await api("/api/admin/product_reg", body);
    ["rgName", "rgCat", "rgPrice", "rgOfficial", "rgLink", "rgRating", "rgSeller", "rgComment"].forEach((id) => ($("#" + id).value = ""));
    rgMedia = [];
    renderRgPreview();
    toast("등록 신청 완료!" + (r.note ? " " + r.note : "") + " (판매 반영은 1분 내)");
    refresh();
  } catch (e) {
    toast(e.message, true);
  } finally {
    $("#rgAdd").disabled = false;
  }
});

function renderRegs() {
  const dl = $("#catList");
  dl.innerHTML = categoryList.map((c) => `<option value="${esc(c)}">`).join("");
  const box = $("#regList");
  box.innerHTML = regCache.length
    ? regCache.map((r) => `
      <div class="req-card">
        <div class="head">
          <div>
            <div class="name">${esc(r.name)} · ${fmtWon(r.price)}원</div>
            <div class="sub">[${esc(r.category)}] · ${fmtDate(r.created_at)}</div>
            <div class="sub" style="word-break:break-all">링크: ${esc(r.link)}</div>
            ${r.result ? `<div class="sub">${esc(r.result)}</div>` : (r.status !== "완료" ? '<div class="sub">봇이 처리 중이에요 (최대 1분)</div>' : "")}
          </div>
          <span class="badge ${esc(r.status)}">${esc(r.status)}</span>
        </div>
      </div>`).join("")
    : '<div class="empty">등록 신청 내역이 없어요.</div>';
}

// ---- BEST 관리
$("#bestSet").addEventListener("click", async () => {
  const game = $("#bestGame").value.trim();
  if (!game) return toast("게임 이름을 입력하세요.", true);
  try {
    await api("/api/admin/best", { action: "set", game });
    $("#bestGame").value = "";
    toast("BEST 지정 완료! 유저 목록 최상단에 표시됩니다.");
    refresh();
  } catch (e) { toast(e.message, true); }
});

function renderBests() {
  const box = $("#bestAdminList");
  box.innerHTML = bestCache.length
    ? bestCache.map((b) => `
      <div class="req-card">
        <div class="head">
          <div class="name">⭐ ${esc(b.game)}</div>
          <button class="small danger" data-bestoff="${esc(b.game)}">해제</button>
        </div>
      </div>`).join("")
    : '<div class="empty">지정된 BEST 게임이 없어요.</div>';
  box.querySelectorAll("[data-bestoff]").forEach((b) =>
    b.addEventListener("click", async () => {
      try {
        await api("/api/admin/best", { action: "unset", game: b.dataset.bestoff });
        toast("BEST 해제");
        refresh();
      } catch (e) { toast(e.message, true); }
    }));
}

// ---- 사은품 관리
let gfImageData = "";

function clearGfImage() {
  gfImageData = "";
  $("#gfPreviewImg").src = "";
  $("#gfPreview").hidden = true;
  $("#gfDrop").hidden = false;
  $("#gfImageFile").value = "";
}

$("#gfDrop").addEventListener("click", () => $("#gfImageFile").click());
$("#gfImageFile").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file || !file.type.startsWith("image/")) return toast("이미지 파일만 첨부할 수 있어요.", true);
  try {
    gfImageData = await compressImage(file);
    $("#gfPreviewImg").src = gfImageData;
    $("#gfPreview").hidden = false;
    $("#gfDrop").hidden = true;
  } catch (err) { toast("이미지를 읽을 수 없어요.", true); }
});
$("#gfRemoveImage").addEventListener("click", clearGfImage);
["dragover", "dragleave", "drop"].forEach((evt) =>
  $("#gfDrop").addEventListener(evt, (e) => {
    e.preventDefault();
    $("#gfDrop").classList.toggle("dragover", evt === "dragover");
    if (evt === "drop") {
      $("#gfImageFile").files = e.dataTransfer.files;
      $("#gfImageFile").dispatchEvent(new Event("change"));
    }
  }));

$("#gfAdd").addEventListener("click", async () => {
  const body = {
    action: "add",
    min_amount: $("#gfMin").value.trim(),
    value: $("#gfValue").value.trim() || "0",
    game: $("#gfGame").value.trim(),
    link: $("#gfLink").value.trim(),
  };
  if (gfImageData) body.image = gfImageData;
  if (!body.min_amount || !body.game || !body.link) {
    return toast("기준 금액/사은품 게임/링크를 입력하세요.", true);
  }
  try {
    await api("/api/admin/gift", body);
    ["gfMin", "gfValue", "gfGame", "gfLink"].forEach((id) => ($("#" + id).value = ""));
    clearGfImage();
    toast("사은품 등록 완료! 유저 목록 상단에 파란 배너로 표시됩니다.");
    refresh();
  } catch (e) { toast(e.message, true); }
});

function renderGifts() {
  const box = $("#giftAdminList");
  box.innerHTML = giftCache.length
    ? giftCache.map((g) => `
      <div class="req-card" style="border-color:#bfdbfe;background:#eff6ff">
        <div class="head">
          <div style="display:flex;align-items:center;gap:12px;min-width:0">
            ${g.image ? `<img class="req-thumb" src="/api/shop/giftimg?id=${g.id}" alt="" style="max-height:60px">` : ""}
            <div>
            <div class="name">🎁 ${esc(g.game)}${g.value ? ` <span class="sub">(정가 ${fmtWon(g.value)}원)</span>` : ""}</div>
            <div class="sub">1회 <b>${fmtWon(g.min_amount)}원</b> 이상 구매 시 지급 · ${fmtDate(g.created_at)}</div>
            <div class="sub" style="word-break:break-all">링크: ${esc(g.link)}</div>
            </div>
          </div>
          <button class="small danger" data-gfdel="${g.id}">삭제</button>
        </div>
      </div>`).join("")
    : '<div class="empty">등록된 사은품이 없어요.</div>';
  box.querySelectorAll("[data-gfdel]").forEach((b) =>
    b.addEventListener("click", async () => {
      if (!confirm("이 사은품을 삭제할까요?")) return;
      try {
        await api("/api/admin/gift", { action: "delete", id: Number(b.dataset.gfdel) });
        toast("삭제 완료");
        refresh();
      } catch (e) { toast(e.message, true); }
    }));
}

api("/api/me").then((me) => { $("#who").textContent = `${me.name} 님`; }).catch(() => {});
refresh().catch((e) => toast(e.message, true));
setInterval(() => refresh().catch(() => {}), 30000);
