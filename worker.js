// ENVY v10 — Cloudflare Worker Proxy
// 모든 호스트 허용, 프레임 차단 헤더 제거, 11번가 앱유도 스크립트/배너 제거

export default {
  async fetch(request) {
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

    // 11번가 앱유도/리다이렉트/배너 제거
    body = body
      .replace(/<script[^>]*>[^<]*openApp[^<]*<\/script>/gi, "")
      .replace(/location\.href\s*=\s*['"][^'"]*app\.11st[^'"]*['"]/gi, "")
      .replace(/<meta[^>]+http-equiv=['"]refresh['"][^>]*>/gi, "")
      .replace(/<div[^>]*id=['"]?appBanner[^>]*>[\s\S]*?<\/div>/gi, "");

    return new Response(body, { status: resp.status, headers: newHeaders });
  },
};
