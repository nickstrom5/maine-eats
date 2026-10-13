# App Review: Guideline 2.1 "Information Needed" (prepared before submitting)

Wisconsin's first submission (2026-09-28) drew a 2.1 request for a physical-device screen recording plus six answers, because the
developer account has a short review history. Expect the same here. Record the screen recording **before** submitting and upload it
in **App Review Information → Attachment**; put the reply text below into **App Review Information → Notes** from the start (only the
reply: the Notes field holds 4,000 characters). If Apple asks anyway, paste it into **Reply to App Review** with the recording. Keep it
under 4,000 characters after any edit (count it). Recount the numbers after the final data build.

## Screen recording (Nick, on his iPhone, latest iOS)

Install through TestFlight first (internal group; the tester email must be the Apple ID under Settings › your name › Media &
Purchases on the phone, or TestFlight shows "not available"). Record with Control Center → Screen Recording, 60–120 s, no sound:

0. If Maine Eats was installed before, delete it and reinstall from TestFlight, so location starts unset and the guides open in
   Featured order.
1. Start on the Home Screen and tap **Maine Eats**. The recording must begin with the launch.
2. Home: scroll the guide cards a little.
3. Tap **Lobster Shacks & Rolls**, then **Red's Eats** ("Wiscasset · Seafood", Seasonal).
4. Tap **Ratings, hours & photos**. Apple's place card opens. Close it.
5. Tap the **heart** (Save), then go back twice.
6. Tap the Home search box and type `lobster roll portland`. Open one result.
7. Tap the **Map** tab, then **Lobster**. Tap a numbered circle to zoom in, then a pin, then the ⓘ in its bubble.
8. Tap **Saved**, where the saved place shows. Then **About**, and scroll to the sources.

## Reply text

```
Thank you. Here is the information requested. A screen recording from an iPhone running the latest iOS is attached. It starts at launch and shows the full flow.

1. Screen recording: attached. There is no account, login, user-generated content or paid content.

2. Purpose and audience: Maine Eats is a free guide to restaurants in Maine. Its focus is the state's food traditions: lobster shacks and pounds (37 places), clam shacks, red snapper hot dogs and Maine Italian sandwiches, whoopie pies and potato donuts, diners, Damariscotta River oyster bars and summer dairy bars. Each was checked by hand in October 2026 against a 2025 or 2026 source: the restaurant's own website or menu, local news, or a town or chamber listing. It also lists 4,225 restaurants, cafés, bars and bakeries in Maine's towns. It is for Maine residents and visitors deciding where to eat, with sourced facts and no ads, account or tracking.

3. How to use it (no login, no setup, no sample files needed):
- Guides tab (Home) → Lobster Shacks & Rolls (or Clam Shacks, Red Snappers & Italians, Whoopie Pies & Donuts, Diners, Oyster Bars, Dairy Bars, Maine Icons, Oldest Places, All Restaurants) → tap a place.
- On a place, tap "Ratings, hours & photos" to open Apple Maps' own place card through MapKit. Directions, Call and Website are below it.
- Search from the Home search box by name, town, village or street ("lobster roll portland", "cape neddick").
- The Map tab shows each guide as pins. "My location" and the Nearest sort use location only if allowed, on the device.
- The heart saves a place on the device, under the Saved tab. The About tab lists the data sources, licenses and the independence statement.
- On iPad, a sidebar replaces the tabs; a place opens in the right-hand column.
- Location: if you're outside Maine (as App Review usually is), the map says so and stays on Maine, and distance sorting still works from where you are.

4. External services and data:
- Apple MapKit: maps, local search to find a place's Apple Maps listing, and Apple's place card for live hours, photos and ratings.
- Core Location: optional, on-device only, for distance sorting.
- Core Spotlight: on-device indexing so places appear in iPhone search.
- No backend, accounts, analytics, advertising, payments or AI services. The restaurant data is bundled in the app.
- Bundled data: Overture Maps Foundation open place data (CDLA Permissive 2.0 / Apache 2.0 / CC0; license texts in the app); the State of Maine's public liquor-license data (trade names, addresses and license class only); the City of Lewiston's posted inspection results; U.S. Census town boundaries; James Beard award records (facts only); and our research of restaurants' own websites, menus and local news.
- The website with the privacy policy and support page is static and hosted on GitHub Pages: https://nickstrom5.github.io/maine-eats/

5. Regional differences: none. The content covers Maine; the app is offered in the United States and works the same everywhere.

6. Regulated or protected material: the app is not in a regulated industry and includes no protected third-party material. The data is open-licensed or public record, with attribution and licenses on the About tab. Ratings, hours and photos are shown only inside Apple's own place card through MapKit, under Apple's terms; the app stores no ratings or reviews. Maine's official inspection result is Pass or Fail; it appears only where the City of Lewiston posts it, labeled official with its date and a link to the city's report. Restaurant names are factual references. Every website link was checked before release, and adult venues are excluded. The app is independent and not affiliated with any restaurant, agency or the James Beard Foundation.

Support: work-with-nick@gmail.com
```

## If App Review cites Guideline 4.3(a) (Resolution Center only; never in the Notes)

Nick's call (2026-10-07, for every state): submit each state as its own app and keep this answer ready. Don't volunteer a comparison
with the other state apps. If Apple still asks for one app, the fallback is a single multi-state app with a state picker (Nick decides
then).

```
Thank you for the review. Maine Eats is not a repackaged copy of another app. It is a guide built for Maine, from Maine's own sources:
- Its guides are Maine's food traditions, each place checked by hand against a 2025 or 2026 source: lobster shacks and pounds
  (37 places, most of them seasonal), clam shacks, red snapper hot dogs and Maine Italians, whoopie pies and potato donuts, diners,
  Damariscotta River oyster bars and summer dairy bars, with each shack's season where it posts one.
- It shows the City of Lewiston's official Pass/Fail inspection results with their dates, and explains Maine's Pass/Fail rule.
- Its directory is built from Maine's own public records: the Bureau of Alcoholic Beverages and Lottery Operations' license data,
  placed on Maine's town, plantation and unorganized-territory boundaries.
- None of its places, research, guides or text is shared with any other app; the people who use it are in Maine or traveling there.
We're glad to answer any question about how the app works.
```
