# Maine sources (verified 2026-10-08/09)

Every host below was checked against its robots.txt with `pipeline/check_sources.py` before it was fetched or cited. Never bypass
bot protection (403s, bot checks, CAPTCHAs, logins).

## Official records

| Source | What it is | Terms / cadence | Used for |
|---|---|---|---|
| Maine CDC Health Inspection Program (HIP), maine.gov/dhhs/mecdc/services/business-services/health-inspections | Licenses and inspects eating places statewide under the Maine Food Code (10-144 CMR Ch. 200) and HIP rule Ch. 201 (eff. June 3, 2024). Portland, Lewiston and South Portland inspect their own places as delegated municipalities (Ch. 201 §3) and log them in the state system ("MUN -" license types). | Results only through apps.web.maine.gov/online/hip_search/health-inspection-search.html: one search at a time, Google reCAPTCHA plus a CSRF token. No bulk file or API (data.maine.gov is gone). | **Not scraped.** Linked as the place to look up any place's inspections. A bulk extract would need a FOAA request to hiplicensing.dhhs@maine.gov (Nick's call; not sent). |
| Ch. 201 §6(D) | "A failed inspection occurs when an establishment receives more than 3 critical violations or more than 10 non-critical violations." §6(B): at least every 24 months (Portland says at least once a year). | Rule text (PDF on maine.gov/dhhs/mecdc/sites/...; allowed by robots) | The official result is **Pass/Fail**: shown as such, with its date, never as a grade or score. |
| BABLO License Data, maine.gov/dafs/bablo/liquor-licensing/license-data | Monthly Excel (file named by month, e.g. `10-2026.xlsx`, "Data current as of: 10/1/2026"): 7,506 active licenses, 5,759 at Maine addresses. Premises name, legal entity, license number, status, type, premises type, address, expiration, initial issue date. | Published "to make commonly requested public information readily available"; no license terms stated. We use facts only (trade name, address, class). | The statewide existence check and license-only places (Class A Restaurant, Class A Restaurant/Lounge, Restaurant, Class A Lounge, Tavern, hotels/inns). `Legal Entity Name` is dropped on read and never stored. `Initial Issue Date` is the current term's start, not an opening date, and isn't used as one. Active-only: a seasonal place between terms can be missing. |
| City of Lewiston, lewistonmaine.gov/621 "Restaurant Inspection Reports" | One page listing each city-inspected establishment with its address and a link per inspection labeled "MM/DD/YYYY - Passed/Failed" (since April 2014). 113 establishments, 78 inspected since 2024, newest 2026-03-30 (one link is mis-dated "2302", ignored). | City website; facts and links. The city says it inspects 150–175 places a year, so the page is partial. | The latest result on the matching Lewiston place (strong name match, one-to-one), with its date and a link to the report. Never a list of failed places. |
| City of Portland, cdphc.portlandmaine.gov/food-service-inspections | "More than 800 establishments", inspected "at least once a year". | Links to the state HIP search; posts no results itself. | Nothing to show. |
| City of South Portland | Delegated, posts no inspection results. | — | Nothing to show. |
| U.S. Census cartographic boundaries, cb_2025_23_cousub_500k | 529 county subdivisions: 430 towns, 23 cities, 29 plantations, 42 unorganized territories, 4 reservations, 1 gore. | Public domain | Each place's town; the state outline. Overture's own address-point municipality names (township codes, "Saint George") are replaced by the Census town. |
| BLS QCEW 2025 | About 3,470 private NAICS 722 establishments in Maine (area 23000), per the state prompt's late-September research. | data.bls.gov's robots.txt disallows all crawling, so it wasn't re-fetched. | A size check only. |

## Map listings
Overture Maps places, release 2026-09-23.1 (DuckDB over S3): 7,203 eating/drinking listings with region ME (4,855 from Meta).
Address points from Overture's addresses theme (772,684 in Maine) place the license records, which have no coordinates.

## Calibration (pipeline/calibrate.py → data/me/calibration.json)
Statewide, every listing was checked against the active on-premises liquor licenses (same name nearby, or the same street address with
a distinctive name word in common). Only places that serve alcohol hold one, so rates are well under 100%; they compare kinds of listing.

| Listing | Matched a liquor license | Here |
|---|---|---|
| Meta, Overture confidence 0.95+ | 44% of 2,694 | kept |
| Meta 0.90–0.95 | 24% of 1,136 | kept |
| Meta below 0.90 | 9% of 1,005 | dropped |
| BrightQuery 0.95+ | 11% of 507 | dropped |
| Other single sources | 6% of 1,668 | dropped |

The other direction: the kept listings held 82% of Class A Restaurant licensees, 76% of Class A Restaurant/Lounges and 69% of other
restaurant licensees; licensed places they lacked were added from the list. Lewiston's posted list matched 49% of Meta 0.95+ listings,
but the page lists only about half of what the city inspects, so it's a lower bound.

## Honors (data/research/HONORS.md)
- No MICHELIN Guide restaurant selection for Maine (Michelin's Aug 11, 2026 release lists every North American guide; Maine isn't one).
  guide.michelin.com isn't fetched (robots).
- James Beard: confirmed wins only, from jamesbeard.org pages and Wikipedia's award lists; finalists are labeled finalists. Closed winners
  (Waterman's Beach Lobster, Hugo's, Arrows) carry no award onto another place.

## Research hosts
Blocked for Claude (robots.txt or bot check), never cited: visitmaine.com, mainepublic.org, wgme.com, wmtw.com, wabi.tv,
ellsworthamerican.com, mdislander.com, seacoastonline.com, bostonglobe.com, nytimes.com, eater.com, seriouseats.com, foodandwine.com,
travelandleisure.com, thrillist.com, atlasobscura.com, theinfatuation.com, guide.michelin.com, harpswell.maine.gov, midcoastvillager.com
(where knox.villagesoup.com now redirects). newscentermaine.com and toasttab.com answer article requests with 403.
