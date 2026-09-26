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

// 파일들 → 미디어 dataURL 목록 (이미지는 압축, mp4/webm 8MB 이하, 최대 4개). 게임 등록·수정 공용
async function readMediaFiles(files, list) {
  const out = [...list];
  for (const file of files) {
    if (out.length >= 4) { toast("미디어는 최대 4개까지예요.", true); break; }
    if (file.type.startsWith("image/")) {
      try {
        out.push(await compressImage(file));
      } catch (e) { toast(`이미지를 읽을 수 없어요: ${file.name}`, true); }
    } else if (file.type === "video/mp4" || file.type === "video/webm") {
      if (file.size > 8 * 1024 * 1024) { toast(`영상은 8MB 이하만 가능해요: ${file.name}`, true); continue; }
      out.push(await new Promise((res, rej) => {
        const r = new FileReader();
        r.onload = () => res(r.result);
        r.onerror = rej;
        r.readAsDataURL(file);
      }));
    } else {
      toast(`지원하지 않는 형식이에요: ${file.name}`, true);
    }
  }
  return out;
}

async function addRgFiles(files) {
  rgMedia = await readMediaFiles(files, rgMedia);
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
            <div class="name">${r.kind === "edit" ? "[수정] " + (r.old_name !== r.name ? `${esc(r.old_name)} → ` : "") : ""}${esc(r.name)} · ${fmtWon(r.price)}원</div>
            <div class="sub">[${esc(r.category)}] · ${fmtDate(r.created_at)}</div>
            <div class="sub" style="word-break:break-all">링크: ${esc(r.link)}</div>
            ${r.result ? `<div class="sub">${esc(r.result)}</div>` : (r.status !== "완료" ? '<div class="sub">봇이 처리 중이에요 (최대 1분)</div>' : "")}
          </div>
          <span class="badge ${esc(r.status)}">${esc(r.status)}</span>
        </div>
      </div>`).join("")
    : '<div class="empty">등록 신청 내역이 없어요.</div>';
}

// ---- 게임 관리 (확인·수정)
let gameCache = [];
let gmOpen = "";      // 수정 창이 열린 게임 이름
let gmMedia = [];     // 교체할 새 미디어 dataURL (비어 있으면 기존 유지)

async function loadGames() {
  try {
    const d = await api("/api/admin/games");
    gameCache = d.games || [];
    const sel = $("#gmCat");
    const cur = sel.value;
    const cats = [...new Set(gameCache.map((g) => g.category))];
    sel.innerHTML = '<option value="">전체 카테고리</option>' +
      cats.map((c) => `<option value="${esc(c)}">${esc(c)}</option>`).join("");
    sel.value = cats.includes(cur) ? cur : "";
    $("#gmInfo").textContent = d.updated_at ? `봇 마지막 동기화 ${fmtDate(d.updated_at)}` : "";
    renderGames();
  } catch (e) { toast(e.message, true); }
}

function gmThumb(g) {
  if (!g.media.length) return '<div class="gm-thumb gm-noimg">이미지 없음</div>';
  const src = `/api/shop/image?name=${encodeURIComponent(g.name)}&i=0`;
  return g.media[0] === "video"
    ? `<video class="gm-thumb" src="${src}" muted preload="metadata"></video>`
    : `<img class="gm-thumb" src="${src}" loading="lazy" alt="">`;
}

function gmEditor(g) {
  const dt = g.detail || {};
  const cur = g.media.map((m, i) => {
    const src = `/api/shop/image?name=${encodeURIComponent(g.name)}&i=${i}`;
    return m === "video" ? `<video src="${src}" muted preload="metadata"></video>` : `<img src="${src}" alt="">`;
  }).join("");
  return `
    <div class="gm-edit">
      <label>게임 이름</label>
      <input type="text" data-f="name" maxlength="100" value="${esc(g.name)}">
      <div class="row2">
        <div><label>카테고리</label><input type="text" data-f="category" maxlength="30" list="catList" value="${esc(g.category)}"></div>
        <div><label>판매가 (원)</label><input type="text" data-f="price" maxlength="12" value="${g.price}"></div>
      </div>
      <div class="row2">
        <div><label>정가 (원, 선택)</label><input type="text" data-f="official" maxlength="12" value="${dt.official || ""}"></div>
        <div><label>수위 (선택)</label><input type="text" data-f="rating" maxlength="40" value="${esc(dt.rating || "")}"></div>
      </div>
      <label>다운로드 링크</label>
      <input type="text" data-f="link" maxlength="500" value="${esc(g.link)}">
      <label>공식 판매처 링크 (선택)</label>
      <input type="text" data-f="seller" maxlength="300" value="${esc(dt.seller || "")}">
      <label>코멘트 (선택 · 한 줄당 하나)</label>
      <textarea data-f="comment" maxlength="1500" style="min-height:70px">${esc((dt.comments || []).join("\n"))}</textarea>
      <label>이미지·영상</label>
      <div class="gm-media" data-gm-cur>${cur || '<span class="hint">등록된 미디어가 없어요.</span>'}</div>
      <div class="dropzone" data-gm-drop style="margin-top:8px"><span>새 미디어로 교체하려면 클릭하거나 끌어다 놓으세요 (최대 4개, 첫 번째가 대표)</span></div>
      <input type="file" data-gm-file accept="image/*,video/mp4,video/webm" multiple hidden>
      <div class="gm-media" data-gm-new hidden></div>
      <div class="controls">
        <button class="small good" data-gm-save>수정 저장</button>
        <button class="small" data-gm-cancel>취소</button>
      </div>
    </div>`;
}

function renderGames() {
  const q = $("#gmSearch").value.trim().toLowerCase();
  const cat = $("#gmCat").value;
  const rows = gameCache.filter((g) => (!cat || g.category === cat) &&
    (!q || g.name.toLowerCase().includes(q) || (g.link || "").toLowerCase().includes(q)));
  const box = $("#gmList");
  const head = `<div class="hint" style="margin-bottom:6px">${rows.length}개${rows.length !== gameCache.length ? ` / 전체 ${gameCache.length}개` : ""}</div>`;
  box.innerHTML = rows.length ? head + rows.map((g) => {
    const dt = g.detail || {};
    const tags = [
      g.pending ? `<span class="gm-tag">수정 ${esc(g.pending)}</span>` : "",
      g.sale_price ? `<span class="gm-tag">할인 ${fmtWon(g.sale_price)}원</span>` : "",
      g.best ? '<span class="gm-tag">BEST</span>' : "",
      g.is_subscription ? '<span class="gm-tag dim">정기결제</span>' : "",
    ].join("");
    return `
      <div class="req-card gm-row" data-gm="${esc(g.name)}">
        <div class="head">
          <div style="display:flex;gap:12px;min-width:0;flex:1">
            ${gmThumb(g)}
            <div style="min-width:0">
              <div class="name">${esc(g.name)}${tags}</div>
              <div class="sub">[${esc(g.category)}] · ${fmtWon(g.price)}원${dt.official ? ` (정가 ${fmtWon(dt.official)}원)` : ""}${dt.rating ? ` · ${esc(dt.rating)}` : ""} · 미디어 ${g.media.length}개${g.reg ? ` · 등록 ${fmtDate(g.reg)}` : ""}</div>
              ${g.link ? `<div class="sub">링크: <a class="gm-link" href="${esc(g.link)}" target="_blank" rel="noopener noreferrer">${esc(g.link)}</a></div>` : ""}
            </div>
          </div>
          ${g.is_subscription ? "" : `<button class="small" data-gm-toggle>${gmOpen === g.name ? "닫기" : "수정"}</button>`}
        </div>
        ${gmOpen === g.name ? gmEditor(g) : ""}
      </div>`;
  }).join("") : '<div class="empty">게임이 없어요.</div>';

  box.querySelectorAll("[data-gm-toggle]").forEach((b) =>
    b.addEventListener("click", () => {
      const name = b.closest("[data-gm]").dataset.gm;
      gmOpen = gmOpen === name ? "" : name;
      gmMedia = [];
      renderGames();
    }));
  const card = gmOpen && [...box.querySelectorAll("[data-gm]")].find((c) => c.dataset.gm === gmOpen);
  if (card && card.querySelector(".gm-edit")) bindGmEditor(card);
}

function renderGmNew(card) {
  const box = card.querySelector("[data-gm-new]");
  box.hidden = gmMedia.length === 0;
  card.querySelector("[data-gm-cur]").style.opacity = gmMedia.length ? ".35" : "";
  card.querySelector("[data-gm-drop]").hidden = gmMedia.length >= 4;
  box.innerHTML = gmMedia.map((du, i) => `
    <div style="position:relative">
      ${du.startsWith("data:video") ? `<video src="${du}" muted></video>` : `<img src="${du}" alt="">`}
      <button type="button" data-gmrm="${i}" style="position:absolute;top:4px;right:4px;width:20px;height:20px;border-radius:50%;border:none;background:rgba(0,0,0,.7);color:#fff;font-weight:800;cursor:pointer;line-height:1">×</button>
    </div>`).join("");
  box.querySelectorAll("[data-gmrm]").forEach((b) =>
    b.addEventListener("click", () => { gmMedia.splice(Number(b.dataset.gmrm), 1); renderGmNew(card); }));
}

function bindGmEditor(card) {
  const g = gameCache.find((x) => x.name === gmOpen);
  const file = card.querySelector("[data-gm-file]");
  const drop = card.querySelector("[data-gm-drop]");
  const add = async (files) => { gmMedia = await readMediaFiles(files, gmMedia); renderGmNew(card); };
  drop.addEventListener("click", () => file.click());
  file.addEventListener("change", (e) => { add([...e.target.files]); e.target.value = ""; });
  ["dragover", "dragleave", "drop"].forEach((evt) =>
    drop.addEventListener(evt, (e) => {
      e.preventDefault();
      drop.classList.toggle("dragover", evt === "dragover");
      if (evt === "drop") add([...e.dataTransfer.files]);
    }));
  renderGmNew(card);
  card.querySelector("[data-gm-cancel]").addEventListener("click", () => { gmOpen = ""; gmMedia = []; renderGames(); });
  card.querySelector("[data-gm-save]").addEventListener("click", async (e) => {
    const v = (k) => card.querySelector(`[data-f="${k}"]`).value;
    const body = {
      old_name: g.name,
      name: v("name").trim(), category: v("category").trim(), price: v("price").trim(),
      official: v("official").trim(), link: v("link").trim(), rating: v("rating").trim(),
      seller: v("seller").trim(), comment: v("comment"), images: gmMedia,
    };
    if (!body.name || !body.category || !body.price || !body.link) {
      return toast("이름/카테고리/판매가/링크는 필수입니다.", true);
    }
    const changes = [];
    if (body.name !== g.name) changes.push(`이름: ${g.name} → ${body.name}`);
    if (body.category !== g.category) changes.push(`카테고리: ${g.category} → ${body.category}`);
    if (Number(body.price.replace(/,/g, "")) !== g.price) changes.push(`가격: ${fmtWon(g.price)} → ${fmtWon(body.price.replace(/,/g, ""))}원`);
    if (body.link !== g.link) changes.push("다운로드 링크 변경 (만료 타이머 초기화)");
    if (gmMedia.length) changes.push(`미디어 ${gmMedia.length}개로 교체`);
    if (!confirm(`'${g.name}' 수정할까요?${changes.length ? "\n\n· " + changes.join("\n· ") : ""}`)) return;
    try {
      e.target.disabled = true;
      const r = await api("/api/admin/product_edit", body);
      gmOpen = "";
      gmMedia = [];
      toast("수정 완료!" + (r.queued ? " (판매 목록 반영은 1분 내)" : "") + (r.note ? " " + r.note : ""));
      loadGames();
      refresh();
    } catch (err) {
      toast(err.message, true);
      e.target.disabled = false;
    }
  });
}

$("#gmSearch").addEventListener("input", renderGames);
$("#gmCat").addEventListener("change", renderGames);
$("#gmReload").addEventListener("click", loadGames);
document.querySelector('.tabs button[data-tab="games"]').addEventListener("click", () => {
  if (!gmOpen) loadGames();
});

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


// ---- 뽑기 보상표 / 기록
let gaConfig = null;
let gaColors = {};

async function loadGachaAdmin() {
  try {
    const d = await api("/api/admin/gacha");
    gaConfig = d.config;
    gaColors = d.colors || {};
    renderGachaEditor(d.custom);
    renderGachaLog(d);
  } catch (e) {
    $("#gaEditor").innerHTML = `<div class="empty">${esc(e.message)}</div>`;
  }
}

function renderGachaEditor(custom) {
  $("#gaStatus").textContent = custom ? "현재: 관리자가 수정한 보상표 사용 중" : "현재: 기본 보상표 사용 중";
  $("#gaEditor").innerHTML = ["normal", "premium"].map((key) => {
    const b = gaConfig[key];
    return `
      <div class="ga-box" data-box="${key}">
        <h3>${key === "normal" ? "일반 상자" : "고급 상자"}</h3>
        <div class="ga-row3">
          <div><label>표시 이름</label><input type="text" data-f="name" value="${esc(b.name)}" maxlength="20"></div>
          <div><label>1회 비용 (${b.cost_kind === "point" ? "포인트" : "원"})</label><input type="text" data-f="cost" value="${b.cost}" maxlength="8"></div>
          <div><label>1인 하루 제한 (0 = 무제한)</label><input type="text" data-f="daily_limit" value="${b.daily_limit || 0}" maxlength="4"></div>
        </div>
        <div class="ga-tier" style="margin-top:12px;font-size:.78rem;color:var(--text-dim);font-weight:600"><span>등급</span><span>확률 %</span><span>보상 (이름 | 가중치, 한 줄에 하나)</span></div>
        ${b.tiers.map((t) => `
          <div class="ga-tier" data-tier>
            <input type="text" data-f="label" value="${esc(t.label)}" maxlength="10" style="border-left:5px solid ${gaColors[t.label] || "#8b8f98"}">
            <input type="text" data-f="p" value="${t.p}" maxlength="6">
            <textarea data-f="items">${esc(t.items.map((it) => it.w === 1 && t.items.every((x) => x.w === 1) ? it.n : `${it.n} | ${it.w}`).join("\n"))}</textarea>
          </div>`).join("")}
      </div>`;
  }).join("");
}

function collectGachaConfig() {
  const boxes = {};
  document.querySelectorAll("#gaEditor .ga-box").forEach((box) => {
    const key = box.dataset.box;
    const base = gaConfig[key];
    const val = (f) => box.querySelector(`[data-f="${f}"]`).value.trim();
    boxes[key] = {
      name: val("name"), cost_kind: base.cost_kind,
      cost: Number(val("cost").replace(/,/g, "")), daily_limit: Number(val("daily_limit") || 0),
      tiers: [...box.querySelectorAll("[data-tier]")].map((row) => ({
        label: row.querySelector('[data-f="label"]').value.trim(),
        p: Number(row.querySelector('[data-f="p"]').value.trim()),
        items: row.querySelector('[data-f="items"]').value.split("\n").map((l) => l.trim()).filter(Boolean)
          .map((l) => {
            const [n, w] = l.split("|").map((x) => x.trim());
            return { n, w: w ? Number(w) : 1 };
          }),
      })),
    };
  });
  return boxes;
}

$("#gaSave").addEventListener("click", async () => {
  try {
    $("#gaSave").disabled = true;
    const r = await api("/api/admin/gacha", { action: "set", boxes: collectGachaConfig() });
    gaConfig = r.config;
    renderGachaEditor(true);
    toast("보상표 저장 완료 — 유저 화면에 바로 반영됩니다.");
  } catch (e) {
    toast(e.message, true);
  } finally {
    $("#gaSave").disabled = false;
  }
});
$("#gaReset").addEventListener("click", async () => {
  if (!confirm("기본 보상표로 되돌릴까요? (수정한 내용은 사라집니다)")) return;
  try {
    const r = await api("/api/admin/gacha", { action: "reset" });
    gaConfig = r.config;
    renderGachaEditor(false);
    toast("기본 보상표로 되돌렸어요.");
  } catch (e) { toast(e.message, true); }
});

function renderGachaLog(d) {
  const today = d.today || [];
  const tiers = d.today_tiers || [];
  $("#gaStats").innerHTML = today.length
    ? today.map((t) => `<div class="stat"><div class="num">${fmtWon(t.n)}회</div><div class="lbl">오늘 ${esc(t.box_name)} · ${fmtWon(t.spent)}${t.box_name.includes("일반") ? "P" : "원"} 소모</div></div>`).join("")
      + `<div class="stat"><div class="num" style="font-size:.95rem;padding-top:6px">${tiers.map((t) => `${esc(t.tier)} ${t.n}`).join(" · ") || "-"}</div><div class="lbl">오늘 등급 분포</div></div>`
    : '<div class="stat"><div class="num">0회</div><div class="lbl">오늘 뽑기</div></div>';
  const rows = d.pulls || [];
  $("#gaLog").innerHTML = rows.length
    ? rows.map((p) => `
      <div class="item-row">
        <div><div class="name"><span class="gc-tier-chip" style="--c:${gaColors[p.tier] || "#8b8f98"}">${esc(p.tier)}</span> ${esc(p.item)}
          <span class="hint" style="margin:0">— ${esc(p.username)} (${esc(p.uid)})</span></div>
          <div class="sub">${esc(p.box_name)} ${fmtWon(p.cost)}${p.cost_kind === "point" ? "P" : "원"} · ${fmtDate(p.created_at)}${p.result ? " · " + esc(p.result) : ""}</div></div>
        <span class="badge ${esc(p.status)}">${esc(p.status)}</span>
      </div>`).join("")
    : '<div class="empty">아직 뽑기 기록이 없어요.</div>';
}

loadGachaAdmin();
setInterval(loadGachaAdmin, 60000);
