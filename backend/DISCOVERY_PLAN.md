# Implementation plan: broaden profile & issue discovery

Goal: fill `profiles.json` and `issues.json` with **many more, recent-leaning**
entries so the demo's "load more" never dead-ends. Quality of match is explicitly
not a priority — abundance is.

## Status

- **Phase 1 — DONE.** Widened `text_blob` (bio/location/links), keep thin profiles
  (`_has_signal`), default to no prefilter (`--prefilter` to opt back in).
- **Phase 2 — DONE.** New stage 1b `services/fetch_profiles/expand.py`: 1-hop
  follow/star/repo crawl, keeps only DIDs verified to have real Tangled content
  (repo/issue/pull/actor profile), with resolved handles. Phase-4 crawl knobs added
  to `config.py` (`EXPANSION_FANOUT_PER_DID`, `EXPANSION_MAX_DIDS`).
- **Phases 3–5** — not done (closed-issue inclusion, broader cap bumps, load-more
  padding). Not needed yet given current pool sizes.

Result: **profiles 8 → 258, issues 21 → 1325** (17 ≤7 days, 82 ≤30 days; newest 0–2
days). Feed paginates ~265 pages of 5; recommend ~52 pages.

## Root cause (measured)

Current: 61 DIDs discovered → 36 content-bearing → **8 profiles**; **21 issues**, all
50–275 days old, 0 within 3 days. "Load more" runs out because the served pool is tiny.

The funnel collapses in three places:

1. **`content_only` prefilter** (`create_profiles.select_dids`) drops 25 passive
   (star/follow-only) DIDs: 61 → 36.
2. **Empty-`text_blob` drop** (`build_profile` returns `None`) is the big one. The blob
   (`build_text_blob`) is built **only from repo names/descriptions + Bluesky post text**.
   Bio / location / links / issues / PRs are fetched but never added, so 28 of the 36
   content-bearing DIDs (issue/PR filers, bio-only users) are dropped: 36 → 8.
3. **Small universe.** Discovery only sees `sh.tangled.*` activity inside the firehose
   window, and for a platform Tangled's size that window's ~61 DIDs is close to the entire
   3-day-active population. The firehose stops on "caught up to live," not on the caps.

**Constraint to know:** `MAX_BACKFILL_DAYS = 3` is the **public Jetstream relay's ~72h
retention** — not a tunable. A longer firehose lookback is not possible against the public
relay. To reach "the past week+", use **PDS history** (`listRecords` has no time limit) and
**graph crawl** (follows / stars / repo owners), which are not time-bounded.

---

## Phase 1 — Stop dropping profiles (biggest, cheapest win: ~8 → ~60)

No new network model; just widen what counts as profileable.

- **`create_profiles.build_text_blob`** — fold in the actor `description` (bio),
  `location`, and `links`, plus repo names/descriptions and post text as today. This alone
  recovers most bio-only / issue-filer DIDs and gives the taxonomy more to match on.
- **`create_profiles.build_profile`** — stop returning `None` on an empty blob. Keep the
  profile whenever there is *any* signal (handle, bio, ≥1 repo/post/star/follow). A
  featureless profile still surfaces via the recommender's cold-start fallback, so it's
  useful for the demo. (Optionally synthesize a minimal blob from the handle so it isn't
  literally empty.)
- **`create_profiles.run`** — default `content_only=False` (fetch every discovered DID).
  Keep `--no-prefilter` as the now-default; add `--prefilter` if we ever want the old
  behavior back.

Expected: up to ~60 profiles from the existing 61 DIDs, immediately.

## Phase 2 — Grow the universe with a bounded graph crawl (the durable fix)

New step that expands the seed DID set beyond the 3-day firehose, using untimed PDS data.

- **New module `services/fetch_profiles/expand.py`** (or a function in `discover.py`):
  given the firehose `raw_dids`, for each DID fetch `sh.tangled.graph.follow`,
  `sh.tangled.feed.star`, and `sh.tangled.repo` records and collect every referenced DID
  (follow subjects, star repo-owners, repo `repoDid`s). Add the new DIDs to the raw map
  with empty `events` (they flow through stage 2/3 exactly like firehose-only DIDs).
- **Bounded** by new config knobs (see Phase 4): hops (default 1, optionally 2), fan-out
  per DID, and a hard `EXPANSION_MAX_DIDS` ceiling. Dedup against DIDs already seen.
- Wire it into the stage-1 CLI (`discover.run`) behind a `--expand` flag, or as a tiny
  stage-1b script run between discover and create_profiles. Print how many DIDs were added.

Expected: one hop off ~61 active DIDs typically reaches several hundred community DIDs,
which feeds **both** profiles and issues. This is what gets "the past week+" of issues,
since those authors weren't necessarily active in the 72h firehose window.

## Phase 3 — Issue breadth

`build_issues` candidate set is already `raw_dids ∪ profiles`, so Phase 2 multiplies it for
free. On top of that:

- **Relax `_is_open`** for the demo (include closed/resolved issues too) — more cards, and
  most Tangled issue records carry no state anyway.
- Keep the firehose-recent merge as-is (it's the only ≤3-day source).
- Optional: also scan issues filed *on* repos we discovered (not just *by* candidate DIDs)
  by adding repo-owner DIDs from Phase 2 to the candidate set (already covered if the crawl
  collects repo owners).

Expected: dozens of issues, with the crawl pulling in more recent ones than the 8 active
DIDs had on their own.

## Phase 4 — Caps & config (so we don't silently truncate)

In `services/fetch_profiles/config.py`:

- `DEFAULT_MAX_DIDS`: 200 → ~2000 (headroom; not the binding constraint today but cheap).
- `DEFAULT_WALL_CLOCK_CAP_SECONDS`: 60 → ~120.
- Add: `EXPANSION_HOPS = 1`, `EXPANSION_FANOUT_PER_DID = 50`, `EXPANSION_MAX_DIDS = 1000`.
- Add a comment reaffirming `MAX_BACKFILL_DAYS = 3` is the relay limit and that graph crawl
  is the mechanism for exceeding the window.
- Consider bumping `ENRICH_CONCURRENCY` / `FETCH_CONCURRENCY` (8) modestly for the larger set.

## Phase 5 — (optional) graceful "load more"

With a bigger pool this is less urgent, but:

- `recommender.recommend` returns `matches[:top_n]` only when real matches exist and does
  **not** pad from the fallback. Pad short pages with cold-start results so each "load more"
  page is full until the pool is genuinely exhausted.
- Frontend: when a page returns fewer than `limit`, show "you're all caught up" instead of
  an abrupt stop.

---

## Suggested order & how to run

1. Phase 1 (profiles funnel) — rerun stage 2 only:
   `uv run services/create_feature_profiles/create_profiles.py` → expect ~60 profiles.
2. Phase 4 config bumps.
3. Phase 2 crawl — rerun stage 1 (+expand) then stage 2.
4. Phase 3 — rerun stage 3: `uv run services/fetch_issues/build_issues.py`.
5. Phase 5 polish if time permits.

Full rebuild:
```bash
cd backend
uv run services/fetch_profiles/discover.py --expand   # stage 1 + graph crawl
uv run services/create_feature_profiles/create_profiles.py   # stage 2 (no prefilter, wide blob)
uv run services/fetch_issues/build_issues.py          # stage 3 (relaxed open filter)
```

## Risk / notes

- More PDS fetches = longer build & more flaky-PDS skips; all fetch paths are already
  best-effort (one bad PDS never fails the run), so this is safe, just slower.
- Featureless profiles rank last via cold-start fallback — fine for a demo, and they still
  make "load more" deep.
- No change to the runtime API surface or the committed-JSON demo model; only the offline
  build gets broader.
