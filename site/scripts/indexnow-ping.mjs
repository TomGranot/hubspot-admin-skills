// Pings IndexNow (Bing, Yandex, and partners) with the site's URLs after a
// production build, so new and changed pages get crawled without waiting for
// a sitemap re-read. The key is not a secret — the protocol requires it to be
// publicly served from the site root (public/<key>.txt).
//
// Runs only when Netlify's CONTEXT is "production" (never on deploy previews
// or local builds; set INDEXNOW_FORCE=1 to override). Failures never break
// the build.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const SITE_URL = 'https://hubspot.granot.io';
const KEY = 'f41ca645b721f4cd05c8a3357ed52561';

const context = process.env.CONTEXT ?? '';
if (context !== 'production' && process.env.INDEXNOW_FORCE !== '1') {
  console.log(`indexnow: skipped (CONTEXT=${context || 'unset'})`);
  process.exit(0);
}

const distDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../dist');
const sitemap = fs.readFileSync(path.join(distDir, 'sitemap-0.xml'), 'utf-8');
const urls = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);

if (urls.length === 0) {
  console.log('indexnow: no URLs found in sitemap, skipping');
  process.exit(0);
}

try {
  const res = await fetch('https://api.indexnow.org/indexnow', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    body: JSON.stringify({
      host: new URL(SITE_URL).host,
      key: KEY,
      keyLocation: `${SITE_URL}/${KEY}.txt`,
      urlList: urls,
    }),
  });
  console.log(`indexnow: submitted ${urls.length} URLs, response ${res.status}`);
} catch (error) {
  console.warn(`indexnow: ping failed (build continues): ${error.message}`);
}
