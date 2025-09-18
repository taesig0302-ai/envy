// ENVY v10.1 — Cloudflare Worker Proxy (iframe endpoint + root 허용)
// /iframe?target=... 또는 /?target=... 모두 지원

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

  body = body
    .replace(/<script[^>]*>[^<]*openApp[^<]*<\/script>/gi, "")
    .replace(/location\.href\s*=\s*['"][^'"]*app\.11st[^'"]*['"]/gi, "")
    .replace(/<meta[^>]+http-equiv=['"]refresh['"][^>]*>/gi, "")
    .replace(/<div[^>]*id=['"]?appBanner[^>]*>[\s\S]*?<\/div>/gi, "");

  return new Response(body, { status: resp.status, headers: newHeaders });
}

export default {
  async fetch(request) {
    return handle(request);
  },
};

// optional explicit /iframe route for compatibility
export const iframe = {
  async fetch(request) {
    return handle(request);
  },
};
