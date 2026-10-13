"""How often is a map listing a real, licensed restaurant? Measured against Maine's official lists -> data/me/calibration.json

Two yardsticks:
- Lewiston (the city's posted food-service inspections, establishments inspected since Jan 2024): every kind of licensed eating
  place the city inspects, so an absolute rate, like Hartford in Connecticut or Milwaukee in Wisconsin. Small (about 80 places).
- Statewide (BABLO active on-premises liquor licenses: Class A Restaurant, Class A Restaurant/Lounge, Restaurant, Class A Lounge,
  Tavern, hotels and inns): only places that serve alcohol hold one, so these rates are much lower than a food-license rate. They
  compare source groups across the whole state and show which kinds of places the listings miss.
A match = the same business name nearby, or the same street address with a distinctive name word in common (listings_util).
Both directions are reported: listings that match a license, and licenses found among the listings (one per business).
"""
import json
import numpy as np, pandas as pd
from common import ME
import official
from official import ON_PREMISE
from listings_util import official_match

o = pd.read_pickle(f"{ME}/stage1.pkl")
F = official.load()
o = o[~o.j_junk & ~o.j_outside & o.town.notna()].reset_index(drop=True)
TOWNWORDS = frozenset(w for t in o.town.dropna().unique() for w in t.upper().split())


def groups_web(L):
    s = L.src.fillna("none")
    return np.select([L.closed21, L.ov_closed, (s == "meta") & L.in21, s == "meta", s.isin(["AllThePlaces", "DAC"]) & L.in21,
                      s.isin(["AllThePlaces", "DAC"]), L.in21, s == "Foursquare", s == "BrightQuery", s == "Microsoft"],
                     ["Google 2021 says closed", "Overture says closed", "Meta + open in Google 2021", "Meta only",
                      "brand feed + Google 2021", "brand feed only", "Foursquare/BrightQuery/Microsoft + Google 2021",
                      "Foursquare only", "BrightQuery only", "Microsoft only"], "other")


def groups_app(L):
    conf, s = L.confidence.fillna(0), L.src.fillna("none")
    return np.select([L.ov_closed, (s == "meta") & (conf >= 0.95), (s == "meta") & (conf >= 0.9), s.isin(["AllThePlaces", "DAC"]),
                      (s == "BrightQuery") & (conf >= 0.95), s == "meta"],
                     ["Overture says closed", "Meta, confidence 0.95+", "Meta, 0.90-0.95", "brand feed", "BrightQuery 0.95+", "Meta, below 0.90"],
                     "other sources")


def measure(L, R, grp_fn, label):
    m = official_match(L.reset_index(drop=True), R.reset_index(drop=True), town_words=TOWNWORDS)
    L = L.reset_index(drop=True)
    L["hit"] = L.index.map(lambda i: i in m)
    L["grp"] = grp_fn(L)
    t = L.groupby("grp").hit.agg(["size", "mean"]).sort_values("size", ascending=False)
    print(f"\n== {label}: {len(L)} listings vs {R.biz.nunique()} licensed businesses")
    print(t.assign(mean=(t["mean"] * 100).round(1)).rename(columns={"size": "listings", "mean": "% matched"}).to_string())
    got = set(R.reset_index(drop=True).biz.iloc[list(m.values())])
    return L, m, {g: {"n": int(r["size"]), "matched": round(float(r["mean"]), 3)} for g, r in t.iterrows()}, got


res = {"web": {}, "app": {}, "coverage": {}, "source": F.source_file.iat[0]}
# ---- Lewiston: every city-inspected eating place (inspected 2024 or later)
LL = o[o.town == "Lewiston"]
RL = F[(F.jur == "lewiston") & F.active]
for kind, fn in (("web", groups_web), ("app", groups_app)):
    _, m, res[kind]["lewiston"], got = measure(LL, RL, fn, f"Lewiston inspected food places, {kind} grouping")
cover = np.mean([b in got for b in RL.drop_duplicates("biz").biz])
print(f"Lewiston inspected establishments found among the map listings: {cover:.1%} of {RL.biz.nunique()}")
res["coverage"]["lewiston"] = {"share": round(float(cover), 3), "n": int(RL.biz.nunique())}

# ---- statewide: on-premises liquor licenses
RS = F[(F.jur == "bablo") & F.active & F.kind.isin(ON_PREMISE | {"brewery", "club", "venue"})]
for kind, fn in (("web", groups_web), ("app", groups_app)):
    L, m, res[kind]["statewide_liquor"], got = measure(o, RS, fn, f"statewide on-premises liquor licenses, {kind} grouping")
RB = RS.drop_duplicates("biz").assign(found=lambda d: d.biz.isin(got))
by_kind = RB.groupby("kind").found.agg(["size", "mean"])
by_cls = RB[RB.cls.notna()].groupby("cls").found.agg(["size", "mean"])
print("\nliquor-license businesses found among the map listings:\n" + by_kind.assign(mean=(by_kind["mean"] * 100).round(1)).to_string())
print(by_cls.assign(mean=(by_cls["mean"] * 100).round(1)).to_string())
res["coverage"]["liquor"] = {k: {"n": int(r["size"]), "found": round(float(r["mean"]), 3)} for k, r in by_kind.iterrows()}
res["coverage"]["liquor_class"] = {k: {"n": int(r["size"]), "found": round(float(r["mean"]), 3)} for k, r in by_cls.iterrows()}
L["cat"] = L.cat.fillna("?")
t = L[L.grp.isin(["Meta, confidence 0.95+", "Meta, 0.90-0.95"])].groupby("cat").hit.agg(["size", "mean"]).sort_values("size", ascending=False)
print("\nMeta 0.90+ listings with a liquor license, by Overture category:\n" + t.assign(mean=(t["mean"] * 100).round(1)).to_string())
res["liquor_by_category"] = {c: {"n": int(r["size"]), "matched": round(float(r["mean"]), 3)} for c, r in t.iterrows()}
# ---- the size check: BLS QCEW 2025 counts about 3,470 private NAICS 722 establishments in Maine (area 23000; per the state
# prompt's late-September research; data.bls.gov's robots.txt disallows all crawling, so it isn't re-fetched here)
res["qcew_722_2025"] = 3470
json.dump(res, open(f"{ME}/calibration.json", "w"), indent=1)
print("\nwrote calibration.json")
