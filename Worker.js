// Worker.js — Multi-origin embed proxy (DataLab / Itemscout / SellerLife / 11st)
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36';

const HOSTS = {
  'datalab.naver.com':    { cookieVar: 'DATALAB_COOKIE' },
  'app.itemscout.io':     { cookieVar: 'ITEMSCOUT_COOKIE' },
  'www.itemscout.io':     { cookieVar: 'ITEMSCOUT_COOKIE' },
  'sellerlife.co.kr':     { cookieVar: 'SELLERLIFE_COOKIE' },
  'www.sellerlife.co.kr': { cookieVar: 'SELLERLIFE_COOKIE' },
  'm.11st.co.kr':         { cookieVar: null },
  '11st.co.kr':           { cookieVar: null },
};

export default {
  async fetch(request, env) {
    const reqUrl = new URL(request.url);
    const targetParam = reqUrl.searchParams.get('url');
    if (!targetParam) return new Response('Missing ?url', { status: 400 });

    let target;
    try { target = new URL(targetParam); } catch { return new Response('Bad url', { status: 400 }); }

    const conf = HOSTS[target.hostname];
    if (!conf) return new Response('Upstream not allowed', { status: 403 });

    const h = new Headers(request.headers);
    h.delete('cookie');
    h.set('user-agent', UA);
    h.set('referer', `${target.origin}/`);
    h.set('origin', target.origin);
    const cookieKey = conf.cookieVar;
    if (cookieKey && env[cookieKey]) h.set('cookie', env[cookieKey]);

    const body = (request.method === 'GET' || request.method === 'HEAD') ? undefined : await request.arrayBuffer();

    const upstream = await fetch(target.toString(), {
      method: request.method, headers: h, body, redirect: 'manual',
    });

    const headers = new Headers(upstream.headers);
    ['x-frame-options','content-security-policy','content-security-policy-report-only','frame-ancestors']
      .forEach(k => headers.delete(k));
    headers.set('x-frame-options', 'ALLOWALL');

    const loc = headers.get('location');
    if (loc) {
      try {
        const u = new URL(loc, target);
        headers.set('location', `${reqUrl.origin}${reqUrl.pathname}?url=${encodeURIComponent(u.toString())}`);
      } catch {}
    }

    const ct = (headers.get('content-type') || '').toLowerCase();

    if (ct.includes('text/html')) {
      let html = await upstream.text();
      const originRe = new RegExp(target.origin.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
      html = html.replace(originRe, `${reqUrl.origin}${reqUrl.pathname}?url=${encodeURIComponent(target.origin)}`);
      return new Response(html, { status: upstream.status, headers });
    }

    return new Response(upstream.body, { status: upstream.status, headers });
  }
};