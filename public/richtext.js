// H Company - 자유 입력 상품 정보 → HTML (유저 [영상] 상세 · 관리자 미리보기 공용)
// 규칙: 줄바꿈 그대로 · 빈 줄 = 문단 나눔 · "## 소제목" · "- 목록" · "항목 : 내용" = 정보 표
//       "---" = 구분선 · **굵게** · ~~취소선~~ · http(s) 주소는 자동 링크
"use strict";

(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function inline(s) {
    return esc(s)
      .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
      .replace(/~~(.+?)~~/g, "<s>$1</s>")
      .replace(/https?:\/\/[^\s<]+/g, (u) => {
        const tail = (u.match(/[.,!?)\]]+$/) || [""])[0];   // 문장 끝 구두점은 링크에서 뺌
        const url = tail ? u.slice(0, -tail.length) : u;
        return `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>${tail}`;
      });
  }

  function renderRichText(text) {
    let html = "", kind = null, buf = [];
    const flush = () => {
      if (kind === "p") html += `<p>${buf.map(inline).join("<br>")}</p>`;
      if (kind === "ul") html += `<ul>${buf.map((l) => `<li>${inline(l)}</li>`).join("")}</ul>`;
      if (kind === "rows") {
        html += `<div class="rt-table">${buf.map(([k, v]) =>
          `<div class="rt-row"><span class="k">${inline(k)}</span><span class="v">${inline(v)}</span></div>`).join("")}</div>`;
      }
      kind = null;
      buf = [];
    };
    const push = (k, item) => {
      if (kind !== k) flush();
      kind = k;
      buf.push(item);
    };
    for (const raw of String(text || "").replace(/\r\n?/g, "\n").split("\n")) {
      const line = raw.trim();
      let m;
      if (!line) { flush(); continue; }
      if (/^-{3,}$/.test(line)) { flush(); html += "<hr>"; continue; }
      if ((m = line.match(/^#{1,3}\s+(.+)$/))) { flush(); html += `<div class="rt-h">${inline(m[1])}</div>`; continue; }
      if ((m = line.match(/^[-*•·]\s+(.+)$/))) { push("ul", m[1]); continue; }
      // "항목 : 내용" — 콜론 뒤 공백 필수 (https:// · 12:30 같은 건 표로 안 바뀜)
      m = line.match(/^([^:：]{1,24}?)\s*(?::\s+|：\s*)(.+)$/);
      if (m && !/^https?$/i.test(m[1].trim())) { push("rows", [m[1].trim(), m[2]]); continue; }
      push("p", line);
    }
    flush();
    return html;
  }

  window.renderRichText = renderRichText;
})();
