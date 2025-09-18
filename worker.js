// ENVY v10.5 worker — stronger 11st banner killer
async function proxyFetch(request) {
  const url = new URL(request.url);
  const target = url.searchParams.get("target");
  if (!target) return new Response("target required", {status:400});

  const init = {
    method: request.method,
    redirect: "follow",
    body: ["GET","HEAD"].includes(request.method) ? undefined : await request.clone().arrayBuffer(),
    headers: {
      "user-agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Mobile Safari/537.36",
      "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
      "cache-control": "no-cache"
    }
  };

  const res = await fetch(target, init);
  let body = await res.text();
  const headers = new Headers(res.headers);
  ["x-frame-options","content-security-policy","frame-ancestors"].forEach(h=>headers.delete(h));
  headers.set("x-content-type-options","nosniff");

  const ct = headers.get("content-type") || "";
  if (ct.includes("text/html")) {
    const inj = `
      <style>
        /* Kill typical 11st app-open bars & sticky headers */
        [class*="app"],[id*="app"],[class*="App"],[id*="App"],
        [class*="banner"],[id*="banner"],[class*="open"],[id*="open"],
        [class*="floating"],[id*="floating"],[class*="sticky"],[id*="sticky"],
        header, .header, .gnb, .top, .top-notice, .notice, .download { display:none !important; height:0!important; }
        *[style*="position: fixed"][style*="top: 0"], *[style*="position:sticky"] { display:none !important; height:0!important; }
      </style>
      <script>
        (function(){
          const KILL_TXT = ["앱에서", "앱 열기", "앱 혜택", "open app", "download app"];
          function purge(){
            document.querySelectorAll("*").forEach(el=>{
              const txt=(el.textContent||"").toLowerCase();
              if(KILL_TXT.some(k=>txt.includes(k))){ el.remove(); }
              const s=getComputedStyle(el);
              if((s.position==="fixed"||s.position==="sticky") && (parseInt(s.top||"0")<=20) && (el.offsetHeight>=40)) el.remove();
            });
            // auto click close buttons
            document.querySelectorAll('button,a').forEach(b=>{
              const t=(b.innerText||"").toLowerCase();
              if(t.includes("닫기")||t.includes("close")||t.includes("x")){ try{ b.click(); }catch(e){} }
            });
          }
          const obs=new MutationObserver(purge);
          obs.observe(document.documentElement,{childList:true,subtree:true});
          setInterval(purge,400);
          addEventListener("load", purge);
          purge();
        })();
      </script>`;
    body = body.replace(/<\/body>/i, inj + "</body>");
  }
  return new Response(body, {status: res.status, headers});
}
export default { fetch: proxyFetch };
export const iframe = { fetch: proxyFetch };
