// ENVY v10.4 Worker — stronger cleanup for 11st banners
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
        .app, .open-app, .app-open, .appOpen, .download, .floating, .banner, .sticky, .header, .gnb, .top-notice,
        [class*="app"], [id*="app"], [class*="banner"], [id*="banner"], [class*="floating"] { display: none !important; height: 0 !important; }
        body { margin: 0 !important; padding: 0 !important; }
      </style>
      <script>
        (function(){
          const killTexts = ["앱에서", "앱 열기", "앱 혜택", "download", "open app"];
          function nuke() {
            document.querySelectorAll("*").forEach(el => {
              const t=(el.textContent||"").toLowerCase();
              if (t && killTexts.some(k=>t.includes(k))) { el.remove(); }
            });
            // auto-click close buttons if found
            document.querySelectorAll('button, a').forEach(b=>{
              const t=(b.innerText||"").toLowerCase();
              if (t.includes("닫기") || t.includes("close") || t.includes("앱 열기")) { try{ b.click(); }catch(e){} }
            });
          }
          const obs = new MutationObserver(nuke);
          obs.observe(document.documentElement, {childList:true, subtree:true});
          setInterval(nuke, 800);
          nuke();
        })();
      </script>`;
    body = body.replace(/<\/body>/i, inject + "</body>");
  }
  return new Response(body, { status: resp.status, headers: newHeaders });
}

export default { fetch: handle };
export const iframe = { fetch: handle };
