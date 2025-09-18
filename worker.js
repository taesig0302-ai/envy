// ENVY v10.3 — Worker tweaks: stronger banner hiding for 11st, generic frame-ancestors removal
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

  const ct = newHeaders.get("content-type") || "";
  if (ct.includes("text/html")) {
    const inject = `
      <style>
        /* try hard to remove/disable app-open banners and sticky bars */
        .app, .open-app, .app-open, .appOpen, .download, .floating, .banner, .sticky, .header, .gnb, .top-notice,
        [class*="app"], [id*="app"], [class*="banner"], [id*="banner"], [class*="floating"] { display: none !important; height: 0 !important; visibility: hidden !important; }
        body { margin-top: 0 !important; padding-top: 0 !important; }
      </style>
      <script>
        try {
          const killTexts = ["앱에서", "앱 열기", "앱 혜택", "download", "open app"];
          function hideByText() {
            document.querySelectorAll("*").forEach(el => {
              const t = (el.textContent||"").trim().toLowerCase();
              if (t && killTexts.some(k => t.includes(k))) { el.style.display = "none"; el.style.height="0"; }
            });
          }
          const obs = new MutationObserver(hideByText);
          obs.observe(document.documentElement, {childList: true, subtree: true});
          hideByText();
        } catch(e) {}
      </script>`;
    body = body.replace(/<\/body>/i, inject + "</body>");
  }

  return new Response(body, { status: resp.status, headers: newHeaders });
}

export default { fetch: handle };
export const iframe = { fetch: handle };
