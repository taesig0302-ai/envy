// Cloudflare Worker — 11번가 iFrame 프록시 (ENVY v9.4)
const MOBILE_UA =
  "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Mobile Safari/537.36";

class BaseInjector {
  constructor(baseHref) { this.baseHref = baseHref; }
  element(e) { e.append(`<base href="${this.baseHref}">`, { html: true }); }
}

function cleanHeaders(h) {
  const nh = new Headers(h);
  ["x-frame-options","frame-ancestors","content-security-policy","content-security-policy-report-only"].forEach(k => nh.delete(k));
  nh.set("access-control-allow-origin", "*");
  nh.set("access-control-allow-headers", "*");
  nh.set("access-control-allow-methods", "GET,HEAD,OPTIONS");
  if (!nh.has("cache-control")) nh.set("cache-control","public, max-age=60");
  return nh;
}

async function proxyFetch(target, req) {
  const acceptLang = req.headers.get("accept-language") || "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7";
  return fetch(target, { redirect: "follow", headers: { "user-agent": MOBILE_UA, "accept-language": acceptLang, "accept-encoding": "gzip, deflate, br" } });
}

export default {
  async fetch(req) {
    const url = new URL(req.url);
    const mode = url.pathname;  // "/iframe" | "/fetch"
    const target = url.searchParams.get("target");
    if (!target) return new Response("target URL required", { status: 400 });

    let resp = await proxyFetch(target, req);
    let headers = cleanHeaders(resp.headers);
    const isHTML = (headers.get("content-type") || "").includes("text/html");

    if (mode === "/iframe" && isHTML) {
      const baseHref = new URL(target).origin + "/";
      return new HTMLRewriter().on("head", new BaseInjector(baseHref)).transform(new Response(resp.body, { status: resp.status, headers }));
    }
    return new Response(resp.body, { status: resp.status, headers });
  }
};
