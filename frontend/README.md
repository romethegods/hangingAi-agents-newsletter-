# HangingAi website

Next.js 16 (App Router, Cache Components) + Tailwind 4. Server-rendered; all data
comes from the FastAPI backend in `../backend`.

```bash
npm install
API_URL=http://localhost:8000 npm run dev   # http://localhost:3000
npm run lint && npm run typecheck && npm test && npm run build
```

| Env var | Default | |
|---|---|---|
| `API_URL` | `http://localhost:8000` | Backend base URL (server-side only) |
| `SITE_URL` | `https://hangingai.com` | Canonical URLs, sitemap, Open Graph |

How data loading works (`src/lib/api.ts`): each API call is a `use cache`
function (about 1 minute), reached only from request-time code. Pages prerender a
static shell (header, tabs, skeletons) at build time and stream data in per
request, so `next build` never needs the API.
