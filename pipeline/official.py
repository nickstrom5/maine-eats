"""Official Maine records: BABLO liquor licenses (statewide) and the City of Lewiston's posted food-service inspections.

load() returns one table of licensed businesses with a normalized name key, street number and street key, coordinates placed on
Overture address points (the records have none), the town, the license kind and whether it is active.

- BABLO "License Data" (maine.gov/dafs/bablo/liquor-licensing/license-data, monthly Excel; the file name changes each month,
  e.g. 10-2026.xlsx "current as of 10/1/2026"). Active licenses only, so a seasonal place between terms is missing, not closed.
  Only the Premises Name (trade name) is kept: `Legal Entity Name` is dropped on read and never stored. `Initial Issue Date` is the
  current term's start, not the year a place opened, so it isn't used as one.
- Lewiston (lewistonmaine.gov/621, "Restaurant Inspection Reports"): one page listing each city-inspected establishment with its
  address and a link per inspection, labeled "MM/DD/YYYY - Passed" or "- Failed" (the state's Pass/Fail under 10-144 CMR Ch. 201
  §6(D)). The page is read once per refresh; the report PDFs are linked, never fetched in bulk.

Maine's statewide inspection results (Maine CDC Health Inspection Program) are search-only behind reCAPTCHA and aren't read.
"""
import os, re, math, json, glob, html
import numpy as np, pandas as pd
from common import norm_name, RAW, ME, canon_city

OFF = os.path.join(RAW, "official")
DIRS = {"N": "N", "S": "S", "E": "E", "W": "W", "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W"}
TYPES = set("""ST STREET AVE AV AVENUE BLVD BOULEVARD RD ROAD DR DRIVE LN LANE CT COURT PL PLACE PKWY PARKWAY TER TERRACE TRL TRAIL WAY
HWY HIGHWAY CIR CIRCLE PLZ PLAZA SQ SQUARE MALL BND PASS XING RUN ROW WALK RDG TPKE TPK TURNPIKE PIKE EXT EXTENSION GRN GREEN CRES
COMMONS CMNS LNDG LANDING WHARF PIER""".split())
# BABLO premises types -> our kinds. Off-premises sellers (stores, agency liquor stores, wholesalers) aren't places to eat.
KIND = {"Class A Restaurant": "restaurant", "Class A Restaurant/Lounge": "restaurant", "Restaurant (not Class A)": "restaurant",
        "Class A Lounge": "bar", "Tavern": "bar", "Hotel": "hotel", "Hotel (Food Optional)": "hotel", "Bed and Breakfast": "hotel",
        "Small Maine Brewery": "brewery", "Small Maine Winery": "brewery", "Small Maine Distillery": "brewery", "Brewery": "brewery",
        "Tenant Brewery": "brewery", "Winery": "brewery", "Tenant Winery": "brewery",
        "Club with catering privileges": "club", "Club without catering privileges": "club",
        "Golf Course": "venue", "Auditorium": "venue", "Performing Art Center": "venue", "Bowling Center": "venue",
        "Vessel Corporation": "venue", "Indoor Golf Center": "venue", "Civic Auditorium": "venue", "Outdoor Stadium": "venue",
        "Indoor Racquet Center": "venue", "Disc Golf Course": "venue", "Indoor Ice Skating Center": "venue", "Ski Area": "venue",
        "Outdoor Golf Center": "venue", "Qualified Catering Service": "caterer"}
ON_PREMISE = {"restaurant", "bar", "hotel"}   # the licenses a restaurant or bar holds
CLASS = {"Class A Restaurant": "Class A Restaurant", "Class A Restaurant/Lounge": "Class A Restaurant/Lounge",
         "Restaurant (not Class A)": "Restaurant", "Class A Lounge": "Class A Lounge", "Tavern": "Tavern"}


def road(a):
    """One spelling for numbered roads: 'US ROUTE 1' = 'US-1' = 'ROUTE 1' = 'RT 1' = 'ME-3' = 'STATE ROUTE 3' = 'RTE #1'."""
    a = re.sub(r"(\d)\s*&\s*(\d)", r"\1-\2", a.upper())
    a = re.sub(r"\b(ROUTE|RTE|RT)\s+ONE\b", r"\1 1", a)
    a = re.sub(r"\bHWY\s+(?=(?:U\.?\s?S\.?|STATE|ROUTE|RTE|RT)\b)", "", a)   # "2336 HWY US 1"
    a = re.sub(r"\b(?:U\.?\s?S\.?|STATE)[-\s]+(?:ROUTE|RTE|RT|HIGHWAY|HWY)?\s*#?\s*-?\s*(\d+[A-Z]?)\b", r"RT \1", a)
    # "ME 3" is a route right after the house number (or written "ME-3" / "ME Route 3"); "Pick Me Up" isn't
    a = re.sub(r"\b(?:ME|MAINE)(?:\s*-\s*|\s+(?:ROUTE|RTE|RT|HIGHWAY|HWY)\s*#?\s*-?\s*)(\d+[A-Z]?)\b", r"RT \1", a)
    a = re.sub(r"^(\s*\d+[A-Z]?(?:\s*-\s*\d+[A-Z]?)?\s+|[&/]\s*)ME\s+(\d+[A-Z]?)\b", r"\1RT \2", a)
    a = re.sub(r"\b(?:ROUTE|RTE|RT)\.?\s*#?\s*(\d+[A-Z]?)\b", r"RT \1", a)
    a = re.sub(r"\bTPKE\b|\bTPK\b", "TURNPIKE", a)
    return re.sub(r"\bHIGHWAY\b", "HWY", a)


def street_key(a):
    """'2505 Main St' -> ('2505', 'MAIN'); '134 ROUTE 1' -> ('134', 'RT 1'); '45 Mill Rock Rd E' -> ('45', 'MILL ROCK')."""
    if not isinstance(a, str):
        return None, None
    a = re.sub(r"[.,#]", " ", road(a))
    m = re.match(r"^\s*(\d+)[A-Z]?(?:\s*-\s*\d+[A-Z]?)?\s+(.*)$", a)
    if not m:
        return None, None
    words = [w for w in m.group(2).split() if w]
    if len(words) > 1 and words[0] in ("SAINT", "ST", "MOUNT", "MT", "FORT", "FT"):   # "Saint John St" = "St John St"
        words = [{"SAINT": "ST", "MOUNT": "MT", "FORT": "FT"}.get(words[0], words[0]) + "_"] + words[1:]
    while len(words) > 1 and words[0] in DIRS and words[1] not in TYPES:   # "3 West St" is West Street, not a direction
        words = words[1:]
    core = []
    for w in words:
        if w in TYPES and core:
            break
        core.append(w)
    core = [w.rstrip("_") for w in core]
    core = [{"FIRST": "1ST", "SECOND": "2ND", "THIRD": "3RD", "FOURTH": "4TH", "FIFTH": "5TH", "SIXTH": "6TH"}.get(w, w) for w in core]
    return m.group(1), " ".join(core[:3]) or None


def street_dir(a):
    """The direction before the street name: '345 N Main St' -> 'N'; '345 Main St' and '3 West St' -> None."""
    if not isinstance(a, str):
        return None
    m = re.match(r"^\s*\d+[A-Z]?(?:\s*-\s*\d+[A-Z]?)?\s+(.*)$", re.sub(r"[.,#]", " ", road(a)))
    w = m.group(1).split() if m else []
    return DIRS[w[0]] if len(w) > 1 and w[0] in DIRS and w[1] not in TYPES else None


TYPE_ABBR = {"STREET": "ST", "AVENUE": "AVE", "AV": "AVE", "ROAD": "RD", "DRIVE": "DR", "LANE": "LN", "COURT": "CT", "PLACE": "PL",
             "PARKWAY": "PKWY", "TERRACE": "TER", "TRAIL": "TRL", "HIGHWAY": "HWY", "CIRCLE": "CIR", "PLAZA": "PLZ", "SQUARE": "SQ",
             "TURNPIKE": "TPKE", "TPK": "TPKE", "PIKE": "TPKE", "EXTENSION": "EXT", "GREEN": "GRN", "LANDING": "LNDG", "COMMONS": "CMNS",
             "BOULEVARD": "BLVD"}


def street_type(a):
    if not isinstance(a, str):
        return None
    m = re.match(r"^\s*\d+[A-Z]?(?:\s*-\s*\d+[A-Z]?)?\s+(.*)$", re.sub(r"[.,#]", " ", road(a)))
    w = m.group(1).split() if m else []
    for i, x in enumerate(w):
        if i and x in TYPES:
            return TYPE_ABBR.get(x, x)
    return None


def dir_ok(d1, d2):
    return d1 is None or d2 is None or d1 == d2


def street_nums(a):
    """'157-159 W Main St' -> {'157', '159'}; '2505 Main St' -> {'2505'}."""
    if not isinstance(a, str):
        return set()
    a = road(a)
    m = re.match(r"^\s*(\d+)[A-Z]?(?:\s*-\s*(\d+)[A-Z]?)?\s", a.upper() + " ")
    if not m:
        return set()
    lo = int(m.group(1)); hi = int(m.group(2)) if m.group(2) else lo
    if hi < lo:   # "1500-02"
        hi = int(str(lo)[: len(str(lo)) - len(m.group(2))] + m.group(2)) if m.group(2) else lo
    return {str(x) for x in range(lo, hi + 1, 2 if (hi - lo) % 2 == 0 else 1)} if 0 <= hi - lo <= 12 else {str(lo)}


def _names(*vals):
    out = []
    for v in vals:
        if not isinstance(v, str):
            continue
        for part in re.split(r"\s*/\s*|\s+\bdba\b\s+|\s+&\s+(?=[A-Z][a-z])", v, flags=re.I):
            k = norm_name(re.sub(r"\b(?:LLC|INC|CORP|CORPORATION|LTD|CO)\b\.?", "", part, flags=re.I))
            if k and k not in out:
                out.append(k)
    return out


_AP = None


def address_index():
    """(street number, street key) -> address points [(lat, lon, municipality, zip, dir, type)] for Maine, plus per (street key, town)
    the sorted numbered points, to interpolate a number the points lack."""
    global _AP
    if _AP is None:
        ap = pd.read_parquet(f"{ME}/addresses_me.parquet", columns=["number", "street", "postcode", "muni", "state", "lat", "lon"])
        ap = ap[ap.state == "ME"]
        idx, line, bystreet = {}, {}, {}
        for n, s, z, m, la, lo in zip(ap.number.astype(str), ap.street.fillna(""), ap.postcode.fillna(""), ap.muni, ap.lat, ap.lon):
            s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
            k = street_key(f"{n} {s}")
            if k[1]:
                d, t = street_dir(f"{n} {s}"), street_type(f"{n} {s}")
                idx.setdefault(k, []).append((la, lo, m, z[:5], d, t))
                line.setdefault((k[1], m), []).append((int(k[0]), la, lo, z[:5], d, t))
                bystreet.setdefault(k[1], {}).setdefault(m, set()).add(z[:5])
        for v in line.values():
            v.sort(key=lambda p: (p[0], p[1], p[2]))
        _AP = (idx, line, bystreet)
    return _AP


def _same_dir(pts, d, at, t=None):
    if d is not None:
        pts = [p for p in pts if p[at] == d] or [p for p in pts if p[at] is None]
    if t is not None:
        pts = [p for p in pts if p[at + 1] == t] or pts
    return pts


def _interpolate(num, st, town, d=None, t=None):
    """A number missing from the points: between the nearest numbers on both sides (same parity first) within 60, else the nearest within 20."""
    import bisect
    pts = _same_dir(address_index()[1].get((st, town)) or [], d, 4, t)
    if not pts:
        return None
    n = int(num)
    for same_side in (True, False):
        cand = [p for p in pts if (p[0] % 2 == n % 2 or not same_side)]
        nums = [p[0] for p in cand]
        i = bisect.bisect_left(nums, n)
        lo_, hi_ = (cand[i - 1] if i > 0 else None), (cand[i] if i < len(cand) else None)
        if lo_ and hi_ and hi_[0] - lo_[0] <= 120 and n - lo_[0] <= 60 and hi_[0] - n <= 60:
            f = (n - lo_[0]) / max(hi_[0] - lo_[0], 1)
            la, lo = lo_[1] + f * (hi_[1] - lo_[1]), lo_[2] + f * (hi_[2] - lo_[2])
            if math.hypot((hi_[1] - lo_[1]) * 111, (hi_[2] - lo_[2]) * 80) < 0.6:
                return la, lo, town
    near = min(pts, key=lambda p: abs(p[0] - n))
    if abs(near[0] - n) <= 20:
        return near[1], near[2], town
    return None


def geocode(addr, town=None, zip5=None):
    """A license address -> (lat, lon, municipality, exact?) on the address points: same number and street, in the same town or zip;
    else interpolated between neighboring numbers on that street in that town. None when it can't be placed or would be a guess."""
    idx = address_index()[0]
    st = street_key(addr)[1]
    d, t = street_dir(addr), street_type(addr)
    nums = sorted(street_nums(addr))
    ambiguous = set()
    for n in nums:
        pts = _same_dir(idx.get((n, st)) or [], d, 4, t)
        if not pts:
            continue
        same = [p for p in pts if town and p[2] == town] or [p for p in pts if zip5 and p[3] == zip5]
        if (town or zip5) and not same:
            continue   # "123 Main St" in Bangor is not 123 Main St in Bath: never borrow another town's point
        pts = same or pts
        la, lo = float(np.median([p[0] for p in pts])), float(np.median([p[1] for p in pts]))
        if max(math.hypot((p[0] - la) * 111, (p[1] - lo) * 80) for p in pts) > 1.0:
            if zip5 and [p for p in pts if p[3] == zip5] and len({p[3] for p in pts}) > 1:
                pts = [p for p in pts if p[3] == zip5]
                la, lo = float(np.median([p[0] for p in pts])), float(np.median([p[1] for p in pts]))
            if max(math.hypot((p[0] - la) * 111, (p[1] - lo) * 80) for p in pts) > 1.0:
                ambiguous.add(n)
                continue
        return la, lo, pts[0][2], True
    if not town and zip5 and st:   # a village's mail: the one town where this street has this zip
        ts = [m for m, zs in (address_index()[2].get(st) or {}).items() if zip5 in zs]
        town = ts[0] if len(ts) == 1 else None
    if town and st:
        for n in nums:
            g = None if n in ambiguous else _interpolate(n, st, town, d, t)
            if g:
                return g[0], g[1], g[2], False
    return None


def zip_towns():
    """zip -> (the municipality most of its address points are in, every municipality it covers). Licenses give a mailing city,
    not always the town: "Cape Neddick" 03902 is York, "Northeast Harbor" 04662 is Mount Desert."""
    ap = pd.read_parquet(f"{ME}/addresses_me.parquet", columns=["postcode", "muni", "state"])
    ap = ap[(ap.state == "ME") & ap.postcode.notna()]
    ap["z"] = ap.postcode.str[:5]
    g = ap.groupby("z").muni
    return g.agg(lambda x: x.mode().iat[0]).to_dict(), g.agg(lambda x: set(x.value_counts()[lambda c: c >= 20].index)).to_dict()


# villages and mailing names -> their town, for records whose address can't be placed on a point
VILLAGES = {"York Beach": "York", "York Harbor": "York", "Cape Neddick": "York", "Belgrade Lakes": "Belgrade", "The Forks PLT": "The Forks",
            "Northeast Harbor": "Mount Desert", "Seal Harbor": "Mount Desert", "Somesville": "Mount Desert", "Otter Creek": "Mount Desert",
            "Bass Harbor": "Tremont", "Bernard": "Tremont", "New Harbor": "Bristol", "Pemaquid": "Bristol", "Round Pond": "Bristol",
            "Tenants Harbor": "St. George", "Port Clyde": "St. George", "Cape Porpoise": "Kennebunkport", "Peaks Island": "Portland",
            "Bailey Island": "Harpswell", "Orr's Island": "Harpswell", "Lincolnville Beach": "Lincolnville", "Five Islands": "Georgetown",
            "East Boothbay": "Boothbay", "Ocean Park": "Old Orchard Beach", "Kennebunk Beach": "Kennebunk", "Moody": "Wells",
            "Kittery Point": "Kittery", "Biddeford Pool": "Biddeford", "Camp Ellis": "Saco", "Prouts Neck": "Scarborough",
            "South Freeport": "Freeport", "Poland Spring": "Poland", "South Paris": "Paris", "Lisbon Falls": "Lisbon",
            "Corea": "Gouldsboro", "Prospect Harbor": "Gouldsboro", "Birch Harbor": "Gouldsboro", "Sunset": "Deer Isle",
            "Christmas Cove": "South Bristol", "Walpole": "South Bristol", "Spruce Head": "South Thomaston", "Bethel": "Bethel",
            "West Boothbay Harbor": "Southport", "Trevett": "Boothbay", "Ogunquit": "Ogunquit", "Wells Beach": "Wells"}


def town_names():
    return {f["properties"]["town"] for f in json.load(open(f"{ME}/me_towns.geojson"))["features"]}


def split_address(full, line1, city, zip_):
    """BABLO gives either Line 1 / City / Zip, or only the combined 'Premises Address' ("257 HAROLD DOW HIGHWAY  ELIOT ME 03903")."""
    if isinstance(line1, str) and line1.strip():
        return line1.strip(), city if isinstance(city, str) else None, str(zip_ or "")[:5]
    full = re.sub(r"\s+$", "", str(full or ""))
    m = re.match(r"^(.*?)\s+ME\s+(\d{5})(?:-\d{4})?$", full)
    if not m:
        return full, None, ""
    head, z = m.group(1), m.group(2)
    if "  " in head:   # a double space separates the street from the town
        st, _, c = head.rpartition("  ")
        return st.strip(), c.strip(), z
    words = head.split()
    for k in (3, 2, 1):   # the longest known town or mailing name at the end
        c = " ".join(words[-k:])
        if len(words) > k and canon_city(c) in _MAILNAMES:
            return " ".join(words[:-k]), c, z
    return head, None, z


_MAILNAMES = set()


def lewiston():
    """City of Lewiston inspection reports -> [{name, addr, inspections: [(date, result, url)]}] from the saved page."""
    t = open(f"{OFF}/lewiston/621.html", encoding="utf-8", errors="replace").read()
    t = t[t.find("Alphabetical Listing"):]
    out = []
    # each establishment: <strong>NAME</strong> - ADDRESS<br> then its report links, up to the next <strong>
    for m in re.finditer(r"<strong>([^<]{2,120})</strong>\s*(?:&nbsp;)?\s*[-–]\s*([^<]{3,120})(.*?)(?=<strong>|$)", t, re.S):
        name, addr, rest = html.unescape(m.group(1)).strip(), html.unescape(m.group(2)).strip(), m.group(3)
        ins = []
        for a in re.finditer(r'href="(/DocumentCenter/View/\d+)/?"[^>]*>\s*([^<]+)</a>', rest):
            lab = html.unescape(a.group(2)).replace("\xa0", " ")
            d = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", lab)
            res = re.search(r"\b(Passed|Failed|Pass|Fail)\b", lab, re.I)
            if d and res and "2014-01-01" <= f"{d.group(3)}-{int(d.group(1)):02d}-{int(d.group(2)):02d}" <= str(pd.Timestamp.today().date()):
                ins.append((f"{d.group(3)}-{int(d.group(1)):02d}-{int(d.group(2)):02d}",
                            "Pass" if res.group(1).lower().startswith("pass") else "Fail", "https://www.lewistonmaine.gov" + a.group(1)))
        if ins:
            out.append({"name": name, "addr": re.sub(r"\.$", "", addr), "inspections": sorted(set(ins))})
    return out


def load(cache=True):
    global _MAILNAMES
    path = f"{ME}/official.pkl"
    files = sorted(glob.glob(f"{OFF}/bablo/*.xlsx"))
    newest = max([os.path.getmtime(f) for f in files] + [os.path.getmtime(__file__), os.path.getmtime(f"{OFF}/lewiston/621.html")])
    if cache and os.path.exists(path) and os.path.getmtime(path) > newest:
        return pd.read_pickle(path)
    towns = town_names()
    ap = pd.read_parquet(f"{ME}/addresses_me.parquet", columns=["postal_city"])
    _MAILNAMES = towns | {canon_city(c) for c in ap.postal_city.dropna().unique()}
    ztown, _ = zip_towns()
    # a village's mailing name -> the town most of its address points are in ("York Beach" -> York, "Belgrade Lakes" -> Belgrade)
    pc = pd.read_parquet(f"{ME}/addresses_me.parquet", columns=["postal_city", "muni"]).dropna()
    pc["c"] = pc.postal_city.map(canon_city)
    share = pc.groupby("c").muni.agg(lambda x: (x.mode().iat[0], (x == x.mode().iat[0]).mean()))
    vtown = {c: t for c, (t, f) in share.items() if f >= 0.8}
    vtown.update(VILLAGES)
    src = files[-1]   # the newest monthly file
    d = pd.read_excel(src, "FOAA Report", dtype=str).drop(columns=["Legal Entity Name"])   # never kept
    d = d[d["Premises Type Name"].isin(KIND)].fillna("")
    rows = []
    for _, r in d.iterrows():
        street, city, z = split_address(r["Premises Address"], r["Premises Address Line 1"], r["Premises City/Town"], r["Premises Zip Code"])
        if not re.search(r"\bME\b", r["Premises Address"]) and r["Premises State"] not in ("ME", ""):
            continue
        mail = canon_city(city)
        town = mail if mail in towns else vtown.get(mail)
        num, st = street_key(street)
        if not re.match(r"\s*\d", street):   # "T16 R6 WELLS", "KINEO TOWNSHIP": no street number
            num, st = None, None
        rows.append({"jur": "bablo", "lic": r["License Number"], "ztown": ztown.get(z), "name": r["Premises Name"].strip() or None,
                     "keys": _names(r["Premises Name"]), "addr": street, "city": mail, "town": town, "zip": z, "num": num, "street": st,
                     "kind": KIND[r["Premises Type Name"]], "cls": CLASS.get(r["Premises Type Name"]), "ptype": r["Premises Type Name"],
                     "ltype": r["License Type"], "active": r["License Status"] == "Active", "expires": (r["License Expiration Date"] or "")[:10],
                     "insp": None})
    for e in lewiston():
        num, st = street_key(e["addr"])
        rows.append({"jur": "lewiston", "lic": "LEW-" + norm_name(e["name"]).replace(" ", "-"), "ztown": "Lewiston", "name": e["name"],
                     "keys": _names(e["name"]), "addr": e["addr"], "city": "Lewiston", "town": "Lewiston", "zip": "", "num": num,
                     "street": st, "kind": "food", "cls": None, "ptype": None, "ltype": None,
                     # a city page lists places inspected since 2014: only a 2024+ inspection says it's current
                     "active": e["inspections"][-1][0] >= "2024-01-01", "expires": "", "insp": e["inspections"]})
    df = pd.DataFrame(rows)
    df = df[df.name.notna()].reset_index(drop=True)
    g = [geocode(a, t, z) or (geocode(a, zt, z) if t is None and isinstance(zt, str) else None)
         for a, t, z, zt in zip(df.addr, df.town, df.zip, df.ztown)]
    df["lat"] = [x[0] if x else np.nan for x in g]
    df["lon"] = [x[1] if x else np.nan for x in g]
    df["town"] = [x[2] if x else (t if isinstance(t, str) else zt) for x, t, zt in zip(g, df.town, df.ztown)]
    df["geo_exact"] = [bool(x and x[3]) for x in g]
    df["source_file"] = os.path.basename(src)
    # one business holds several licenses (on-premises + cocktails-to-go + a mobile bar): same address, a name in common
    from common import name_sim, _stems, GENERIC
    df["biz"] = np.arange(len(df))
    for (town, num, st), grp in df[df.num.notna() & df.street.notna()].groupby(["town", "num", "street"]):
        idx = list(grp.index)
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                ka, kb = df.at[idx[a], "keys"], df.at[idx[b], "keys"]
                if any(name_sim(x, y) >= 85 or ((_stems(x) - GENERIC) & (_stems(y) - GENERIC)) for x in ka for y in kb):
                    old, new = df.at[idx[b], "biz"], df.at[idx[a], "biz"]
                    df.loc[df.biz == old, "biz"] = new
    df.to_pickle(path)
    return df


if __name__ == "__main__":
    df = load(cache=False)
    a = df[df.active]
    print("source:", df.source_file.iat[0], "| records:", len(df), "| active:", len(a), "| placed on an address point:", f"{a.lat.notna().mean():.1%}")
    print(a.groupby(["jur", "kind"]).agg(n=("lic", "size"), biz=("biz", "nunique"), placed=("lat", lambda s: round(s.notna().mean(), 3))).to_string())
    print("active on-premise businesses:", a[a.kind.isin(ON_PREMISE)].biz.nunique(), "| towns:", a.town.nunique())
    print(a[a.lat.isna() & a.kind.isin(ON_PREMISE)][["name", "addr", "city", "town", "zip"]].head(20).to_string())
    lw = df[df.jur == "lewiston"]
    print("Lewiston establishments:", len(lw), "| inspected 2024+:", int(lw.active.sum()),
          "| latest inspection:", max(i[0] for x in lw.insp for i in x))
