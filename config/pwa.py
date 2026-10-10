"""PWA: manifesto e service worker (app instalável).

O `service worker` faz cache apenas de estáticos; requisições dinâmicas
(navegação, `/api/*`, `/scan`, `/healthz`) sempre vão à rede, para não servir
dados desatualizados de entrega.
"""

from django.http import HttpResponse, JsonResponse


def manifest(request):
    data = {
        "name": "PNAE [CPN]",
        "short_name": "PNAE [CPN]",
        "description": "Registro de distribuição de alimentação escolar (PNAE) por QR Code.",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#f1f5f9",
        "theme_color": "#047857",
        "lang": "pt-BR",
        "icons": [
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
            {
                "src": "/static/icons/icon-512-maskable.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
    }
    return JsonResponse(data)


def service_worker(request):
    # Versão do cache: mude para forçar a atualização.
    version = "v4"
    script = """\
const CACHE = 'ifmg-alimenta-%s';
const STATIC_ASSETS = [
  '/static/vendor/tailwind/tailwind.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/vendor/zxing/zxing-browser.min.js',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(STATIC_ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;              // nunca cacheia POST/scan
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  // Só estáticos vão ao cache; navegação e APIs sempre na rede.
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((cache) => cache.put(req, copy));
        return res;
      }))
    );
  }
});
""" % version
    return HttpResponse(script, content_type="application/javascript; charset=utf-8")
