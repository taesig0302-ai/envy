// ENVY v10.7.2 worker.js
// 11번가 배너 제거 강화 버전

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const target = url.searchParams.get("target");
    if (!target) return new Response("target required", { status: 400 });

    const res = await fetch(target);
    let body = await res.text();
    const headers = new Headers(res.headers);
    ["x-frame-options","content-security-policy","frame-ancestors"].forEach(h=>headers.delete(h));
    headers.set("x-content-type-options","nosniff");

    const ct = headers.get("content-type") || "";
    if (ct.includes("text/html")) {
      const inj = `
        <style>
          header,.header,.gnb,[class*='banner'],[id*='banner'],
          [class*='app'],[id*='app'],[class*='download'],[id*='download'],
          .top,.top-notice,.notice,.sticky {
            display:none!important;height:0!important;overflow:hidden!important;
          }
          *[style*='position:fixed'][style*='top: 0'],
          *[style*='position:sticky'] {
            display:none!important;height:0!important;
          }
        </style>
        <script>
          (function(){
            const KILL_TXT = ["앱에서","앱 열기","앱 혜택","open app","download app"];
            function purge(){
              document.querySelectorAll("*").forEach(el=>{
                const txt=(el.textContent||"").toLowerCase();
                if (KILL_TXT.some(k=>txt.includes(k))) {
                  let p=el,hop=0;
                  while(p && hop<3){
                    if((p.offsetHeight||0)>=40){p.remove();break;}
                    p=p.parentElement;hop++;
                  }
                }
                const s=getComputedStyle(el);
                if((s.position==="fixed"||s.position==="sticky") && (parseInt(s.top||"0")<=20) && (el.offsetHeight>=40)) el.remove();
              });
              document.querySelectorAll('button,a,[role="button"]').forEach(b=>{
                const t=(b.innerText||b.getAttribute("aria-label")||"").toLowerCase();
                if(t.includes("닫기")||t.includes("close")||t.trim()==="x"){try{b.click();}catch(e){}}
              });
            }
            new MutationObserver(purge).observe(document.documentElement,{childList:true,subtree:true});
            addEventListener("load",purge);
            setInterval(purge,300);
            purge();
          })();
        </script>`;
      body = body.replace(/<\/body>/i, inj + "</body>");
    }
    return new Response(body, { status: res.status, headers });
  }
};
