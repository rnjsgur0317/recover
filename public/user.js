// 복구센터 - 유저 페이지
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

async function loadMe() {
  const me = await api("/api/me");
  $("#who").textContent = `${me.name} 님`;
}

async function loadMy() {
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
}

// ---- 구매내역 캡쳐 첨부
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

loadMe().catch(() => {});
loadMy().catch(() => {});
setInterval(() => loadMy().catch(() => {}), 30000);
