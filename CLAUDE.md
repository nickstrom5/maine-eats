# Maine Eats (me-eats): notes for Claude Code sessions

Three products share this folder and one data pipeline (built from 2026-10-08; pipeline ported from `../ct-eats/`, app and site
modeled on `../wi-eats/` and `../ct-eats/`; never modify those or any other state's folder):
- **The iOS/iPadOS app** "Maine Eats: Restaurants" (subtitle "Lobster Shack & Clam Guide", Home Screen "Maine Eats", bundle
  `com.maineeats.ios`; SwiftUI, iOS 18+), with its website in `docs/` (GitHub Pages; planned home maine.eatsranked.com).
- **The web leaderboard** (`site/`, untracked), a private claude.ai Artifact whose URL is in `LOCAL.md` (untracked; republish
  `site/index.html` with `maine.json`, `me_detail.json`, `me_shapes.json` from the same path to keep the URL). It uses Google 2021
  ratings and review signals; the app never does. Keep its URL out of tracked files.

Read `../STATE_EATS_PLAYBOOK.md` and `playbook/12-sources.md` first.

## Nick's decisions
- 2026-10-09: name, subtitle and Home Screen name above; icon = a flat lobster roll in a split-top bun with a red claw on top, on deep
  ocean teal (concept A of `scripts/icon-concepts.swift`), redrawn 2026-10-09 in the shared Eats Ranked style Nick approved (same food
  and colours; no wave, claw level): generator `scripts/make-brand.swift` (the site's header logo, `lobster_roll_svg` in
  `scripts/make-site.py`, copies it), style guide `../state-prompts/ICON-STYLE.md`; palette = "cozy ocean":
  sea-salt cream #FBF6EC, deep ocean teal #0E4D5C (white text on it), sea glass #CDE6E3, buoy yellow #F2B705 only as a fill under dark
  text #10262E, lobster coral #C2492F for thin accents. No team marks, no state seal.
- 2026-10-08/09 on the leaderboard: "better colors", "ocean vibes", "cozy", then "better design" → deep-water header with a shack-season
  note, grouped boards, lobster-buoy ranks for the top three, Zilla Slab + Figtree, a chart-style map (sand land, shoal band, sea).

## Data rules (the app's promise)
- The App Store build ships **no Google-derived data**: `ME_APP=1 .venv/bin/python pipeline/maine.py` writes `data/app/places.json`;
  copy it to `MaineEats/Resources/places.json` after every rebuild.
- Maine's inspection results are search-only behind reCAPTCHA: never scraped. The official result is **Pass/Fail** (Ch. 201 §6(D));
  never compute a grade. Lewiston's posted results attach to Lewiston places only (strong name match, one-to-one, inspected 2023 or
  later), shown with the date and the city's report link, never as a board.
- BABLO license data: only the Premises Name is used; `Legal Entity Name` is dropped on read. Initial Issue Date is not an opening year.
  Active-only file: a seasonal place missing from it is not closed.
- The classics guides (lobster shacks & rolls, clam shacks, red snappers & Italians, whoopie pies & donuts, Franco-American, diners,
  oyster bars, dairy bars) list only **hand-checked** places (`hc`, matched to `data/research/app/*.json` or `honors.json`, each with
  a 2025–26 source showing it open). A classic with fewer than 4 places isn't offered (Home or iPad sidebar). Franco-American had 1.
  An active liquor license alone isn't accepted as "open" evidence (Dolly's in Frenchville is a lead until Nick decides otherwise).
- **Seasonal is normal**: lobster pounds, clam shacks and dairy bars close for winter; that's `seasonal`, never closed. Closures need a
  source (`data/research/closed_*.json`), and a closure never removes a place the research found open ("Look Lobster" took Quoddy Bay
  Lobster's address).
- Adult venues: `data/research/adult_venues.json` (sourced) removes a place at that address with a shared distinctive name word
  ("Diamonds", 190 Harlow St, Bangor, holds a plain Class A Lounge license; The Rock Room in the same building stays). A listing Overture
  files as adult entertainment is hidden with the non-restaurants until checked ("Hour Place", Jay).
- Every research source passes `pipeline/check_sources.py` (robots.txt for ClaudeBot/Claude-User/anthropic-ai, bot checks). Run it before
  each release; it exits 1 on any blocked source.
- Hijacked pages (QA 2026-10-19, P1 #4; ported 2026-10-21): `check_websites.py` runs `pipeline/injection.py`, Wisconsin's detector, on every
  page (planted casino, betting, adult, pharma and link-farm links, visible, hidden or off-screen; other-language gambling text; parked
  and default pages). Keep it identical to `../wi-eats/pipeline/injection.py`; `test_injection.py` must pass. `--recheck-ok` fetches every
  passing page again before each submission (resumable: pages re-checked in the last 2 days are skipped), `--retry-transient` re-fetches
  429s and connection errors afterwards, and `CHECK_WORKERS=4` slows a run (Squarespace rate-limits across all our concurrent checkers).
- Tracking tags: the app export strips `ref=google`, `referrer=google_food_ordering`, `cn_channel`, `utm_*`, `fbclid`, Yext `cid=RF:YXT…`
  and similar from every outbound link (`pipeline/tracking_params.py`, the same in every state; store ids and locations stay). The site
  reads the app export, and a unit test fails if a tracked link is bundled (QA 2026-10-19, P1 #13).
- Website links: `pipeline/check_websites.py` (fail closed; anchored to the place's town, zip, phone, street, or a domain that spells its
  name; chain domains exempt; atomic saves; back up `data/me/website_check.json` before stopping a run). Order: export, check, export.
  Hacked, expired or wrong-business sites found later go in `pipeline/website_blocklist.json` (`match` "domain" = it and its subdomains,
  "url" = one page; keep the sentinel entry first): `scripts/make-site.py` drops the link (never the place) from every page and the web
  app's data, and `qa-site.py` fails if a listed one is anywhere in `docs/`. Merge the link sweep's batch files with
  `scripts/merge-blocklist.py <batch-N-me.json …>`, then regenerate and QA. Since 2026-10-16 `pipeline/maine.py` (ME_APP=1) drops the same links from the app's `places.json`.
- Place ids come from the source record (Overture GERS id, license number, or researched name + town); `data/id_history.json` keeps every
  id and the export writes aliases.

- maine.gov answered our user agent with 403 on 2026-10-16 (BABLO's license-data page). Don't retry around it; if it still refuses at
  the next refresh, ask Nick to download the monthly xlsx by hand (see `playbook/12-sources.md`).
- Family-wide wording (Nick, 2026-10-13): a Meta 0.95+ listing is a "High-confidence listing", never "confirmed"; the filter reads "Only
  licensed, high-confidence or hand-checked places"; the site's pre-launch button is "Ask for early access" with no invite promise.

## Rebuild
```bash
.venv/bin/python pipeline/fetch_overture.py      # Overture places + address points -> data/me
.venv/bin/python pipeline/fetch_towns.py         # Census towns + address points tagged with their town -> data/me
# BABLO: download the newest monthly xlsx from the license-data page into data/raw/official/bablo/ and record its "current as of"
# date in data/raw/official/bablo/asof.json; Lewiston: save lewistonmaine.gov/621 to data/raw/official/lewiston/621.html
cd pipeline
../.venv/bin/python official.py                  # licenses + Lewiston -> data/me/official.pkl
../.venv/bin/python listings.py                  # clean listings, towns, Google 2021 match -> data/me/stage1.pkl
../.venv/bin/python calibrate.py                 # match rates -> data/me/calibration.json
../.venv/bin/python reviews.py                   # streams UCSD reviews (never stored) -> data/me/review_signals.parquet (web only)
../.venv/bin/python maine.py                     # web leaderboard -> site/
ME_APP=1 ../.venv/bin/python maine.py            # app data -> data/app/places.json
../.venv/bin/python check_websites.py            # then rerun the ME_APP=1 export
../.venv/bin/python check_sources.py             # every research source still usable
```
The venv is an APFS clone of ct-eats' (plus openpyxl and pypdf).

## Build the app
- The Xcode project is generated: `xcodegen generate`. Never commit `MaineEats.xcodeproj`.
- Compile check without a simulator: `DEVELOPER_DIR="/Applications/Xcode 1.app/Contents/Developer" xcodebuild build -project
  MaineEats.xcodeproj -scheme MaineEats -destination 'generic/platform=iOS Simulator' -derivedDataPath ./DerivedData CODE_SIGNING_ALLOWED=NO`
- **Archive and upload only with the public Xcode** (`/Applications/Xcode 1.app`); `Xcode.app` is a beta App Review refuses. Check
  `DTXcodeBuild` in the archive. Bump `CURRENT_PROJECT_VERSION` for every upload.
- Simulators: this Mac is shared. Before booting, check `ps -u $(id -u) | wc -l` (wait if over ~2,300), `sysctl vm.swapusage` (wait if
  nearly full) and `xcrun simctl list devices | grep Booted` (wait if other sessions have 2+ "… Eats" simulators up). Use only our own
  "ME Eats 6.9" (iPhone 17 Pro Max, 1320×2868) and "ME Eats iPad 13" (2064×2752), one booted at a time, shut down when done. UI tests
  need a signed runner (no `CODE_SIGNING_ALLOWED=NO`).
- Light mode only (`UIUserInterfaceStyle: Light`). `-screenshot <home|lobster|clams|sweets|detail|map|icons|saved|about>` is DEBUG-only
  (fixed location: Portland's Old Port).

## Website (`docs/`)
Generated by `scripts/make-site.py` (never hand-edit `docs/*.html`); QA with `scripts/qa-site.py` (`--static-only` skips the browser
pass; `--docs`/`--skip-pages` for mutation runs on a copy). Until the `maine.eatsranked.com` CNAME resolves, the site and the app's
`Links.swift` use https://nickstrom5.github.io/maine-eats/. Preview: the `me-eats-site` launch config serves `build/serve/maine-eats`
(a symlink to `docs/`) on port 8842.
- Pages: home, a page per guide with 5+ places (Franco-American has none yet), Maine Icons, Oldest restaurants (40+ years at the
  address, the app's rule), 29 town pages and a hub, the 8 regions (each naming its counties), one page per hand-checked or honored
  place, about/privacy/terms/404, and `/explore/` (the web app, `scripts/explore.js`, reading `docs/data/core.json` and lazily
  `detail.json`). Keep `explore.js` in step with `Search.swift` and `Guide.swift` (the route-word fix and the 40-year rule are in both).
- Lewiston's Pass/Fail shows only on a place's own page and in the web app's place panel, never in a list (QA fails otherwise).
- Casino labels: only at the casino's own address (Hollywood Casino Bangor 500 Main St; Oxford Casino 777 Casino Way); the build
  warns about any other.
- Strict CSP: scripts and styles are hashed; no inline `style=` or `on…=`. No ratings, no `aggregateRating`, no "every"/"all restaurants".

## Outward actions need Nick's explicit yes, every time
Creating the public repo, pushing, Pages, anything in App Store Connect, uploads, emails, records requests (FOAA). Never submit for
review or accept agreements. Public commits use `329204362+nickstrom5@users.noreply.github.com`. Never publish scraped or Google data
files. Support email: nick@eatsranked.com (Nick, 2026-10-12), everywhere: site, app, listing, review reply, pipeline user agents. A unit test fails on "gmail.com" in the app's source.
