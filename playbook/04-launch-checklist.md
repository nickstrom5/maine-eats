# Launch checklist (Maine Eats)

Everything below is outward-facing: each step needs Nick's explicit yes at the time.

Status 2026-10-16 (Nick's yes): public repo https://github.com/nickstrom5/maine-eats pushed (commit 7e67507), GitHub Pages live at
https://nickstrom5.github.io/maine-eats/ (HTTPS enforced; all 211 sitemap and data URLs return 200; repo Website field set), Maine on
the eatsranked.com hub (eatsranked commit 89fb163, verify.py --browser passes). Build 1.0.0 (1) archived with the public Xcode
(`build/MaineEats.xcarchive`, DTXcodeBuild 27A266a), **not uploaded**: the upload waits for Nick's App Store Connect record.

## Before any of it
- Data refresh: the newest BABLO monthly file (record its "current as of" date in `data/raw/official/bablo/asof.json`), Lewiston's
  page, then the full rebuild in `CLAUDE.md`, `pipeline/check_websites.py --fresh`, the `ME_APP=1` export again, and
  `pipeline/check_sources.py` (exits 1 on any blocked source).
- Unit tests and the UI smoke test on "ME Eats 6.9" and "ME Eats iPad 13" (one simulator at a time); recapture screenshots if any UI changed.
- `scripts/make-site.py` then `scripts/qa-site.py` (0 problems).

## Website
1. **Create the public repo** `nickstrom5/maine-eats` (empty, no README). Then push `main` with only site and app files (`.gitignore`
   keeps `site/`, `data/me`, `data/app`, `data/raw`, Google data, `LOCAL.md` and build products out; the app's data copy is
   `MaineEats/Resources/places.json`). Before the first commit, check `git status` shows no `DerivedData*`, `site/`, `.venv` or `data/raw`.
   Author: `git -c user.name="Nick Soderstrom" -c user.email="329204362+nickstrom5@users.noreply.github.com" commit`.
2. **Enable GitHub Pages** from `main` / `docs`. Check every sitemap URL returns 200 at https://nickstrom5.github.io/maine-eats/
   (the privacy and support URLs must load before App Review).
3. **Cloudflare DNS (Nick):** `maine` CNAME → `nickstrom5.github.io`, **DNS only** (grey cloud).
4. When `dig maine.eatsranked.com` shows the CNAME: set `CUSTOM_DOMAIN = "maine.eatsranked.com"` in `scripts/make-site.py`, re-run it
   (writes `docs/CNAME`), push, wait for the Pages certificate, then `gh api -X PUT repos/nickstrom5/maine-eats/pages -F https_enforced=true`,
   set the repo's Website field, and switch `MaineEats/App/Links.swift` and the App Store Connect URLs in the next build.
5. **Hub:** add Maine to `eatsranked/tools/site-data.json` (counts from `playbook/site-numbers.json`; no "every restaurant" wording) and a
   256 px copy of `docs/icon-512.png` as `eatsranked/docs/icons/maine.png`, rebuild the hub, push (the hub is shared and public).

## App Store
1. **Nick:** register the bundle ID `com.maineeats.ios` and create the App Store Connect record "Maine Eats: Restaurants" (SKU e.g.
   `maine-eats`). The API can't create app records.
2. Trademark check: USPTO search for "Maine Eats" (classes 9, 43).
3. Archive with the **public Xcode**:
   `DEVELOPER_DIR="/Applications/Xcode 1.app/Contents/Developer" xcodebuild archive -project MaineEats.xcodeproj -scheme MaineEats
   -destination 'generic/platform=iOS' -archivePath build/MaineEats.xcarchive -derivedDataPath ./DerivedData-release -allowProvisioningUpdates`,
   then check `DTXcodeBuild` in `build/MaineEats.xcarchive/Products/Applications/MaineEats.app/Info.plist` (27A266a or whatever is current
   and public). Version 1.0.0 (1); bump `CURRENT_PROJECT_VERSION` for every upload.
4. Upload to TestFlight (with Nick's yes): `xcodebuild -exportArchive -archivePath build/MaineEats.xcarchive -exportOptionsPlist
   <a copy of scripts/ExportOptions-AppStore.plist with destination "upload"> -exportPath build/export -allowProvisioningUpdates`.
5. Fill in the listing from `06-app-store-listing.md` (App Store Connect's version must be `1.0.0`); screenshots one file at a time
   (6.9" and 13"); App Review notes from `13-app-review-reply.md`; untick "Sign-in required"; reviewer phone; age rating 13+ (alcohol
   "Infrequent"); price $0; availability United States; content rights: yes, third-party (open data, public records, Apple's place card);
   App Privacy: Data Not Collected, with the privacy policy URL.
6. Record the screen recording from `13-app-review-reply.md` on Nick's iPhone from TestFlight.
7. Show Nick the final summary; **only he submits for review.**

## Open decisions for Nick
- Records request (FOAA) to Maine CDC HIP (hiplicensing.dhhs@maine.gov) for the eating-place license list and an inspection extract.
  Only with his yes; nothing has been sent.
- Whether an active 2025–26 liquor-license term counts as "open" evidence for a hand-checked guide (now: no; Dolly's in Frenchville,
  Helen's in Machias and Ogunquit Lobster Pound wait in the leads files).
