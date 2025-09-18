// Cloudflare Worker proxy for iFrame embedding (e.g., 11st, Google Translate)
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
    const newHeaders = new Headers(resp.headers);
    newHeaders.delete("x-frame-options");
    newHeaders.delete("content-security-policy");
    newHeaders.set("x-content-type-options", "nosniff");
    return new Response(resp.body, { status: resp.status, headers: newHeaders });
  },
};
