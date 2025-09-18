// Cloudflare Worker proxy (11st/Translate) — strip app redirects & frame-blocking headers
export default {
  async fetch(request) {
    const url = new URL(request.url);
    const target = url.searchParams.get("target");
    if (!target) {
      return new Response("target URL required ?target=https%3A%2F%2F...", { status: 400 });
    }

    const headers = {
      "user-agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Mobile Safari/537.36",
      "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
      "cache-control": "no-cache",
    };
    const init = {
      method: request.method,
      headers,
      body: ["GET","HEAD"].includes(request.method) ? undefined : await request.clone().arrayBuffer(),
      redirect: "follow",
    };

    const resp = await fetch(target, init);
    let body = await resp.text();

    // 헤더에서 프레임 차단 제거
    const newHeaders = new Headers(resp.headers);
    newHeaders.delete("x-frame-options");
    newHeaders.delete("content-security-policy");
    newHeaders.set("x-content-type-options", "nosniff");

    // 11번가 앱유도/리다이렉트 스크립트 제거(휴리스틱)
    body = body
      .replace(/<script[^>]*>[^<]*openApp[^<]*<\/script>/gi, "")
      .replace(/location\.href\s*=\s*['"][^'"]*app\.11st[^'"]*['"]/gi, "")
      .replace(/<meta[^>]+http-equiv=['"]refresh['"][^>]*>/gi, "")
      .replace(/<div[^>]*id=['"]?appBanner[^>]*>[\s\S]*?<\/div>/gi, "");

    return new Response(body, { status: resp.status, headers: newHeaders });
  },
};
