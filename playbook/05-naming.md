# Naming, icon and palette (Nick's calls, 2026-10-09)

## Name
Candidates checked 2026-10-08 (Apple's public search API, RDAP):
- **Maine Eats: Restaurants** (chosen). No App Store app by that name; maineeats.com is registered to someone else (expires
  2026-10-17), which doesn't matter: the site is maine.eatsranked.com. Home Screen `Maine Eats` (10 characters, fits; "ME Eats" reads
  as "me eats").
- Pine Tree Eats: the state nickname; drops "Maine" from the name (weaker search); pinetreeeats.com unregistered.
- Vacationland Eats: the plate motto, widely used by other businesses (trademark risk); vacationlandeats.com unregistered.
- Avoided: "Downeast" (one region, and Down East magazine), "Maine Lobster Shacks" (an existing app by PVI Maine LLC), "The Way Life
  Should Be", "Visit Maine".
USPTO search for MAINE EATS: pending (Nick).

## Icon
Three flat concepts on deep ocean teal (`scripts/icon-concepts.swift`, sheet in `brand/concepts.png`): A lobster roll in a split-top bun
with a claw, B whoopie pie, C whole lobster. Nick picked **A**. A red snapper hot dog wasn't drawn: Chicago's icon is a hot dog, and each
state app must look like its own (Guideline 4.3(a)). `scripts/make-brand.swift` draws the app icon, favicons and og.png.
Redrawn 2026-10-09 in the shared Eats Ranked icon style Nick approved (`../state-prompts/ICON-STYLE.md`): same food and colours, flat
teal with no wave, the claw level on the heap. `scripts/make-site.py` (`lobster_roll_svg`) copies it as the site's header logo.

## Palette
"Cozy ocean" (Nick asked for ocean vibes and cozy): sea-salt cream #FBF6EC, deep ocean teal #0E4D5C, ocean #236B78, sea glass #CDE6E3,
buoy yellow #F2B705 as a fill under ink #10262E only (1.8:1 as text on white), lobster coral #C2492F for thin accents. Light mode only in
the app. No Red Sox or Sea Dogs marks.
