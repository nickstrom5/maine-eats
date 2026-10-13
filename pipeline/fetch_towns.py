"""Maine's towns, cities, plantations and unorganized territories -> data/me/

Maine is a town state: every place is in one of 529 Census county subdivisions (430 towns, 23 cities, 29 plantations, 42
unorganized territories, 4 reservations and a gore). Villages (Cape Neddick, Peaks Island, Northeast Harbor) are in a town and
stay searchable through the listing's mailing name. Source: Census cartographic boundary file cb_2025_23_cousub_500k (public
domain, clipped to the shoreline), downloaded from www2.census.gov/geo/tiger/GENZ2025/shp/.

Regions are the Maine Office of Tourism's eight, drawn on county lines (our grouping; the tourism map's own lines differ a little).

- me_towns.geojson   every town, full detail, with its county and region (for placing each restaurant in its town)
- me_state_detail.geojson  the state outline (to drop listings outside Maine)
- me_shapes.json     the simplified state outline and county outlines for the maps
"""
import os, json
import duckdb
from shapely import wkb
from shapely.geometry import mapping, Polygon
from shapely.ops import unary_union

ME = os.path.join(os.path.dirname(__file__), "..", "data", "me")
REGION = {"York": "Maine Beaches", "Cumberland": "Greater Portland & Casco Bay", "Sagadahoc": "Midcoast & Islands",
          "Lincoln": "Midcoast & Islands", "Knox": "Midcoast & Islands", "Waldo": "Midcoast & Islands", "Hancock": "Downeast & Acadia",
          "Washington": "Downeast & Acadia", "Oxford": "Lakes & Mountains", "Androscoggin": "Lakes & Mountains",
          "Franklin": "Lakes & Mountains", "Kennebec": "Kennebec Valley", "Somerset": "Kennebec Valley", "Penobscot": "Maine Highlands",
          "Piscataquis": "Maine Highlands", "Aroostook": "Aroostook County"}
con = duckdb.connect(); con.execute("INSTALL spatial; LOAD spatial;")
rows = con.execute(f"SELECT NAME, NAMELSAD, NAMELSADCO, GEOID, ST_AsWKB(geom) FROM ST_Read('{ME}/cousub/cb_2025_23_cousub_500k.shp') ORDER BY NAME").fetchall()
towns = []
for n, lsad, co, g, w in rows:
    co = co.replace(" County", "")
    kind = "UT" if lsad.endswith(" UT") else lsad.rsplit(" ", 1)[-1].lower()
    towns.append((n, co, REGION[co], kind, g, wkb.loads(bytes(w)).buffer(0)))
assert len(towns) == 529, len(towns)
# one name per place: a plantation, unorganized territory or reservation that shares another's name says what it is ("Lincoln" the
# city in Penobscot County and "Lincoln Plantation" in Oxford County; "Unity" the town and "Unity Township")
from collections import Counter
_n = Counter(t[0] for t in towns)
SUFFIX = {"plantation": " Plantation", "UT": " Township"}
towns = [((n + SUFFIX[k]) if _n[n] > 1 and k in SUFFIX else (f"{n} ({co} County)" if _n[n] > 1 and k == "reservation" and co != "Penobscot" else n),
          co, r, k, g, geom) for n, co, r, k, g, geom in towns]
assert len({t[0] for t in towns}) == 529, Counter(t[0] for t in towns).most_common(3)
json.dump({"type": "FeatureCollection", "features": [
    {"type": "Feature", "properties": {"town": n, "county": co, "region": r, "kind": k, "geoid": g}, "geometry": mapping(geom)}
    for n, co, r, k, g, geom in towns]}, open(f"{ME}/me_towns.geojson", "w"))


def rings(geom, tol, min_area, holes=False):
    geom = geom.simplify(tol, preserve_topology=True)
    polys = [p for p in getattr(geom, "geoms", [geom]) if p.geom_type == "Polygon" and p.area >= min_area]
    r = lambda ring: [[round(x, 4), round(y, 4)] for x, y in ring.coords]
    if holes:
        return [[r(p.exterior)] + [r(h) for h in p.interiors if abs(Polygon(h).area) >= min_area] for p in polys]
    return [r(p.exterior) for p in polys]


state = unary_union([t[5] for t in towns]).buffer(0)
json.dump(mapping(state.simplify(0.0003, preserve_topology=True)), open(f"{ME}/me_state_detail.geojson", "w"))
counties = {}
for n, co, r, k, g, geom in towns:
    counties.setdefault(co, []).append(geom)
out = {"state": rings(state, 0.002, 0.0003, holes=True),
       "counties": [{"name": co, "region": REGION[co], "c": rings(unary_union(gs).buffer(0), 0.003, 0.0003)} for co, gs in sorted(counties.items())]}
json.dump(out, open(f"{ME}/me_shapes.json", "w"), separators=(",", ":"))
print("towns:", len(towns), "| state rings:", len(out["state"]), "| counties:", len(out["counties"]), "|",
      os.path.getsize(f"{ME}/me_shapes.json") // 1024, "KB")

# ---- every Overture address point tagged with its Census town (the points' own municipality names use township codes,
# "Saint George", "Rangeley Plt"), so license geocoding and listings agree on one set of town names
import numpy as np, pandas as pd
from shapely import STRtree, points
ap = pd.read_parquet(f"{ME}/addresses_me.parquet")
geoms = [t[5] for t in towns]
tree = STRtree(geoms)
pt_idx, poly_idx = tree.query(points(ap.lon.to_numpy(), ap.lat.to_numpy()), predicate="intersects")
town = np.full(len(ap), None, dtype=object)
town[pt_idx] = np.array([towns[i][0] for i in poly_idx], dtype=object)
if "muni_addr" not in ap:   # keep the points' own municipality name once, on the first run
    ap["muni_addr"] = ap.muni
ap["muni"] = town
ap.to_parquet(f"{ME}/addresses_me.parquet")
print("address points:", len(ap), "| in a town:", int(pd.notna(town).sum()))
