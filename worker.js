// ENVY v10.2 — Worker: 더 강력한 11번가/프레임 차단 제거 + HTML 주입
async function handle(request) {
  const url = new URL(request.url);
  const target = url.searchParams.get("target");
  if (!target) return new Response("target URL required", { status: 400 });

  const init = {
    method: request.method,
    redirect: "follow",
    body: ["GET","HEAD"].includes(request.method) ? undefined : await request.clone().arrayBuffer(),
    headers: {
      "user-agent":
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Mobile Safari/537.36",
      "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
      "cache-control": "no-cache",
    },
  };

  const resp = await fetch(target, init);
  let body = await resp.text();

  const newHeaders = new Headers(resp.headers);
  ["x-frame-options","content-security-policy","frame-ancestors"].forEach(h => newHeaders.delete(h));
  newHeaders.set("x-content-type-options", "nosniff");

  // HTML인 경우 배너/앱유도 요소를 강제 숨기는 스타일/스크립트 삽입
  const ct = newHeaders.get("content-type") || "";
  if (ct.includes("text/html")) {
    const inject = `
      <style>
        /* 11번가 앱유도 바/플로팅 버튼 가려보기 */
        [class*="app"], [id*="app"], .floating, .banner, .download, .openApp, .appOpen { display: none !important; }
      </style>
      <script>
        try {
          const killTexts = ["앱에서", "앱 열기", "앱 혜택"];
          function hideByText() {
            document.querySelectorAll("*").forEach(el => {
              const t = (el.textContent||"").trim();
              if (t && killTexts.some(k => t.indexOf(k) >= 0)) { el.style.display = "none"; }
            });
          }
          hideByText(); setInterval(hideByText, 1000);
        } catch(e) {}
      </script>`;
    body = body.replace(/<\/body>/i, inject + "</body>");
  }

  return new Response(body, { status: resp.status, headers: newHeaders });
}

export default { fetch: handle };
export const iframe = { fetch: handle };
