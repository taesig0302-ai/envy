
// ENVY v11.1 Worker (11st iframe helper, banner killer)
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
  ["x-frame-options","content-security-policy","frame-ancestors","x-content-security-policy"].forEach(h=>headers.delete(h));
  headers.set("x-content-type-options","nosniff");

  const ct = headers.get("content-type") || "";
  if (ct.includes("text/html")) {
    body = body
      .replace(/<meta[^>]+content-security-policy[^>]*>/ig, "")
      .replace(/<meta[^>]+http-equiv=["']content-security-policy["'][^>]*>/ig, "");

    const inj = `
      <style>
        [class*="banner"],[id*="banner"],[class*="app"],[id*="app"],
        [class*="floating"],[id*="floating"],[class*="sticky"],[id*="sticky"],
        header,.header,.gnb,.top,.top-notice,.notice,.download {
          display:none !important; height:0 !important; overflow:hidden !important;
        }
        .modal, .mask, .overlay, .dimmed, .backdrop { display:none !important; }
        body { margin:0 !important; padding:0 !important; }
      </style>
      <script>
        (function(){
          if (navigator.serviceWorker) {
            try { navigator.serviceWorker.getRegistrations().then(rs=>rs.forEach(r=>r.unregister())); } catch(e){}
            navigator.serviceWorker.register = ()=>Promise.reject(new Error("blocked"));
          }
          const KILL_TXT = ["앱에서", "앱 열기", "앱 혜택", "open app", "download app", "app"];
          function purge(){
            document.querySelectorAll("*").forEach(el=>{
              const t=(el.textContent||"").toLowerCase();
              if(KILL_TXT.some(k=>t.includes(k))){
                let p=el, hop=0;
                while(p && hop<3){
                  if((p.offsetHeight||0)>=36){ p.remove(); break; }
                  p=p.parentElement; hop++;
                }
              }
            });
            document.querySelectorAll("*").forEach(el=>{
              const s = getComputedStyle(el);
              if((s.position==="fixed"||s.position==="sticky") && (parseInt(s.top||"0")<=20) && (el.offsetHeight>=36)){
                el.remove();
              }
            });
            const suspects = ['.modal','.mask','.overlay','.dimmed','.backdrop','#overlay','#mask'];
            suspects.forEach(sel => document.querySelectorAll(sel).forEach(n=>n.remove()));
          }
          new MutationObserver(purge).observe(document.documentElement,{childList:true,subtree:true});
          addEventListener("load", purge);
          setInterval(purge, 300);
          purge();
        })();
      </script>`;
    body = body.replace(/<\/body>/i, inj + "</body>");
  }

  return new Response(body, {status: res.status, headers});
}
export default { fetch: proxyFetch };
export const iframe = { fetch: proxyFetch };
