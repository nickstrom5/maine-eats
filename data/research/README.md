# Maine research records (hand-checked guides and honors)

Everything here is **facts only**, each with source URLs. No review text, no ratings or stars from anyone, no readers' polls,
no "best of" votes or rankings, no Yelp/TripAdvisor/Google/Facebook as evidence. A place enters a guide only when a **2025 or 2026
source** shows it open: its own current site or menu (with a 2025–26 date, season or event on it), a dated 2025–26 news story, or
a dated 2025–26 official listing (a town page, a chamber of commerce). Never bypass bot protection: a 403, a 429/503 on repeat,
a bot check, a login wall or Facebook/Instagram-only means the place goes in `app/LEADS_<region>.md`, not in the guide.

**Check every host before you fetch or cite it:** `cd me-eats/pipeline && ../.venv/bin/python check_sources.py URL [URL ...]`
prints `usable` or why not. Don't fetch any host whose robots.txt disallows ClaudeBot, Claude-User or anthropic-ai. Known
blocked (2026-10-08): visitmaine.com (bot check), mainepublic.org, wgme.com, wmtw.com, wabi.tv, ellsworthamerican.com,
mdislander.com, seacoastonline.com, bostonglobe.com, nytimes.com, eater.com, seriouseats.com, foodandwine.com,
travelandleisure.com, thrillist.com, atlasobscura.com, guide.michelin.com; knox.villagesoup.com now redirects to midcoastvillager.com,
which disallows ClaudeBot; newscentermaine.com and toasttab.com answer article requests with 403 (treat as blocked). Known usable: pressherald.com, bangordailynews.com,
centralmaine.com, sunjournal.com, wcsh6.com, downeast.com, themainemag.com, mainebiz.biz,
boothbayregister.com, penbaypilot.com, lcnme.com, wiscassetnewspaper.com, islandadvantages.com,
fiddleheadfocus.com, theforecaster.net, portlandfoodmap.com, visitportland.com, barharborinfo.com, mainetourism.com,
yankeemagazine.com, lobsterfrommaine.com, jamesbeard.org, en.wikipedia.org. Search-result snippets may point you to a source, but
the source you cite must be one you could read.

**Seasonal is normal in Maine.** Lobster pounds, clam shacks, dairy bars and many coastal dining rooms open only about May to
October. "Closed for the season" or a winter "temporarily closed" is NOT closed: set `"seasonal": true` with the season the source
gives, and keep `"open": true`. Only a source that says the business closed for good, was sold and renamed, or burned down without
reopening makes it closed.

**Portland, Oregon leaks into third-party data** (jamesbeard.org files an Oregon chef under "Maine, Portland"). Check the state,
not just the city.

## `app/<region>.json`: a JSON array of places

```json
{
  "name": "Red's Eats",                          // the name on the place's own sign/site (never a legal entity or a person's legal name)
  "address": "41 Water St",                      // street address of THIS location
  "town": "Wiscasset",                           // the Maine town, city or plantation it's in (the municipality, not the village)
  "village": null,                               // the village/mailing name people use, if different: "Cape Neddick" (York),
                                                 // "Peaks Island" (Portland), "Northeast Harbor" (Mount Desert), "New Harbor" (Bristol),
                                                 // "Bass Harbor" (Tremont), "Tenants Harbor" (St. George), "Cape Porpoise" (Kennebunkport)
  "zip": "04578",
  "kinds": ["lobster shack", "lobster roll"],    // from the list below; a place can have several
  "dishes": ["lobster roll", "fried clams"],     // signature dishes, plain words, from its own menu or the source
  "seasonal": true,                              // true for places that close for a season
  "season": "mid-April to mid-October",          // when the source says so; else null
  "founded": 1977,                               // year it opened AT THIS ADDRESS (not the brand's founding, not before a move); null if unsure
  "founded_note": "How the source states it",    // keep claims like "first Italian sandwich" as the place's own claim
  "branch_of": null,                             // for a branch: the original's name and town
  "note": "One line in our own words: what it is and what it's known for.",
  "website": "https://...",                      // its own site, if it has one that loads (not Facebook)
  "open": true,
  "evidence_date": "2026-07",                    // month of the newest source showing it open (2025-01 or later)
  "sources": ["https://...", "https://..."]      // every fact above must be supported by one of these
}
```

`kinds` (use these exact strings):
- `lobster shack` — a lobster shack, pound or wharf that cooks lobsters (boiled/steamed lobster, lobster rolls), usually counter
  service and seasonal (Red's Eats, Five Islands Lobster Co., McLoons, Thurston's, Shaw's Wharf, Waterman's Beach Lobster).
- `lobster roll` — a place notable for its lobster roll (a sit-down restaurant can be one too).
- `clam shack` — a clam shack or seafood stand known for fried clams (whole-belly), clam cakes, chowder (The Clam Shack in
  Kennebunkport, Bob's Clam Hut in Kittery, Day's in Yarmouth, Taste of Maine).
- `red snapper` — serves red snapper hot dogs (Maine's bright-red natural-casing franks) as a signature (Flo's in Cape Neddick).
- `italian sandwich` — a Maine Italian sandwich shop (the soft roll with ham, cheese, onion, pepper, tomato, olives, pickles);
  Amato's says it originated the sandwich in 1902: keep that as Amato's claim.
- `whoopie pie` — a bakery or shop known for whoopie pies.
- `potato doughnut` — known for potato doughnuts (Maine-style, made with mashed potatoes).
- `blueberry pie` — known for wild blueberry pie (a bakery, diner or pie shop that features it).
- `franco american` — Franco-American food: poutine, tourtière (meat pie), ployes (buckwheat pancakes), cretons, boudin
  (Lewiston–Auburn, Biddeford–Saco, Waterville, the St. John Valley in Aroostook).
- `diner` — a diner (a classic diner car or a long-running diner: Moody's in Waldoboro, Palace Diner in Biddeford).
- `oyster bar` — an oyster bar, especially Damariscotta River oysters (Glidden Point, Pemaquid, Dodge Cove...).
- `dairy bar` — an ice cream stand / dairy bar that scoops (often seasonal).
- `oldest` — serving food at this address since 1950 or earlier (verify the year; an inn or tavern counts if it serves meals).
- `bean supper` — NOT used: church suppers aren't restaurants.

## `honors.json`: James Beard and other honors (statewide)

Same place fields plus:
```json
  "james_beard": ["America's Classics 2001"],    // exact award and year; semifinalist/finalist/winner said exactly. NEVER call a finalist a winner.
  "other_honors": [],                            // only real honors (awards, guide inclusions). No polls, votes, "best of" lists, star ratings.
  "chef": "..."                                  // the honored person, when the honor is a chef award
```
There is **no MICHELIN Guide for Maine**: never imply one.

## `closed_<region>.json`
Places a 2025–26 source shows closed for good: `{"name", "address", "town", "closed_reason", "sources"}`.

## `app/LEADS_<region>.md`
Places that probably belong in a guide but couldn't be verified (Facebook-only, stale site, blocked, undated menu).
