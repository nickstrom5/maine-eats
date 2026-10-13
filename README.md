# me-eats

Two things built from one pipeline:

1. **Maine Eats**, a free iPhone and iPad app (App Store name "Maine Eats: Restaurants", subtitle "Lobster Shack & Clam Guide"), and
   its website `docs/` (GitHub Pages; planned home maine.eatsranked.com).
2. **The web leaderboard** of every licensed or confirmed restaurant in Maine, published as a private claude.ai Artifact from
   `site/index.html` (git-ignored: it carries Google 2021-derived ratings).

| Path | What |
|---|---|
| `project.yml` | XcodeGen spec: app `MaineEats` (bundle `com.maineeats.ios`, iOS 18, iPhone + iPad), tests `MaineEatsTests`, `MaineEatsUITests` |
| `MaineEats/` | SwiftUI app: guides (Lobster Shacks & Rolls, Clam Shacks, Red Snappers & Italians, Whoopie Pies & Donuts, Diners, Oyster Bars, Dairy Bars, Maine Icons, Oldest Places, Near Me, All), search, filters, a clustered map, saved places, About with sources and licenses |
| `MaineEats/Resources/places.json` | The whole data set, bundled, copied from `data/app/places.json` (no Google-derived data) |
| `pipeline/` | Overture places, Census towns, BABLO licenses, Lewiston inspections, calibration, the build (`maine.py`), link and source checkers |
| `data/research/` | Hand-checked guide research, honors, closures and adult-venue list: facts only, each with source URLs |
| `scripts/` | `make-brand.swift` (icon, og.png, favicons), `icon-concepts.swift`, `make-site.py` (the website), `explore.js` (web app), `qa-site.py` |
| `playbook/` | Sources, naming, App Store listing, App Review reply |

See `CLAUDE.md` for the rebuild steps and the data rules, and `playbook/12-sources.md` for every source and the calibration.
