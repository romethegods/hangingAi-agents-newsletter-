# HangingAi

> A newsletter where AI agents of all kinds come to flex their skills!

AI news, papers, models and open-source agent tools, scraped from the sources
that matter and ranked for each reader. Newsletter + website + public API.

## How it works

```
 registry.py ──> scheduler (min-heap) ──> crawler ──> parser ──> relevance ──> pipeline ──> Postgres ──> FastAPI
 (what to crawl)  (when; backoff)         robots.txt   HTML→     AI keyword    canonical URL          feed / search /
                                          rate limit   items     filter        + MinHash dedup        tools / sources
                                          nodriver                             + star velocity
```

| Piece | File | Idea |
|---|---|---|
| Sources | `backend/app/scraping/registry.py` | One `SourceDef` per site. News sites are config (CSS selectors), not code |
| Scheduling | `scraping/scheduler.py` | Min-heap by next-run time; exponential backoff on failure |
| Politeness | `scraping/robots.py`, `rate_limit.py` | robots.txt (RFC 9309), token bucket per domain, honest `HangingAiBot` UA |
| Browser | `scraping/browser.py` | One headless Chrome (nodriver), bounded pool of tabs |
| Parsers | `scraping/parsers/` | GitHub trending/topics, HF papers/models (embedded JSON), generic news cards |
| Dedup | `scraping/canonical.py`, `minhash.py` | Exact: canonical URL hash + unique index. Near: MinHash + LSH on headlines |
| Ranking | `app/ranking.py` | Time-decayed hot score, diversified top-k, 7-day sliding-window star velocity |
| API | `app/main.py` | Keyset-paginated feed, Postgres full-text search, tools directory |

## Sources (M1)

| Source | Status |
|---|---|
| Hugging Face Daily Papers, Trending Models (with preview images) | ✅ |
| Hugging Face Trending Spaces (live demo apps, embeddable) | ✅ |
| GitHub Trending (AI-filtered), topics: ai-agents, llm, mcp, rag | ✅ |
| GitHub README demos (video, YouTube, GIF, screenshot), 20 repos/hour | ✅ |
| TMZ (AI stories only) | ✅ |

Every source passes a safe-for-work filter (hub content tags + keywords). Images and demos are
hotlinked or embedded from their source (YouTube via youtube-nocookie, Spaces via hf.space);
nothing is downloaded or re-hosted.
| CNN Tech | ⛔ disabled: blocks headless browsers, RSS is dead. We don't bypass bot protection |

## Local development

Requires [uv](https://docs.astral.sh/uv/) and Google Chrome/Chromium.

```bash
cd backend
uv sync
cp ../.env.example ../.env           # then point DATABASE_URL at a Postgres 16
uv run alembic upgrade head
uv run python -m app.worker --once   # scrape everything once (+ one README demo batch)
uv run python -m app.worker --media  # only scan GitHub READMEs for demos
uv run uvicorn app.main:app --reload # http://localhost:8000/docs
```

Website (needs Node 24+, see `frontend/README.md`):

```bash
cd frontend && npm install && API_URL=http://localhost:8000 npm run dev
```

Or the backend in Docker: `docker compose up --build`.

Tests (starts a throwaway Postgres automatically via pgserver, or set `TEST_DATABASE_URL`):

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
```

When a site redesign breaks a parser test, re-capture its fixture:
`uv run python scripts/capture_fixture.py <url> tests/fixtures/<name>.html`

## API

| Endpoint | |
|---|---|
| `GET /api/feed?sort=latest\|hot&content_type=news\|paper\|model&cursor=` | Feed; `latest` is cursor-paginated |
| `GET /api/articles/{id}` | One item, plus the same story from other outlets |
| `GET /api/search?q=` | Full-text search (title weighted over summary) |
| `GET /api/tools?sort=trending\|stars\|new&platform=github\|huggingface&has_demo=&topic=` | Tools directory |
| `GET /api/tools/{id}` | One tool, with its demo |
| `GET /api/topics` | Most common tool topics, for filter chips |
| `GET /api/sources` | Crawl health: last run, last error, failure streak |
| `GET /health` | Liveness + DB check |

**Rate limits** (per client IP, token bucket): 120 requests/min with bursts of 60 for `/api/*`,
and 30/min with bursts of 10 for `/api/search`. Every response carries `RateLimit-Limit`,
`RateLimit-Remaining` and `RateLimit-Reset`; refusals are `429` with `Retry-After`. Our own
web server calls the API over the private network and is exempt. Configure with the
`RATE_LIMIT_*` settings in `backend/app/config.py`.

## Community & the daily brief

No sign-up. The first time someone follows, votes or comments, they get a guest
identity (`hanging-1234`, renameable) in an httpOnly cookie. Adding an email is
optional: it delivers the brief each morning and moves the identity to another
device (a guest who signs into an existing account is merged into it).

- **Brief** (`/brief`, emailed at the reader's local hour): releases of followed
  tools, rising tools in followed topics, "for you" must-reads, and one demo.
  Nothing repeats within 7 days; sending is idempotent per user per day.
- **Comments & upvotes** on stories and tools; upvotes feed the hot ranking.
- **Safety:** SFW filter, 2-link cap, duplicate check and per-visitor rate limits
  on every write; 3 reports hide a comment for review at `/moderate`
  (`ADMIN_EMAILS`); moderators can restore, remove or ban.
- **Release tracking:** followed GitHub tools' releases pages, every 6 hours.

`python -m app.worker --releases` and `--briefs` run those jobs on their own.

## Arena

`/arena`: two anonymous models answer one prompt side by side (streamed live);
the reader votes, then the names are revealed. Elo ratings (K=32 for a model's
first 30 battles, then 16) feed a public leaderboard; pairs favor models with
fewer battles, and A/B order is random. Votes where an answer names its own
model are recorded but not rated.

Models are listed in `backend/app/arena/registry.py`: Claude Haiku 4.5 (needs
`ANTHROPIC_API_KEY`) and open models through Hugging Face's router (needs
`HF_TOKEN`). Without keys, two free "dev" models stand in on localhost.
Cost controls: 20 battles per visitor per day, a site-wide daily budget
(`ARENA_DAILY_BUDGET_USD`, checked against the worst case before each battle),
2,000-character prompts and 1,024-token answers.

## Chat rooms

Every story and tool has its own IRC-style room (`#voicestudio`). It polls
every 5 s while open (paused in background tabs) and shows "N here now".
`/nick name` renames you; `/help` lists commands. Messages are comments, so the
same filters, votes, reports and moderation apply.

## Roadmap

- [x] **M0** skeleton: FastAPI, Postgres, Alembic, Docker, CI
- [x] **M1** nodriver scraping pipeline + API
- [ ] **M2** Claude Haiku summaries + tags, embeddings (pgvector) for semantic dedup and recommendations
- [x] **M3** Next.js website (`frontend/`): feed, article pages, tools directory, search
- [x] **M4** guest identities, follows, comments, upvotes, moderation
- [x] **M5** personalized daily brief (web + optional email)
- [ ] **M6** "Ask HangingAi" agent over our own data
- [ ] **M7** move from Railway to a Google Cloud VM (see `docs/DEPLOY.md`)
