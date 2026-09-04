// 복구센터 - 관리자 페이지
"use strict";

const $ = (sel) => document.querySelector(sel);

function toast(msg, isError) {
  const el = $("#toast");
  el.textContent = msg;
  el.className = isError ? "show error" : "show";
  clearTimeout(el._t);
  el._t = setTimeout(() => (el.className = ""), 3000);
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

let cache = [];
let filter = "대기";

document.querySelectorAll(".filter-bar button").forEach((b) =>
  b.addEventListener("click", () => {
    document.querySelectorAll(".filter-bar button").forEach((x) => x.classList.toggle("active", x === b));
    filter = b.dataset.f;
    render();
  }));

async function refresh() {
  const data = await api("/api/admin/requests");
  cache = data.requests;
  render();
}

function render() {
  const pending = cache.filter((r) => r.status === "대기").length;
  $("#stats").innerHTML = `
    <div class="stat"><div class="num">${pending}</div><div class="lbl">대기중</div></div>
    <div class="stat"><div class="num">${cache.filter((r) => r.status === "완료").length}</div><div class="lbl">완료</div></div>
    <div class="stat"><div class="num">${cache.filter((r) => r.status === "거절").length}</div><div class="lbl">거절</div></div>`;
  const cb = $("#cntPending");
  cb.hidden = pending === 0;
  cb.textContent = pending;

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
      if (!confirm(`[${r.game}] 요청 기록을 삭제할까요?${r.status === "대기" ? " (DM은 발송되지 않습니다)" : ""}`)) return;
      try {
        await api("/api/admin/delete", { id: r.id });
        toast("삭제 완료");
        refresh();
      } catch (e) { toast(e.message, true); }
    });
  });
}

api("/api/me").then((me) => { $("#who").textContent = `${me.name} 님`; }).catch(() => {});
refresh().catch((e) => toast(e.message, true));
setInterval(() => refresh().catch(() => {}), 30000);
