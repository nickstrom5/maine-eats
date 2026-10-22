"""Stage 2: the Maine list -> site/maine.json (web leaderboard) or, with ME_APP=1, data/app/places.json (the app)

Adapted from ct-eats/pipeline/connecticut.py. Statewide base: Overture Maps listings (stage1.pkl), each placed in one of Maine's 529
towns, cities, plantations and unorganized territories by its point, kept by the rule calibrate.py measured against official lists
(BABLO's liquor licenses statewide, Lewiston's posted inspections):
  - Meta listings and chain store feeds (AllThePlaces, DAC) are kept; single sources like Foursquare, BrightQuery and Microsoft are
    dropped (statewide 5-12% of them matched an on-premises liquor license, against 41-44% for Meta);
  - anything Google (2021) or Overture already shows as closed is dropped, unless it's on an official list.
Official records: every listing is checked against BABLO's active on-premises liquor licenses (Class A Restaurant, Class A
Restaurant/Lounge, Restaurant, Class A Lounge, Tavern, hotels and inns) statewide, and in Lewiston against the city's posted
food-service inspections. Licensed restaurants and bars the map data doesn't have are added from the lists. Only the Premises Name
(trade name) of a license is ever used. Maine's statewide inspection results are search-only (reCAPTCHA), so there are no
inspection boards; Lewiston's posted Pass/Fail results show on its places, labeled official, with the date.
Seasonal places (lobster pounds, clam shacks) are normal in Maine: a winter closure is never treated as closed.
Web leaderboard only: ratings, reviews and price level from Google's Sep 2021 snapshot (UCSD Google Local), and dish signals from
Google reviews written through Sep 2021. ME_APP=1 drops all of that (the App Store build ships no Google-derived data).
"""
import os, re, sys, json, math, glob, hashlib, unicodedata, collections, urllib.parse
import numpy as np, pandas as pd
from shapely.geometry import shape, Point
from shapely.prepared import prep
from rapidfuzz import fuzz
from common import (norm_name, nice, name_sim, cuisine, FOOD_COST, MARGIN, MARGIN_CUISINE, SPEND, GENERIC, _stems, DATA, ME, ROOT, RAW,
                    canon_city, CUISINE_RULES)
from brands import brand_of
import official
import tracking_params   # outbound links lose their tracking tags (QA 2026-10-19, P1 #13)

from official import street_key, street_nums, street_dir, dir_ok, ON_PREMISE
from listings_util import official_match, _close_words

APP = os.environ.get("ME_APP") == "1"
SITE = os.environ.get("ME_SITE") or (os.path.join(ROOT, "data", "app") if APP else os.path.join(ROOT, "site"))
# "data as of": the day the official lists were downloaded (the newest source), so it moves with every refresh
GENERATED = __import__("datetime").date.fromtimestamp(max(os.path.getmtime(f) for f in glob.glob(f"{RAW}/official/bablo/*.xlsx"))).isoformat()
RESEARCH_CHECKED = "October 2026"   # when the hand-checked guides were last researched (shown in the app and on the site)
OVERTURE = "2026-09-23.1"
GOOD_SOURCES = {"meta", "AllThePlaces", "DAC"}
BASE = {1: 600_000, 2: 1_000_000, 3: 2_200_000, 4: 3_500_000}   # typical yearly sales by price tier (same as Chicago)
B_FIT = 0.764   # review-volume exponent fit on Chicago's published sales (chi-eats meta.model.b)
TAX_CUISINE = {
    "pizza_restaurant": "Pizza", "mexican_restaurant": "Mexican", "taco_restaurant": "Mexican", "texmex_restaurant": "Mexican",
    "sandwich_shop": "Sandwiches & Deli", "delicatessen": "Sandwiches & Deli", "bakery": "Bakery & Sweets", "donut_shop": "Bakery & Sweets",
    "dessert_shop": "Bakery & Sweets", "ice_cream_shop": "Bakery & Sweets", "bagel_shop": "Bakery & Sweets", "cupcake_shop": "Bakery & Sweets",
    "frozen_yogurt_shop": "Bakery & Sweets", "chocolatier": "Bakery & Sweets", "popcorn_shop": "Bakery & Sweets",
    "bar_and_grill_restaurant": "Bar & Pub", "gastropub": "Bar & Pub", "bar": "Bar & Pub", "brewery": "Bar & Pub", "pub": "Bar & Pub",
    "sports_bar": "Bar & Pub", "cocktail_bar": "Bar & Pub", "wine_bar": "Bar & Pub", "dive_bar": "Bar & Pub", "beer_bar": "Bar & Pub",
    "irish_pub": "Bar & Pub", "tiki_bar": "Bar & Pub", "speakeasy": "Bar & Pub", "hookah_bar": "Bar & Pub", "gay_bar": "Bar & Pub",
    "chinese_restaurant": "Chinese", "italian_restaurant": "Italian", "burger_restaurant": "Burgers",
    "breakfast_and_brunch_restaurant": "Breakfast & Diner", "diner": "Breakfast & Diner", "barbecue_restaurant": "BBQ",
    "chicken_restaurant": "Chicken & Wings", "chicken_wings_restaurant": "Chicken & Wings", "sushi_restaurant": "Japanese & Sushi",
    "japanese_restaurant": "Japanese & Sushi", "ramen_restaurant": "Japanese & Sushi", "seafood_restaurant": "Seafood", "poke_restaurant": "Seafood",
    "steakhouse": "Steakhouse", "indian_restaurant": "South Asian", "pakistani_restaurant": "South Asian", "thai_restaurant": "Thai",
    "hot_dog_restaurant": "Hot Dogs", "mediterranean_restaurant": "Mediterranean & Middle Eastern",
    "greek_restaurant": "Mediterranean & Middle Eastern", "middle_eastern_restaurant": "Mediterranean & Middle Eastern",
    "korean_restaurant": "Korean", "vietnamese_restaurant": "Vietnamese", "salad_bar": "Healthy & Vegan", "vegan_restaurant": "Healthy & Vegan",
    "vegetarian_restaurant": "Healthy & Vegan", "health_food_restaurant": "Healthy & Vegan", "coffee_shop": "Coffee & Café", "cafe": "Coffee & Café",
    "coffee_roastery": "Coffee & Café", "smoothie_juice_bar": "Healthy & Vegan", "juice_bar": "Healthy & Vegan", "bubble_tea_shop": "Coffee & Café",
    "tea_room": "Coffee & Café", "soul_food": "Soul & Southern", "southern_american_restaurant": "Soul & Southern",
    "cajun_and_creole_restaurant": "Seafood", "caribbean_restaurant": "Latin & Caribbean", "jamaican_restaurant": "Latin & Caribbean",
    "latin_american_restaurant": "Latin & Caribbean", "cuban_restaurant": "Latin & Caribbean", "puerto_rican_restaurant": "Latin & Caribbean",
    "peruvian_restaurant": "Latin & Caribbean", "brazilian_restaurant": "Latin & Caribbean", "colombian_restaurant": "Latin & Caribbean",
    "dominican_restaurant": "Latin & Caribbean", "salvadoran_restaurant": "Latin & Caribbean", "african_restaurant": "African",
    "ethiopian_restaurant": "African", "french_restaurant": "European", "german_restaurant": "European", "polish_restaurant": "European",
    "portuguese_restaurant": "European", "spanish_restaurant": "European", "tapas_bar": "European", "noodles_restaurant": "Chinese",
    "belgian_restaurant": "European", "russian_restaurant": "European", "fondue_restaurant": "European", "irish_restaurant": "European",
    "scandinavian_restaurant": "European", "european_restaurant": "European", "eastern_european_restaurant": "European",
    "hungarian_restaurant": "European", "british_restaurant": "European", "dutch_restaurant": "European", "ukrainian_restaurant": "European",
}
# host venues whose restaurants are shown "at" the host: Maine's two commercial casinos, by their own street address only (a radius
# once labeled Geaghan's and half of South Paris as casino restaurants)
CASINOS = [("Hollywood Casino Bangor", "Bangor", r"^500 MAIN ST\b", ("HOLLYWOOD CASINO",)), ("Oxford Casino", "Oxford", r"^777 CASINO WAY\b", ("OXFORD CASINO",))]
KINDS = ["lobster shack", "lobster roll", "clam shack", "red snapper", "italian sandwich", "whoopie pie", "potato doughnut", "blueberry pie",
         "franco american", "diner", "oyster bar", "dairy bar", "oldest"]
TAGS = ["lobster", "clams", "hotdog", "italian", "whoopie", "donut", "franco", "diner", "oyster", "dairy"]   # bit order in the data files


def pct(s):
    return (s.rank(pct=True) * 100).round(1)


def km(la1, lo1, la2, lo2):
    return math.hypot((la1 - la2) * 111, (lo1 - lo2) * 83)


def curated_matcher(frame):
    """A researched place -> row of frame: same street number and street with a similar name; else a near-exact name in the same town;
    else a near-exact name that's unique statewide (only when the research gives no street number)."""
    by_key, by_num = {}, {}
    for i, a in enumerate(frame.street):
        sk = street_key(a)[1]
        for n in street_nums(a):
            if sk:
                by_key.setdefault((n, sk), []).append(i)
                by_num.setdefault(n, []).append((sk, i))
    towns = [c.lower() if isinstance(c, str) else "" for c in frame.city]
    row_nums = [street_nums(a) for a in frame.street]
    vills = [c.lower() if isinstance(c, str) else "" for c in frame.get("village", pd.Series(None, index=frame.index))]
    ks = list(frame.k.fillna(""))

    def match(c):
        keys = {norm_name(m) for m in (c.get("match_names") or [])} or {norm_name(c["name"])}
        keys.discard("")
        _, sk = street_key(c.get("address") or "")
        cands = set()
        for n in street_nums(c.get("address") or ""):
            cands.update(by_key.get((n, sk), []))
            if sk:   # a spelling slip in the street or a longer name for it ("Old County" / "County")
                cands.update(i for sk2, i in by_num.get(n, []) if sk2 != sk and (fuzz.ratio(sk, sk2) >= 85
                             or set(sk.split()) < set(sk2.split()) or set(sk2.split()) < set(sk.split())))
        best, bs = None, 0
        for i in cands:
            # at the same address a different name is a different business unless a distinctive word is shared: a wharf's two
            # businesses can share only the town's or harbor's name
            mine = set().union(*(distinct(m) for m in keys)) if keys else set()
            s_ = max((fuzz.token_set_ratio(m, ks[i]) for m in keys), default=0)
            if (s_ >= 90 or (s_ >= 60 and mine & distinct(ks[i]))) and s_ > bs:
                best, bs = i, s_
        if best is None and not c.get("chain"):
            # a near-exact name in the same town or village, never at a different street number ("The Spot" at 163 Wooster St is not
            # the original at a different number); statewide only when the research gives no street number (a second location elsewhere is its own place)
            ctown = (c.get("city") or "").lower()
            cvil = (c.get("village") or "").lower()
            cnums = street_nums(c.get("address") or "")
            ok = lambda i: not (cnums and row_nums[i] and not (cnums & row_nums[i]))
            sim = [max(fuzz.ratio(m, k) for m in keys) if k else 0 for k in ks]
            hits = [i for i, s_ in enumerate(sim) if s_ >= 90 and (towns[i] == ctown or (cvil and vills[i] == cvil)) and ok(i)] \
                or ([i for i, s_ in enumerate(sim) if s_ >= 95 and ok(i)] if not cnums else [])
            if len(hits) == 1:
                best = hits[0]
        return best
    return match


def load_research():
    """data/research/app/*.json (the hand-checked guides) and data/research/honors.json (James Beard), facts only, each with sources.
    A place in several files is one entry with everything the files know."""
    out, by = [], {}
    files = sorted(glob.glob(f"{DATA}/research/app/*.json")) + [f for f in [f"{DATA}/research/honors.json"] if os.path.exists(f)]
    for f in files:
        try:
            entries = json.load(open(f))
        except json.JSONDecodeError as e:
            print("!! research file doesn't parse, skipped:", f, e); continue
        for e in entries:
            if e.get("open") is False or not e.get("name") or not e.get("sources"):
                continue
            town = e.get("town") or e.get("city")
            key = (norm_name(e["name"]), (town or "").lower(), (street_key(e.get("address") or "")[0] or ""))
            c = by.get(key)
            if c is None:
                c = {"name": e["name"], "address": e.get("address"), "city": town, "village": e.get("village"), "zip": e.get("zip"),
                     "chain": False, "match_names": [re.sub(r"\s*\([^)]*\)\s*$", "", e["name"]).upper()], "founded": None, "open": True, "tags": [], "dishes": [],
                     "james_beard": [], "other_honors": [], "rsources": [], "research_only": True}
                by[key] = c; out.append(c)
            c["match_names"] = list(dict.fromkeys(c["match_names"] + [m.upper() for m in (e.get("match_names") or [])]))
            c["tags"] = list(dict.fromkeys(c["tags"] + [k.lower() for k in (e.get("kinds") or [])]))
            c["dishes"] = list(dict.fromkeys(c["dishes"] + (e.get("dishes") or [])))
            c["james_beard"] = list(dict.fromkeys(c["james_beard"] + (e.get("james_beard") or [])))
            c["other_honors"] = list(dict.fromkeys(c["other_honors"] + (e.get("other_honors") or [])))
            c["rsources"] = list(dict.fromkeys(c["rsources"] + (e.get("sources") or [])))
            for k in ("note", "website", "season", "branch_of", "chef", "village", "zip"):
                c[k] = c.get(k) or e.get(k)
            c["seasonal"] = bool(c.get("seasonal") or e.get("seasonal"))
            if not c.get("founded") and isinstance(e.get("founded"), int):
                c["founded"] = e["founded"]
            if e.get("note") and not c.get("iconic_reason"):
                c["iconic_reason"] = e["note"]
    return out


o = pd.read_pickle(f"{ME}/stage1.pkl")
o["city"] = o.town            # the town is the polygon's; the mailing name survives as `village` when it's a village
o["village"] = o.village.map(lambda v: canon_city(v) if isinstance(v, str) else v)   # one name per village
G = pd.read_pickle(f"{ME}/google21.pkl")
if APP:   # the App Store build ignores every Google 2021 match
    o["in21"] = False; o["closed21"] = False; o["gi"] = np.nan
calib = json.load(open(f"{ME}/calibration.json"))
TOWNWORDS = frozenset(w for t in o.town.dropna().unique() for w in norm_name(t).split())
# words two different businesses at one address share without being the same place: the town, the village, the wharf, "ristorante"
VILLAGEWORDS = frozenset(w for v in o.village.dropna().unique() for w in norm_name(str(v)).split())
NOT_DISTINCT = TOWNWORDS | VILLAGEWORDS | {"HOLLYWOOD", "CASINO", "RISTORANTE", "RESTAURANTE", "CUCINA", "BISTRO", "CANTINA", "TRAVEL",
                                          "PLAZA", "MALL", "CENTER", "COMMONS", "VILLAGE", "MILL", "MARKETPLACE", "WHARF", "PIER", "HARBOR",
                                          "HARBOUR", "LOBSTER", "POUND", "MAINE", "OCEAN", "SEA", "COASTAL", "INN"}


NOT_DISTINCT = NOT_DISTINCT | {w[:-1] for w in NOT_DISTINCT if len(w) > 3 and w.endswith("S")}   # as _stems spells them


def distinct(k):
    """A name's words that tell one business from its neighbors: not generic, not a town's or village's name, three letters or more."""
    return {w for w in _stems(k or "") - GENERIC - NOT_DISTINCT if len(w) >= 3}

# ---------------------------------------------------------------- official records: BABLO statewide, Lewiston's inspected places
F = official.load()
F = F[F.active & F.lat.notna()].reset_index(drop=True)
LICENSE_FILE = F.source_file.iat[0]
# BABLO's own "Data current as of" date for that file (recorded from the license-data page when the file is downloaded)
_asof = json.load(open(f"{RAW}/official/bablo/asof.json")).get(LICENSE_FILE, {}).get("current_as_of")
LICENSE_DATE = pd.Timestamp(_asof).strftime("%b %-d, %Y") if _asof else None
for jur, kinds in (("bablo", ON_PREMISE | {"brewery", "club", "venue", "caterer"}), ("lewiston", {"food"})):
    sel = o.index[o.town.eq("Lewiston")] if jur == "lewiston" else o.index
    R = F[(F.jur == jur) & F.kind.isin(kinds)]
    # one license, one place: the best name match takes it, and a listing that loses it (an old tenant's name, a duplicate) falls back to
    # its own keep rule
    m = official_match(o.loc[sel].reset_index(drop=True), R.reset_index(drop=True), one_to_one=True, town_words=TOWNWORDS)
    o["off_" + jur] = np.nan
    for i, j in m.items():
        o.at[sel[i], "off_" + jur] = R.index[j]
o["off"] = o.off_bablo.where(o.off_bablo.notna(), o.off_lewiston)
o["official"] = o.off.notna()
print("listings matched to an active license:", int(o.official.sum()), "| BABLO:", int(o.off_bablo.notna().sum()), "| Lewiston:", int(o.off_lewiston.notna().sum()))

# ---------------------------------------------------------------- keep rule (see calibrate.py / calibration.json)
base_ok = ~o.j_junk & ~o.j_closedname & ~o.j_outside & ~o.j_far & ~o.ov_closed & ~(o.nowhere & ~o.in21) & o.town.notna()
CUR = load_research()
print("hand-checked research entries:", len(CUR))
_m = curated_matcher(o[base_ok].reset_index())
_bo = o.index[base_ok]
verified = pd.Series(False, index=o.index)
for c in CUR:
    j = _m(c)
    if j is not None:
        verified[_bo[j]] = True
keep = base_ok & (~o.closed21 | o.official | verified) & (o.src.isin(GOOD_SOURCES) | o.official | verified)
if APP:
    # measured against BABLO's on-premises liquor licenses statewide (calibration.json): Meta listings with Overture confidence >= 0.95
    # matched one 44% of the time, Meta 0.90-0.95 24%; lower-confidence Meta 9%, BrightQuery >= 0.95 11% and the rest 6% are dropped
    # (the same ordering Hartford, Milwaukee and Dane County showed against full food-license lists)
    conf = o.confidence.fillna(0)
    keep = base_ok & (o.official | verified | ((o.src == "meta") & (conf >= 0.9)) | o.src.isin(["AllThePlaces", "DAC"]))
print("kept listings:", int(keep.sum()), "of", len(o), "| dropped single-source (Foursquare/BrightQuery/Microsoft):",
      int((base_ok & ~o.src.isin(GOOD_SOURCES) & ~o.official & ~verified).sum()), "| closed per Google 2021:", int((base_ok & o.closed21 & ~o.official).sum()))
o = o[keep].reset_index(drop=True)

# ---------------------------------------------------------------- duplicate listings of one place
o["biz"] = o.off.map(lambda j: F.biz.iat[int(j)] if j == j else np.nan)
o["rank"] = o.official.astype(int) * 8 + o.in21.astype(int) * 4 + o.src.isin(GOOD_SOURCES).astype(int) * 2 + o.confidence.fillna(0)
o = o.sort_values("rank", ascending=False).reset_index(drop=True)
cell, drop = {}, set()
for i, r in o.iterrows():
    key = (round(r.lat / 0.001), round(r.lon / 0.0013))
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for j in cell.get((key[0] + dy, key[1] + dx), []):
                d_ = math.hypot((o.lat.iat[j] - r.lat) * 111000, (o.lon.iat[j] - r.lon) * 83000)
                same_biz = r.biz == r.biz and r.biz == o.biz.iat[j] and name_sim(r.k, o.k.iat[j]) >= 80
                if same_biz or (d_ < 80 and (r.k == o.k.iat[j] or (fuzz.token_set_ratio(r.k, o.k.iat[j]) >= 92 and r.st & o.st.iat[j]))) or (
                        d_ < 150 and isinstance(r.brand_n, str) and r.brand_n == o.brand_n.iat[j]):
                    drop.add(i); break
            if i in drop: break
        if i in drop: break
    if i not in drop:
        cell.setdefault(key, []).append(i)
o = o.drop(index=list(drop)).reset_index(drop=True)
akey = [(b if isinstance(b, str) else k, n, c) if n and isinstance(c, str) else None for b, k, n, c in zip(o.brand_n, o.k, o.num, o.city)]
seen, dup = set(), []
for a in akey:   # o is sorted best-first, so the better-sourced copy survives
    dup.append(a is not None and a in seen)
    if a is not None:
        seen.add(a)
has_addr = o.num.notna()
for b, grp in o[o.brand_n.notna()].groupby("brand_n"):
    with_a, without = grp[has_addr[grp.index]], grp[~has_addr[grp.index]]
    for i, r in without.iterrows():
        if len(with_a) and (np.hypot((with_a.lat - r.lat) * 111, (with_a.lon - r.lon) * 83) < 1.5).any():
            dup[i] = True
o = o[~np.array(dup)].reset_index(drop=True)
near_dup = set()
for (k, c), grp in o[o.brand_n.isna() & o.k.fillna("").str.len().ge(4) & o.city.notna()].groupby(["k", "city"]):
    if len(grp) < 2 or not (_stems(k) - GENERIC):
        continue
    idx = list(grp.index)   # already best-first
    for a in range(len(idx)):
        for b in range(a + 1, len(idx)):
            if idx[b] in near_dup or idx[a] in near_dup:
                continue
            if math.hypot((o.lat[idx[a]] - o.lat[idx[b]]) * 111000, (o.lon[idx[a]] - o.lon[idx[b]]) * 83000) < 500 and not (o.official[idx[a]] and o.official[idx[b]]):
                near_dup.add(idx[b])
    good = grp[grp.in21 | grp.official]
    for i in grp.index[~(grp.in21 | grp.official)]:
        if i not in near_dup and len(good) and i not in good.index and (np.hypot((good.lat - o.lat[i]) * 111, (good.lon - o.lon[i]) * 83) < 1.5).any():
            near_dup.add(i)
o = o.drop(index=list(near_dup)).reset_index(drop=True)
print("after merging duplicate listings:", len(o), "(dropped", len(drop) + sum(dup) + len(near_dup), "; same name within 500 m:", len(near_dup), ")")
confirmed = ((o.src == "meta") & (o.confidence.fillna(0) >= 0.95)) if APP else o.in21
o["tier"] = np.where(o.official, "official", np.where(confirmed, "both", "listing"))

# ---------------------------------------------------------------- licensed places the map listings don't have
# BABLO: active Class A Restaurant, Class A Restaurant/Lounge, Restaurant, Class A Lounge, Tavern and hotel/inn licenses. Lewiston: places
# the city inspected since 2024 whose name says food (schools, clubs, hospitals and theaters aren't restaurants).
FOODWORD = re.compile(r"\b(?:PIZZA|PIZZERIA|APIZZA|RESTAURANT|GRILL|KITCHEN|CAFE|BAKERY|BAKE SHOP|DELI|DINER|BAR|PUB|TAVERN|TACOS?|TAQUERIA|BURGERS?|"
                      r"WINGS|CHICKEN|SUSHI|THAI|CHINA|CHINESE|JERK|PATTY|PATTIES|SEAFOOD|FISH|COFFEE|ESPRESSO|TEA|BISTRO|EATERY|BBQ|BAGELS?|DONUTS?|"
                      r"DUNKIN|SUBWAY|WENDYS|MCDONALDS|BURGER KING|TACO BELL|POPEYES|KFC|DOMINOS|STARBUCKS|PHO|RAMEN|HALAL|GYRO|KEBAB|EMPANADAS?|"
                      r"LOUNGE|CANTINA|TRATTORIA|STEAK|SOUL|CUISINE|FOOD)\b")
NOT_REST = re.compile(r"\b(?:SCHOOL|ACADEMY|ELEMENTARY|MIDDLE|HIGH|COLLEGE|UNIVERSITY|CHURCH|MINISTR\w*|SHELTER|SOUP KITCHEN|PANTRY|HEAD START|"
                      r"CHILD|DAYCARE|NURSING|HOSPITAL|MEDICAL|CENTER$|MARKET|GROCERY|SUPERMARKET|PHARMACY|CVS|WALGREENS|DOLLAR|WALMART|TARGET|"
                      r"STADIUM|PARK -|CONCESSIONS?|THEATRE|THEATER|XFINITY|SALVATION ARMY|YMCA|COMMUNITY|SOCIETY|CORRECTIONAL|DISTRIBUT\w*)\b")
found = set(o.biz.dropna())
add_d = F[(F.jur == "bablo") & F.kind.isin(ON_PREMISE) & ~F.biz.isin(found)].copy()
add_h = F[(F.jur == "lewiston") & ~F.biz.isin(found)].copy()
add_h = add_h[add_h.name.map(norm_name).str.contains(FOODWORD) & ~add_h.name.str.upper().str.contains(NOT_REST)]
# a Lewiston record at the same address as a BABLO license already being added is the same place
add = pd.concat([add_d, add_h])
add["pri"] = add.kind.map({"restaurant": 0, "food": 1, "bar": 2, "hotel": 3})
_ad = {}
for j, (t_, n_, s_, ks) in zip(add.index, zip(add.town, add.num, add.street, add["keys"])):
    if isinstance(n_, str) and isinstance(s_, str):
        _ad.setdefault((t_, n_, s_), []).append((j, ks))
for grp in _ad.values():   # one business under two lists at one address: one row (the BABLO one first)
    for a_ in range(1, len(grp)):
        if any(name_sim(x, y) >= 85 or ((_stems(x) - GENERIC) & (_stems(y) - GENERIC)) for x in grp[0][1] for y in grp[a_][1]):
            add.loc[grp[a_][0], "biz"] = add.loc[grp[0][0], "biz"]
add = add.sort_values("pri").drop_duplicates("biz")
ENTITY = re.compile(r"\b(?:LLC|L\.L\.C|INC|CORP|CORPORATION|LTD|LIMITED|LLP|ENTERPRISES?|HOLDINGS?|GROUP|MANAGEMENT|PARTNERS|ASSOCIATES)\b\.?", re.I)
# a trade name that is only a legal entity ("XYZ HOLDINGS LLC") is never shown: kept only when the rest names food
ent = add.name.str.contains(ENTITY) & ~add.name.map(lambda n: norm_name(ENTITY.sub(" ", n))).str.contains(FOODWORD)
print("license-only records left out because the trade name is a legal entity:", int(ent.sum()), add.name[ent].head(8).tolist())
add = add[~ent]
# ... or plainly another kind of business: not a name to show as a restaurant
OTHER_BIZ = re.compile(r"\b(?:REMODEL\w*|CONSTRUCTION|CONTRACTING|CONTRACTORS?|PLUMBING|ROOFING|LANDSCAP\w*|AUTOMOTIVE|AUTO (?:BODY|REPAIR|SALES)|"
                       r"TIRES?|INSURANCE|REALTY|REAL ESTATE|HAIR|SALON|BARBER\w*|NAILS|CLEANERS|CLEANING|MOVERS|STORAGE|PROPERTIES)\b")
other = add.name.map(norm_name).str.contains(OTHER_BIZ)
print("license-only records left out because the trade name is another business:", int(other.sum()), add.name[other].tolist()[:8])
add = add[~other]
print("licensed places not in the map listings:", len(add), add.kind.value_counts().to_dict())
rows = []
for _, f in add.iterrows():
    rows.append({"id": f.lic, "name": f["name"], "street": f.addr, "city": f.town, "village": f.city if f.city and f.city != f.town else None,
                 "zip": f.zip or None, "lat": f.lat, "lon": f.lon, "cat": "bar" if f.kind == "bar" else "restaurant", "tax": None,
                 "confidence": np.nan, "brand": None, "src": "official", "official": True, "off": f.name, "biz": f.biz, "tier": "official",
                 "in21": False, "closed21": False, "dom": None, "web": None, "phone": None})
A = pd.DataFrame(rows)


def clean_official(n):
    n = re.split(r"\s*;\s*", n or "")[0]
    the = bool(re.search(r"\(THE\)\s*$|,\s*THE\s*$", n, flags=re.I))   # "GREEN LADLE, THE" is "The Green Ladle"
    n = re.sub(r",\s*THE\s*$", "", n, flags=re.I)
    n = re.sub(r"\s*\(THE\)\s*$", "", n, flags=re.I)
    m = re.search(r"\bD/?B/?A\b\.?\s+(.+)$", n, flags=re.I)
    if m:
        n = m.group(1)
    n = re.sub(r"\s*#\s*\d+\w*.*$|\s*\(#?[A-Z]?\d+\)|\s+(?:STORE|UNIT|NO\.?)\s*\d{3,}\s*$", "", n, flags=re.I)
    n = ENTITY.sub("", n)
    n = re.split(r"\s*/\s*", n)[0] if "/" in n else n
    n = re.sub(r"\s+", " ", n).strip(" -,&/.")
    n = nice(n) if n.isupper() or n.islower() else n
    return ("The " + n) if the and n else n


A["name"] = A.name.map(clean_official)
A = A[(A.name.str.len() >= 2) & (A.name.map(norm_name) != "")].reset_index(drop=True)   # a broken trade name ("The") isn't a name
A["k"] = A.name.map(norm_name)
A["st"] = A.k.map(lambda k: _stems(k) - GENERIC if k else set())
A["num"] = A.street.map(lambda a: (re.match(r"\s*(\d+)", a or "") or [None, None])[1])
A["brand_n"] = A.k.map(brand_of)
# Google 2021 listings for the added rows (web only; the ones no map listing took)
taken = set(o.gi.dropna().astype(int))
grid = {}
for i, (la, lo) in enumerate(zip(G.latitude, G.longitude)):
    grid.setdefault((round(la / 0.0015), round(lo / 0.002)), []).append(i)
pairs = []
for ai, r in ([] if APP else A.iterrows()):
    if not r.k:
        continue
    gy, gx = round(r.lat / 0.0015), round(r.lon / 0.002)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for gi in grid.get((gy + dy, gx + dx), []):
                if gi in taken or not G.k.iat[gi] or G.closed21.iat[gi]:
                    continue
                dist = math.hypot((G.latitude.iat[gi] - r.lat) * 111000, (G.longitude.iat[gi] - r.lon) * 83000)
                if dist > 200:
                    continue
                s = name_sim(r.k, G.k.iat[gi])
                same_num = r.num is not None and G.num.iat[gi] == r.num
                if same_num and r.st & G.st.iat[gi]:
                    s = max(s, 80)
                if s < 95 and not r.st & G.st2.iat[gi]:
                    continue
                if (s >= 88 and dist < 150) or (s >= 75 and same_num):
                    pairs.append((s + (10 if same_num else 0) - dist / 25, ai, gi))
A["gi"] = np.nan
ta, tg = set(), set()
for sc, ai, gi in sorted(pairs, key=lambda t: -t[0]):
    if ai in ta or gi in tg:
        continue
    ta.add(ai); tg.add(gi); A.at[ai, "gi"] = gi
A["in21"] = A.gi.notna()
# a licensed place the address match missed can sit on top of its own map listing under a slightly different name: merge it into that
# listing, unless the listing already matched a license of its own (two neighbors are two places)
kgrid = {}
for j, (la, lo) in enumerate(zip(o.lat, o.lon)):
    kgrid.setdefault((round(la / 0.0015), round(lo / 0.002)), []).append(j)
merge, same_lic = {}, set()
for ai, r in A.iterrows():
    if not r.k:
        continue
    best, bs = None, -1
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for j in kgrid.get((round(r.lat / 0.0015) + dy, round(r.lon / 0.002) + dx), []):
                if j in merge.values():
                    continue
                dist = math.hypot((o.lat.iat[j] - r.lat) * 111000, (o.lon.iat[j] - r.lon) * 83000)
                s = name_sim(r.k, o.k.iat[j]) if o.k.iat[j] else 0
                if o.official.iat[j]:   # a listing with its own license: only the same business's second license
                    if dist <= 80 and s >= 95:
                        same_lic.add(ai)
                    continue
                shared = bool(r.st & o.st.iat[j]) or _close_words(r.st, o.st.iat[j])
                nested = len(r.k.split()) >= 2 and o.k.iat[j] and (set(r.k.split()) <= set(o.k.iat[j].split()) or set(o.k.iat[j].split()) <= set(r.k.split()))
                if (dist <= 60 and (s >= 88 or (shared and s >= 60) or nested)) or (dist <= 25 and s >= 75):
                    if s - dist / 10 > bs:
                        best, bs = j, s - dist / 10
    if best is not None:
        merge[ai] = best
for ai, j in merge.items():
    for c in ("official", "off", "biz", "tier"):
        o.at[o.index[j], c] = A.at[ai, c]
A = A.drop(index=list(set(merge) | same_lic)).reset_index(drop=True)
print("license rows merged into a map listing on the second pass:", len(merge), "| second licenses:", len(same_lic - set(merge)), "| license rows added:", len(A))
o = pd.concat([o, A], ignore_index=True)

# ---------------------------------------------------------------- hand-checked places the map listings don't have as a place to eat
import duckdb
OV = duckdb.connect().execute(f"""SELECT name, street, city, zip, lat, lon, cat, tax, web FROM '{ME}/overture_me_bbox.parquet'
                                  WHERE region = 'ME' AND name IS NOT NULL""").df()
OV["k"] = OV.name.map(norm_name)
_m = curated_matcher(o)
missing = [c for c in CUR if not c.get("chain") and _m(c) is None]
added, not_placed = [], []
for c in missing:
    keys = {norm_name(m) for m in (c.get("match_names") or [])} or {norm_name(c["name"])}
    spot = None
    near = OV  # any-category Overture listing of the business (an inn, a farm stand, a wharf shack) in the same area
    g = official.geocode(c.get("address") or "", c.get("city"), (c.get("zip") or "")[:5] or None)
    if g:
        spot = (g[0], g[1])
        cand = OV[(np.abs(OV.lat - g[0]) < 0.004) & (np.abs(OV.lon - g[1]) < 0.005)]
        sims = [max(fuzz.ratio(m, k) for m in keys) if isinstance(k, str) and k else 0 for k in cand.k]
        if len(sims) and max(sims) >= 85:
            h = cand.iloc[int(np.argmax(sims))]
            spot = (h.lat, h.lon)
    if spot is None:   # no address point: Overture's own listing of the place (any category) in the same town, by name
        town_l = {(c.get("city") or "").lower(), (c.get("village") or "").lower()} - {""}
        cand = OV[OV.city.fillna("").str.lower().isin(town_l)]
        sims = [max(fuzz.ratio(m, k) for m in keys) if isinstance(k, str) and k else 0 for k in cand.k]
        if len(sims) and max(sims) >= 88:
            h = cand.iloc[int(np.argmax(sims))]
            spot = (h.lat, h.lon)
    if spot is None:
        not_placed.append(c["name"]); continue
    added.append({"id": "research-" + c["name"], "name": c["name"], "street": c.get("address"), "city": c.get("city"), "village": c.get("village"),
                  "zip": c.get("zip"), "lat": spot[0], "lon": spot[1], "cat": "restaurant", "tax": None, "confidence": np.nan, "brand": None,
                  "src": "research", "official": False, "off": np.nan, "biz": np.nan, "tier": "both", "in21": False, "closed21": False,
                  "dom": None, "gi": np.nan, "k": norm_name(c["name"]), "st": _stems(norm_name(c["name"])) - GENERIC,
                  "num": (re.match(r"\s*(\d+)", c.get("address") or "") or [None, None])[1], "brand_n": None, "web": c.get("website")})
if added:
    o = pd.concat([o, pd.DataFrame(added)], ignore_index=True)
print("hand-checked places added (not in the map listings as a place to eat):", len(added), "| not placed:", not_placed)
# town from the point for every added row (license records give a mailing city)
TF = json.load(open(f"{ME}/me_towns.geojson"))["features"]
TP = [(f["properties"]["town"], prep(shape(f["geometry"])), shape(f["geometry"])) for f in TF]


def town_at(x, y):
    pt = Point(x, y)
    for n, pg, g in TP:
        if pg.contains(pt):
            return n
    d, n = min((g.distance(pt), n) for n, pg, g in TP)
    return n if d < 0.015 else None


fix = o.src.isin(["official", "research"]) & o.lat.notna()
o.loc[fix, "city"] = [town_at(x, y) or c for x, y, c in zip(o.loc[fix, "lon"], o.loc[fix, "lat"], o.loc[fix, "city"])]
o["village"] = o.get("village", pd.Series(None, index=o.index))
# a village is a real village name: not one of the 529 towns (a neighbor's mailing name) and not a typo of its own town
TOWN_SET = {n for n, _, _ in TP}
def real_village(v, town):
    if not isinstance(v, str) or not v.strip() or v in TOWN_SET:
        return None
    # township and plantation codes aren't what anyone calls a place ("Edmunds TWP", "T7 R9 NWP", "The Forks PLT")
    if re.search(r"\b(?:TWP|PLT|Township|Plantation|Grant|Gore|Strip|Purchase)\b|\bT\d+\s*R\d+", v, re.I):
        return None
    if isinstance(town, str) and (fuzz.ratio(v.lower(), town.lower()) >= 85 or town.lower().startswith(v.lower())):
        return None
    return v
o["village"] = [real_village(v, t) for v, t in zip(o.village, o.city)]

# ---------------------------------------------------------------- fields
gi = [int(v) if v == v and v is not None else None for v in o.gi]
o["rating"] = [G.avg_rating.iat[i] if i is not None else np.nan for i in gi]
o["reviews"] = [G.num_of_reviews.iat[i] if i is not None else np.nan for i in gi]
o["gprice"] = [len(G.price.iat[i]) if i is not None and isinstance(G.price.iat[i], str) else np.nan for i in gi]
o["gcats"] = ["|".join(G.category.iat[i] or []) if i is not None else "" for i in gi]
o["gmap_id"] = [G.gmap_id.iat[i] if i is not None else None for i in gi]
o["name_out"] = [b if isinstance(b, str) and fuzz.ratio(norm_name(n), norm_name(b)) >= 88 else nice(n) if n.isupper() or n.islower() else n
                 for n, b in zip(o.name, o.brand_n)]


def pick_cuisine(tax, k, gcats, raw):
    for c, pat in CUISINE_RULES[:-1]:          # a specific word in the name wins ("Flo's Hot Dogs", "Amato's Italian Sandwiches")
        if pat.search(k or ""):
            return c
    if isinstance(tax, str) and tax in TAX_CUISINE:
        return TAX_CUISINE[tax]
    c = cuisine(k, gcats, raw)                 # "bar"-type names, then Google's categories
    if c == "Coffee & Café" and isinstance(tax, str) and tax.endswith("restaurant") and not re.search(r"COFFEE|ESPRESSO|TEA|ROAST", k or ""):
        return "American & Other"              # "Hard Rock Cafe" and "Cristy's Restaurant" are restaurants, not coffee shops
    return c


o["cuisine"] = [pick_cuisine(t, k, gc, n) for t, k, gc, n in zip(o.tax, o.k, o.gcats, o.name)]
first_cat = o.gcats.str.split("|").str[0].fillna("")
cafe_tax = o.tax.isin(["cafe", "coffee_shop"]) & o.cuisine.eq("Coffee & Café") & first_cat.ne("") & ~first_cat.str.contains(r"Coffee|Cafe|Café|Espresso|Tea|Bakery|Donut|Dessert|Ice cream|Juice|Breakfast")
o.loc[cafe_tax, "cuisine"] = [cuisine(k, g, "") for k, g in zip(o.loc[cafe_tax, "k"], o.loc[cafe_tax, "gcats"])]
o.loc[o.cat.isin(["bar", "brewery"]) & (o.cuisine == "American & Other"), "cuisine"] = "Bar & Pub"
o.loc[o.cat.isin(["coffee_shop", "cafe"]) & (o.cuisine == "American & Other"), "cuisine"] = "Coffee & Café"
o.loc[o.city.fillna("") == "", "city"] = None


# brand sanity: a brand rule that matched a name prefix must agree with the listing's website, Overture's brand feed, or its kind of food
def mode(x):
    return x.mode().iat[0]


bdom = {}
for b, grp in o[o.brand_n.notna()].groupby("brand_n"):
    d = grp.dom.dropna()
    if len(d) >= 3:
        top, n = collections.Counter(d).most_common(1)[0]
        if n >= 0.5 * len(d):
            bdom[b] = top
FAMILY = {"Chicken & Wings": "quick", "Burgers": "quick", "Hot Dogs": "quick", "Sandwiches & Deli": "cafe", "Pizza": "pizza",
          "Mexican": "mex", "Latin & Caribbean": "mex", "Coffee & Café": "cafe", "Bakery & Sweets": "cafe",
          "Breakfast & Diner": "cafe", "Healthy & Vegan": "cafe", "Steakhouse": "sitdown", "Seafood": "sea",
          "Bar & Pub": "bar", "Italian": "italian", "Chinese": "asian", "Japanese & Sushi": "asian", "Thai": "asian", "Korean": "asian",
          "Vietnamese": "asian", "South Asian": "sasian", "Mediterranean & Middle Eastern": "med", "European": "sitdown", "BBQ": "bbq",
          "Soul & Southern": "soul", "African": "african"}
brand_cuisine = o[o.brand_n.notna()].groupby("brand_n").cuisine.agg(mode)


def core(k):
    w = [x for x in k.split() if x not in GENERIC and x not in ("RESTAURANT", "RESTAURANTS", "CAFE", "STORE")]
    return " ".join(w) or k


def brand_rest_generic(name, b):
    """The name is the brand plus only generic words, town names or a store number ("Dunkin' Southington", "Subway #1234")."""
    nk, bk = norm_name(name), norm_name(b)
    if not bk or not (nk == bk or nk.startswith(bk + " ")):
        return False
    rest = set(nk[len(bk):].split()) - GENERIC - TOWNWORDS - {"RESTAURANT", "RESTAURANTS", "CAFE", "STORE", "SUBS", "BAGELS", "DONUTS",
                                                               "DRIVE", "THRU", "INSIDE", "AND", "LOCATION", "OUTLET", "MALL"}
    return not rest


def brand_ok(b, dm, cu, tax, obrand, name, src):
    if not isinstance(b, str):
        return None
    dm = dm if isinstance(dm, str) else None
    nk, bk = norm_name(name), norm_name(b)
    if src not in ("AllThePlaces", "DAC") and brand_of(nk) != b:
        return None                                 # only Overture's label says so
    ob = norm_name(obrand) if isinstance(obrand, str) else ""
    brand_feed = src in ("AllThePlaces", "DAC")
    label = bool(ob) and fuzz.token_set_ratio(ob, bk) >= 80
    related = brand_feed or fuzz.partial_ratio(bk, nk) >= 60 or (label and fuzz.partial_ratio(ob, nk) >= 60)
    if not related:
        return None
    squashed = re.sub(r"[^a-z]", "", b.lower())
    own_site = dm and (bdom.get(b) == dm or dm.split(".")[0].replace("-", "") in (squashed, squashed + "s"))
    want = brand_cuisine.get(b)
    other_food = isinstance(tax, str) and tax in TAX_CUISINE and want and FAMILY.get(cu) and FAMILY.get(want) and FAMILY[cu] != FAMILY[want]
    if own_site or (label and brand_feed):
        return b
    if other_food:   # a pizzeria named "Five Guys Flippin' Pies" isn't the burger chain, whatever its name starts with
        return None
    exact = fuzz.ratio(core(nk), core(bk)) >= 90 or (label and fuzz.ratio(core(nk), core(ob)) >= 90) \
        or (len(bk) >= 6 and brand_rest_generic(name, b))
    if exact:
        return b
    if dm and b in bdom and src != "BrightQuery":
        return None
    if src not in ("AllThePlaces", "DAC") and not label and not brand_rest_generic(name, b):
        return None   # only the name's first words say so, and the rest is its own ("Casey's Irish Pub")
    return b


old_brand = o.brand_n.copy()
o["brand_n"] = [brand_ok(b, dm, cu, t, ob, n, sr) for b, dm, cu, t, ob, n, sr in zip(o.brand_n, o.dom, o.cuisine, o.tax, o.brand, o.name, o.src)]
rej = o[old_brand.notna() & o.brand_n.isna()]
print("brand matches rejected:", len(rej), collections.Counter(old_brand[rej.index]).most_common(10))
o.loc[o.brand_n.notna(), "name_out"] = [b if fuzz.ratio(norm_name(n), norm_name(b)) >= 80 or brand_rest_generic(n, b) else n
                                        for n, b in zip(o.loc[o.brand_n.notna(), "name_out"], o.loc[o.brand_n.notna(), "brand_n"])]


def chain_mode(x):
    real = x[x != "American & Other"]
    return (real if len(real) else x).mode().iat[0]


CHAIN_CUISINE = {"Amato's": "Sandwiches & Deli", "Pat's Pizza": "Pizza", "Otto Pizza": "Pizza", "Portland Pie Co.": "Pizza",
                 "Gritty McDuff's": "Bar & Pub", "Sea Dog Brewing": "Bar & Pub", "The Holy Donut": "Bakery & Sweets",
                 "Moe's Italian Sandwiches": "Sandwiches & Deli", "Flatbread Company": "Pizza", "Mr. Bagel": "Bakery & Sweets",
                 "Anania's": "Sandwiches & Deli", "Bissell Brothers": "Bar & Pub", "Cousins Maine Lobster": "Seafood",
                 "Luke's Lobster": "Seafood", "Bob's Clam Hut": "Seafood", "Friendly's": "American & Other",
                 "Bertucci's": "Italian", "Papa Gino's": "Pizza", "D'Angelo": "Sandwiches & Deli", "Moe's Southwest Grill": "Mexican",
                 "99 Restaurant": "American & Other", "Ninety Nine": "American & Other", "Max Burger": "Burgers", "Rizzuto's": "Italian",
                 "Dunkin'": "Coffee & Café", "Starbucks": "Coffee & Café", "Tim Hortons": "Coffee & Café", "Honey Dew Donuts": "Coffee & Café",
                 "Dairy Queen": "Bakery & Sweets", "Cold Stone Creamery": "Bakery & Sweets", "Baskin-Robbins": "Bakery & Sweets",
                 "Carvel": "Bakery & Sweets", "Rita's": "Bakery & Sweets", "Ben & Jerry's": "Bakery & Sweets", "Panera Bread": "Sandwiches & Deli",
                 "Einstein Bros. Bagels": "Bakery & Sweets", "Bruegger's": "Bakery & Sweets", "Texas Roadhouse": "Steakhouse",
                 "Tropical Smoothie Cafe": "Healthy & Vegan", "Smoothie King": "Healthy & Vegan", "Sweetgreen": "Healthy & Vegan",
                 "Shake Shack": "Burgers", "Five Guys": "Burgers", "Cracker Barrel": "American & Other", "Golden Corral": "American & Other",
                 "Nathan's Famous": "Hot Dogs", "Bareburger": "Burgers", "Little Pub": "Bar & Pub", "Bonefish Grill": "Seafood",
                 "Carrabba's": "Italian", "J. Timothy's": "Bar & Pub", "City Steam Brewery": "Bar & Pub"}
allc = o.loc[o.brand_n.notna(), ["brand_n", "cuisine"]]
all_brand_cuisine = allc.groupby("brand_n").cuisine.agg(chain_mode)
o.loc[o.brand_n.notna(), "cuisine"] = o.loc[o.brand_n.notna(), "brand_n"].map(lambda b: CHAIN_CUISINE.get(b) or all_brand_cuisine.get(b))

# price: Google price level, else the chain's usual level, else the cuisine's usual level (both from Maine's own Google data)
o["price"] = o.gprice
o["price_est"] = o.price.isna().astype(int)
bp = o[o.gprice.notna()].groupby("brand_n").gprice.median()
o.loc[o.price.isna() & o.brand_n.notna(), "price"] = o.brand_n.map(bp)
cp = o[o.gprice.notna()].groupby("cuisine").gprice.median()
o.loc[o.price.isna(), "price"] = o.cuisine.map(cp)
o["price"] = o.price.fillna(2).round().clip(1, 4).astype(int)

# chain size statewide. Unbranded same-name places count as one chain only when they share a website
bc = o.brand_n.value_counts()
o["chain_n"] = o.brand_n.map(lambda b: int(bc.get(b, 0)) if isinstance(b, str) else 1)
STORE_DOMS_ALL = {"cumberlandfarms.com", "hannaford.com", "shawsonline.com", "shaws.com", "marketbasket.com", "demoulasmarketbasket.com",
                  "walmart.com", "target.com", "costco.com", "bjs.com", "wholefoodsmarket.com", "traderjoes.com", "irvingoil.com",
                  "circlek.com", "bigapplefood.com", "7-eleven.com", "cvs.com", "walgreens.com", "riteaid.com", "renys.com", "dollargeneral.com"}
first_stem = o.k.fillna("").map(lambda k: next((w for w in k.split() if w not in GENERIC and len(w) >= 3), None))
grpkey = pd.Series([(d, s) if isinstance(d, str) and isinstance(s, str) and not isinstance(b, str) and d not in STORE_DOMS_ALL else None
                    for d, s, b in zip(o.dom, first_stem, o.brand_n)], index=o.index)
gsize = grpkey.dropna().value_counts()
member = [g is not None and gsize.get(g, 0) >= 2 for g in grpkey]
o.loc[member, "chain_n"] = [int(gsize[g]) for g, m in zip(grpkey, member) if m]
o["ckey"] = grpkey.map(lambda g: "|".join(g) if g else None)
chain_dom = set(o.ckey[member])
grp_cuisine = o[member].groupby("ckey").cuisine.agg(chain_mode)
o.loc[member, "cuisine"] = [grp_cuisine.get(k) for k in o.loc[member, "ckey"]]
sib = o.gprice.notna()
for key, sel in (("brand_n", o.brand_n.notna()), ("ckey", pd.Series(member, index=o.index))):
    med = o[sel & sib].groupby(key).gprice.median()
    fill = sel & (o.price_est == 1) & o[key].isin(med.index)
    o.loc[fill, "price"] = o.loc[fill, key].map(med).round().clip(1, 4).astype(int)
print("name-based chains:", len(chain_dom), "|", int(sum(member)), "locations")

o["bar"] = o.cat.isin(["bar", "brewery"]) | (o.cuisine == "Bar & Pub")
o["name_out"] = o.name_out.map(lambda n: re.sub(r"\b(?:Tcby|Ihop|Bj's|Bjs)\b", lambda m: {"tcby": "TCBY", "ihop": "IHOP"}.get(m.group(0).lower(), "BJ's"), n))
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]+")
CJK = r"[぀-ヿ㐀-鿿가-힯豈-﫿＀-￯]"
TAILWORDS = re.compile(r"^(?:best|award|voted|magazine|official|order|delivery|takeout|take out|catering|now open|open|to go|curbside|franchise|inside .*|"
                       r"drive thru.*|drive-thru.*|walk-up window|"
                       r"(?:(?:ice cream|chocolates?|fudge|coffee|cafe|café|restaurant|bar|grill|pizza|apizza|shawarma|hookah lounge|seafood|lobster rolls?|"
                       r"bakery|deli|sandwiches|grinders|tacos|gifts?|shopping|treats|sweets|full bar|food|game room|drinks|spirits|live music|events|patio|"
                       r"lodging|rooms|resort|motel|cocktails|beer|wine|burgers|wings|craft beer|sports bar|and|&|,|-|\s)+))$", re.I)


def tidy(n, brand):
    """Emoji and non-Latin duplicates of an English name, LLC in the middle, marketing tails, notes in parentheses."""
    n = unicodedata.normalize("NFKC", n)
    if re.search(r"[ÃÂâð][\u0080-¿ŒœŠšŸŽžƒˆ˜–-›€™]", n):
        for enc in ("cp1252", "latin-1"):   # UTF-8 read as Windows-1252
            try:
                n = n.encode(enc).decode("utf-8"); break
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
    n = re.sub(r"[®™©]", "", EMOJI.sub("", n))
    if re.search(r"[A-Za-z]{3,}", re.sub(CJK, "", n)):
        n = re.sub(r"\s*\([^()]*" + CJK + r"[^()]*\)", "", n)
    latin = re.sub(CJK + "+", " ", n)
    if re.search(r"[A-Za-z]{3,}", latin) and re.search(CJK, n):
        n = re.sub(r"\(\s*\)", "", latin)
    m = re.match(r"^(.*?)[,\s]+(?:LLC|Inc)\.?\s*-{1,2}\s*(.+)$", n, flags=re.I)
    if m:
        n = m.group(2) if len(m.group(2).split()) >= 2 and len(m.group(1).split()) <= 2 else m.group(1)
    n = re.sub(r"[,\s]+(?:LLC|L\.L\.C|LLP|L\.L\.P|Inc|Corp)\.?(?=\s|$|,)", "", n, flags=re.I)
    n = re.sub(r"\s*\([^()]*\)\s*$", "", n) if re.sub(r"\s*\([^()]*\)\s*$", "", n).strip() else n
    n = re.sub(r",\s*(?:ME|Maine)\s*$", "", n)
    parts = re.split(r"\s+[-–]{1,2}\s+|--", n)
    if len(parts) > 1:
        tail = " ".join(parts[1:])
        if TAILWORDS.match(tail.strip()) or re.search(r"\b(?:Best|Award|Magazine|Voted|20\d\d)\b", tail):
            n = parts[0]
    if isinstance(brand, str):
        n = re.sub(r"\s*#\s*\d+\s*$", "", n)
    n = re.sub(r"[`·•○●◦]+", " ", n)
    n = re.sub(r"\s+", " ", n).strip(" -–,.") or n
    return nice(n) if n.isupper() and len(n) > 4 else n


o["name_out"] = [tidy(n, b) for n, b in zip(o.name_out, o.brand_n)]
o["name_out"] = o.name_out.str.replace(r"(?i)\s+(?:at|@)\s+(?:the\s+)?(?:hollywood casino|oxford casino)\b.*$", "", regex=True)
entity_name = o.name_out.str.contains(r"(?i)\b(?:enterprises?|holdings?|management|associates|partners|llc|inc|corp)\.?\s*$", regex=True)
print("legal-entity names dropped:", int(entity_name.sum()), o.name_out[entity_name].tolist()[:10])
o = o[~entity_name].reset_index(drop=True)
o.loc[o.brand_n.notna(), "name_out"] = [b if brand_rest_generic(n, b) and len(norm_name(b)) >= 3 else n
                                        for n, b in zip(o.loc[o.brand_n.notna(), "name_out"], o.loc[o.brand_n.notna(), "brand_n"])]
o["spell"] = o.name_out.map(lambda n: re.sub(r"[^a-z0-9]", "", n.lower()))
o["name_out"] = o.groupby("spell").name_out.transform(lambda s: s.mode().iat[0] if len(s) > 1 else s.iat[0])
# names that aren't a business: a street address, "closed", a town or "Town of X", a lone generic word, no Latin letters
towns_l = set(o.city.dropna().str.lower()) | set(o.village.dropna().str.lower())
nm = o.name_out.fillna("")
junk = (nm.str.match(r"(?i)^\d+\s+(?:[NSEW]\.?\s+)?[\w.' ]+?\b(?:St|Street|Ave|Avenue|Dr|Drive|Rd|Road|Blvd|Ln|Lane|Way|Ct|Pl|Hwy|Pkwy|Trl|Tpke|Turnpike)\b\.?(?:\s*#\s*\w+)?(?:\s*,.*)?$")
        | nm.str.contains(r"(?i)(?:\bclosed|\bretired)\s*\)?\s*$") | (nm.str.lower().str.strip().isin(towns_l) & o.brand_n.isna())
        | nm.str.match(r"(?i)^(?:city|town|borough) of ") | nm.str.strip().str.lower().isin(["kitchen", "bar", "pub", "tavern", "grill", "deli", "pizza", "bakery", "coffee", "diner", "restaurant", "cafe", "café"])
        | ~nm.str.contains(r"[A-Za-z]")
        | nm.str.contains(r"\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}") | nm.str.contains(r"_") | nm.str.contains(r"@.*!!|!!!")
        | nm.str.contains(r"(?i)\w(?:llc|inc)$") | nm.str.contains(r"(?i)\b(?:information|incorporated)\b"))
print("junk names dropped:", int(junk.sum()), nm[junk].head(12).tolist())
o = o[~junk].reset_index(drop=True)

# ---------------------------------------------------------------- not restaurants (hidden unless "include non-restaurants" is on)
STORE = re.compile(r"^(?:CUMBERLAND FARMS|IRVING(?: OIL| MAINWAY)?|CIRCLE K|BIG APPLE(?: FOOD STORE)?|MOBIL|SHELL|SUNOCO|GULF|CITGO|VALERO|BP|EXXON|"
                   r"SPEEDWAY|7 ELEVEN|DEAD RIVER|HANNAFORD(?: SUPERMARKET)?|SHAWS|MARKET BASKET|WALMART\b.*|COSTCO\b.*|TARGET|"
                   r"BJS WHOLESALE.*|WHOLE FOODS(?: MARKET)?|TRADER JOES|ALDI|RENYS|CVS|WALGREENS|RITE AID|DOLLAR \w+|"
                   r"DASHMART|GOPUFF)$|\b(?:ZENSHI|SUSHI WITH GUSTO|HISSHO SUSHI|AFC SUSHI|SNOWFOX)\b|\b(?:GAS STATION|TRAVEL (?:CENTER|PLAZA)|TRUCK STOP|SERVICE PLAZA|PACKAGE STORE|LIQUORS? (?:STORE|SHOPPE?|OUTLET)|"
                   r"WINE (?:MERCHANTS?|SHOP|STORE|OUTLET)|WINE SPIRITS|LIQUORS? SPIRITS|VENDING|COMMISSARY|FOOD PANTRY|MEAT MARKET|BUTCHER|"
                   r"GHOST KITCHEN|VIRTUAL KITCHEN|MRBEAST|MR BEAST|ITS JUST WINGS|WOW BAO|GENTLEM[AE]NS CLUB|TRAMPOLINE|INDOOR PLAYGROUND|"
                   r"LINDT|ROCKY MOUNTAIN CHOCOLATE|JELLY BELLY)\b")
REALFOOD = re.compile(r"\b(?:RESTAURANT|GRILL|BAR|PUB|TAVERN|PIZZA|APIZZA|CAFE|KITCHEN|STEAK|BISTRO|DINER|BREWING|BREWERY|TAP|SALOON|"
                      r"TAPROOM|LOUNGE|INN RESTAURANT|EATERY|BURGERS?|BBQ|TACOS?|DRIVE IN|DELI|COFFEE|ICE CREAM|CREAMERY|BAKERY|DAIRY|SEAFOOD|LOBSTER|CLAM|DONUTS?)\b")
CANDY = re.compile(r"\b(?:CANDY|CANDIES|FUDGE|POPCORN|CONFECTION\w*|CHOCOLATES?|CHOCOLATIER|TRUFFLES?|SWEETS? SHOPPE?|KETTLE CORN|NUTRITION)\b")
HARD = re.compile(r"\b(?:AIRPORT|TERMINAL|CONCOURSE|GATE [A-Z]?\d+|JETPORT|CROSS INSURANCE (?:ARENA|CENTER)|HADLOCK FIELD|"
                  r"LEVY|SODEXO|ARAMARK|DELAWARE NORTH|CENTERPLATE|COMPASS GROUP|CHARTWELLS|BON APPETIT|HMSHOST|EUREST|GUCKENHEIMER|SSP AMERICA|"
                  r"COMMISSARY|DINING HALL|UNIVERSITY DINING|BOWDOIN DINING|BATES DINING|COLBY DINING|CORRECTIONAL|PRISON|CAREERS|TRUCK ENTRANCE)\b")
SOFT = re.compile(r"\b(?:STADIUM|ARENA|FESTIVAL|CONCESSIONS?|FOOD ?SERVICES?|UNIVERSITY|COLLEGE|SCHOOL|ACADEMY|ELEMENTARY|STUDENT|CAMPUS|"
                  r"HOSPITAL|MEDICAL CENTER|CLINIC|HEALTH CENTER|SENIOR|RETIREMENT|ASSISTED LIVING|NURSING|CARE CENTER|REHAB|CHURCH|PARISH|"
                  r"CONGREGATION|TEMPLE|SYNAGOGUE|MOSQUE|MINISTR(?:Y|IES)|VFW|AMERICAN LEGION|AMVETS|FRATERNAL ORDER|ELKS LODGE|"
                  r"MOOSE LODGE|KNIGHTS COLUMBUS|COUNTRY CLUB|GOLF CLUB|GOLF COURSE|YACHT CLUB|ATHLETIC CLUB|SOCIAL CLUB|BEACH CLUB|"
                  r"SPORTSMEN'?S CLUB|ROD GUN|FISH GAME|CATERING|CATERERS?|BANQUETS?|BANQUET HALL|EVENT (?:CENTER|VENUE|SPACE)|"
                  r"CONVENTION CENTER|CONFERENCE CENTER|MUSEUM|ZOO|AQUARIUM|THEATER|THEATRE|CINEMAS?|BOWLING|LANES|"
                  r"HOTEL|MOTEL|INN SUITES|SUITES|MARRIOTT|HILTON|HYATT|SHERATON|WESTIN|HOLIDAY INN|HAMPTON INN|FAIRFIELD INN|RESIDENCE INN|"
                  r"COURTYARD|SPRINGHILL|RADISSON|BEST WESTERN|COMFORT INN|SUPER 8|RED ROOF|DAYS INN|GREAT WOLF|"
                  r"CORPORATE|EMPLOYEE|CAFETERIA|MOBILE|FOOD TRUCK|KIOSK|GYM|FITNESS|YMCA|YWCA|BOYS GIRLS CLUB|DAYCARE|DAY CARE|CHILD CARE|"
                  r"CHILDCARE|LEARNING CENTER|JAIL|MILITARY|NATIONAL GUARD|NAVAL SHIPYARD|BATH IRON WORKS|BUILDING)\b")
kd = o.name_out.map(norm_name).fillna("")
k_ = o.k.fillna("")
busy = o.reviews.fillna(0) >= 200
gfirst = o.gcats.fillna("").str.split("|").str[0]
plainly_food = kd.str.contains(REALFOOD) | o.cat.isin(["bar", "brewery", "coffee_shop", "cafe"]) \
    | gfirst.str.contains(r"\b(?:Bar|Pub|Restaurant|Cafe|Café|Coffee|Tavern|Grill|Brewery|Diner|Bakery)\b", regex=True)
brand_store = o.brand_n.isin(["Cumberland Farms", "Hannaford", "Irving", "Circle K", "Big Apple", "Rite Aid", "Walmart",
                              "Whole Foods Market", "Trader Joe's", "7-Eleven", "Stop & Shop", "Price Chopper"])
store = kd.str.contains(STORE) | brand_store | (o.dom.isin(STORE_DOMS_ALL) & ~plainly_food) \
    | (kd.str.contains(CANDY) & ~kd.str.contains(REALFOOD) & ~busy)
venue = kd.str.contains(HARD) | k_.str.contains(HARD) | o.name.fillna("").str.upper().str.contains(r"\(T-?\d|\bGATE [A-Z]?\d", regex=True) \
    | (kd.str.contains(SOFT) & ~(busy | plainly_food))
LICENSE_ONLY_NONREST = re.compile(r"\b(?:CINEMAS?|AMC|CINEPOLIS|THEATERS?|THEATRES?|FEATURES|PICTURE SHOW|CABARET|GOLF|GOL$|BOWLING|LANES|BOWLERO|"
                                  r"AXE|AXES|PICKLEBALL|ARENA|ARCADE|ESCAPOLOGY|ESCAPE ROOMS?|FUN ZONE|CHELSEA PIERS|TENNIS|SPA|PAINTBAR|"
                                  r"WINEMAKING|RAILROAD(?: CO)?$|RAILWAY$|MARINA$|AUTO STOP|WATERMARK|SENIOR|ASSISTED|WOODS$|TELETHEATER|TECHNOLOGIES|"
                                  r"PLAY$|XTREME|SUPERCHARGED|TRAMPOLINE|SKATING|RINK|GARDEN CENTER|GIFT|MUSEUM|"
                                  r"APARTMENTS?|POOLS?|SWIM|AQUATIC|SPORTSM[AE]NS?|GUN CLUB|ASSOCIATION|ATTN|C O|EVENTS?|STUDIOS?|"
                                  r"BOATS|SPORTS CENTER|HOSPITALITY GROUP|KNIGHTS|HEALTH|CONDOMINIUMS?|HOMEOWNERS|NEIGHBORHOOD|COMMUNITY|"
                                  r"PARKS REC|RECREATION|CAMP|BIBLE|FOUNDATION|SOCIETY|COUNCIL|LEAGUE|UNION|INSTITUTE|CENTER$|FARMS?|AMUSEMENT|"
                                  r"ENTERTAINMENT|CORPORATION|HOLDINGS|MANAGEMENT|VENTURES|FIELD|PERFORMING ARTS|VINEYARDS?|WINERY)\b")
lic_only = o.src.eq("official")
# a license-only cafe permit row is filed as a bar, which made it "plainly food": for those, only the name speaks
ku = o.name_out.fillna("").str.upper().str.replace(r"['’`]", "", regex=True).str.replace(r"[^A-Z0-9 ]", " ", regex=True)   # norm_name drops RESTAURANT and CAFE
plainly_food = plainly_food & ~(lic_only & ~ku.str.contains(REALFOOD))
venue = kd.str.contains(HARD) | k_.str.contains(HARD) | o.name.fillna("").str.upper().str.contains(r"\(T-?\d|\bGATE [A-Z]?\d", regex=True) \
    | (kd.str.contains(SOFT) & ~(busy | plainly_food))
lic_cred = o.off.map(lambda j: (F.ptype.iat[int(j)] or "") if j == j else "").fillna("").str.upper()
# private clubs (a club permit) aren't open to the public. A hotel permit with only the hotel's name is a hotel: a chain hotel, a B&B or
# an inn without a dining room (qa/data.md); an independent inn with one keeps it (Copper Beech, Gelston House, Lighthouse Inn). A caterer
# permit is a caterer; a restaurant caterer permit is a restaurant that caters, unless the name is an event hall's.
DINING = r"\b(?:RESTAURANT|TAVERN|DINING|GRILL|GRILLE|BISTRO|KITCHEN|BAR|PUB|STEAKHOUSE|CAFE|PIZZA|PIZZERIA|TAP ?ROOM|LOBSTER|CHOWDER)\b"
HOTEL_ONLY = (r"\b(?:HOTEL|MOTEL|SUITES|MARRIOTT|HILTON|HYATT|SHERATON|WESTIN|WYNDHAM|BAYMONT|DELAMAR|RESIDENCE INN|HAMPTON INN|FAIRFIELD INN|"
              r"HOLIDAY INN|COMFORT INN|DAYS INN|SUPER 8|RED ROOF|BEST WESTERN|QUALITY INN|TOWNEPLACE|HOMEWOOD|AC HOTEL|CAMBRIA|"
              r"MOTOR INN|COTTAGES|CABINS|SPORTING CAMPS?|BED (?:AND )?BREAKFAST|B AND B|GUEST ?HOUSE)\b")
EVENT_HALL = (r"\b(?:BANQUETS?|BALLROOM|EVENTS?|CATERING|CATERERS|LACE FACTORY|BELLA VISTA|VILLA$|CASTLE|FOUR SEASONS|WOODWINDS|WATERVIEW|"
              r"WHISPERING OAKS|REIGN|ON THE WATER|GOODSPEED STATION|SAINT CLEMENTS|ST CLEMENTS|BARNS|MANOR|ESTATE|COUNTRY CLUB|CONFERENCE)\b")
venue |= lic_cred.str.contains("CLUB")
venue |= lic_only & lic_cred.str.contains(r"HOTEL|BED AND BREAKFAST") & ku.str.contains(HOTEL_ONLY) & ~ku.str.contains(DINING)
venue |= lic_only & lic_cred.str.contains("CATERING")
venue |= lic_only & ku.str.contains(EVENT_HALL) & ~ku.str.contains(DINING)
venue |= lic_only & lic_cred.str.contains("LOUNGE") & ku.str.contains(r"\bBOWL$")   # a bowling alley's bar, not "Hungry Bowl"
club = kd.str.contains(r"\bCLUB\b") & ~kd.str.contains(r"NIGHT ?CLUB|CLUB CAR|CLUB SANDWICH|SUPPER CLUB")
venue |= lic_only & (kd.str.contains(LICENSE_ONLY_NONREST) | club) & ~busy
# airports: the Portland International Jetport and Bangor International terminals
for la, lo in ((43.6462, -70.3093), (44.8074, -68.8281)):
    venue |= (np.hypot((o.lat - la) * 111, (o.lon - lo) * 83) < 0.6) & ~busy
# betting lounges (a sportsbook is gaming first) and private member clubs (lodges, fire companies, legion posts) aren't restaurants
# open to the public, whatever their category says
GAMING = re.compile(r"\b(?:SPORTSBOOK|SPORTS BOOK|OFF TRACK|OTB|TELETRACK|BETTING|SLOT|SLOTS|GAMING)\b")
MEMBERS = re.compile(r"\b(?:ELKS|MOOSE|LODGE NO|V ?F ?W|POST \d+|HIBERNIANS?|FORESTERS|BENFICA|VASCO DA GAMA|VETS CLUB|VETERANS (?:CLUB|ASSOCIATION|POST|HALL)|"
                     r"POLISH CLUB|MENS CLUB|WOMENS CLUB|POLYTECHNIC CLUB|UNIVERSITY CLUB|SOCIETA|TURN ?VEREIN|SOKOL|SONS ITALY|POLISH FALCONS|GRANGE (?:HALL|NO)|HOSE CO(?:MPANY)?|FIRE (?:COMPANY|DEPARTMENT|DEPT)|VOLUNTEER FIRE|VFW|AMERICAN LEGION|"
                     r"KNIGHTS COLUMBUS|SONS ITALY|AMVETS|ORDER EAGLES|EAGLES AERIE|POLISH FALCONS|ROD GUN|FISH GAME|"
                     r"SPORTSM[AE]NS|YACHT CLUB|COUNTRY CLUB|GOLF CLUB|BEACH CLUB|SOCIAL CLUB|ATHLETIC CLUB|SWIM CLUB|TENNIS CLUB|EAGLES CLUB|EAGLES|"
                     r"REDEMPTION|"
                     r"FRANCO AMERICAN CLUB|LE CLUB|CERCLE|ST JOHN BAPTISTE|LEGION POST|SNOWMOBILE CLUB)\b")
gaming, members = kd.str.contains(GAMING), kd.str.contains(MEMBERS)
print("betting venues hidden:", int(gaming.sum()), o.name_out[gaming].tolist()[:6], "| member clubs hidden:", int(members.sum()))
HOME_HOSTS = r"bakesy\.shop|castiron\.me|hotplate\.com|cottagefoods|homecook"
home = (o.web.fillna("").str.contains(HOME_HOSTS, case=False, regex=True)
        | o.name_out.fillna("").str.contains(r"(?i)\b(?:sourdough|cakes?|cookies?|treats|bakes|confections) by [A-Z][a-z]+|\bcustom cakes\b|\bhome ?bak", regex=True)
        | (o.name_out.fillna("").str.contains(r"(?i)\b(?:cakes?|cookies?|treats|bakes)\b", regex=True) & ~o.street.fillna("").str.contains(r"\d+\s+[A-Za-z]"))) & ~o.official
print("home bakers hidden:", int(home.sum()), o.name_out[home].tolist()[:8])
home |= o.name_out.fillna("").str.contains(r"(?i)\bdelivery$", regex=True) & ~o.official   # delivery-only brands at a kitchen
o["venue"] = store | venue | gaming | members | home
print("non-restaurants flagged:", int(o.venue.sum()), "| stores:", int(store.sum()), "| venues:", int((venue & ~store).sum()))
# host venues: Maine's two commercial casinos (by address, above)
st_up = o.street.fillna("").str.upper()
o["host"] = None
for name, town_, addr_re, names_ in CASINOS:
    at = (st_up.str.contains(addr_re, regex=True) & o.city.eq(town_)) | o.name_out.fillna("").str.upper().str.contains("|".join(names_))
    o.loc[at & o.host.isna(), "host"] = name
print("restaurants at the casinos:", o.host.value_counts().to_dict())

# ---------------------------------------------------------------- Maine signals from 2021 reviews (web leaderboard only)
SIGS = ["lobster", "clams", "snapper", "italian", "whoopie", "donut", "franco", "oyster", "blueberry", "icecream"]
if not APP and os.path.exists(f"{ME}/review_signals.parquet"):
    sig = pd.read_parquet(f"{ME}/review_signals.parquet").set_index("gmap_id")
    for k in SIGS:
        o["n_" + k] = o.gmap_id.map(sig["n_" + k]).fillna(0).astype(int)
        o["r_" + k] = o.gmap_id.map(sig["r_" + k])
else:
    for k in SIGS:
        o["n_" + k] = 0; o["r_" + k] = np.nan
share = lambda k: o["n_" + k] / o.reviews.clip(lower=1)
nkey = o.name_out.map(norm_name).fillna("")
LOBSTER_NAME = r"\bLOBSTER (?:POUND|SHACK|SHANTY|HUT|PIER|WHARF|DOCK|CO|COMPANY|ROLL|ROLLS)\b|\bLOBSTER$|\bLOBSTERS$"
o["t_lobster"] = nkey.str.contains(LOBSTER_NAME) | ((o.n_lobster >= 3) & (share("lobster") >= 0.05))
o["t_clams"] = nkey.str.contains(r"\bCLAM (?:SHACK|HUT|BAR|SHOP)\b") | ((o.n_clams >= 3) & (share("clams") >= 0.04) & o.cuisine.isin(["Seafood", "American & Other", "Bar & Pub"]))
o["t_hotdog"] = (o.cuisine == "Hot Dogs") | (o.n_snapper >= 2)
o["t_italian"] = nkey.str.contains(r"\bITALIAN SANDWICH") | ((o.n_italian >= 3) & (share("italian") >= 0.05) & o.cuisine.isin(["Sandwiches & Deli", "Pizza", "American & Other"]))
o["t_whoopie"] = nkey.str.contains(r"\bWHOOPIE") | (o.n_whoopie >= 3)
o["t_donut"] = (o.n_donut >= 2) | nkey.str.contains(r"\bPOTATO (?:DONUT|DOUGHNUT)")
o["t_franco"] = nkey.str.contains(r"\bPOUTINE|\bTOURTIERE|\bPLOYES?\b|\bFRANCO") | ((o.n_franco >= 3) & (share("franco") >= 0.04))
o["t_diner"] = nkey.str.contains(r"\bDINER\b")
o["t_oyster"] = nkey.str.contains(r"\bOYSTER (?:BAR|CO|COMPANY|HOUSE)\b|\bRAW BAR\b") | ((o.n_oyster >= 5) & (share("oyster") >= 0.15))
o["t_dairy"] = nkey.str.contains(r"\bDAIRY (?:BAR|BARN|JOY|TWIST|TREAT|DELITE)\b|\bCREAMERY\b") | ((o.n_icecream >= 5) & (share("icecream") >= 0.25) & o.cuisine.eq("Bakery & Sweets") & o.brand_n.isna())
if APP:   # tags in the app come from names and the hand-checked research only, never from reviews
    o["t_lobster"] = nkey.str.contains(LOBSTER_NAME); o["t_clams"] = nkey.str.contains(r"\bCLAM (?:SHACK|HUT|BAR|SHOP)\b")
    o["t_hotdog"] = o.cuisine == "Hot Dogs"; o["t_italian"] = nkey.str.contains(r"\bITALIAN SANDWICH")
    o["t_whoopie"] = nkey.str.contains(r"\bWHOOPIE"); o["t_donut"] = nkey.str.contains(r"\bPOTATO (?:DONUT|DOUGHNUT)")
    o["t_franco"] = nkey.str.contains(r"\bPOUTINE|\bTOURTIERE|\bPLOYES?\b|\bFRANCO"); o["t_oyster"] = nkey.str.contains(r"\bOYSTER (?:BAR|CO|COMPANY|HOUSE)\b|\bRAW BAR\b")
    o["t_dairy"] = nkey.str.contains(r"\bDAIRY (?:BAR|BARN|JOY|TWIST|TREAT|DELITE)\b|\bCREAMERY\b")
print("tags:", {t: int(o["t_" + t].sum()) for t in TAGS})

# ---------------------------------------------------------------- the hand-checked research (data/research), honors
for col in ("jbf", "honors", "icon", "founded", "cur_tags", "dishes", "season", "branch", "rnote", "rsite", "chef", "rsrc", "raddr", "rname"):
    o[col] = None
o["seasonal"] = False
match_curated = curated_matcher(o)
o["hc"] = False   # hand-checked: matched to an open research entry with a 2025-26 source
matched_cur, unmatched = 0, []
for c in CUR:
    best = match_curated(c)
    if best is None:
        unmatched.append(c["name"] + " (" + (c.get("city") or "") + ")")
        continue
    matched_cur += 1
    i = o.index[best]
    o.at[i, "hc"] = True
    for col, vals in (("jbf", c.get("james_beard")), ("honors", c.get("other_honors")), ("cur_tags", c.get("tags")), ("dishes", c.get("dishes"))):
        if vals:
            have = [x for x in (o.at[i, col] or "").split("; ") if x]
            o.at[i, col] = "; ".join(have + [v for v in dict.fromkeys(vals) if v not in have])
    for col, v in (("icon", c.get("iconic_reason")), ("founded", c.get("founded")), ("season", c.get("season")), ("branch", c.get("branch_of")),
                   ("rnote", c.get("note")), ("rsite", c.get("website")), ("chef", c.get("chef")), ("rsrc", (c.get("rsources") or [None])[0]),
                   ("raddr", c.get("address")), ("rname", c.get("name"))):
        if v and not o.at[i, col]:
            o.at[i, col] = v
    if c.get("seasonal"):
        o.at[i, "seasonal"] = True
    if c.get("village") and not isinstance(o.at[i, "village"], str):
        o.at[i, "village"] = c["village"]
print(f"research entries matched: {matched_cur}/{len(CUR)}; unmatched ({len(unmatched)}): {unmatched[:20]}")
closed_v = []
for f in sorted(glob.glob(f"{DATA}/research/closed*.json")):
    try:
        closed_v += [dict(c, city=c.get("town") or c.get("city")) for c in json.load(open(f))]
    except json.JSONDecodeError as e:
        print("!! closed file doesn't parse, skipped:", f, e)
# a closure may give the address the permit and listings use too ("alt_addresses")
closed_v = [dict(c, address=a) for c in closed_v for a in [c.get("address")] + (c.get("alt_addresses") or [])]
# a closure never removes a place the research found open (a new business often takes a closed one's address and part of its name:
# "Look Lobster at Quoddy Bay" replaced Quoddy Bay Lobster at 7 Sea St)
hits = [(c, b) for c in closed_v for b in [match_curated(c)] if b is not None]
kept_open = [(c["name"], o.name_out.iat[b]) for c, b in hits if o.hc.iat[b]]
if kept_open:
    print("closures that matched a hand-checked open place, not removed:", kept_open)
gone = [(c["name"], o.name_out.iat[b]) for c, b in hits if not o.hc.iat[b]]
drop_closed = {o.index[b] for c, b in hits if not o.hc.iat[b]}
o = o.drop(index=list(drop_closed)).reset_index(drop=True)
print("verified closed, removed:", len(drop_closed), gone)
# ---------------------------------------------------------------- Lewiston's posted inspections (the official Pass/Fail, with its date)
# The city posts each inspection it does as "MM/DD/YYYY - Passed/Failed" with the report (official.lewiston()). Shown with its date and
# a link to the report, never as a grade or a board. A result attaches one-to-one, best match first, and needs a strong name match (a
# distinctive word in common, or the same name) in Lewiston: an address alone never carries one business's inspection to a neighbor.
o["lw_r"] = None; o["lw_d"] = None; o["lw_u"] = None; o["lw_n"] = None; o["lw_c"] = None
LW = official.lewiston()
LW_FETCHED = __import__("datetime").date.fromtimestamp(os.path.getmtime(f"{RAW}/official/lewiston/621.html")).isoformat()
g = o[o.city.eq("Lewiston")].assign(kk=o.name_out.map(norm_name))
pairs = []
for ei, e in enumerate(LW):
    last = e["inspections"][-1]
    if last[0] < "2023-01-01":
        continue   # an inspection more than ~2 years old (Maine inspects at least every 24 months) isn't current
    k = norm_name(e["name"]); nums = street_nums(e["addr"]); sk = street_key(e["addr"])[1]
    mine = distinct(k)
    for i, kk, st in zip(g.index, g.kk, g.street):
        if not kk:
            continue
        sim = name_sim(k, kk)
        if not (mine & distinct(kk)) and sim < 90:
            continue
        sk2 = street_key(st)[1]
        same_addr = bool(nums & street_nums(st)) and sk and sk2 and (sk2 == sk or fuzz.ratio(sk2, sk) >= 85)
        far = nums and street_nums(st) and min(abs(int(x) - int(y)) for x in nums for y in street_nums(st)) > 20
        if (same_addr and sim >= 70) or (sim >= 90 and not far):
            pairs.append((sim + (20 if same_addr else 0), ei, i))
taken_lw, used_e = set(), set()
for sc, ei, i in sorted(pairs, key=lambda t: -t[0]):
    if ei in used_e or i in taken_lw:
        continue
    used_e.add(ei); taken_lw.add(i)
    e = LW[ei]; d_, res_, url_ = e["inspections"][-1]
    o.at[i, "lw_r"] = res_; o.at[i, "lw_d"] = d_; o.at[i, "lw_u"] = url_; o.at[i, "lw_n"] = e["name"]; o.at[i, "lw_c"] = len(e["inspections"])
print("Lewiston inspection results matched:", len(used_e), "of", sum(1 for e in LW if e["inspections"][-1][0] >= "2023-01-01"),
      "| latest:", max(e["inspections"][-1][0] for e in LW))
tags_c = o.cur_tags.fillna("").str.lower()
for t, kinds in (("lobster", ["lobster shack", "lobster roll"]), ("clams", ["clam shack"]), ("hotdog", ["red snapper"]),
                 ("italian", ["italian sandwich"]), ("whoopie", ["whoopie pie"]), ("donut", ["potato doughnut"]),
                 ("franco", ["franco american"]), ("diner", ["diner"]), ("oyster", ["oyster bar"]), ("dairy", ["dairy bar"])):
    o["t_" + t] |= tags_c.map(lambda s: any(k in s.split("; ") for k in kinds))
# a hand-checked place the map data files as "American & Other" takes its cuisine from what the research says it is
KIND_CUISINE = [("red snapper", "Hot Dogs"), ("italian sandwich", "Sandwiches & Deli"), ("whoopie pie", "Bakery & Sweets"),
                ("potato doughnut", "Bakery & Sweets"), ("blueberry pie", "Bakery & Sweets"), ("diner", "Breakfast & Diner"),
                ("franco american", "European"), ("oyster bar", "Seafood"), ("lobster shack", "Seafood"), ("lobster roll", "Seafood"),
                ("clam shack", "Seafood"), ("dairy bar", "Bakery & Sweets")]   # the signature first: a hot dog stand that sells lobster rolls
generic = o.hc & o.cuisine.eq("American & Other")
o.loc[generic, "cuisine"] = [next((c for k, c in KIND_CUISINE if k in t.split("; ")), "American & Other") for t in tags_c[generic]]
print("hand-checked places given a cuisine from their research kind:", int((generic & o.cuisine.ne("American & Other")).sum()))
o["t_oldest"] = tags_c.str.contains("oldest")
o["honored"] = o.hc
o.loc[o.honored, "venue"] = False
o["bar"] = o.cat.isin(["bar", "brewery"]) | (o.cuisine == "Bar & Pub")

# ---------------------------------------------------------------- sales / profit: the Chicago model (web leaderboard only)
auv = {a["brand"]: a for a in json.load(open(f"{DATA}/chain_auv.json")) if a.get("auv_usd")}
for mine, theirs in {"Ninety Nine": "99 Restaurant", "Irving": "Circle K"}.items():
    if theirs in auv and mine not in auv:
        auv[mine] = auv[theirs]
med_rev = o[o.reviews.notna() & (o.chain_n < 5)].groupby("price").reviews.median()
rel = (o.reviews + 10) / (o.price.map(med_rev) + 10)
bump = np.where(o.bar, 1.15, 1.0)
o["rev"] = (o.price.map(BASE) * bump * rel.fillna(0.6) ** B_FIT).clip(100_000, 40_000_000)
o["rev_src"] = np.where(o.reviews.notna(), "model", "model-low")
n_auv = 0
for b, a in auv.items():
    sel = o.brand_n == b
    if not sel.any():
        continue
    n_auv += 1
    med = o.loc[sel, "reviews"].median()
    r_ = (o.loc[sel, "reviews"] / med) ** 0.35 if med == med else pd.Series(np.nan, index=o.index[sel])
    o.loc[sel, "rev"] = a["auv_usd"] * r_.fillna(0.85).clip(0.6, 1.5)
    o.loc[sel, "rev_src"] = "chain"
o.loc[o.venue & o.rev_src.isin(["model", "model-low"]), "rev_src"] = "venue"
m_rat = o.rating.mean()
o["bayes"] = (o.reviews * o.rating + 40 * m_rat) / (o.reviews + 40)
margin = o.price.map(MARGIN)
margin = o.cuisine.map(MARGIN_CUISINE).fillna(margin) * (0.8 + 0.4 * pct(o.bayes).fillna(40) / 100)
o["margin"] = margin.round(4)
o["profit"] = o.rev * o.margin
o["food_cost"] = o.cuisine.map(FOOD_COST).fillna(30)
o["value_raw"] = o.bayes - 0.18 * (o.price - 1)
# iconic points (hand-checked places only): honors + history (verified year at this address) + how many people know it
jb = o.jbf.fillna("")
# the best honor counts: a winner, else a nominee (the Foundation's word for a finalist; a "semifinalist" mention doesn't cancel it),
# else a semifinalist
win = jb.str.contains(r"\bwinner\b", case=False); fin = jb.str.contains(r"(?<!semi)finalist|\bnominee", case=False); semi = jb.str.contains("semifinalist", case=False)
acc = (jb.str.contains("America's Classic") * 35 + win * 22 + (fin & ~win) * 12 + (semi & ~fin & ~win) * 5 + o.icon.notna() * 24 + o.honors.notna() * 6).clip(upper=48)
years = (int(GENERATED[:4]) - pd.to_numeric(o.founded, errors="coerce")).clip(lower=0)
o["s_icon"] = np.where(o.honored, (acc + years.fillna(0).clip(upper=80) / 80 * 32 + pct(np.log1p(o.reviews)).fillna(0) / 100 * 20).clip(upper=100), np.nan)


def r(x, n=0):
    if x is None or (isinstance(x, float) and x != x):
        return None
    return int(round(float(x))) if n == 0 else round(float(x), n)


def clean_url(u):
    """Website links without tracking parameters (Reserve with Google tokens, utm_*, click ids)."""
    base, _, q = u.partition("?")
    keep_ = [kv for kv in q.split("&") if kv and not re.match(r"(rwg_token|utm_[a-z]+|fbclid|gclid|y_source|cmpid|cid|ref)=", kv)]
    return base + ("?" + "&".join(keep_) if keep_ else "")


o = o[o.lat.notna()].reset_index(drop=True)
# the license this place's facts come from (shown as "on BABLO's list" with the premises class; never the legal entity)
o["lic_kind"] = o.off.map(lambda j: (F.cls.iat[int(j)] or F.ptype.iat[int(j)]) if j == j else None)
o["lic_jur"] = o.off.map(lambda j: F.jur.iat[int(j)] if j == j else None)
o["lic_since"] = None   # BABLO's "Initial Issue Date" is the current term's start, not an opening date
o["lic"] = o.off.map(lambda j: F.lic.iat[int(j)] if j == j else None)
o["hfd_cls"] = None
o["seats"] = None
# the address shown: a license address only when it starts with a street number
def clean_street(a):
    """'Bank of X, 406 Main St' -> '406 Main St'; '1902 Post Rd 1902 Post Rd' -> '1902 Post Rd'; '5 Elm St, ME 04101' ->
    '5 Elm St'. Anything that isn't a street address (a town, "All Over Town!") -> None. "10 Maine St" (Brunswick) stays."""
    if not isinstance(a, str):
        return None
    a = re.sub(r"^[^\d,]{2,60},\s*(?=\d)", "", a.strip())
    m = re.match(r"^(\d+)\s+(.+?)\s+\1\b", a)   # the address twice, or two addresses run together: the first
    if m:
        a = f"{m.group(1)} {m.group(2)}"
    # a state after a comma or with a zip ("10 Maine St" is Brunswick's main street)
    a = re.sub(r"(?:,\s*(?:ME|Maine)(?:\s+0\d{4})?|\s+ME\s+0\d{4})\s*$", "", a, flags=re.I)
    a = re.sub(r"\b(.{3,40}?)\s+\1$", r"\1", a, flags=re.I)   # "Earth Concourse Earth Concourse"
    a = a.strip(" ,")
    return a if re.match(r"\s*\d+[A-Za-z]?(?:\s*-\s*(?:\d+[A-Za-z]?|[A-Za-z]))?,?\s+\S", a) else None


o["street"] = o.street.map(clean_street)
o["street"] = o.street.map(lambda a: re.sub(r"\bUS RTE\b|\bUS Rte\b", "US Route", a) if isinstance(a, str) else a)
# the town's own name after the street type ("200 Church Street Wallingford")
TYPEW = r"(?:St|Street|Rd|Road|Ave|Avenue|Blvd|Dr|Drive|Ln|Lane|Tpke|Turnpike|Hwy|Highway|Pl|Place|Way|Ct|Court|Pkwy|Sq|Plz|Plaza)\.?"
o["street"] = [re.sub(r"(" + TYPEW + r"),?\s+" + re.escape(c) + r"(?:,?\s+ME)?$", r"\1", a, flags=re.I)
               if isinstance(a, str) and isinstance(c, str) else a for a, c in zip(o.street, o.city)]

# a village label that belongs to another town: a village is kept in a town only where at
# least two places put it, or where most of the village's places are
vt = collections.Counter(zip(o.village, o.city))
vmain = {v: g.city.mode().iat[0] for v, g in o[o.village.notna()].groupby("village")}
odd = [isinstance(v, str) and vt[(v, c)] < 2 and vmain.get(v) != c for v, c in zip(o.village, o.city)]
print("village labels dropped (another town's):", sum(odd), list(zip(o.village[odd], o.city[odd]))[:8])
o.loc[odd, "village"] = None
if APP:
    # the same place twice: same name at the same street address, or (not a chain) same name in the same town within 400 m.
    # The licensed record wins, then a confirmed listing, then the one with more facts; the kept copy inherits what the dropped one knew.
    TRANK = {"official": 2, "both": 1, "listing": 0}
    # the hand-checked copy wins (it carries the research), then the licensed one; the kept copy takes the license from the other
    rank = o.tier.map(TRANK).fillna(0) * 10 + o.hc.astype(int) * 25 + o.web.notna().astype(int)
    keyname = o.name_out.map(lambda n: norm_name(n) or re.sub(r"[^a-z0-9]", "", str(n).lower()))
    # same name at the same address in the same town ("195 Main St" in Bangor is not "195 Main St" in Bath)
    keyaddr = ["|".join(k) + "|" + (street_dir(s_) or "") + "|" + str(c_) if all(k := street_key(s_)) else None for s_, c_ in zip(o.street, o.city)]
    drop, merged, seen = set(), [], {}
    for pos, i in enumerate(o.index):
        if keyaddr[pos] and keyname[i]:
            k = (keyname[i], keyaddr[pos])
            if k in seen:
                j = seen[k]
                lose = i if rank[i] <= rank[j] else j
                drop.add(lose); seen[k] = j if lose == i else i
                merged.append((seen[k], lose))
            else:
                seen[k] = i
    # one phone number at one street number in one town, under two spellings of a name
    phone_n = o.phone.map(lambda v: (re.sub(r"\D", "", v or "")[-10:] if isinstance(v, str) else "") or None)
    by_ph = {}
    for i in o.index:
        if i in drop or not isinstance(phone_n[i], str) or len(phone_n[i]) < 10 or not isinstance(o.at[i, "street"], str):
            continue
        num = street_key(o.at[i, "street"])[0]
        if not num:
            continue
        k = (phone_n[i], num, o.at[i, "city"])
        j = by_ph.get(k)
        if j is None or j in drop:
            by_ph[k] = i; continue
        a_, b_ = keyname[i], keyname[j]
        if a_ and b_ and (distinct(a_) & distinct(b_) or fuzz.token_set_ratio(a_, b_) >= 90):
            lose = i if rank[i] <= rank[j] else j
            drop.add(lose); by_ph[k] = j if lose == i else i
            merged.append((by_ph[k], lose))
    # one address, two spellings of one business: the same number,
    # street and side of it in one town, and a distinctive word in common
    by_addr = collections.defaultdict(list)
    for pos, i in enumerate(o.index):
        if i not in drop and keyaddr[pos] and keyname[i]:
            by_addr[keyaddr[pos]].append(i)
    for grp in by_addr.values():
        for a_ in range(len(grp)):
            for b_ in range(a_ + 1, len(grp)):
                i, j = grp[a_], grp[b_]
                if i in drop or j in drop:
                    continue
                if distinct(keyname[i]) & distinct(keyname[j]):
                    lose = i if rank[i] <= rank[j] else j
                    drop.add(lose); merged.append((j if lose == i else i, lose))
    single = o[(o.chain_n.fillna(1) < 2) & ~o.index.isin(drop)]
    for (nm_, town), g in single.groupby([keyname[single.index], single.city]):
        if len(g) < 2 or not nm_:
            continue
        idx = list(g.index)
        for a_ in range(len(idx)):
            for b_ in range(a_ + 1, len(idx)):
                i, j = idx[a_], idx[b_]
                if i in drop or j in drop:
                    continue
                if km(o.at[i, "lat"], o.at[i, "lon"], o.at[j, "lat"], o.at[j, "lon"]) < 0.4:
                    lose = i if rank[i] <= rank[j] else j
                    drop.add(lose); merged.append((j if lose == i else i, lose))
    for keep_i, lose in merged:
        if o.at[keep_i, "cuisine"] == "American & Other" and o.at[lose, "cuisine"] != "American & Other":
            o.at[keep_i, "cuisine"] = o.at[lose, "cuisine"]   # a license row's generic cuisine gives way to what the research says
        for col in [c for c in o.columns if c.startswith("t_")] + ["hc", "honored", "seasonal"]:
            if bool(o.at[lose, col]) and not bool(o.at[keep_i, col]):
                o.at[keep_i, col] = o.at[lose, col]
        for col in ("dishes", "season", "branch", "rnote", "rsite", "rsrc", "web", "phone", "founded", "icon", "jbf", "honors", "chef", "s_icon", "village",
                    "cur_tags", "lw_r", "lw_d", "lw_u", "lw_n", "lw_c", "host", "zip", "brand_n", "raddr", "rname"):
            if pd.isna(o.at[keep_i, col]) and not pd.isna(o.at[lose, col]):
                o.at[keep_i, col] = o.at[lose, col]
        if TRANK.get(o.at[lose, "tier"], 0) > TRANK.get(o.at[keep_i, "tier"], 0):   # the license travels with the place
            for col in ("tier", "official", "lic_kind", "lic_jur", "lic_since", "lic", "hfd_cls", "seats"):
                o.at[keep_i, col] = o.at[lose, col]
        o.at[keep_i, "chain_n"] = max(o.at[keep_i, "chain_n"] or 1, o.at[lose, "chain_n"] or 1) if isinstance(o.at[keep_i, "brand_n"], str) else o.at[keep_i, "chain_n"]
        if o.at[keep_i, "hc"]:
            o.at[keep_i, "venue"] = False   # a hand-checked place is a restaurant, whichever copy carried the check
    print("duplicates removed for the app:", len(drop), [o.at[i, "name_out"] for i in list(drop)[:8]])
    json.dump([[o.at[k, "name_out"], o.at[k, "street"], o.at[k, "city"], o.at[l, "name_out"], o.at[l, "street"], o.at[l, "city"]] for k, l in merged],
              open(f"{ME}/app_merged.json", "w"), indent=0, default=str)   # for review: kept, dropped
    o = o.drop(index=list(drop))
    fixes = json.load(open(f"{DATA}/research/name_fixes.json")) if os.path.exists(f"{DATA}/research/name_fixes.json") else []
    for fx in fixes:
        hit = (o.name_out.str.upper() == fx["name"].upper()) & (o.city == fx["town"]) & o.street.fillna("").str.startswith(fx["street_number"] + " ")
        o.loc[hit, "name_out"] = fx["fixed"]
        print("name fix:", fx["name"], "->", fx["fixed"], int(hit.sum()))
# a hand-checked place shows the researched address, and the researched name when the listing only adds a tail to it
# ("Red's Eats - Lobster Rolls" -> "Red's Eats"; a license's mailing address -> the place's own street address)
for i in o.index[o.hc]:
    ra, rn = o.at[i, "raddr"], o.at[i, "rname"]
    if isinstance(ra, str) and re.match(r"\s*\d", ra):
        o.at[i, "street"] = ra
    if isinstance(rn, str):
        rn = re.sub(r"\s*\([^)]*\)\s*$", "", rn).strip()
        # a license-only row's trade name is the permit's shorthand: the researched name is the place's own
        same_biz = distinct(norm_name(rn)) & distinct(norm_name(o.at[i, "name_out"]))
        if norm_name(rn) and (o.at[i, "src"] == "official" or same_biz
                              or (len(rn) < len(o.at[i, "name_out"]) and norm_name(o.at[i, "name_out"]).startswith(norm_name(rn)))):
            o.at[i, "name_out"] = rn

# adult clubs aren't restaurants and don't belong in a 13+ app or the leaderboard; smoke/vape/cigar shops are hidden with non-restaurants
webs = o.web.fillna("").astype(str) + " " + o.rsite.fillna("").astype(str)
adult = (o.name_out.str.contains(r"gentlem[ae]n'?s club|exotic dancer|strip club|adult entertainment", case=False, regex=True)
         | (o.name_out.str.contains(r"\bcabaret\b", case=False, regex=True) & ~o.name_out.str.contains(r"yale|theat|dinner", case=False, regex=True))) \
    | webs.str.contains(r"centerfolds|gentlemensclub|stripclub", case=False, regex=True)
# strip clubs under plain trade names ("Diamonds" holds an ordinary Class A Lounge license): a checked address list, each entry
# sourced (data/research/adult_venues.json), matched by street number and street in the same town
AV = json.load(open(f"{DATA}/research/adult_venues.json")) if os.path.exists(f"{DATA}/research/adult_venues.json") else []
# same address AND a distinctive word of the club's name: other businesses share these buildings (Half Acre Nightclub at 190 Harlow St)
av_keys = {(street_key(v["address"]), v["town"]): distinct(norm_name(v["name"])) for v in AV}
adult |= pd.Series([isinstance(a_, str) and bool(av_keys.get((street_key(a_), c_), set()) & distinct(norm_name(n_)))
                    for a_, c_, n_ in zip(o.street, o.city, o.name_out)], index=o.index) & ~o.hc
print("adult clubs removed:", int(adult.sum()), o.name_out[adult].tolist())
o = o[~adult]
# a listing Overture files as adult entertainment, matched by a shared distinctive name word within 100 m, is hidden with the
# non-restaurants until someone checks it (Overture also files adult-education centers and a tap room that way)
import duckdb as _ddb
OA = _ddb.connect().execute(f"""SELECT name, lat, lon FROM '{ME}/overture_me_bbox.parquet' WHERE region = 'ME'
                                AND (cat = 'adult_entertainment_venue' OR tax IN ('strip_club', 'adult_entertainment_venue'))""").df()
oa_hide = pd.Series(False, index=o.index)
for nm_, la_, lo_ in zip(OA.name, OA.lat, OA.lon):
    near_ = (np.abs(o.lat - la_) < 0.001) & (np.abs(o.lon - lo_) < 0.0013)
    for i in o.index[near_]:
        if distinct(norm_name(o.at[i, "name_out"])) & distinct(norm_name(nm_)) and not o.at[i, "hc"]:
            oa_hide[i] = True
print("hidden as Overture adult-entertainment listings (unverified):", int(oa_hide.sum()), o.name_out[oa_hide].tolist())
o.loc[oa_hide, "venue"] = True
SMOKE = r"\bvape\b|\bvapor\b|smoke shop|smoke lounge|\btobacco|cigar|\bcbd\b|dispensary|head shop|hookah|\bsmoke ?shop|\bkratom\b"
SMOKE_KEEP = r"^$"
smoke = (o.name_out.str.contains(SMOKE, case=False, regex=True) | o.web.fillna("").str.contains(r"hookah|smokeshop|smoke-shop|cigar|vape", case=False, regex=True)) \
    & ~o.hc & ~o.name_out.str.contains(SMOKE_KEEP, regex=True)
o.loc[smoke, "venue"] = True
print("smoke/vape/cigar shops hidden with non-restaurants:", int(smoke.sum()))
o = o.reset_index(drop=True)
nv = o[~o.venue]
CITIES = sorted(o.city.dropna().unique().tolist()); CUIS = sorted(o.cuisine.unique().tolist()); BRANDS = sorted(o.brand_n.dropna().unique().tolist())
VILLS = sorted(o.village.dropna().unique().tolist())
ci, cu, br, vi = {c: i for i, c in enumerate(CITIES)}, {c: i for i, c in enumerate(CUIS)}, {c: i for i, c in enumerate(BRANDS)}, {c: i for i, c in enumerate(VILLS)}
TIER = {"listing": 0, "both": 1, "official": 2}
JUR = {"bablo": 1, "lewiston": 2}
SRCS = ["official", "meta", "AllThePlaces", "DAC", "research", "BrightQuery", "Foursquare", "Microsoft"]
HOSTS = [c[0] for c in CASINOS]
REGION = {f["properties"]["town"]: f["properties"]["region"] for f in TF}
REGIONS = sorted(set(REGION.values()))
KBIT = {k: 1 << i for i, k in enumerate(KINDS)}


def phone_e164(v):
    """+1 and ten digits, or nothing: listings carry "+2075551234" (a Maine number missing its 1, which would dial another country)."""
    d = re.sub(r"\D", "", v if isinstance(v, str) else "")
    if len(d) == 11 and d[0] == "1":
        d = d[1:]
    return "+1" + d if len(d) == 10 and d[0] in "23456789" and d[3] in "23456789" else None


def place_id(x):
    """A stable id from the source record, never from a display name or rounded coordinates (a nudge of a few meters or a corrected name
    used to make a new id): Overture's GERS id for a map listing, the permit number for a license-only row, the researched name and town
    for a hand-checked place no map listing has."""
    src = str(x.id) if isinstance(x.id, str) and x.id else f"{norm_name(x.name_out)}|{x.city}"
    if src.startswith("research-"):
        src = f"research|{norm_name(src[9:])}|{x.city}"
    return hashlib.md5(src.encode()).hexdigest()[:12]


def jbf_flags(jb):
    jb = jb or ""
    return (1 if "America's Classic" in jb else 0) | (2 if re.search(r"\bwinner\b", jb, re.I) else 0) \
        | (4 if re.search(r"(?<!semi)finalist|\bnominee", jb, re.I) else 0) | (8 if re.search(r"semifinalist", jb, re.I) else 0) | (16 if jb == "" else 0)


if APP:
    places, seen_ids = [], set()
    LINKS = json.load(open(f"{ME}/website_check.json")) if os.path.exists(f"{ME}/website_check.json") else None
    if LINKS is None:   # fail closed: only checked links ever ship
        print("!! data/me/website_check.json is missing: shipping NO website links. Run check_websites.py, then this export again.")
    link_drops, link_cands = collections.Counter(), {}
    # hacked, expired or wrong-business sites a later link sweep found (pipeline/website_blocklist.json; the site drops them too)
    BLOCK = [b for b in json.load(open(os.path.join(os.path.dirname(__file__), "website_blocklist.json"))) if b.get("severity") != "none"]
    def blocked(u):
        pu = urllib.parse.urlparse(u if "://" in u else "https://" + u)
        h = pu.netloc.lower().removeprefix("www.")
        for b in BLOCK:
            d = b["domain"].lower().removeprefix("www.")
            if b.get("match") == "url":
                if (h + pu.path).rstrip("/") == (d + urllib.parse.urlparse("https://" + b.get("url", d)).path).rstrip("/") or u.rstrip("/") == b.get("url", "").rstrip("/"):
                    return True
            elif h == d or h.endswith("." + d):
                return True
        return False
    ICON_YEAR = int(GENERATED[:4]) - 40
    for i, x in o.iterrows():
        p = {"id": place_id(x), "n": x.name_out, "c": ci.get(x.city) if isinstance(x.city, str) else None,
             "cu": cu[x.cuisine], "t": TIER[x.tier], "s": SRCS.index(x.src) if x.src in SRCS else 1}
        if isinstance(x.village, str): p["vi"] = vi[x.village]
        if isinstance(x.street, str): p["a"] = nice(x.street, addr=True)
        if isinstance(x.zip, str) and re.match(r"^0(?:39|4\d)\d{2}", x.zip): p["z"] = x.zip[:5]
        p["la"], p["lo"] = round(float(x.lat), 5), round(float(x.lon), 5)
        if isinstance(x.brand_n, str): p["b"] = br[x.brand_n]
        if x.chain_n and int(x.chain_n) > 1: p["ch"] = int(x.chain_n)
        if x.official and isinstance(x.lic_jur, str): p["j"] = JUR[x.lic_jur]
        if isinstance(x.lic_kind, str) and x.lic_jur == "bablo": p["lk"] = x.lic_kind
        if x.venue: p["v"] = 1
        if x.bar: p["bar"] = 1
        if isinstance(x.host, str): p["host"] = HOSTS.index(x.host)
        tags = sum(1 << bi for bi, tg in enumerate(TAGS) if bool(x["t_" + tg]))
        if tags: p["g"] = tags
        if x.hc:
            p["hc"] = 1
            kinds = [k for k in (x.cur_tags or "").split("; ") if k in KBIT]
            if kinds: p["k"] = sum(KBIT[k] for k in kinds)
            # the Icons guide: James Beard and other honors, or 40+ years at the address (a recent branch isn't one)
            fy = pd.to_numeric(x.founded, errors="coerce")
            p["fs"] = round(float(x.s_icon), 1)   # the classics' "Featured first" order (honors, years at the address)
            if (isinstance(x.jbf, str) and x.jbf) or (isinstance(x.honors, str) and x.honors) or (fy == fy and fy <= ICON_YEAR):
                p["ip"] = p["fs"]
            for k, v in (("note", x.rnote), ("jbf", x.jbf), ("hon", x.honors), ("dish", x.dishes), ("sea", x.season), ("br", x.branch), ("chef", x.chef), ("src", x.rsrc)):
                if isinstance(v, str) and v:
                    if k == "hon":   # honors are facts; ratings and readers' polls stay out
                        v = "; ".join(h for h in v.split("; ") if not re.search(r"readers'? ?choice|\bvote[ds]?\b|\bpoll\b|yelp|tripadvisor|opentable|\bstars?\b|\bbest of\b", h, re.I)) or None
                    if v: p[k] = v
            if x.seasonal: p["seas"] = 1
            if isinstance(x.jbf, str) and x.jbf: p["h"] = jbf_flags(x.jbf)
        if x.founded == x.founded and x.founded is not None: p["f"] = int(float(x.founded))
        web = x.rsite if isinstance(x.rsite, str) else (x.web if isinstance(x.web, str) else None)
        if web:
            w_ = clean_url(web.strip())
            lc_ = link_cands.setdefault(w_, {"name": x.brand_n if isinstance(x.brand_n, str) else x.name_out, "towns": [], "zips": [], "phones": [], "streets": []})
            for k_, v_ in (("towns", x.city), ("towns", x.village), ("zips", (x.zip or "")[:5] if isinstance(x.zip, str) else None),
                           ("phones", phone_e164(x.phone)), ("streets", x.street)):
                if isinstance(v_, str) and v_ and v_ not in lc_[k_] and len(lc_[k_]) < 40:
                    lc_[k_].append(v_)
            v_ = (LINKS or {}).get(w_, {})
            u_ = w_ if re.match(r"(?i)https?://", w_) else "https://" + w_   # what the checker fetched
            fin = urllib.parse.urlparse(v_.get("final") or "")
            # a link the checker saw end on https at the same host ships as https (the first hop isn't left in the clear)
            if u_.lower().startswith("http://") and fin.scheme == "https" and fin.netloc.lower().removeprefix("www.") == urllib.parse.urlparse(u_).netloc.lower().removeprefix("www."):
                u_ = "https://" + u_[7:]
            if v_.get("ok") and blocked(u_):
                link_drops["on the website blocklist"] += 1
            elif v_.get("ok") and urllib.parse.urlparse(u_).scheme in ("http", "https") and urllib.parse.urlparse(u_).netloc:
                p["w"] = u_
            else:
                link_drops[v_.get("why", "not checked yet")] += 1
        ph = phone_e164(x.phone)
        if ph: p["ph"] = ph
        if isinstance(x.lw_r, str) and isinstance(x.lw_d, str):
            p["lw"] = {"r": x.lw_r, "d": x.lw_d, "u": x.lw_u}
            if isinstance(x.lw_n, str) and norm_name(x.lw_n) != norm_name(x.name_out):
                p["lw"]["n"] = nice(x.lw_n) if x.lw_n.isupper() else x.lw_n   # the name the city inspected it under
        while p["id"] in seen_ids:
            p["id"] = p["id"] + "x"
        seen_ids.add(p["id"])
        places.append(p)
    print("website links dropped:", sum(link_drops.values()), link_drops.most_common(8))
    json.dump(link_cands, open(f"{ME}/website_candidates.json", "w"), indent=0, ensure_ascii=False)
    # saved places survive an id change: every id ever exported is remembered (data/id_history.json, kept in the repo), and one that's
    # gone points at the same-named place within 300 m (the app remaps saved ids through "aliases")
    HIST = f"{DATA}/id_history.json"
    hist = json.load(open(HIST)) if os.path.exists(HIST) else {}
    now_ids = {p["id"] for p in places}
    by_name = collections.defaultdict(list)
    for p in places:
        by_name[norm_name(p["n"])].append(p)
    aliases = {}
    for old_id, (nk, la, lo) in hist.items():
        if old_id in now_ids:
            continue
        near = [p for p in by_name.get(nk, []) if km(la, lo, p["la"], p["lo"]) < 0.3]
        if near:
            aliases[old_id] = min(near, key=lambda p: km(la, lo, p["la"], p["lo"]))["id"]
    for p in places:
        hist[p["id"]] = [norm_name(p["n"]), p["la"], p["lo"]]
    json.dump(hist, open(HIST, "w"), separators=(",", ":"), sort_keys=True)
    print("ids remembered:", len(hist), "| aliases for ids that changed:", len(aliases))
    # tracking tags (ref=google, utm_*, cn_channel …) off every outbound link; the store's own parameters stay (tracking_params.py)
    tp_changes = tracking_params.scrub(places)
    print("tracking parameters stripped from links:", sum(tp_changes.values()), dict(tp_changes))
    body = json.dumps(places, separators=(",", ":"), ensure_ascii=False, sort_keys=True, default=str)
    out = {"v": 1, "generated": GENERATED, "data_version": hashlib.md5(body.encode()).hexdigest()[:12], "research_checked": RESEARCH_CHECKED,
           "overture": OVERTURE, "aliases": aliases, "cities": CITIES, "villages": VILLS, "regions": REGIONS,
           "town_region": [REGIONS.index(REGION[c]) if c in REGION else None for c in CITIES], "cuisines": CUIS, "brands": BRANDS,
           "tags": TAGS, "kinds": KINDS, "hosts": HOSTS, "sources": SRCS, "count": len(places), "count_restaurants": int(len(nv)),
           "calibration": calib.get("app", {}), "license_file": LICENSE_FILE, "license_date": LICENSE_DATE, "lewiston_fetched": LW_FETCHED,
           "lewiston_latest": max(e["inspections"][-1][0] for e in LW), "places": places}
    os.makedirs(SITE, exist_ok=True)
    json.dump(out, open(f"{SITE}/places.json", "w"), separators=(",", ":"), ensure_ascii=False, allow_nan=False, default=str)
    json.dump(json.load(open(f"{ME}/me_shapes.json")), open(f"{SITE}/me_shapes.json", "w"), separators=(",", ":"))
    print("APP: wrote", len(places), "places (", len(nv), "restaurants ) |", os.path.getsize(f"{SITE}/places.json") // 1024, "KB | tiers:",
          nv.tier.value_counts().to_dict(), "| tags:", {tg: int(nv["t_" + tg].sum()) for tg in TAGS}, "| hand-checked:", int(nv.hc.sum()))
    sys.exit(0)

SRC = {"model": 0, "model-low": 1, "chain": 2, "reported": 3, "venue": 4}
# columnar: one array per field; decimals stored as integers (lat 41.3083 -> 413083) and scaled back in the page
SCALE = {"lat": 10000, "lon": 10000, "rating": 10, "margin": 1000, "value_raw": 1000}
C = collections.OrderedDict((c, []) for c in ["name", "addr", "city", "vil", "zip", "lat", "lon", "cuisine", "brand", "chain_n", "rating", "reviews",
                                               "price", "price_est", "rev_k", "rev_src", "margin", "value_raw", "tier", "jur", "bar", "venue", "tags",
                                               "src", "host", "hc"])
# sparse fields: [row, values...] for the few places that have them
SIGKEY = {"lr": "lobster", "cl": "clams", "sn": "snapper", "it": "italian", "wh": "whoopie", "pd": "donut", "fr": "franco", "oy": "oyster",
          "bp": "blueberry", "ic": "icecream"}
SP = {k: [] for k in list(SIGKEY) + ["hon"]}
extra = {}
for i, x in o.iterrows():
    tags = sum(1 << b for b, t in enumerate(TAGS) if bool(x["t_" + t]))
    z = int(x.zip[:5]) if isinstance(x.zip, str) and re.match(r"^0(?:39|4\d)\d{2}", x.zip) else None
    vals = {"name": x.name_out, "addr": nice(x.street, addr=True) if isinstance(x.street, str) else None,
            "city": ci.get(x.city) if isinstance(x.city, str) else None, "vil": vi.get(x.village) if isinstance(x.village, str) else None,
            "zip": z, "lat": x.lat, "lon": x.lon, "cuisine": cu[x.cuisine],
            "brand": br.get(x.brand_n) if isinstance(x.brand_n, str) else None, "chain_n": int(x.chain_n), "rating": x.rating, "reviews": r(x.reviews),
            "price": int(x.price), "price_est": int(x.price_est), "rev_k": int(round(x.rev / 1000)), "rev_src": SRC[x.rev_src], "margin": x.margin,
            "value_raw": x.value_raw, "tier": TIER[x.tier], "jur": JUR.get(x.lic_jur, 0) if isinstance(x.lic_jur, str) else 0, "bar": int(bool(x.bar)),
            "venue": int(bool(x.venue)), "tags": tags, "src": SRCS.index(x.src) if x.src in SRCS else 1,
            "host": HOSTS.index(x.host) + 1 if isinstance(x.host, str) else 0, "hc": int(bool(x.hc))}
    for key, sk in SIGKEY.items():
        n, rr = x["n_" + sk], x["r_" + sk]
        if n:
            SP[key].append([i, int(n), int(round(rr * 100)) if rr == rr and rr is not None else None])
    if x.honored:
        SP["hon"].append([i, int(round(x.s_icon * 10)), jbf_flags(x.jbf) if isinstance(x.jbf, str) and x.jbf else 0])
    for c, v in vals.items():
        if c in SCALE:
            v = None if v is None or v != v else int(round(float(v) * SCALE[c]))
        elif isinstance(v, float):
            v = None if v != v else v
        C[c].append(v.item() if hasattr(v, "item") else v)
    e = {}
    if x.hc:
        e.update({k: v for k, v in (("jbf", x.jbf), ("honors", x.honors), ("note", x.rnote), ("founded", r(x.founded)), ("dishes", x.dishes),
                                    ("season", x.season), ("branch", x.branch), ("chef", x.chef), ("kinds", x.cur_tags), ("src", x.rsrc),
                                    ("site", x.rsite)) if v is not None and v == v and v != ""})
    if x.official:
        e["lic_kind"] = x.lic_kind if x.lic_jur == "bablo" else None
        e["found"] = "list" if x.src == "official" else "match"
    if isinstance(x.lw_r, str) and isinstance(x.lw_d, str):
        e["lw"] = x.lw_r + "|" + x.lw_d + "|" + (x.lw_u or "")
    e = {k: v for k, v in e.items() if v is not None and not (isinstance(v, float) and v != v)}
    if e:
        extra[i] = e
meta = {"generated": GENERATED, "cities": CITIES, "villages": VILLS, "regions": REGIONS,
        "town_region": [REGIONS.index(REGION[c]) if c in REGION else None for c in CITIES], "cuisines": CUIS, "brands": BRANDS,
        "src": list(SRC), "tiers": list(TIER), "tags": TAGS, "hosts": HOSTS, "food_cost": dict(FOOD_COST), "spend": SPEND, "count": len(o),
        "count_restaurants": int(len(nv)), "count_official": int(nv.official.sum()), "count_both": int((nv.tier == "both").sum()),
        "count_listing": int((nv.tier == "listing").sum()), "n_cities": int(nv.city.nunique()), "overture_release": OVERTURE,
        "rating_mean": round(float(m_rat), 3), "model": {"b": B_FIT, "n_chains": n_auv}, "calibration": calib, "n_honored": int(o.honored.sum()),
        "n_hc": int(o.hc.sum()), "srcs": SRCS, "license_file": LICENSE_FILE, "license_date": LICENSE_DATE, "lewiston_fetched": LW_FETCHED,
        "lewiston_latest": max(e["inspections"][-1][0] for e in LW)}
for _k, _v in list(C.items()) + list(SP.items()):
    _bad = [j for j, x in enumerate(_v) if (isinstance(x, float) and x != x) or (isinstance(x, list) and any(isinstance(y, float) and y != y for y in x))]
    if _bad: print("NaN in", _k, len(_bad), _v[_bad[0]])
os.makedirs(SITE, exist_ok=True)
json.dump({"n": len(o), "scale": SCALE, "cols": C, "sparse": SP, "meta": meta},
          open(f"{SITE}/maine.json", "w"), separators=(",", ":"), allow_nan=False, default=str)
json.dump({"n": len(o), "extra": {str(k): v for k, v in extra.items()}}, open(f"{SITE}/me_detail.json", "w"), separators=(",", ":"), allow_nan=False, default=str)
json.dump(json.load(open(f"{ME}/me_shapes.json")), open(f"{SITE}/me_shapes.json", "w"), separators=(",", ":"))
o.to_pickle(f"{ME}/stage2.pkl")
print("wrote", len(o), "places (", int(len(nv)), "restaurants ) in", nv.city.nunique(), "towns;", os.path.getsize(f"{SITE}/maine.json") // 1024,
      "KB | tiers:", nv.tier.value_counts().to_dict(), "| top towns:", nv.city.value_counts().head(8).to_dict())
