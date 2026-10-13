"""Writes the public website in docs/ from the same data file the app ships (data/app/places.json).

Pages: the landing page; one guide page per Maine classic with at least 5 hand-checked places (lobster shacks and rolls, clam
shacks, red snappers and Italians, whoopie pies and donuts, Franco-American food, diners, oyster bars, dairy bars), Maine icons
and Maine's oldest restaurants; one page per big town and a cities hub; the 8 regions; one page per hand-checked or honored place;
about, privacy, terms and 404; the web app at explore/; plus sitemap.xml, robots.txt, site.webmanifest, the license texts, the web
app's data files and playbook/site-numbers.json. Everything listed is hand-checked research or licensed open data; nothing comes
from Google or any ratings site, and nothing is ranked by ratings.

Every page gets a strict Content-Security-Policy <meta> built from sha256 hashes of its own inline <script> and <style> blocks,
so a page with an inline style attribute, event handler or unhashed script fails here, at build time.

Ported from ct-eats/scripts/make-site.py (Connecticut), with the place, region, cities-hub and about pages of
wi-eats/scripts/make-site.py (Wisconsin). Never hand-edit docs/*.html: change this file and re-run it.

Usage (from me-eats/): .venv/bin/python scripts/make-site.py
Re-run it after every data rebuild, then run scripts/qa-site.py. When the restaurant or town count changes, it also redraws
docs/og.png (swift scripts/make-brand.swift og), whose tagline carries those numbers.
"""
import base64
import datetime
import hashlib
import html
import json
import math
import os
import re
import shutil
import subprocess
import unicodedata
import urllib.parse
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS = f"{ROOT}/docs"
# Where the site lives. Today: GitHub Pages at the project address, because maine.eatsranked.com has no DNS record yet.
# Once Nick adds the Cloudflare record (CNAME maine -> nickstrom5.github.io, DNS only) and `dig` shows it, set
# CUSTOM_DOMAIN = "maine.eatsranked.com", re-run, push, and switch MaineEats/App/Links.swift with it.
# GitHub then forwards the old github.io links (the ones inside shipped app builds) to it.
CUSTOM_DOMAIN = None
DOMAIN = f"https://{CUSTOM_DOMAIN}" if CUSTOM_DOMAIN else "https://nickstrom5.github.io/maine-eats"
BASE = "" if CUSTOM_DOMAIN else "/maine-eats"     # path prefix for root-relative links
BRAND = "Maine Eats"
SHORT = "Maine Eats"                              # the Home Screen label (CFBundleDisplayName)
APP_NAME = "Maine Eats: Restaurants"              # the App Store name
TAGLINE = "Lobster shack & clam guide"
# the public contact address (Nick, 2026-10-12: Cloudflare Email Routing on eatsranked.com). The app's own About screen
# (MaineEats/App/Links.swift) and the App Store listing switch in the app's next build; the site uses this one everywhere.
EMAIL = "nick@eatsranked.com"
OLD_EMAIL = "work-with-nick@" + "gmail.com"     # must never appear on the site again (split so a grep of this file finds no address)
PARENT = {"@type": "Organization", "@id": "https://eatsranked.com/#organization", "name": "Eats Ranked", "url": "https://eatsranked.com/"}
AUTHOR = "Nicholas Soderstrom"                    # the app's maker (the app's About screen names him); name only, never an email
# Once the App Store listing exists, paste its URL here (looks like https://apps.apple.com/app/id123456789) and re-run: every
# "Get early access" button becomes an App Store link (Apple's official badge if docs/img/app-store-badge.svg is there; get it
# from Apple's marketing tools, never draw the Apple logo), the notes stop saying "coming", the privacy page says the label "is",
# and the web app's place panel links the App Store (it reads window.APP_STORE_URL).
APP_STORE_URL = ""
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

D = json.load(open(f"{ROOT}/data/app/places.json"))
SHAPES = json.load(open(f"{ROOT}/data/app/me_shapes.json"))
TOWN_SHAPES = json.load(open(f"{ROOT}/data/me/me_towns.geojson"))["features"]
DATA_DATE = D["generated"]
# when the hand checks behind hc=1 were done (each against a 2025 or 2026 source); the app's About screen says the same
CHECKED = D.get("research_checked") or "October 2026"
_y = int(re.search(r"\d{4}", CHECKED).group())
SOURCE_YEARS = f"{_y - 1} or {_y}"
# datePublished: the day these pages were first generated. Set it to the day Nick first publishes the site, then leave it.
PUBLISHED = "2026-10-09"
# change these when the policy or terms text changes, not on every build (2026-10-12: the contact address moved to EMAIL)
PRIVACY_UPDATED = TERMS_UPDATED = "2026-10-12"
# the last real change to the pages' own text (2026-10-12: the QA pass rewrote the home page, FAQ, guide and region copy, titles
# and the footer), so the sitemap's lastmod and each Article's dateModified aren't older than what they describe
COPY_UPDATED = "2026-10-12"
LASTMOD = max(PUBLISHED, DATA_DATE, COPY_UPDATED)
DATA_YEAR = int(DATA_DATE[:4])


def nice_date(iso):
    y, m, d = iso.split("-")
    return f"{MONTHS[int(m) - 1]} {int(d)}, {y}"


def long_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d:%B} {d.day}, {d.year}"


CITIES, VILLAGES, CUISINES, HOSTS, REGIONS = D["cities"], D["villages"], D["cuisines"], D["hosts"], D["regions"]
# the bit meanings must match the app (MaineEats/Models/Place.swift: PlaceTags and Kinds)
assert D["tags"] == ["lobster", "clams", "hotdog", "italian", "whoopie", "donut", "franco", "diner", "oyster", "dairy"], D["tags"]
assert D["kinds"] == ["lobster shack", "lobster roll", "clam shack", "red snapper", "italian sandwich", "whoopie pie", "potato doughnut",
                      "blueberry pie", "franco american", "diner", "oyster bar", "dairy bar", "oldest"], D["kinds"]
assert HOSTS == ["Hollywood Casino Bangor", "Oxford Casino"], HOSTS
TAG = {t: 1 << i for i, t in enumerate(D["tags"])}
KIND = {k: 1 << i for i, k in enumerate(D["kinds"])}
# Kinds.labels in Place.swift
KIND_LABEL = {"lobster shack": "Lobster shack", "lobster roll": "Lobster roll", "clam shack": "Clam shack", "red snapper": "Red snappers",
              "italian sandwich": "Maine Italians", "whoopie pie": "Whoopie pies", "potato doughnut": "Potato donuts", "blueberry pie": "Blueberry pie",
              "franco american": "Franco-American", "diner": "Diner", "oyster bar": "Oyster bar", "dairy bar": "Dairy bar", "oldest": "Historic"}
ALL_TOWNS = sorted(f["properties"]["town"] for f in TOWN_SHAPES)
N_ALL_TOWNS = len(ALL_TOWNS)
assert N_ALL_TOWNS == 529, N_ALL_TOWNS
COUNTY_OF_TOWN = {f["properties"]["town"]: f["properties"]["county"] for f in TOWN_SHAPES}
REGION_OF_TOWN = {CITIES[i]: REGIONS[r] for i, r in enumerate(D["town_region"]) if r is not None}
# the Maine Office of Tourism's eight regions, drawn on county lines (pipeline/fetch_towns.py); southwest coast first, then up the
# coast, then inland and north. Must be exactly the data's eight.
REGION_ORDER = ["Maine Beaches", "Greater Portland & Casco Bay", "Midcoast & Islands", "Downeast & Acadia", "Lakes & Mountains",
                "Kennebec Valley", "Maine Highlands", "Aroostook County"]
assert sorted(REGION_ORDER) == sorted(REGIONS), REGIONS
REGION_COUNTIES = {r: sorted(c["name"] for c in SHAPES["counties"] if c["region"] == r) for r in REGION_ORDER}
assert all(REGION_COUNTIES.values()) and sum(len(v) for v in REGION_COUNTIES.values()) == 16, REGION_COUNTIES
# Where a casino restaurant really is: only a place at the casino's own address is "inside" it. The pipeline's host match
# (pipeline/maine.py CASINOS: anything within 0.8 km) also catches downtown Bangor pubs and South Paris shops, so a host label
# shows only at these addresses; the others are reported on each build until the pipeline is fixed.
HOST_AT = {"Hollywood Casino Bangor": ("Bangor", "500 Main St", "Inside Hollywood Casino Hotel & Raceway in Bangor."),
           "Oxford Casino": ("Oxford", "777 Casino Way", "Inside Oxford Casino Hotel in Oxford.")}
HOST_DROPPED = []
STATE_HIP = "https://apps.web.maine.gov/online/hip_search/health-inspection-search.html"
LEWISTON_PAGE = "https://www.lewistonmaine.gov/621/Restaurant-Inspection-Reports"
BABLO_PAGE = "https://www.maine.gov/dafs/bablo/liquor-licensing/license-data"
SUFFIX = re.compile(r"\s+(plt|plantation|twp|township)$", re.I)


def village_ok(v, city):
    """A village name worth showing: not the town's own name with a plantation or township word added ("The Forks PLT" in
    The Forks), not another town's name, and not the start of the town's name."""
    if not v or v in ALL_TOWNS or (city or "").startswith(v):
        return False
    return SUFFIX.sub("", v).lower() != (city or "").lower()


# Restaurant websites the site never links: hacked (hidden casino, pharma or porn links, injected scripts), expired, taken over, another
# business's page or a directory listing. pipeline/website_blocklist.json is a list of {"domain", "match": "domain" (that registered
# domain and every subdomain; the default) | "url" (that one page: "url", else "domain" holding a path), "place", "reason", "severity",
# "evidence", "found"}. A place keeps everything else: only its website link goes, from every page and from the web app's detail.json,
# and it shows like any place without a website. More entries (the link sweep's batch files) need no code change: merge them with
# scripts/merge-blocklist.py and re-run this script. qa-site.py fails if a listed domain or URL is anywhere in docs/, or if the file is
# missing or empty (its first entry is a sentinel for a domain that can't exist, so the check is never vacuous).
# WEBSITE_BLOCKLIST=<file> swaps in another list (used only to prove the mechanism on a test entry).
BLOCKLIST_FILE = os.environ.get("WEBSITE_BLOCKLIST") or f"{ROOT}/pipeline/website_blocklist.json"
BLOCKLIST = json.load(open(BLOCKLIST_FILE, encoding="utf-8"))
assert isinstance(BLOCKLIST, list) and BLOCKLIST, f"{BLOCKLIST_FILE}: must be a non-empty list"
for _b in BLOCKLIST:
    assert isinstance(_b, dict) and _b.get("domain") and _b.get("match", "domain") in ("domain", "url") and _b.get("reason"), \
        f"{BLOCKLIST_FILE}: each entry needs domain, match (domain|url) and reason: {_b!r}"


def _url_key(u):
    """An exact page, whatever its scheme, www. or trailing slash: "HTTPS://www.X.com/a/" -> "x.com/a"."""
    return re.sub(r"^(?:https?:)?//", "", str(u).strip(), flags=re.I).lower().removeprefix("www.").rstrip("/")


def _bl_key(b):
    return _url_key(b.get("url") or b["domain"]) if b.get("match") == "url" else b["domain"].strip().lower().removeprefix("www.").rstrip(".")


BLOCKED = Counter()        # entry key -> website links left out
BLOCKED_PLACES = defaultdict(list)


def blocked_by(u):
    """The blocklist entry key that covers website `u`, or None. Domain entries first, so a page on a blocked domain counts there."""
    host = (urllib.parse.urlsplit(u).hostname or "").lower().rstrip(".")
    for b in BLOCKLIST:
        if b.get("match", "domain") == "domain" and (host == _bl_key(b) or host.endswith("." + _bl_key(b))):
            return _bl_key(b)
    for b in BLOCKLIST:
        if b.get("match") == "url" and _url_key(u) == _bl_key(b):
            return _bl_key(b)
    return None


class P:
    """One place, with the same meaning the app gives each field (MaineEats/Models/Place.swift)."""

    def __init__(self, i, r):
        self.i, self.r = i, r
        self.id = r["id"]
        self.name = r["n"]
        self.city = CITIES[r["c"]] if r.get("c") is not None else ""
        v = VILLAGES[r["vi"]] if r.get("vi") is not None else None
        self.village = v if village_ok(v, self.city) else None
        self.region = REGION_OF_TOWN.get(self.city)
        self.county = COUNTY_OF_TOWN.get(self.city)
        self.cuisine = CUISINES[r["cu"]]
        self.addr = r.get("a") or ""
        self.zip = r.get("z") or ""
        self.lat, self.lon = r.get("la"), r.get("lo")
        self.t = r.get("t") or 0
        self.j = r.get("j")
        self.lk = r.get("lk") or ""        # the BABLO premises class; never the license holder (the data has none)
        self.tags = r.get("g") or 0
        self.kinds = r.get("k") or 0
        self.hc = r.get("hc") == 1   # hand-checked open with a 2025-26 source; the only places the guides list
        self.venue = r.get("v") == 1
        self.chain_n = r.get("ch") or 1
        self.chain = self.chain_n >= 5
        self.ip = r.get("ip")        # iconic points: true icons only (honors, or 40+ years at the address); never shown
        self.fs = r.get("fs")        # the featured score every hand-checked place has (the app's "Featured first")
        self.founded = r.get("f")    # the year at this address (not the brand's founding year)
        self.note = r.get("note") or ""
        self.dish = r.get("dish") or ""
        self.season = r.get("sea") or ""
        self.seasonal = r.get("seas") == 1
        self.branch = r.get("br") or ""
        self.chef = r.get("chef") or ""
        # the James Beard Foundation calls its finalists "nominees" (as Connecticut's site does)
        self.jbf = re.sub(r"\bfinalist\b", "nominee", r.get("jbf") or "")
        self.hon = r.get("hon") or ""
        self.h = r.get("h") or 0
        host = HOSTS[r["host"]] if r.get("host") is not None else None
        if host and (self.city, self.addr) != HOST_AT[host][:2]:
            HOST_DROPPED.append(f"{self.name} ({self.addr}, {self.city}) is not at {host}")
            host = None
        self.host = host
        w = r.get("w") or ""
        self.site = w if urllib.parse.urlsplit(w).scheme in ("http", "https") and urllib.parse.urlsplit(w).hostname else ""
        if self.site and blocked_by(self.site):   # hacked, expired or not the place's own site: the link goes, the place stays
            BLOCKED[blocked_by(self.site)] += 1
            BLOCKED_PLACES[blocked_by(self.site)].append(f"{self.name} ({self.city})")
            self.site = ""
        ph = r.get("ph") or ""
        self.phone = ph if re.fullmatch(r"\+1[2-9]\d{9}", ph) else ""   # a valid US number only; anything else could dial abroad
        lw = r.get("lw")
        # the City of Lewiston's latest posted result: Pass or Fail with its date, and the city's report (http(s) only)
        if lw and lw.get("r") in ("Pass", "Fail") and re.fullmatch(r"\d{4}-\d{2}-\d{2}", lw.get("d") or "") and self.city == "Lewiston":
            u = lw.get("u") or ""
            self.lw = {"r": lw["r"], "d": lw["d"], "u": u if urllib.parse.urlsplit(u).scheme in ("http", "https") else "", "n": lw.get("n") or ""}
        else:
            self.lw = None
        self.slug = None

    @property
    def place_name(self):
        """"Cape Neddick (York)" or "Portland", as the app's Place.placeName."""
        return f"{self.village} ({self.city})" if self.village else self.city

    @property
    def jb_label(self):
        # the best honor only, and never a nominee called a winner (Place.jamesBeardLabel)
        return ("America's Classic" if self.h & 1 else "James Beard winner" if self.h & 2 else "James Beard nominee" if self.h & 4
                else "James Beard semifinalist" if self.h & 8 else None)

    def kind_names(self):
        return [KIND_LABEL[k] for k in D["kinds"] if self.kinds & KIND[k]]

    def featured_key(self):
        # the app's "Featured first": the featured score (else iconic points), then the verified year at this address, then name
        score = self.fs if self.fs is not None else self.ip
        return (-(score if score is not None else -1), self.founded or 9999, self.name.lower())

    def phone_text(self):
        return f"({self.phone[2:5]}) {self.phone[5:8]}-{self.phone[8:]}" if self.phone else ""


PLACES = [P(i, r) for i, r in enumerate(D["places"])]
REST = [p for p in PLACES if not p.venue]
assert all(not p.venue for p in PLACES if p.hc), "a hand-checked place is hidden as a non-restaurant"
assert all(p.hc for p in PLACES if p.ip is not None or p.fs is not None or p.founded), "a score or a year without hand-checking"
assert all(p.jb_label != "James Beard winner" or re.search(r"\bwinner\b", p.jbf, re.I) for p in PLACES), "a winner label without a win"
assert all(p.region for p in REST), [p.name for p in REST if not p.region][:5]
N_REST = len(REST)
assert N_REST == D["count_restaurants"], (N_REST, D["count_restaurants"])
TOWN_COUNT = Counter(p.city for p in REST if p.city)
N_TOWNS = len(TOWN_COUNT)


def guide(mask):
    return sorted([p for p in REST if p.hc and p.kinds & mask], key=P.featured_key)


# The app's guides (MaineEats/Models/Guide.swift): hand-checked only, by `k` kind bits. A listing merely named "... Lobster Pound"
# or "... Diner" stays in the directory but is not in a guide.
GUIDE_MASK = {"lobster": KIND["lobster shack"] | KIND["lobster roll"], "clams": KIND["clam shack"],
              "sandwiches": KIND["red snapper"] | KIND["italian sandwich"],
              "sweets": KIND["whoopie pie"] | KIND["potato doughnut"] | KIND["blueberry pie"], "franco": KIND["franco american"],
              "diners": KIND["diner"], "oysters": KIND["oyster bar"], "dairy": KIND["dairy bar"]}
GUIDE_TITLE = {"lobster": "Lobster Shacks & Rolls", "clams": "Clam Shacks", "sandwiches": "Red Snappers & Italians",
               "sweets": "Whoopie Pies & Donuts", "franco": "Franco-American", "diners": "Diners", "oysters": "Oyster Bars", "dairy": "Dairy Bars"}
G = {k: guide(m) for k, m in GUIDE_MASK.items()}
LOBSTER, CLAMS, SAND, SWEETS, FRANCO, DINERS, OYSTERS, DAIRY = (G[k] for k in GUIDE_MASK)
ICONS = sorted([p for p in REST if p.ip is not None], key=lambda p: (-p.ip, p.name.lower()))   # Guide.icons: iconic points
LONG_RUNNING_YEAR = int(D["generated"][:4]) - 40
# Guide.oldest (Place.isLongRunning): 40 or more years at the same address, counted from the data's own year
OLDEST = sorted([p for p in REST if p.founded and p.founded <= LONG_RUNNING_YEAR], key=lambda p: (p.founded, p.name.lower()))
HC = [p for p in REST if p.hc]
CLASSIC = [p for p in HC if p.kinds & sum(GUIDE_MASK.values())]
CASINO = [p for p in REST if p.host]
LEWISTON_RESULTS = [p for p in REST if p.lw]
# a guide gets its own page once it has at least this many places (the web app shows every guide whatever its size)
MIN_GUIDE_PAGE = 5
# the app offers a classic as a list (Home, iPad sidebar) only with at least this many places (MaineEats/Models/AppModel.swift)
APP_MIN_GUIDE = 4
NAMED_IN_TOWN = {t: Counter(p.city for p in REST if p.tags & TAG[t] and not p.hc) for t in D["tags"]}
NAMED = {t: sum(NAMED_IN_TOWN[t].values()) for t in D["tags"]}

# ---------------------------------------------------------------- html helpers
e = html.escape


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower().replace("'", "").replace("’", "")).strip("-")


def and_list(xs):
    xs = list(xs)
    if not xs:
        return ""
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def isare(n):
    return "is" if n == 1 else "are"


def plural(n, one, many=None):
    return f"{n:,} {one if n == 1 else (many or one + 's')}"


def lc(s):
    """Lowercase for the middle of a sentence, keeping the proper nouns: "Red snappers & Italians" -> "red snappers & Italians"."""
    t = s.lower()
    for w in ("Italian", "Franco-American", "Maine", "James Beard"):
        t = re.sub(rf"\b{w.lower()}", w, t)
    return t


def cap(s):
    return s[:1].upper() + s[1:]


def miles(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def explore_url(**params):
    """A web app link with its state in the hash, e.g. explore_url(g="all", town="Portland", kind="Seafood")."""
    return "/explore/#" + urllib.parse.urlencode(params)


def checked_open(ps):
    """'checked open in October 2026', or 'checked in business ...' when the list has seasonal places, which may be closed for
    the season right now (a winter closing isn't a closure). Never "confirmed" or "verified" open: a hand check is a check."""
    return f"checked in business in {CHECKED}" if any(p.seasonal for p in ps) else f"checked open in {CHECKED}"


# A private address must never reach a public page. Only the sha256 digests of its pieces live here (the address, its user and
# domain), so this public file doesn't spell it out; private_words() reports any word or email on a page that hashes to one.
PRIVATE_DIGESTS = {
    "4a7e25559b2ffc162afaef2b1680778c6e77d8c2982c3870595f6ee8fea7a455",
    "ff8ea15b513b5561b1c48b725aff52338eddb8ecdd46af58759e2f2c554b0582",
    "31b7679e2f02e2b0561693acc0c78f067633b6713ac53fb5980dcb0f7c2ea237",
    "928009cbd52e0a32a3542c0f41efa0ac8feef2e05974b8126f26c7d4f9b593e3",
}


def private_words(text):
    t = text.lower()
    words = set(re.findall(r"[\w.%+-]+@[\w.-]+", t)) | set(re.findall(r"[a-z0-9]+(?:\.[a-z0-9]+)*", t)) | set(re.findall(r"[a-z0-9]+", t))
    return [w for w in words if hashlib.sha256(w.encode()).hexdigest() in PRIVATE_DIGESTS]


# ---------------------------------------------------------------- brand mark and header wave
def _n(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


def lobster_roll_svg(size=32):
    """The app icon in miniature (roll() in scripts/make-brand.swift; redrawn 2026-10-09 in the shared Eats Ranked icon style,
    ../state-prompts/ICON-STYLE.md): a split-top bun, toasted side out with a lighter crust on top, lobster meat heaped in the split
    over a line of lettuce, and one red claw lying level on top inside a thin teal ring, on flat deep ocean teal. Flat shapes only,
    no letters."""
    s = 64.0
    Y = lambda v: s - v * s      # make-brand.swift draws with y up
    X = lambda v: v * s
    pt = lambda x, y: f"{_n(X(x))} {_n(Y(y))}"
    ocean, toast, crust, red, meat, lettuce = "#0E4D5C", "#D38B39", "#F0C47E", "#D8402A", "#F8E0D0", "#7DB548"
    parts = [f'<rect width="64" height="64" rx="14" fill="{ocean}"/>']
    # the meat: five chunks, back pair first; each red with a white oval inside it, dropped and nudged so the red shows as a crescent
    chunks = [(.37, .555, .115, .075, .03, -.03), (.63, .555, .115, .075, .03, .03),
              (.245, .50, .095, .072, .03, .045), (.50, .51, .12, .075, .032, -.03), (.755, .50, .095, .072, .03, -.045)]
    for i, (x, y, rx, ry, cap, lean) in enumerate(chunks):
        oval = f'cx="{_n(X(x))}" cy="{_n(Y(y))}" rx="{_n(X(rx))}" ry="{_n(X(ry))}"'
        parts.append(f'<clipPath id="logo-c{i}"><ellipse {oval}/></clipPath><ellipse {oval} fill="{red}"/>'
                     f'<ellipse cx="{_n(X(x + lean))}" cy="{_n(Y(y - cap))}" rx="{_n(X(rx + .02))}" ry="{_n(X(ry))}" fill="{meat}" '
                     f'clip-path="url(#logo-c{i})"/>')
    # the bun: 0.72 x 0.24, flat bottom, soft ends, top edge dipping a little; the lettuce line follows its top edge
    x0, x1, y0, y1, low, high, dip = .14, .86, .22, .46, .095, .075, .016
    parts.append(f'<path d="M{pt(x0 + .05, y1 + .002)} Q{pt(.5, y1 + .002 - 2 * dip)} {pt(x1 - .05, y1 + .002)}" fill="none" '
                 f'stroke="{lettuce}" stroke-width="{_n(X(.05))}" stroke-linecap="round"/>')
    bun = (f"M{pt(x0 + low, y0)} L{pt(x1 - low, y0)} Q{pt(x1, y0)} {pt(x1, y0 + low)} L{pt(x1, y1 - high)} Q{pt(x1, y1)} {pt(x1 - high, y1)} "
           f"Q{pt(.5, y1 - 2 * dip)} {pt(x0 + high, y1)} Q{pt(x0, y1)} {pt(x0, y1 - high)} L{pt(x0, y0 + low)} Q{pt(x0, y0)} {pt(x0 + low, y0)} Z")
    yb = y1 - .06
    top = f"M{pt(0, yb)} L{pt(x0, yb)} Q{pt(.5, yb - 2.5 * dip)} {pt(x1, yb)} L{pt(1, yb)} L{pt(1, 1)} L{pt(0, 1)} Z"
    parts.append(f'<clipPath id="logo-bun"><path d="{bun}"/></clipPath><path d="{bun}" fill="{toast}"/>'
                 f'<path d="{top}" fill="{crust}" clip-path="url(#logo-bun)"/>')
    # the claw, level, pincers to the right: knuckle, hand with its fixed finger, moving finger; one teal ring under all three
    L, ox, oy = .56, .5 - .56 / 2, .665
    q = lambda x, y: pt(ox + x * L, oy + y * L)
    knuckle = f'<ellipse cx="{_n(X(ox + .08 * L))}" cy="{_n(Y(oy))}" rx="{_n(X(.08 * L))}" ry="{_n(X(.095 * L))}"/>'
    hand = (f"M{q(.12, .08)} C{q(.16, .15)} {q(.23, .185)} {q(.32, .185)} C{q(.42, .185)} {q(.48, .16)} {q(.51, .11)} "
            f"C{q(.52, .07)} {q(.53, .03)} {q(.55, 0)} C{q(.70, -.05)} {q(.85, -.07)} {q(.96, -.03)} "
            f"C{q(.88, -.12)} {q(.70, -.19)} {q(.38, -.19)} C{q(.24, -.19)} {q(.15, -.15)} {q(.12, -.08)} "
            f"C{q(.105, -.03)} {q(.105, .03)} {q(.12, .08)} Z")
    finger = (f"M{q(.44, .15)} C{q(.52, .25)} {q(.66, .28)} {q(.78, .26)} C{q(.87, .245)} {q(.94, .215)} {q(1.0, .145)} "
              f"C{q(.92, .125)} {q(.72, .09)} {q(.58, .05)} C{q(.51, .035)} {q(.44, .09)} {q(.44, .15)} Z")
    claw = f'{knuckle}<path d="{hand}"/><path d="{finger}"/>'
    parts.append(f'<g fill="none" stroke="{ocean}" stroke-width="{_n(X(.0254))}" stroke-linejoin="round">{claw}</g><g fill="{red}">{claw}</g>')
    return (f'<svg viewBox="0 0 64 64" width="{size}" height="{size}" aria-hidden="true" focusable="false">' + "".join(parts) + "</svg>")


LOGO = lobster_roll_svg(32)


def shoreline(n=6, w=1200, h=18):
    """The Maine coast under the teal header: a low sea-glass wave and a teal one (the app's Theme.Shoreline, two waves), then
    the page's own color coming up to meet them."""
    seg = w / n

    def wave(mid, amp):
        d = f"M0 {mid:.1f}"
        for i in range(n):
            x0 = i * seg
            d += f" C{x0 + seg * .33:.1f} {mid - amp:.1f} {x0 + seg * .66:.1f} {mid + amp:.1f} {x0 + seg:.1f} {mid:.1f}"
        return d + f" L{w} {h} L0 {h} Z"
    return (f'<svg class="shore" viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true" focusable="false">'
            f'<rect width="{w}" height="{h}" fill="#0E4D5C"/><path class="w1" d="{wave(5.5, 3.2)}"/><path class="w2" d="{wave(8.5, 3.2)}"/>'
            f'<path class="w3" d="{wave(14, 2.2)}"/></svg>')


SHORE = shoreline()

CSS = """
  :root {
    color-scheme: light dark;
    --bg: #fbf6ec; --surface: #fffdf8; --surface2: #f4eddf; --surface3: #e9e0cc; --rule: #e6dcc8; --rule2: #cdbea3;
    --ink: #10262e; --ink2: #2d4750; --muted: #566b70;
    --head: #0e4d5c; --link: #236b78; --fill: #0e4d5c; --onfill: #fff;
    --ctl: #236b78;   /* control outlines: 3:1 or more on every background */
    --buoy: #f2b705; --onbuoy: #10262e; --soft: #fbebc2; --onsoft: #5f4300;
    --coral: #c2492f;   /* a thin accent line only, never text */
    --focus: #c2492f; --chip: #f4eddf; --onchip: #0e4d5c;
    --wave1: #cde6e3; --wave2: #236b78;
    --pass: #1b6b3a; --fail: #a8321f;
    --radius: 16px;
    --text: -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif;
    --display: "Avenir Next Condensed", "HelveticaNeue-CondensedBold", "Arial Narrow", system-ui, sans-serif;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0c1a1f; --surface: #12242a; --surface2: #173038; --surface3: #21404a; --rule: #23393f; --rule2: #37545c;
      --ink: #f3ecdf; --ink2: #d6cebf; --muted: #a3b0ac;
      --head: #86d3d0; --link: #86d3d0; --fill: #86d3d0; --onfill: #0c1a1f; --ctl: #74c2c2;
      --onbuoy: #1a1400; --soft: #3a3011; --onsoft: #fbe3a0; --coral: #f08a6c; --focus: #f2b705; --chip: #173038; --onchip: #86d3d0;
      --wave1: #2f6f73; --wave2: #174f5a;
    }
  }
  * { box-sizing: border-box; }
  html { -webkit-text-size-adjust: 100%; }
  @media (prefers-reduced-motion: no-preference) { html { scroll-behavior: smooth; } }
  @media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
  body { margin: 0; background: var(--bg); color: var(--ink); font: 17px/1.55 var(--text); -webkit-font-smoothing: antialiased; }
  a { color: var(--link); text-underline-offset: 2px; }
  a:focus-visible, summary:focus-visible, button:focus-visible, select:focus-visible, input:focus-visible, [tabindex]:focus-visible { outline: 3px solid var(--focus); outline-offset: 3px; border-radius: 6px; }
  .skip { position: absolute; left: -9999px; top: 0; background: var(--buoy); color: var(--onbuoy); padding: 10px 14px; font-weight: 700; z-index: 30; }
  .skip:focus { left: 8px; top: 8px; }
  .sr { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
  .wrap { max-width: 760px; margin: 0 auto; padding: 0 20px; }
  header.site { background: #0e4d5c; color: #fff; }
  header.site .bar { display: flex; align-items: center; justify-content: space-between; gap: 6px 12px; padding: 12px 20px 6px; }
  .shore { display: block; width: 100%; height: 18px; }
  .shore .w1 { fill: var(--wave1); } .shore .w2 { fill: var(--wave2); } .shore .w3 { fill: var(--bg); }
  .logo { display: inline-flex; align-items: center; gap: 10px; min-height: 44px; font: 800 22px/1 var(--display); text-transform: uppercase; letter-spacing: .02em; color: #fff; text-decoration: none; }
  .logo svg { flex: 0 0 auto; border-radius: 8px; box-shadow: 0 0 0 1px rgba(255,255,255,.3); }
  header.site nav { display: flex; flex-wrap: wrap; gap: 0 14px; justify-content: flex-end; }
  header.site nav a, footer nav a, nav.crumbs a { display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; }
  header.site nav a { color: #e6f2f0; text-decoration: none; font-size: 15px; }
  header.site nav a:hover { color: #fff; text-decoration: underline; }
  header.site a:focus-visible { outline-color: #f2b705; }
  h1, h2 { font-family: var(--display); font-weight: 800; color: var(--head); letter-spacing: -.005em; }
  h1 { font-size: clamp(36px, 7.5vw, 56px); line-height: 1.02; margin: 0 0 16px; text-transform: uppercase; overflow-wrap: anywhere; }
  h2 { font-size: 32px; line-height: 1.1; margin: 0 0 10px; }
  h3 { font-size: 18px; margin: 0; line-height: 1.3; }
  .kicker { font: 700 15px/1.4 var(--text); letter-spacing: .06em; color: var(--muted); margin: 0 0 12px; }
  .lede { font-size: 19px; color: var(--ink2); margin: 0 0 26px; }
  .hero { padding: 36px 0 28px; }
  section { padding: 36px 0; border-top: 1px solid var(--rule); }
  section.hero { border: 0; }
  .sub { color: var(--ink2); margin: 0 0 22px; }
  .cta-row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
  .btn { display: inline-flex; align-items: center; justify-content: center; gap: 10px; min-height: 44px; background: var(--buoy); color: var(--onbuoy); font-weight: 700; padding: 12px 20px; border-radius: 14px; text-decoration: none; font-size: 17px; line-height: 1.2; }
  .btn-ghost { background: transparent; color: var(--head); border: 2px solid var(--ctl); }
  .btn-fill { background: var(--fill); color: var(--onfill); }
  .store-badge { display: inline-flex; min-height: 44px; align-items: center; }
  .store-badge img { display: block; height: 50px; width: auto; }
  .pill { font-size: 14px; color: var(--muted); }
  .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 28px 0 0; padding: 0; list-style: none; }
  .stats li { background: var(--surface); border: 1px solid var(--rule); border-top: 3px solid var(--coral); border-radius: 14px; padding: 14px; }
  .stats b { display: block; font: 800 30px/1 var(--display); color: var(--head); }
  .stats span { font-size: 14px; color: var(--muted); }
  .steps { display: grid; gap: 12px; list-style: none; margin: 0; padding: 0; }
  .step { display: flex; gap: 14px; background: var(--surface); border: 1px solid var(--rule); border-radius: var(--radius); padding: 18px; }
  .step .n { flex: 0 0 32px; height: 32px; border-radius: 50%; background: var(--buoy); color: var(--onbuoy); font-weight: 800; display: grid; place-items: center; }
  .step p { margin: 4px 0 0; color: var(--ink2); }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .card { background: var(--surface); border: 1px solid var(--rule); border-radius: var(--radius); padding: 18px; }
  .card p { margin: 6px 0 0; color: var(--ink2); }
  a.card { display: block; text-decoration: none; color: var(--ink); }
  a.card h3 { color: var(--head); }
  a.card:hover h3 { text-decoration: underline; }
  .towns { display: flex; flex-wrap: wrap; gap: 8px; list-style: none; padding: 0; margin: 0; }
  .towns a { display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; padding: 8px 14px; border-radius: 999px; border: 1px solid var(--rule2); background: var(--surface); text-decoration: none; color: var(--ink); font-size: 15px; }
  .towns a:hover { border-color: var(--ctl); }
  details { background: var(--surface); border: 1px solid var(--rule); border-radius: 14px; padding: 2px 18px; margin-bottom: 10px; }
  summary { cursor: pointer; padding: 12px 0; min-height: 44px; font-weight: 600; list-style: none; display: flex; justify-content: space-between; align-items: center; gap: 12px; }
  summary::-webkit-details-marker { display: none; }
  summary::after { content: "+"; color: var(--head); font-weight: 800; }
  details[open] summary::after { content: "\\2013"; }
  details p { margin: 0 0 16px; color: var(--ink2); }
  .final { text-align: center; }
  .final .cta-row { justify-content: center; }
  nav.crumbs { font-size: 14px; color: var(--muted); padding: 6px 0 0; }
  nav.crumbs ol { list-style: none; padding: 0; margin: 0; display: flex; flex-wrap: wrap; align-items: center; gap: 0 6px; }
  nav.crumbs li { display: inline-flex; align-items: center; min-height: 44px; }
  nav.crumbs li + li::before { content: "/"; content: "/" / ""; margin-right: 6px; color: var(--muted); }   /* the separator has no spoken text */
  nav.crumbs a { color: var(--muted); }
  .places { list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; }
  .places li { background: var(--surface); border: 1px solid var(--rule); border-radius: 14px; padding: 14px 16px; min-width: 0; overflow-wrap: anywhere; scroll-margin-top: 12px; }
  .places h3 a { display: block; padding: 11px 0; margin: -11px 0; text-decoration: none; color: var(--head); }
  .places h3 a:hover { text-decoration: underline; }
  .places .where { margin: 2px 0 0; font-size: 15px; color: var(--muted); }
  .places .facts { margin: 8px 0 0; font-size: 15px; color: var(--ink2); }
  .places .facts b { color: var(--ink); font-weight: 600; }
  .places .note { margin: 6px 0 0; font-size: 15px; color: var(--ink2); }
  .places .link { font-size: 15px; margin: 2px 0 -8px; }
  .places .link a, .toc a, .plinks a, .near a, td a { display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; }
  .places li.again { padding-top: 8px; padding-bottom: 8px; }
  .tag { display: inline-block; font-size: 12px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; background: var(--soft); color: var(--onsoft); border-radius: 6px; padding: 1px 6px; margin: 0 4px 2px 0; }
  .tag-jb { background: var(--fill); color: var(--onfill); }
  .tag-plain { background: var(--chip); color: var(--onchip); }
  .tag-dash { background: transparent; color: var(--muted); border: 1px dashed var(--ctl); }
  .toc { columns: 2; padding-left: 20px; margin: 0; }
  .near { list-style: none; padding: 0; margin: 0; }
  .near span { display: block; font-size: 14px; color: var(--muted); margin: -8px 0 6px; }
  .actions { display: flex; flex-wrap: wrap; gap: 10px; margin: 6px 0 0; }
  .actions .btn { font-size: 16px; padding: 10px 16px; }
  dl.facts { display: grid; grid-template-columns: max-content 1fr; gap: 10px 18px; margin: 0 0 18px; }
  dl.facts dt { font-weight: 700; color: var(--ink); }
  dl.facts dd { margin: 0; color: var(--ink2); }
  dl.facts ul { margin: 0; padding-left: 18px; }
  dl.facts dd a { display: inline-flex; align-items: center; min-height: 44px; }
  .addr { font-size: 17px; color: var(--ink2); margin: 0 0 14px; }
  .qa h3 { margin: 22px 0 6px; font-size: 19px; }
  .qa p { margin: 0 0 10px; color: var(--ink2); }
  .result { display: flex; align-items: center; gap: 12px; margin: 0 0 10px; }
  .rb { flex: 0 0 auto; display: inline-block; padding: 4px 9px; border-radius: 7px; color: #fff; font: 800 15px/1.2 var(--text); letter-spacing: .05em; text-transform: uppercase; }
  .rb-pass { background: var(--pass); } .rb-fail { background: var(--fail); }
  table { border-collapse: collapse; width: 100%; font-size: 15px; }
  th, td { text-align: left; padding: 8px 6px; border-bottom: 1px solid var(--rule); }
  td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; }
  .tablewrap { overflow-x: auto; }
  .fine { font-size: 14px; color: var(--muted); }
  .legal h2 { font-size: 26px; margin-top: 28px; }
  .legal p, .legal li { color: var(--ink2); }
  .notice { white-space: pre-wrap; font-size: 14px; color: var(--ink2); background: var(--surface); border: 1px solid var(--rule); border-radius: 12px; padding: 14px; overflow-wrap: anywhere; margin: 0; font-family: var(--text); }
  footer { padding: 24px 0 56px; color: var(--muted); font-size: 14px; border-top: 1px solid var(--rule2); margin-top: 20px; }
  footer nav { display: flex; flex-wrap: wrap; gap: 0 18px; }
  footer a { color: var(--muted); }
  footer p { margin: 12px 0 0; }
  @media (max-width: 600px) {
    .grid2 { grid-template-columns: 1fr; }
    .stats { grid-template-columns: 1fr 1fr; }
    .toc { columns: 1; }
    header.site .bar { flex-direction: column; align-items: flex-start; padding: 10px 20px 4px; }
    header.site nav { justify-content: flex-start; }
    dl.facts { grid-template-columns: 1fr; gap: 2px; }
    dl.facts dd { margin-bottom: 10px; }
    table { font-size: 14px; }
    th, td { padding: 6px 4px; }
    th { font-size: 13px; line-height: 1.25; }
  }
"""


def find_keys(obj, keys):
    if isinstance(obj, dict):
        return [k for k in obj if k in keys] + [x for v in obj.values() for x in find_keys(v, keys)]
    if isinstance(obj, list):
        return [x for v in obj for x in find_keys(v, keys)]
    return []


def jsonld(obj):
    # no ratings or reviews from anyone, ever (structured data included)
    bad = find_keys(obj, {"aggregateRating", "review", "reviews", "reviewRating", "ratingValue", "reviewCount", "bestRating"})
    assert not bad, bad
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    # a name with "</script>" in it must not end the block: escape the characters HTML cares about (JSON reads them back the same)
    text = text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return '<script type="application/ld+json">' + text + "</script>"


def crumbs(trail):
    """trail: [(name, url)] ending with the current page."""
    items = "".join(f'<li><a href="{u}">{e(n)}</a></li>' if i < len(trail) - 1 else f'<li aria-current="page">{e(n)}</li>'
                    for i, (n, u) in enumerate(trail))
    ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": DOMAIN + u} for i, (n, u) in enumerate(trail)]}
    return f'<nav class="crumbs" aria-label="Breadcrumb"><ol>{items}</ol></nav>', ld


def store_button(label="Get early access"):
    if APP_STORE_URL:
        # Apple's own badge artwork only (never a drawn Apple logo); plain text until the badge file is in docs/img
        if os.path.exists(f"{DOCS}/img/app-store-badge.svg"):
            return (f'<a class="store-badge" href="{e(APP_STORE_URL)}" rel="noopener"><img src="/img/app-store-badge.svg" '
                    'alt="Download on the App Store" width="150" height="50"></a>')
        return f'<a class="btn store-btn" href="{e(APP_STORE_URL)}" rel="noopener">Download on the App Store</a>'
    # pre-launch: no App Store link exists yet, so the button asks for a TestFlight invite by email (Wisconsin's approach)
    return (f'<a class="btn store-btn" href="mailto:{EMAIL}?subject=Maine%20Eats%20early%20access&amp;body=Send%20me%20the%20TestFlight%20link.">'
            f'{label}</a>')


def store_note(text="An iPhone and iPad app, free."):
    return f"{text} Not in the App Store yet." if not APP_STORE_URL else text


# SEO-SPEC: the App Store smart banner. Until the App Store record exists every page carries the commented placeholder; once
# APP_STORE_URL is set, its id fills the real tag.
APPLE_ITUNES_PLACEHOLDER = '<!-- <meta name="apple-itunes-app" content="app-id=APP_ID"> fill in once the App Store record exists -->'


def apple_itunes_meta():
    m = re.search(r"/id(\d+)", APP_STORE_URL or "")
    return f'<meta name="apple-itunes-app" content="app-id={m.group(1)}">' if m else APPLE_ITUNES_PLACEHOLDER


def sha(x):
    return "'sha256-" + base64.b64encode(hashlib.sha256(x.encode()).digest()).decode() + "'"


def fit(options, lo, hi, used=None):
    """The first option whose length is within lo..hi (and, with `used`, not already taken by another page)."""
    for o in options:
        if lo <= len(o) <= hi and (used is None or o not in used):
            return o
    raise ValueError(f"nothing fits {lo}-{hi}: {[(len(o), o) for o in options][:8]}")


TITLES, DESCS = {}, {}
PAGES = []        # (path, lastmod) for the sitemap
written = []


def page(path, title, desc, body, lds=(), robots="index,follow,max-image-preview:large", og_alt=None, extra_css="", head_extra="",
         after="", lastmod=None):
    is404 = path == "404.html"
    if not is404:
        assert 50 <= len(title) <= 60, (path, len(title), title)
        assert 140 <= len(desc) <= 160, (path, len(desc), desc)
        assert title not in TITLES, ("duplicate title", path, TITLES.get(title))
        assert desc not in DESCS, ("duplicate description", path, DESCS.get(desc))
        TITLES[title], DESCS[desc] = path, path
    assert body.count("<h1") == 1, path
    url = DOMAIN + "/" + ("" if path == "index.html" else path.removesuffix("index.html"))
    # GitHub serves 404.html for every missing URL, so it names no canonical address of its own
    canonical = "" if is404 else f'<link rel="canonical" href="{url}">\n'
    og_url = "" if is404 else f'<meta property="og:url" content="{url}">\n'
    og_alt = og_alt or f"{BRAND}: {TAGLINE}. Maine restaurants, with hand-checked lobster shacks, clam shacks, diners and dairy bars."
    # every page names the site's Organization and its parent, Eats Ranked (the hub lists this site as a subOrganization);
    # a page whose own JSON-LD doesn't carry the #org node (places, privacy, terms, the towns hub, 404) gets it on its own
    lds = list(lds)
    if not any(f'"@id": "{DOMAIN}/#org"' in json.dumps(x) and '"parentOrganization"' in json.dumps(x) for x in lds):
        lds.append({"@context": "https://schema.org", **ORG})
    ld = "\n".join(jsonld(x) for x in lds)
    doc = f"""<!DOCTYPE html>
<html lang="en" data-base="{BASE}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
{canonical}<meta name="robots" content="{robots}">
<meta name="referrer" content="strict-origin-when-cross-origin">
<meta name="theme-color" content="#0E4D5C">
<meta name="color-scheme" content="light dark">
{apple_itunes_meta()}
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
{og_url}<meta property="og:type" content="{'website' if path == 'index.html' else 'article'}">
<meta property="og:site_name" content="{BRAND}">
<meta property="og:locale" content="en_US">
<meta property="og:image" content="{DOMAIN}/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(og_alt)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{DOMAIN}/og.png">
<meta name="twitter:image:alt" content="{e(og_alt)}">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
<link rel="icon" type="image/png" sizes="192x192" href="/icon-192.png">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
{head_extra}<style>{CSS}{extra_css}</style>
{ld}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site">
  <div class="bar wrap">
    <a class="logo" href="/" aria-label="{BRAND} home">{LOGO}{BRAND}</a>
    <nav aria-label="Main">
      <a href="/{GUIDE_FILE['lobster']}">Lobster</a>
      <a href="/{GUIDE_FILE['clams']}">Clams</a>
      <a href="/{GUIDE_FILE['dairy']}">Dairy bars</a>
      <a href="/cities/">Towns</a>
      <a href="/explore/">Search</a>
    </nav>
  </div>
  {SHORE}
</header>
<div class="wrap">
{body}
  <footer>
    <nav aria-label="Footer">
      <a href="/">{BRAND} app</a>
      <a href="/explore/">Search Maine restaurants</a>
      {"".join(f'<a href="/{u}">{e(n)}</a>' for u, n in FOOTER_PAGES)}
      <a href="/cities/">Towns and regions</a>
      <a href="/about.html">About and sources</a>
      <a href="/privacy.html">Privacy policy</a>
      <a href="/terms.html">Terms of use</a>
      <a href="mailto:{EMAIL}">Email us</a>
    </nav>
    <p>Place data: hand-checked research by {BRAND} (checked {CHECKED}); Overture Maps Foundation places (CDLA Permissive 2.0, Apache 2.0 for Foursquare data with the <a href="/about.html#foursquare">Foursquare NOTICE</a>, and CC0 for AllThePlaces); Maine Bureau of Alcoholic Beverages and Lottery Operations liquor license data (current as of {e(D.get("license_date") or "")}); City of Lewiston restaurant inspection reports; U.S. Census Bureau town outlines. In the app, maps and each place's live card come from Apple Maps. Data as of {nice_date(DATA_DATE)}.</p>
    <p>{BRAND} is independent: not affiliated with or endorsed by the State of Maine, Maine CDC or its Health Inspection Program, the Bureau of Alcoholic Beverages and Lottery Operations, the City of Lewiston, the James Beard Foundation, Michelin, Apple, or any restaurant, brand, team or chain. James Beard Foundation and James Beard Award are trademarks of the James Beard Foundation. Places open and close, and many close for the season, so check before you go.</p>
    <p>© 2026 {BRAND}, an independent app by {AUTHOR}. Part of <a href="https://eatsranked.com/">Eats Ranked</a>, restaurant apps state by state.</p>
  </footer>
</div>
{after}</body>
</html>
"""
    if BASE:   # served under /maine-eats/: every root-relative link and asset gets the prefix
        doc = re.sub(r'(href|src|srcset)="/', rf'\1="{BASE}/', doc)
    # A Content-Security-Policy in a meta tag (GitHub Pages can't send headers), first in <head>: only this page's own inline
    # scripts and styles run, by hash (JSON-LD blocks are data, not scripts), and nothing loads from any other site. The hashes
    # change with every edit, so they're computed here, after the last change to the page.
    assert not re.search(r"<script(?![^>]*application/ld\+json)[^>]+>", doc), f"{path}: only plain inline <script> and JSON-LD"
    assert not re.search(r"<[a-zA-Z][^>]*\sstyle=", doc), f"{path}: an inline style attribute would be blocked by the CSP"
    assert not re.search(r"<[a-zA-Z][^>]*\son[a-z]+=", doc), f"{path}: an inline event handler would be blocked by the CSP"
    assert "<!--" not in doc.replace(APPLE_ITUNES_PLACEHOLDER, ""), f"{path}: an HTML comment"
    scripts = re.findall(r"<script>(.*?)</script>", doc, re.S)
    styles = re.findall(r"<style>(.*?)</style>", doc, re.S)
    csp = (f"default-src 'none'; script-src {' '.join(map(sha, scripts)) or chr(39) + 'none' + chr(39)}; "
           f"style-src {' '.join(map(sha, styles)) or chr(39) + 'none' + chr(39)}; img-src 'self' data:; connect-src 'self'; "
           "manifest-src 'self'; base-uri 'none'; form-action 'none'; upgrade-insecure-requests")
    doc = doc.replace("<head>\n", f'<head>\n<meta http-equiv="Content-Security-Policy" content="{csp}">\n', 1)
    # data honesty, checked on every page: no Google-derived wording, no MICHELIN claims (only the about page's "there is no
    # MICHELIN Guide for Maine" and the trademark line), no private address, and Lewiston's Pass/Fail results only on a place's own
    # page (the web app shows them in the place panel), never in a list
    low = doc.lower()
    assert "google" not in low, path
    assert OLD_EMAIL not in low and f"mailto:{EMAIL}" in doc, f"{path}: the contact address is {EMAIL}"
    assert 'href="https://eatsranked.com/">Eats Ranked</a>' in doc, f"{path}: the footer's link back to Eats Ranked"
    assert not re.search(r"\b(confirmed|verified) open\b", low), f"{path}: a hand check is 'checked open', never 'confirmed open'"
    assert re.sub(r"there is no michelin guide for maine|michelin is a trademark of michelin|michelin,", "", low).count("michelin") == 0, path
    assert not private_words(doc), path
    markup = re.sub(r"<script>.*?</script>", "", doc, flags=re.S)   # the web app's own code draws the place panel
    if 'class="rb rb-' in markup or "City of Lewiston inspection:" in markup:
        assert path.startswith("places/"), path
    os.makedirs(os.path.dirname(f"{DOCS}/{path}"), exist_ok=True)
    open(f"{DOCS}/{path}", "w", encoding="utf-8").write(doc)
    if not is404:
        PAGES.append((path, lastmod or LASTMOD))
    return path


# ---------------------------------------------------------------- the pages every page links to
GUIDE_FILE = {"lobster": "maine-lobster-shacks.html", "clams": "maine-clam-shacks.html", "sandwiches": "maine-red-snappers-italians.html",
              "sweets": "maine-whoopie-pies-donuts.html", "franco": "maine-franco-american-food.html", "diners": "maine-diners.html",
              "oysters": "maine-oyster-bars.html", "dairy": "maine-dairy-bars.html"}
GUIDE_SHORT = {"lobster": "Lobster shacks & rolls", "clams": "Clam shacks", "sandwiches": "Red snappers & Italians", "sweets": "Whoopie pies & donuts",
               "franco": "Franco-American food", "diners": "Diners", "oysters": "Oyster bars", "dairy": "Dairy bars"}
ICONS_FILE = "maine-icons.html"
OLDEST_FILE = "maine-oldest-restaurants.html"
# a guide with fewer than MIN_GUIDE_PAGE places has no page of its own yet (Franco-American, until more research lands); the web app
# shows it anyway, and its page appears by itself once the data has enough
GUIDE_PAGE = [k for k in GUIDE_FILE if len(G[k]) >= MIN_GUIDE_PAGE]
assert {"lobster", "clams", "dairy"} <= set(GUIDE_PAGE), GUIDE_PAGE   # the header links these three
ICONS_PAGE = len(ICONS) >= MIN_GUIDE_PAGE
assert all(p.h or (p.founded and int(DATA_DATE[:4]) - p.founded >= 40) for p in ICONS), "an icon with neither honors nor 40 years"
FOOTER_PAGES = ([(GUIDE_FILE[k], GUIDE_SHORT[k]) for k in GUIDE_PAGE] + ([(ICONS_FILE, "Maine icons")] if ICONS_PAGE else [])
                + [(OLDEST_FILE, "Oldest restaurants")])


def guide_link(k):
    """The guide's page, or the web app's guide when it has no page yet."""
    return f"/{GUIDE_FILE[k]}" if k in GUIDE_PAGE else explore_url(g=k)


# ---------------------------------------------------------------- place pages: slugs first, so every list can link to them
CHECKED_PLACES = sorted([p for p in REST if p.hc or p.ip is not None or p.h], key=lambda p: (p.city, p.name.lower(), p.id))
_groups = defaultdict(list)
for p in CHECKED_PLACES:
    _groups[slug(f"{p.name} {p.city or 'maine'}")].append(p)
for _base, _ps in _groups.items():
    if len(_ps) == 1:
        _ps[0].slug = _base
        continue
    _with_addr = Counter(f"{_base}-{slug(p.addr)}" for p in _ps)
    for p in _ps:    # every member of a clash gets the same treatment, so slugs don't depend on order
        _s = f"{_base}-{slug(p.addr)}"
        p.slug = _s if _with_addr[_s] == 1 and p.addr else f"{_base}-{p.id[:8]}"
assert len({p.slug for p in CHECKED_PLACES}) == len(CHECKED_PLACES)
assert all(p.slug for p in CLASSIC + ICONS + OLDEST), "a listed place without its own page"


def place_url(p):
    return f"/places/{p.slug}.html"


# ---------------------------------------------------------------- regions and towns
REGION_SLUG = {r: slug(r) for r in REGION_ORDER}


def region_url(r):
    return f"/regions/{REGION_SLUG[r]}.html"


def counties_text(r):
    cs = REGION_COUNTIES[r]
    return f"{and_list(cs)} {'counties' if len(cs) > 1 else 'County'}"


REGION_TOWNS = defaultdict(Counter)
for p in REST:
    REGION_TOWNS[p.region][p.city] += 1
REGION_HINT = {r: [t for t, _ in REGION_TOWNS[r].most_common(3)] for r in REGION_ORDER}
TOWNS_BY_COUNT = sorted(TOWN_COUNT, key=lambda t: (-TOWN_COUNT[t], t))
HC_TOWN = Counter(p.city for p in HC)
# town pages: the 20 towns with the most restaurants, every town with 3 or more hand-checked places, and the coastal towns
# visitors look up by name
N_TOP_TOWNS = 20
TOWN_PAGES = TOWNS_BY_COUNT[:N_TOP_TOWNS]
TOWN_PAGES += [t for t in TOWNS_BY_COUNT if HC_TOWN[t] >= 3 and t not in TOWN_PAGES]
TOWN_PAGES += [t for t in ("Rockland", "Camden", "Freeport", "Boothbay Harbor") if t not in TOWN_PAGES and TOWN_COUNT[t] >= 20]
assert all(TOWN_COUNT[t] >= 9 for t in TOWN_PAGES), [(t, TOWN_COUNT[t]) for t in TOWN_PAGES]


def town_url(t):
    return f"/cities/{slug(t)}.html"


def town_links():
    return '<ul class="towns">' + "".join(f'<li><a href="{town_url(t)}">{e(t)}</a></li>' for t in TOWN_PAGES) + "</ul>"


def region_links(skip=None):
    return '<ul class="towns">' + "".join(f'<li><a href="{region_url(r)}">{e(r)}</a></li>' for r in REGION_ORDER if r != skip) + "</ul>"


def town_line():
    towns = ", ".join(f'<a href="{town_url(t)}">{e(t)}</a>' for t in TOWN_PAGES)
    regions = ", ".join(f'<a href="{region_url(r)}">{e(r)}</a>' for r in REGION_ORDER)
    return f'<p class="fine">Town pages: {towns}. Region pages: {regions}.</p>'


def by_region(places):
    groups = defaultdict(list)
    for p in places:
        groups[p.region].append(p)
    assert None not in groups, [p.name for p in groups[None]]
    return [(r, sorted(groups[r], key=lambda p: (p.city, p.name.lower()))) for r in REGION_ORDER if groups.get(r)]


# ---------------------------------------------------------------- place cards and structured data
def chips(p):
    out = []
    if p.jb_label:
        out.append(f'<span class="tag tag-jb">{p.jb_label}</span>')
    elif p.hon:
        out.append('<span class="tag tag-jb">Honored</span>')
    out += [f'<span class="tag">{k}</span>' for k in p.kind_names() if k != "Historic"]
    if p.seasonal:
        out.append('<span class="tag tag-plain">Seasonal</span>')
    if p.host:
        out.append(f'<span class="tag tag-plain">At {e(p.host)}</span>')
    return "".join(out)


def place_where(p, here_town=None):
    """"7 Sea St, Eastport", with the town linked to its town page when it has one (and isn't this page's town)."""
    town = e(p.place_name)
    if p.city in TOWN_PAGES and p.city != here_town:
        town = f'<a href="{town_url(p.city)}">{town}</a>'
    return ", ".join(x for x in (e(p.addr), town) if x)


def site_host(u):
    return re.sub(r"^https?://(www\.)?", "", u, flags=re.I).split("/")[0]


class Lister:
    """Renders place cards for one page. A place's first card gets its #p- anchor; a later mention points back up to it."""

    def __init__(self, here_town=None):
        self.seen = set()
        self.here_town = here_town

    def item(self, p, extra=None):
        where = place_where(p, self.here_town) + (f" · {e(extra)}" if extra else "")
        if p.id in self.seen:
            return f'<li class="again"><h3><a href="#p-{p.id}">{e(p.name)}</a></h3><p class="where">{where}; listed above</p></li>'
        self.seen.add(p.id)
        facts = []
        if p.dish:
            facts.append(f"<b>Known for:</b> {e(p.dish)}")
        if p.season:
            facts.append(f"<b>Season:</b> {e(p.season)}")
        elif p.seasonal:
            facts.append("<b>Season:</b> seasonal; check before you go")
        if p.founded:
            facts.append(f"<b>At this address since</b> {p.founded}")
        if p.branch:
            facts.append(f"<b>A branch of</b> {e(p.branch)}")
        out = [f'<li id="p-{p.id}"><h3><a href="{place_url(p)}">{e(p.name)}</a></h3>', f'<p class="where">{where}</p>']
        c = chips(p)
        if c or facts:
            out.append('<p class="facts">' + c + (" " if c and facts else "") + " · ".join(facts) + "</p>")
        if p.host:
            out.append(f'<p class="note">{HOST_AT[p.host][2]}</p>')
        if p.note:
            out.append(f'<p class="note">{e(p.note)}</p>')
        if p.jbf:
            out.append(f'<p class="note"><b>James Beard:</b> {e(p.jbf)}</p>')
        if p.site:
            out.append(f'<p class="link"><a href="{e(p.site)}" rel="noopener nofollow">{e(site_host(p.site))}</a></p>')
        out.append("</li>")
        return "".join(out)

    def items(self, ps, extra=lambda p: None):
        return "".join(self.item(p, extra(p)) for p in ps)


def restaurant_ld(p, url):
    a = {"@type": "PostalAddress", "streetAddress": p.addr, "addressLocality": p.village or p.city, "addressRegion": "ME",
         "postalCode": p.zip, "addressCountry": "US"}
    x = {"@context": "https://schema.org", "@type": "Restaurant", "@id": url + "#place", "name": p.name,
         "address": {k: v for k, v in a.items() if v}, "mainEntityOfPage": url}
    if p.lat is not None and p.lon is not None:
        x["geo"] = {"@type": "GeoCoordinates", "latitude": round(p.lat, 5), "longitude": round(p.lon, 5)}
    if p.phone:
        x["telephone"] = p.phone
    if p.site:
        x["url"] = p.site
    if p.cuisine and p.cuisine != "American & Other":
        x["servesCuisine"] = p.cuisine
    return x


def item_list(name, places, url):
    # minimal entries: each place's own page carries its full Restaurant markup
    return {"@context": "https://schema.org", "@type": "ItemList", "name": name, "url": url, "numberOfItems": len(places),
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": p.name, "url": DOMAIN + place_url(p)}
                                for i, p in enumerate(places)]}


# the Eats Ranked hub (eatsranked.com) lists this site as a subOrganization; the Organization says so from this side too
ORG = {"@type": "Organization", "@id": f"{DOMAIN}/#org", "name": BRAND, "url": f"{DOMAIN}/",
       "logo": {"@type": "ImageObject", "url": f"{DOMAIN}/icon-512.png", "width": 512, "height": 512}, "parentOrganization": PARENT}
PERSON = {"@type": "Person", "name": AUTHOR, "url": f"{DOMAIN}/about.html"}


def article_ld(url, headline, desc):
    return {"@context": "https://schema.org", "@type": "Article", "headline": html.unescape(headline), "description": desc,
            "datePublished": PUBLISHED, "dateModified": LASTMOD, "inLanguage": "en", "mainEntityOfPage": url, "image": f"{DOMAIN}/og.png",
            "author": PERSON, "publisher": ORG}


def year_line(ps, n):
    """The n longest at the same address among ps (all on this page, so each name links to its entry)."""
    dated = sorted([p for p in ps if p.founded], key=lambda p: (p.founded, p.name))
    long_ = [p for p in dated if DATA_YEAR - p.founded >= 20] or dated[:1]   # a 2023 opening isn't "the longest" of anything
    return "; ".join(f'<a href="#p-{p.id}">{e(p.name)}</a> in {e(p.place_name)}, there since {p.founded}' for p in long_[:n])


def oldest_of(ps):
    """The places tied for the earliest year at the same address (linked to their entries on this page), that year, and how many."""
    dated = [p for p in ps if p.founded]
    if not dated:
        return "", None, 0
    y = min(p.founded for p in dated)
    top = sorted([p for p in dated if p.founded == y], key=lambda p: p.name.lower())
    return and_list([f'<a href="#p-{p.id}">{e(p.name)}</a> in {e(p.place_name)}' for p in top]), y, len(top)


def oldest_link():
    return f'<a href="/{OLDEST_FILE}">Maine\'s oldest restaurants</a> has the {len(OLDEST)} places with 40 or more years at the same address.'


def how_checked(order="the order is by region and town"):
    return (f"we looked up each place in {CHECKED} and kept it only when a {SOURCE_YEARS} source showed it in business at that address: "
            "its own site or menu, a dated post, Maine news reporting, or a town or chamber of commerce listing. A shack or stand that "
            "posts its opening and closing dates has them printed beside it; one we couldn't source this year was dropped. No review "
            f"site fed into it, {order}, and no rating decides anything. Call ahead, since hours and menus shift. Our sources are on "
            f'the <a href="/about.html">about page</a>.')


def span(ps):
    """The towns at the two ends of a list along the coast: southernmost, and farthest north or east."""
    dated = [p for p in ps if p.lat is not None]
    a = min(dated, key=lambda p: p.lat)
    b = max(dated, key=lambda p: p.lat + p.lon * 0.5)   # Downeast counts as far as the County does
    return (a.city, b.city) if a.city != b.city else None


def notes(p):
    return f"{p.note} {p.dish}"


def cnt(ps, rx):
    return sum(1 for p in ps if re.search(rx, notes(p), re.I))


# What the research notes say, read strictly (a shucking contest at the Pemaquid Oyster Festival isn't serving Pemaquid oysters,
# and homemade waffle cones aren't homemade ice cream). Case matters: "Pemaquid Oyster Festival" is a name, "Pemaquid oysters" a menu.
RIVER_OYSTERS = re.compile(r"\b(Damariscotta River|Pemaquid) oysters\b|\bDamariscotta River oyster farm\b")
AT_OYSTER_FARM = re.compile(r"\boyster farm\b", re.I)          # on a farm ("oyster farmer" is a person, below)
OYSTER_FARMER = re.compile(r"\bfarmer\b", re.I)
OWN_ICE_CREAM = re.compile(r"(homemade|house-made|small-batch|scratch-made)\s+(?:[\w'-]+\s+){0,2}(ice cream|soft serve|hard-serve|flavors|gelato)"
                           r"|(make|makes|made|making) (its|their) own[^;.]{0,20}ice cream|makes? its ice cream|own ice cream|making [^;.]{0,40}ice cream"
                           r"|^(?:[\w'-]+\s+){0,2}ice cream maker\b", re.I)   # "Artisan ice cream maker ..." (not "a stand of the ... ice cream maker")


def river_oysters(ps):
    return [p for p in ps if RIVER_OYSTERS.search(notes(p))]


# ---------------------------------------------------------------- the guide pages: copy written from the data
def qa_oldest(ps, what):
    names, y, k = oldest_of(ps)
    dated = sum(1 for p in ps if p.founded)
    if not k:
        return None
    return (f"Which {what} here has been at its address the longest?",
            f"Of the {plural(dated, 'place')} on this list with a checked year at the same address, the longest-running {'is' if k == 1 else 'are'} "
            f"{names}, there since {y}. Places without a checked year may be older, so this answers for our list, not for the whole state. "
            + oldest_link())


def season_qa(ps, what):
    seas = [p for p in ps if p.seasonal]
    known = [p for p in seas if p.season]
    n = len(ps)
    if not seas:
        return (f"Are {what} open all year?", f"None of the {n} on this list is marked seasonal. Hours change, though, so check before you go.")
    return (f"Are {what} open all year?",
            f"Not all of them. {len(seas)} of the {n} here {isare(len(seas))} seasonal and {n - len(seas)} {'isn' if n - len(seas) == 1 else 'aren'}'t marked seasonal. "
            + (f"{len(known)} of the seasonal ones post their dates, and we list them with each place. " if known else "")
            + "A place that's closed for the winter hasn't closed for good, so check its season before you drive.")


def guide_copy(k, ps):
    n = len(ps)
    co = checked_open(ps)
    seas = [p for p in ps if p.seasonal]
    known = [p for p in seas if p.season]
    sp = span(ps)
    span_txt = f" from {e(sp[0])} to {e(sp[1])}" if sp else ""
    seas_txt = f" {len(seas)} of them {isare(len(seas))} seasonal, so check the season listed with each before you drive." if seas else ""
    c = {"seas": len(seas), "known": len(known)}
    if k == "lobster":
        n_shack = sum(1 for p in ps if p.kinds & KIND["lobster shack"])
        n_roll = sum(1 for p in ps if p.kinds & KIND["lobster roll"])
        c.update(n_shack=n_shack, n_roll=n_roll)
        c["titles"] = [f"Lobster Shacks & Lobster Rolls in Maine: {n} Checked Places", f"Maine Lobster Shacks & Lobster Rolls: {n} Checked Places", f"Maine Lobster Shacks & Rolls: {n} Hand-Checked Places",
                       f"Maine Lobster Shacks & Rolls: {n} Places | {BRAND}"]
        c["descs"] = [f"{n} Maine lobster pounds, shacks and lobster roll stops, each {co}, by region and town, with each shack's season. Free, no ratings.",
                      f"{n} Maine lobster pounds, shacks and lobster roll stops, {co}, by region and town with each one's season. Free, no ratings.",
                      f"{n} Maine lobster pounds, shacks and roll stops, {co}, listed by region and town. Free, no ads, no ratings."]
        c["h1"] = "Maine lobster shacks &amp; lobster rolls"
        c["lede"] = f"{n} lobster pounds, wharf-side shacks and lobster roll stops{span_txt}, each {co} going by its own site or menu, Maine news, or a town or chamber listing.{seas_txt}"
        c["about"] = [("Pounds, shacks and wharves",
                       "A lobster pound began as a saltwater pen for keeping lobsters alive. Today the name usually means a waterfront place that "
                       "cooks them to order, in big pots of seawater or over a wood fire, with picnic tables outside; a lobster shack is the takeout "
                       "version. The Maine lobster roll is usually served cold, the meat lightly dressed with mayonnaise in a toasted, buttered "
                       "split-top bun, and many places will make it with warm butter instead."),
                      (f"The {n} on this list",
                       f"{n_shack} are lobster pounds or shacks and {n_roll} list a lobster roll, many both. {len(seas)} are seasonal, and {len(known)} "
                       f"post their season, which is listed with each place. The longest at the same address: {year_line(ps, 4)}. {oldest_link()}")]
        c["qa"] = [season_qa(ps, "Maine lobster shacks"),
                   ("Lobster pound or lobster shack: what's the difference?",
                    "Mostly the setting. A pound keeps live lobsters, often in tanks or a saltwater pen, and cooks them to order for a lobster "
                    "dinner: the lobster, corn, steamers, butter. A shack is a takeout counter, usually for lobster rolls, chowder and fried "
                    f"seafood. Of the {n} places here, {n_shack} are pounds or shacks and {n_roll} list a lobster roll."),
                   ("Cold with mayo or warm with butter?",
                    "In Maine the lobster roll is traditionally cold: lobster meat with a little mayonnaise in a toasted, buttered split-top bun. "
                    "Warm meat with melted butter is often called Connecticut style. Many places serve both or ask which you want; where a "
                    "place told us, it's in the “Known for” line."),
                   qa_oldest(ps, "lobster place")]
        c["noun"], c["list"] = "place", "Maine lobster shacks and lobster rolls"
    elif k == "clams":
        c["titles"] = [f"Clam Shacks in Maine: {n} Hand-Checked Fried Clam Stops", f"Maine Clam Shacks: {n} Hand-Checked Fried Clam Stops", f"Maine Clam Shacks: {n} Checked Places for Fried Clams",
                       f"Maine Clam Shacks & Fried Clams: {n} Places | {BRAND}"]
        c["descs"] = [f"{n} Maine clam shacks for fried clams, clam cakes and chowder, each {co}, listed by region and town with their seasons. Free, no ratings.",
                      f"{n} Maine clam shacks and seafood stands for fried clams and chowder, {co}, by region and town. Free, no ads, no ratings.",
                      f"{n} Maine clam shacks for fried clams and chowder, {co}, listed by region and town. Free, no ads, no ratings."]
        c["h1"] = "Maine clam shacks"
        c["lede"] = f"{n} clam shacks and seafood stands for fried clams, clam cakes and chowder{span_txt}, each {co} going by its own site or menu, Maine news, or a town or chamber listing.{seas_txt}"
        c["about"] = [("Whole bellies, strips and cakes",
                       "Fried clams in Maine are usually whole-belly soft-shell clams, dipped in batter or crumbs and fried; clam strips are cut from "
                       "bigger sea clams and have no belly. A Maine clam cake is usually a flat, fried patty of chopped clams, and the chowder is "
                       "the creamy New England kind."),
                      (f"The {n} on this list",
                       f"{len(seas)} close for part of the year, and the {len(known)} that publish their dates have them printed with their entry. "
                       + (f"The longest at the same address: {year_line(ps, 3)}. " if any(p.founded for p in ps) else "") + oldest_link())]
        c["qa"] = [("Whole-belly clams or clam strips?",
                    "Whole-belly clams are soft-shell clams (steamers) fried whole, belly and all, and they're what a Maine clam shack is known "
                    "for. Clam strips are cut from larger sea clams, without the belly, and taste milder. Many shacks fry both; where a place "
                    "told us what it's known for, it's listed with it."),
                   season_qa(ps, "Maine clam shacks"), qa_oldest(ps, "clam shack")]
        c["noun"], c["list"] = "clam shack", "Maine clam shacks"
    elif k == "sandwiches":
        n_snap = sum(1 for p in ps if p.kinds & KIND["red snapper"])
        n_ital = sum(1 for p in ps if p.kinds & KIND["italian sandwich"])
        brands = [b for b in ("W.A. Bean", "Jordan's") if any(b in notes(p) for p in ps if p.kinds & KIND["red snapper"])]
        claim = [p for p in ps if p.kinds & KIND["italian sandwich"] and re.search(r"claims to have originated", p.note)]
        c.update(n_snap=n_snap, n_ital=n_ital)
        c["titles"] = [f"Maine Red Snapper Hot Dogs & Italians: {n} Checked Places", f"Red Snapper Hot Dogs & Maine Italians: {n} Places",
                       f"Maine Red Snappers & Italian Sandwiches: {n} Places | {BRAND}"]
        c["descs"] = [f"{n_snap} places for Maine's red snapper hot dogs and {n_ital} for the Maine Italian sandwich, each {co}, by region and town. Free, no ratings.",
                      f"{n} places for red snapper hot dogs and Maine Italian sandwiches, each {co}, listed by region and town. Free, no ads, no ratings.",
                      f"{n} places for Maine's red snapper hot dogs and Italian sandwiches, {co}, listed by region and town in a free guide."]
        c["h1"] = "Maine red snappers &amp; Italian sandwiches"
        c["lede"] = f"{plural(n_snap, 'place')} for red snapper hot dogs and {n_ital} for the Maine Italian sandwich, each {co} going by its own site or menu, Maine news, or a town or chamber listing.{seas_txt}"
        brand_txt = f"; the places here name {and_list(brands)} red snappers" if brands else ""
        claim_txt = f" {e(claim[0].name)} says it originated the sandwich." if claim else ""
        c["about"] = [("The red hot dog and the Italian",
                       f"A red snapper is a natural-casing hot dog dyed bright red, named for the snap of the casing when you bite in{e(brand_txt)}. "
                       "A Maine Italian is a sandwich on a soft sub roll with ham, American cheese, tomato, onion, green pepper, sour pickles and "
                       f"olives, dressed with oil, salt and pepper.{claim_txt}"),
                      (f"The {n} on this list", f"{plural(n_snap, 'serves', 'serve')} red snappers and {n_ital} make Maine Italians. {oldest_link()}")]
        c["qa"] = [("What is a red snapper hot dog?",
                    "A natural-casing hot dog dyed bright red. The casing snaps when you bite it, which gives it its name, and it's usually "
                    f"served on a toasted or steamed New England-style split-top bun{e(brand_txt)}."),
                   ("What goes on a Maine Italian?",
                    "Ham, American cheese, tomato, onion, green pepper, sour pickles and olives on a long, soft roll, with oil, salt and pepper. "
                    f"Elsewhere it would be a sub; in Maine it's an Italian.{claim_txt}"),
                   season_qa(ps, "these places")]
        c["noun"], c["list"] = "place", "Maine red snapper hot dogs and Italian sandwiches"
    elif k == "sweets":
        n_wp = sum(1 for p in ps if p.kinds & KIND["whoopie pie"])
        n_pd = sum(1 for p in ps if p.kinds & KIND["potato doughnut"])
        bp = [p for p in ps if p.kinds & KIND["blueberry pie"]]
        c.update(n_whoopie=n_wp, n_donut=n_pd, n_blueberry=len(bp))
        c["titles"] = [f"Maine Whoopie Pies, Potato Donuts & Blueberry Pie: {n} Places", f"Maine Whoopie Pies & Potato Donuts: {n} Checked Places",
                       f"Maine Whoopie Pies & Donuts: {n} Places | {BRAND}"]
        c["descs"] = [f"{n_wp} places for Maine whoopie pies, {n_pd} for potato donuts and {len(bp)} for blueberry pie, each {co}, by region and town. Free, no ratings.",
                      f"{n} places for Maine whoopie pies, potato donuts and blueberry pie, each {co}, listed by region and town. Free, no ratings.",
                      f"{n} Maine bakeries and diners for whoopie pies, potato donuts and blueberry pie, {co}, by region and town. Free."]
        c["h1"] = "Maine whoopie pies, potato donuts &amp; blueberry pie"
        c["lede"] = f"{n_wp} places for whoopie pies, {n_pd} for potato donuts and {len(bp)} for blueberry pie, each {co} going by its own site or menu, Maine news, or a town or chamber listing.{seas_txt}"
        c["about"] = [("The state treat and the state dessert",
                       "The whoopie pie, two rounds of soft chocolate cake around a sweet white filling, is Maine's official state treat, and wild "
                       "blueberry pie is the official state dessert; the Legislature named both in 2011. A potato donut is made with mashed potato "
                       "in the dough, which keeps it moist."),
                      (f"The {n} on this list",
                       f"Bakeries, diners and shops; several ship whoopie pies. " + (f"The longest at the same address: {year_line(ps, 3)}. " if any(p.founded for p in ps) else "") + oldest_link())]
        if not any(re.search(r"\bship", notes(p), re.I) for p in ps):
            c["about"][1] = (c["about"][1][0], c["about"][1][1].replace("several ship whoopie pies. ", ""))
        c["qa"] = [("Is the whoopie pie really Maine's state treat?",
                    "Yes. In 2011 the Maine Legislature named the whoopie pie the official state treat and wild blueberry pie the official state "
                    f"dessert. {n_wp} places on this list are known for whoopie pies."),
                   ("What is a potato donut?",
                    "A doughnut made with mashed potato in the dough, which keeps it moist and a little dense. "
                    f"{plural(n_pd, 'place')} on this list {'makes' if n_pd == 1 else 'make'} them."),
                   ("Where can I get blueberry pie?",
                    (f"On this list: {and_list(f'<a href=\"#p-{p.id}\">{e(p.name)}</a> in {e(p.place_name)}' for p in bp)}. " if bp else "None of the places on this list yet. ")
                    + "Wild blueberries ripen in August, and many places bake with frozen ones the rest of the year."),
                   qa_oldest(ps, "bakery or diner")]
        c["noun"], c["list"] = "place", "Maine whoopie pies, potato donuts and blueberry pie"
    elif k == "franco":
        c["titles"] = [f"Franco-American Food in Maine: {n} Checked Places", f"Maine Franco-American Food: Poutine & Tourtière, {n} Places",
                       f"Franco-American Food in Maine: {n} Places | {BRAND}"]
        c["descs"] = [f"{n} Maine places for Franco-American food, from tourtière to poutine and ployes, each {co}, listed by region and town. Free, no ratings.",
                      f"{n} places in Maine for Franco-American food like tourtière, poutine and ployes, {co}, by region and town. Free, no ratings."]
        c["h1"] = "Franco-American food in Maine"
        c["lede"] = f"{n} bakeries, diners and restaurants for Franco-American food, each {co} going by its own site or menu, Maine news, or a town or chamber listing.{seas_txt}"
        c["about"] = [("From Lewiston to the St. John Valley",
                       "Many Mainers have French-Canadian roots, and the food came with them: tourtière, a spiced pork pie; poutine; cretons, a "
                       "pork spread; and in the St. John Valley, ployes, thin buckwheat pancakes."),
                      (f"The {n} on this list", oldest_link())]
        c["qa"] = [("What is tourtière?", "A double-crust pie of spiced ground pork, sometimes with beef or potato, traditional at Christmas and New Year's in Franco-American homes."),
                   ("What are ployes?", "Thin buckwheat pancakes from the St. John Valley in northern Aroostook County, cooked on one side only and eaten with butter or with a meal."),
                   qa_oldest(ps, "place")]
        c["noun"], c["list"] = "place", "Franco-American food in Maine"
    elif k == "diners":
        cars = [p for p in ps if re.search(r"dining car|lunch car", p.note, re.I)]
        c["titles"] = [f"Diners in Maine: {n} Hand-Checked Breakfast & Lunch Counters", f"Maine Diners: {n} Hand-Checked Breakfast & Lunch Spots", f"Maine Diners: {n} Long-Running, Hand-Checked Diners",
                       f"Maine Diners: {n} Checked Places | {BRAND}"]
        c["descs"] = [f"{n} Maine diners, each {co} against a {SOURCE_YEARS} source, with what each is known for and its year at the address. By region and town. Free.",
                      f"{n} Maine diners, {co}, with what each one is known for and its year at the same address, by region and town. Free, no ratings."]
        c["h1"] = "Maine diners"
        c["lede"] = f"{n} diners{span_txt}, each {co} going by its own site or menu, Maine news, or a town or chamber listing, with what each is known for."
        car_txt = (f" {and_list(f'<a href=\"#p-{p.id}\">{e(p.name)}</a>' for p in cars)} {'is an old factory-built dining car' if len(cars) == 1 else 'are old factory-built dining cars'}." if cars else "")
        c["about"] = [("Counters, booths and pie",
                       f"The diners on this list are the counter-and-booth kind, most of them open for breakfast and lunch.{car_txt}"),
                      (f"The {n} on this list",
                       f"Another {NAMED['diner']:,} Maine places carry “Diner” in the name. The app's directory has them, unchecked; a diner joins "
                       f"this list once we've sourced it. Longest at one address among these {n}: {year_line(ps, 4)}. {oldest_link()}")]
        c["qa"] = [qa_oldest(ps, "diner"),
                   ("Which diners here are in old dining cars?", (f"{car_txt.strip()} Factory-built dining cars were made in New England and shipped to their sites; few are left." if cars else "None that told us so.")),
                   ("Why isn't my favorite diner on this list?",
                    f"We list a diner only after checking it against a {SOURCE_YEARS} source, so a place merely named “Diner” isn't enough. "
                    f"{NAMED['diner']:,} of those are in the web search and the app's directory. Tell us about one at {EMAIL}.")]
        c["noun"], c["list"] = "diner", "Maine diners"
    elif k == "oysters":
        n_dam = len(river_oysters(ps))
        at_farm = [p for p in ps if AT_OYSTER_FARM.search(notes(p))]
        farmers = [p for p in ps if OYSTER_FARMER.search(p.note) and p not in at_farm]
        c.update(n_river_oysters=n_dam, n_at_farm=len(at_farm), n_farmer_run=len(farmers))
        link = lambda xs: and_list(f'<a href="#p-{p.id}">{e(p.name)}</a>' for p in xs)
        farm_bits = ([f"{len(at_farm)} {isare(len(at_farm))} on an oyster farm"] if at_farm else []) + \
                    ([f"{len(farmers)} {isare(len(farmers))} run by oyster farmers"] if farmers else [])
        c["titles"] = [(f"Oyster Bars in Maine: {n - 1} Hand-Checked Raw Bars and a Farm" if len(at_farm) == 1 else f"Oyster Bars in Maine: {n} Hand-Checked Raw Bars"), f"Maine Oyster Bars & Raw Bars: {n} Hand-Checked Places", f"Maine Oyster Bars: {n} Hand-Checked Raw Bars & Farms",
                       f"Maine Oyster Bars: {n} Checked Places | {BRAND}"]
        c["descs"] = [f"{n} Maine oyster bars and raw bars, from the Damariscotta River to Casco Bay, each {co}, listed by region and town. Free, no ratings.",
                      f"{n} Maine oyster bars and raw bars, {co}, with where their oysters come from, by region and town. Free, no ratings."]
        c["h1"] = "Maine oyster bars"
        c["lede"] = f"{n} oyster bars and raw bars{span_txt}, each {co} going by its own site or menu, Maine news, or a town or chamber listing.{seas_txt}"
        c["about"] = [("From the Damariscotta River",
                       f"The Damariscotta River, in Lincoln County, is the center of Maine oyster farming. {n_dam} of the {n} places here list "
                       f"Damariscotta River or Pemaquid oysters" + (f"; {and_list(farm_bits)}." if farm_bits else ".")),
                      (f"The {n} on this list", (f"The longest at the same address: {year_line(ps, 3)}. " if any(p.founded for p in ps) else "") + oldest_link())]
        c["qa"] = [("Where do Maine oysters come from?",
                    "Farms along the coast, above all the Damariscotta River in Lincoln County, and also Casco Bay, the Downeast coast and "
                    f"the islands. {n_dam} of the {n} places here list Damariscotta River or Pemaquid oysters."),
                   ("Can I eat oysters at a farm?",
                    (f"Yes: {link(at_farm)} {'serves its' if len(at_farm) == 1 else 'serve their'} oysters at the farm." if at_farm else "None of the places on this list is at a farm yet.")
                    + (f" {link(farmers)} {'is' if len(farmers) == 1 else 'are'} run by oyster farmers." if farmers else "")
                    + (" Call ahead; hours change with the season." if at_farm or farmers else "")),
                   season_qa(ps, "Maine oyster bars")]
        c["noun"], c["list"] = "oyster bar", "Maine oyster bars"
    elif k == "dairy":
        n_spring = sum(1 for p in known if re.search(r"March|April", p.season))
        n_giff = cnt(ps, r"Gifford")
        n_home = sum(1 for p in ps if OWN_ICE_CREAM.search(notes(p)))
        c.update(n_spring=n_spring, n_gifford=n_giff, n_homemade=n_home)
        c["titles"] = [f"Dairy Bars in Maine: {n} Hand-Checked Ice Cream Stands", f"Maine Dairy Bars & Ice Cream Stands: {n} Checked Places", f"Maine Dairy Bars & Ice Cream Stands: {n} Places",
                       f"Maine Dairy Bars: {n} Hand-Checked Ice Cream Stands"]
        c["descs"] = [f"{n} Maine dairy bars, ice cream stands and farm creameries, each {co}, listed by region and town with their seasons. Free, no ratings.",
                      f"{n} Maine dairy bars and ice cream stands, {co}, listed by region and town with each one's season. Free, no ads, no ratings."]
        c["h1"] = "Maine dairy bars &amp; ice cream stands"
        c["lede"] = f"{n} dairy bars, ice cream stands and farm creameries{span_txt}, each {co} going by its own site or menu, Maine news, or a town or chamber listing.{seas_txt}"
        c["about"] = [("Soft serve, hard serve and a frappe",
                       "A Maine dairy bar is a roadside ice cream stand, usually a walk-up window with soft serve, hard ice cream and frappes "
                       "(in New England, a frappe is a milkshake made with ice cream)."),
                      (f"The {n} on this list",
                       f"{len(seas)} are seasonal and {len(known)} post their dates; {n_spring} of those open in March or April. {n_home} make their "
                       f"own ice cream and {n_giff} scoop Gifford's, the Skowhegan ice cream maker, as their notes say. "
                       + (f"The longest at the same address: {year_line(ps, 3)}. " if any(p.founded for p in ps) else "") + oldest_link())]
        c["qa"] = [("When do Maine dairy bars open?",
                    f"Many open in early spring and close in the fall. Of the {n} here, {len(seas)} are seasonal; {len(known)} post their dates, and "
                    f"{n_spring} of those open in March or April. The season is listed with each place, and a stand that's closed for the "
                    "winter hasn't closed for good."),
                   ("What's a frappe?", "In New England, a frappe is a milkshake made with ice cream. Ask for a milkshake and you may get milk and syrup without any ice cream."),
                   ("Who makes the ice cream?",
                    f"{n_home} of the {n} make their own, as their notes say, and {n_giff} scoop Gifford's, made in Skowhegan. The “Known for” line "
                    "with each place says what it serves.")]
        c["noun"], c["list"] = "dairy bar", "Maine dairy bars and ice cream stands"
    c["qa"] = [x for x in c["qa"] if x]
    return c


GUIDE_STATS = {}
for k in GUIDE_PAGE:
    ps = G[k]
    path = GUIDE_FILE[k]
    url = f"{DOMAIN}/{path}"
    c = guide_copy(k, ps)
    GUIDE_STATS[k] = {x: v for x, v in c.items() if isinstance(v, int)}
    title = fit(c["titles"], 50, 60, TITLES)
    desc = fit(c["descs"], 140, 160, DESCS)
    nav, bc = crumbs([("Home", "/"), (GUIDE_SHORT[k], "/" + path)])
    L = Lister()
    regions = by_region(ps)
    toc = '<ul class="toc">' + "".join(f'<li><a href="#{REGION_SLUG[r]}">{e(r)}</a> ({len(rp)})</li>' for r, rp in regions) + "</ul>"
    secs = "\n".join(f'<section id="{REGION_SLUG[r]}" aria-labelledby="h-{REGION_SLUG[r]}"><h2 id="h-{REGION_SLUG[r]}">{e(r)}</h2>'
                     f'<p class="sub">{plural(len(rp), c["noun"])}, by town. The region around {e(and_list(REGION_HINT[r]))}; '
                     f'<a href="{region_url(r)}">the {e(r)} page</a> has its other guides too.</p><ol class="places">' + L.items(rp) + "</ol></section>"
                     for r, rp in regions)
    about = "\n".join(f"    <h2>{h}</h2>\n    <p>{t}</p>" for h, t in c["about"])
    qa = "\n".join(f"    <h3>{e(q)}</h3>\n    <p>{a}</p>" for q, a in c["qa"])
    body = f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{BRAND} guide · checked {CHECKED}</p>
    <h1>{c["h1"]}</h1>
    <p class="lede">{c["lede"]}</p>
    <div class="cta-row">{store_button()}<a class="btn btn-ghost" href="{e(explore_url(g=k, view="map"))}">See them on a map</a></div>
    <p class="pill">{store_note()}</p>
  </section>
  <section id="about-{k}">
{about}
    <p>How we made the list: {how_checked()}</p>
    <p>In the {BRAND} app the same places come nearest-first from wherever your phone is, and each opens Apple's own map card for opening times, pictures and the route.</p>
    <h2>Jump to a region</h2>
    <p class="sub">The list is grouped by the Maine Office of Tourism's {len(REGION_ORDER)} regions, which we draw on county lines.</p>
    {toc}
    {town_line()}
  </section>
  <section id="questions" class="qa">
    <h2>{e(GUIDE_SHORT[k])}: questions</h2>
{qa}
  </section>
{secs}
  </main>"""
    written.append(page(path, title, desc, body, [article_ld(url, c["h1"], desc), bc, item_list(c["list"], ps, url)]))



def region_sections(ps, noun, lister):
    regions = by_region(ps)
    toc = '<ul class="toc">' + "".join(f'<li><a href="#{REGION_SLUG[r]}">{e(r)}</a> ({len(rp)})</li>' for r, rp in regions) + "</ul>"
    secs = "\n".join(f'<section id="{REGION_SLUG[r]}" aria-labelledby="h-{REGION_SLUG[r]}"><h2 id="h-{REGION_SLUG[r]}">{e(r)}</h2>'
                     f'<p class="sub">{plural(len(rp), noun)}, by town. See <a href="{region_url(r)}">the {e(r)} page</a> for the region\'s other guides.</p>'
                     f'<ol class="places">' + lister.items(rp) + "</ol></section>" for r, rp in regions)
    return toc, secs


# ---------------------------------------------------------------- Maine icons
ICON_STATS = {}
if ICONS_PAGE:
    ps = ICONS
    n = len(ps)
    url = f"{DOMAIN}/{ICONS_FILE}"
    jb = [p for p in ps if p.h]
    forty = [p for p in ps if p.founded and DATA_YEAR - p.founded >= 40]
    co = checked_open(ps)
    ICON_STATS = {"icons": n, "james_beard": len(jb), "forty_years": len(forty)}
    title = fit([f"Maine Icons: {n} James Beard Honorees & Long-Running Places", f"Maine Restaurant Icons: {n} Honored & Long-Running Places",
                 f"Maine Icons: {n} Hand-Checked Places | {BRAND}"], 50, 60, TITLES)
    desc = fit([f"{n} Maine restaurants, bakeries and shacks with James Beard honors or 40 or more years at the same address, each {co}. Free, no ratings.",
                f"{n} Maine places with James Beard honors or 40-plus years at the same address, {co}, listed by region and town. Free, no ratings."], 140, 160, DESCS)
    nav, bc = crumbs([("Home", "/"), ("Maine icons", "/" + ICONS_FILE)])
    L = Lister()
    toc, secs = region_sections(sorted(ps, key=P.featured_key), "place", L)
    jb_line = and_list(f'<a href="#p-{p.id}">{e(p.name)}</a> in {e(p.place_name)} ({e(p.jb_label or "honored")})' for p in sorted(jb, key=lambda p: p.name.lower()))
    body = f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{BRAND} guide · checked {CHECKED}</p>
    <h1>Maine icons</h1>
    <p class="lede">{n} Maine restaurants, bakeries, shacks and dairy bars with James Beard honors or 40 or more years at the same address, each {co} going by its own site or menu, Maine news, or a town or chamber listing.</p>
    <div class="cta-row">{store_button()}<a class="btn btn-ghost" href="{e(explore_url(g="icons", view="map"))}">See them on a map</a></div>
    <p class="pill">{store_note()}</p>
  </section>
  <section id="about-icons">
    <h2>What makes an icon</h2>
    <p>A place is here for a James Beard Foundation honor (an America's Classics award, a win, or a nomination or semifinalist nod) or for 40 or more years at its current address, checked against its own history page or local news. {len(jb)} of the {n} have James Beard honors and {len(forty)} have been at their address for 40 years or more. Honors are facts from the James Beard Foundation's own award records, not ratings.</p>
    <h2>The {n} on this list</h2>
    <p>The longest at the same address: {year_line(ps, 4)}. {oldest_link()}</p>
    <p>How we made the list: {how_checked()}</p>
    <h2>Jump to a region</h2>
    {toc}
    {town_line()}
  </section>
  <section id="questions" class="qa">
    <h2>Maine icons: questions</h2>
    <h3>Which places here have James Beard honors?</h3>
    <p>{jb_line}. James Beard Foundation and James Beard Award are trademarks of the James Beard Foundation.</p>
    <h3>Is the Icons order a ranking?</h3>
    <p>No. In the web search and the app, the Icons guide puts the most honored and longest-running places first, using the honors and years above. It isn't a rating of the food, and we never show it as a score.</p>
    <h3>Why isn't a famous place here?</h3>
    <p>We add a place only after checking it against a {SOURCE_YEARS} source and confirming its honor or its year at the same address. A place that moved counts from its move. Tell us about one at {EMAIL}.</p>
  </section>
{secs}
  </main>"""
    written.append(page(ICONS_FILE, title, desc, body, [article_ld(url, "Maine icons", desc), bc, item_list("Maine icons", ps, url)]))

# ---------------------------------------------------------------- Maine's oldest restaurants (years at the same address)
url = f"{DOMAIN}/{OLDEST_FILE}"
n = len(OLDEST)
first = OLDEST[0]
ERAS = [("before-1900", "Before 1900", 0, 1900), ("1900-1949", "1900 to 1949", 1900, 1950), ("1950-1979", "1950 to 1979", 1950, 1980),
        ("since-1980", "1980 and later", 1980, 10000)]
eras = [(i, label, [p for p in OLDEST if lo <= p.founded < hi]) for i, label, lo, hi in ERAS]
eras = [x for x in eras if x[2]]
ERA_PHRASE = {"before-1900": "from before 1900", "1900-1949": "from 1900 to 1949", "1950-1979": "from 1950 to 1979", "since-1980": "from 1980 on"}
# what kinds of place made it to 40 years, in words a reader would use (only the kinds actually on the list)
OLD_KINDS = and_list([w for w, hit in (("inns", any(re.search(r"\bInn\b", p.name) for p in OLDEST)),
                                       ("diners", any(p.kinds & KIND["diner"] for p in OLDEST)),
                                       ("lobster pounds", any(p.kinds & KIND["lobster shack"] for p in OLDEST)),
                                       ("dairy bars", any(p.kinds & KIND["dairy bar"] for p in OLDEST))) if hit])
title = fit([f"Oldest Restaurants in Maine: {n} at One Address Since {first.founded}", f"Maine's Oldest Restaurants: {n} Places 40+ Years Old",
             f"Oldest Restaurants in Maine: {n} Places | {BRAND}"], 50, 60, TITLES)
desc = fit([f"{n} Maine {OLD_KINDS} serving at the same address for 40 years or more, oldest first, back to {first.founded}. Free, no ratings.",
            f"{n} Maine places serving at the same address for 40 years or more, oldest first, back to {first.founded}, with the town and year for each. Free.",
            f"{n} Maine places that have served at one address for 40 years or more, listed oldest first with the town and the year for each. Free, no ratings."], 140, 160, DESCS)
nav, bc = crumbs([("Home", "/"), ("Oldest restaurants", "/" + OLDEST_FILE)])
L = Lister()
toc = '<ul class="toc">' + "".join(f'<li><a href="#{i}">{e(label)}</a> ({len(ps)})</li>' for i, label, ps in eras) + "</ul>"
secs = "\n".join(f'<section id="{i}" aria-labelledby="h-{i}"><h2 id="h-{i}">{e(label)}</h2><p class="sub">{plural(len(ps), "place")}, oldest first.</p>'
                 f'<ol class="places">' + L.items(ps) + "</ol></section>" for i, label, ps in eras)
guide_links = and_list(f'<a href="{guide_link(k)}">{e(lc(GUIDE_SHORT[k]))}</a>' for k in GUIDE_PAGE)
body = f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{BRAND} · 40 years or more at one address · checked {CHECKED}</p>
    <h1>Maine's oldest restaurants</h1>
    <p class="lede">{n} Maine places that have fed people at the same address for 40 years or more, oldest first: {and_list(f"{len(ps)} {ERA_PHRASE[i]}" for i, label, ps in eras)}. The first, {e(first.name)} in {e(first.place_name)}, has been there since {first.founded}.</p>
    <div class="cta-row">{store_button()}<a class="btn btn-ghost" href="{e(explore_url(g="oldest", view="map"))}">See them on a map</a></div>
    <p class="pill">{store_note()}</p>
  </section>
  <section id="about-oldest">
    <h2>What the year means</h2>
    <p>The year is when the place started serving at the spot where it stands today, taken from its own history page or from Maine news coverage. Moving resets the count, so a business founded long ago can show a later year; a place that changed its name but kept its spot can keep the earlier one. The year tells you how long, not how good. Only places we checked by hand carry a year, so many of the app's {N_REST - n:,} other restaurants may be just as old without showing it here.</p>
    <p>How we made the list: {how_checked("the order is by years at the same address")}</p>
    <p>This is the Oldest Places list in the app and in the <a href="{e(explore_url(g="oldest"))}">web search</a>. What each one is known for is in its entry below and in the {guide_links} guides.</p>
    <h2>Jump to an era</h2>
    {toc}
    {town_line()}
  </section>
{secs}
  </main>"""
written.append(page(OLDEST_FILE, title, desc, body,
                    [article_ld(url, "Maine's oldest restaurants", desc), bc, item_list("Maine's oldest restaurants, by years at the same address", OLDEST, url)]))

# ---------------------------------------------------------------- town pages
# key, heading, one, many, the guide's places, "in and near" radius in miles, the word for titles, the word for "the nearest are a drive away"
TOWN_SECTIONS = [("lobster", "Lobster shacks and rolls", "lobster shack or roll stop", "lobster shacks and roll stops", LOBSTER, 15, "Lobster Shacks", "lobster shacks"),
                 ("clams", "Clam shacks", "clam shack", "clam shacks", CLAMS, 15, "Clam Shacks", "clam shacks"),
                 ("sandwiches", "Red snappers and Italians", "red snapper or Italian stop", "red snapper and Italian stops", SAND, 10, "Italians", "Italians"),
                 ("sweets", "Whoopie pies and donuts", "whoopie pie or donut stop", "whoopie pie and donut stops", SWEETS, 10, "Whoopie Pies", "whoopie pies"),
                 ("franco", "Franco-American food", "Franco-American place", "Franco-American places", FRANCO, 15, "Franco-American Food", "Franco-American food"),
                 ("diners", "Diners", "diner", "diners", DINERS, 10, "Diners", "diners"),
                 ("oysters", "Oyster bars", "oyster bar", "oyster bars", OYSTERS, 15, "Oyster Bars", "oyster bars"),
                 ("dairy", "Dairy bars", "dairy bar", "dairy bars", DAIRY, 10, "Dairy Bars", "dairy bars")]
NEAR_N = 5          # the nearest few outside the town; the guide has the rest
NEAREST_MAX = 40    # when none is in or near the town, the 3 nearest within this many miles
TOWN_STATS = {}
village_towns = defaultdict(set)
for p in REST:
    if p.village:
        village_towns[p.village].add(p.city)


def mi(d, rad):
    """Whole miles, or tenths where rounding would put a place we call farther than the radius right at it (15.4, not 15)."""
    return f"{d:.1f}" if d > rad and math.floor(d) <= rad else f"{d:.0f}"


for t in TOWN_PAGES:
    here_all = [p for p in REST if p.city == t]
    here = [p for p in here_all if p.lat is not None]
    n_town = TOWN_COUNT[t]
    center = (sorted(p.lat for p in here)[len(here) // 2], sorted(p.lon for p in here)[len(here) // 2])
    # per guide: the town's own places, the others within the radius (closest first), and when there are neither, the 3 nearest
    # within NEAREST_MAX miles, flagged so the page calls them "the nearest" and says none of ours is closer (small guides, under
    # MIN_GUIDE_PAGE places, only when one is in or near the town)
    ins, within, shown, nearest_only = {}, {}, {}, {}
    for k, _, _, _, lst, rad, _, _ in TOWN_SECTIONS:
        ins[k] = [p for p in lst if p.city == t]
        outs = sorted([(miles(center, (p.lat, p.lon)), p) for p in lst if p.city != t and p.lat is not None], key=lambda x: (x[0], x[1].name.lower()))
        within[k] = [x for x in outs if x[0] <= rad]
        nearest_only[k] = not ins[k] and not within[k]
        if nearest_only[k]:
            shown[k] = [x for x in outs if x[0] <= NEAREST_MAX][:3] if len(lst) >= MIN_GUIDE_PAGE else []
        else:
            shown[k] = within[k][:NEAR_N]
    full = {k: ins[k] + [p for _, p in (shown[k] if nearest_only[k] else within[k])] for k in ins}
    counts = {k: len(v) for k, v in full.items()}
    close = {k: counts[k] if not nearest_only[k] else 0 for k in counts}
    vill = Counter(p.village for p in here_all if p.village)
    villages = [v for v, c in vill.most_common() if c >= 3]
    icons = sorted([p for p in here_all if p.hc], key=P.featured_key)
    oldest = sorted([p for p in icons if p.founded], key=lambda p: (p.founded, p.name.lower()))
    cuis = Counter(p.cuisine for p in here_all if p.cuisine != "American & Other").most_common(10)
    casino = [p for p in here_all if p.host]
    region = REGION_OF_TOWN[t]
    county = COUNTY_OF_TOWN[t]
    TOWN_STATS[t] = {"restaurants": n_town, **{k + "_near": c for k, c in close.items()}, "hand_checked_in_town": len(icons)}
    path = f"cities/{slug(t)}.html"
    url = DOMAIN + "/" + path
    order = {k: i for i, (k, *_) in enumerate(TOWN_SECTIONS)}
    ranked = sorted([s for s in TOWN_SECTIONS if close[s[0]]], key=lambda s: (-close[s[0]], order[s[0]]))
    words = [s[6] for s in ranked]
    h1 = f"{t} restaurants: {' & '.join(s[7] for s in ranked[:2])}" if ranked else f"{t} restaurants and the classics nearby"
    pairs = [(words[a], words[b]) for a in range(len(words)) for b in range(a + 1, len(words))] or [("Lobster Shacks", "Dairy Bars")]
    topts = []
    for w1, w2 in pairs:
        w2s = f"{w1} & {w2}"
        topts += [f"{t} Restaurants: {w2s} | {BRAND}", f"{t}, ME Restaurants: {w2s} | {BRAND}", f"{t}, Maine Restaurants: {w2s}",
                  f"{t} Restaurants: {w2s} and More", f"{t}, Maine: {w2s} and More Restaurants", f"{t}, ME: {w2s} and Local Restaurants",
                  f"{t} Restaurants, {w2s} | {BRAND}", f"{t}, Maine: {w2s} | {BRAND}", f"{t}: {w2s} | {BRAND}",
                  f"{t} Restaurants: {w2s} Nearby"]
    if len(words) >= 3:
        topts.insert(0, f"{t} Restaurants: {words[0]}, {words[1]} & {words[2]}")
    if not words:   # nothing hand-checked in or near the town: the title says "nearest", as the page does
        topts = [f"{t}, Maine Restaurants & the Nearest Classics", f"{t}, Maine Restaurants & the Nearest Hand-Checked Classics",
                 f"{t} Restaurants & the Nearest Lobster Shacks", f"{t}, ME Restaurants & the Nearest Hand-Checked Classics",
                 f"{t} Restaurants & the Nearest Classics | {BRAND}"]
    title = fit(topts, 50, 60, TITLES)
    lw_ = [s[7] for s in ranked] or ["hand-checked classics"]
    lwl = and_list(lw_[:3])
    cw = checked_open([p for k in full for p in full[k]] or icons or HC)
    extra_long = and_list((["the town's hand-checked places"] if icons else []) + (["its oldest restaurants"] if oldest else [])
                          or [f"{n_town:,} restaurants in the free app"])
    extra_short = and_list((["local icons"] if icons else []) + (["the oldest places in town"] if oldest else []) or [f"{n_town:,} places in the app"])
    dopts = []
    for ex in (extra_long, extra_short):
        for where in (f"{t}, ME", f"{t}, Maine"):
            dopts += [f"{cap(lwl)} in and near {where}, {cw}, plus {ex}. Free, no ads, no ratings.",
                      f"{cap(lwl)} in and near {where}, {cw}, plus {ex}. Free, no ratings.",
                      f"{cap(lwl)} in and near {where}, {cw}, plus {ex}.",
                      f"Hand-checked {lwl} in and near {where}, each {cw}, plus {ex}. Free.",
                      f"Hand-checked {lwl} in and near {where}, {cw}, plus {ex}, in a free app.",
                      f"Hand-checked {lwl} near {where}, {cw}, plus {ex} and {n_town:,} places in a free app."]
    lw2 = and_list(lw_[:2])
    dopts += [f"{cap(lw2)} in and near {t}, Maine, {cw}, plus {extra_short} and {n_town:,} restaurants in a free app.",
              f"Hand-checked {lw2} in and near {t}, Maine, {cw}, plus the {n_town:,} restaurants in the free {BRAND} app."]
    desc = fit(dopts, 140, 160, DESCS)
    nav, bc = crumbs([("Home", "/"), ("Towns", "/cities/"), (t, "/" + path)])
    lead_bits = [plural(counts[k], one, many) for k, _, one, many, *_ in TOWN_SECTIONS if close[k]]
    far_labels = [far for k, *_, far in TOWN_SECTIONS if counts[k] and nearest_only[k]]
    lede = (f"{e(cap(and_list(lead_bits)))} in and around {e(t)}, each {cw}." if lead_bits else "")
    lede += f" For hand-checked {e(and_list(far_labels))}, the nearest are a drive away; they're below too." if far_labels else ""
    lede += f" The {BRAND} app's directory has {n_town:,} restaurants, cafés, bars and bakeries in {e(t)} and sorts them by distance from you."
    parts = [f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{BRAND} · {e(t)}, Maine{f" · including {e(and_list(villages))}" if villages else ""}</p>
    <h1>{e(h1)}</h1>
    <p class="lede">{lede.strip()}</p>
    <div class="cta-row">{store_button()}<a class="btn btn-ghost" href="{e(explore_url(g="all", town=t))}">Search {e(t)}</a></div>
    <p class="pill">{store_note()}</p>"""]
    if villages:
        vtxt = f"{e(and_list(villages))} {'is a village' if len(villages) == 1 else 'are villages'} in the town of {e(t)}, so places there are listed under {e(t)}."
        parts.append(f'    <p class="fine">{vtxt}</p>')
    parts.append("  </section>")

    # a short, data-driven picture of the town, so each page says something only it can say
    facts = []
    vbits = [f"{c:,} in {e(v)}" for v, c in vill.most_common(3) if c >= 3]
    top = cuis[:3]
    facts.append(f"The app's directory has {n_town:,} places to eat and drink in {e(t)}" + (f", including {and_list(vbits)}" if vbits else "")
                 + (f". The most common kinds are {and_list(f'{e(k)} ({c:,})' for k, c in top)}." if top else "."))
    n_lic = sum(1 for p in here_all if p.t == 2 and p.j == 1)
    if n_lic:
        facts.append(f"{n_lic:,} {'is' if n_lic == 1 else 'are'} matched to a Maine liquor license on the state's list.")
    n_lew = sum(1 for p in here_all if p.t == 2 and p.j == 2)
    if n_lew:
        facts.append(f"{n_lew:,} more {'is' if n_lew == 1 else 'are'} on the City of Lewiston's list of inspected restaurants.")
    n_chain = sum(1 for p in here_all if p.chain)
    if n_chain:
        facts.append(f"{plural(n_chain, 'is a location', 'are locations')} of a chain with five or more in Maine.")
    if icons:
        n_jb = sum(1 for p in icons if p.h)
        old = f'<a href="#p-{oldest[0].id}">{e(oldest[0].name)}</a>, there since {oldest[0].founded}' if oldest else ""
        facts.append(("One is" if len(icons) == 1 else f"{len(icons)} are") + " on our hand-checked lists"
                     + (f", {n_jb} of them with James Beard honors" if n_jb else "") + (f"; the longest at the same address is {old}." if old else "."))
    else:
        facts.append(f"None of our {len(HC)} hand-checked places is in {e(t)} yet, so the classics below are the nearest ones.")
    if casino:
        facts.append(f"{len(casino)} {'is' if len(casino) == 1 else 'are'} inside {e(and_list(sorted({p.host for p in casino})))}; the app labels each one.")
    facts.append(f'{e(t)} is in {e(county)} County, in the <a href="{region_url(region)}">{e(region)}</a> region.')
    parts.append(f'<section id="about-town"><h2>{e(t)} at a glance</h2><p>{" ".join(facts)}</p>'
                 + (f'<p>The City of Lewiston posts its restaurant inspection reports at <a href="{LEWISTON_PAGE}" rel="noopener">lewistonmaine.gov</a>. '
                    "Maine's official result is Pass or Fail, with no score or grade. For the places in Lewiston we matched to a posted report, the "
                    f'place\'s own page and its panel in the <a href="{e(explore_url(g="all", town=t))}">web search</a> show the latest result with '
                    f'its date. For anywhere in Maine, look a place up in the state\'s <a href="{STATE_HIP}" rel="noopener">health inspection search</a>.</p>'
                    if t == "Lewiston" else "")
                 + "</section>")

    L = Lister(here_town=t)
    if icons:
        old_txt = f" Longest at the same address: {year_line(oldest, 3)}. {oldest_link()}" if oldest else ""
        parts.append(f'<section id="icons"><h2>On our lists in {e(t)}</h2><p class="sub">The places in {e(t)} on our hand-checked lists, '
                     f"most featured first: James Beard honorees and long-running places lead. That order isn't a rating.{old_txt}</p>"
                     f'<ol class="places">' + L.items(icons) + "</ol></section>")
    for k, label, one, many, lst, rad, _, _ in TOWN_SECTIONS:
        n_g = len(lst)
        glink = (f'The <a href="{guide_link(k)}">statewide guide</a> has {n_g}.' if n_g > 1 else
                 f'It\'s the only one in the <a href="{guide_link(k)}">statewide guide</a> so far.')
        named = ""
        tag = {"lobster": "lobster", "clams": "clams", "diners": "diner", "dairy": "dairy", "oysters": "oyster"}.get(k)
        if tag and NAMED_IN_TOWN[tag][t]:
            cn = NAMED_IN_TOWN[tag][t]
            how = {"lobster": "“Lobster”", "clams": "“Clam”", "diner": "“Diner”", "dairy": "“Dairy” or “Creamery”", "oyster": "“Oyster”"}[tag]
            q = {"lobster": "lobster", "clams": "clam shack", "diner": "diner", "dairy": "dairy bar", "oyster": "oysters"}[tag]
            named = (f'The app\'s directory also has {plural(cn, "place")} in {e(t)} with {how} in the name that we haven\'t checked yet: '
                     f'<a href="{e(explore_url(g="all", town=t, q=q))}">see {"it" if cn == 1 else "them"} in the web search</a>.')
        dist = {p.id: d for d, p in shown[k]}

        def extra(p, rad=rad):
            return f"{mi(dist[p.id], rad)} mi from {t}" if p.id in dist else None
        if nearest_only[k]:
            if not shown[k]:
                continue
            lo, hi = mi(shown[k][0][0], rad), math.ceil(shown[k][-1][0])
            parts.append(f'<section id="{k}"><h2>The nearest {label.lower()} to {e(t)}</h2><p class="sub">None of our {n_g} hand-checked {many} is in {e(t)} or within {rad} miles. '
                         f'The closest {"is" if len(shown[k]) == 1 else "are"} {lo}{"" if len(shown[k]) == 1 else f" to {hi}"} miles away. {glink} {named}</p>'
                         f'<ol class="places">{L.items([p for _, p in shown[k]], extra)}</ol></section>')
            continue
        bits = []
        if ins[k]:
            dup = Counter(p.name for p in ins[k])
            bits.append(f"In {e(t)}: {and_list(f'<a href=\"#p-{p.id}\">{e(p.name)}</a>' + (f' ({e(p.addr)})' if dup[p.name] > 1 else '') for p in ins[k])}"
                        + (", listed above." if all(p in icons for p in ins[k]) else "."))
        if not within[k]:
            bits.append(f"None of our other {many} is within {rad} miles.")
        elif len(within[k]) > NEAR_N:
            bits.append(f"The {NEAR_N} nearest of the {len(within[k])} others within {rad} miles, closest first.")
        else:
            bits.append(f"{'The others' if ins[k] else 'Those'} within {rad} miles, closest first.")
        listed = [p for _, p in shown[k]]
        parts.append(f'<section id="{k}"><h2>{label} in and near {e(t)}</h2><p class="sub">{" ".join(bits)} {glink} {named}</p>'
                     + (f'<ol class="places">{L.items(listed, extra)}</ol>' if listed else "") + "</section>")
    if cuis:
        pills = "".join(f'<li><a href="{e(explore_url(g="all", town=t, kind=k))}">{e(k)} ({c:,})</a></li>' for k, c in cuis)
        src = and_list(["open map data", "the state's liquor license list"] + (["the city's inspection list"] if t == "Lewiston" else []))
        parts.append(f'<section id="cuisines"><h2>What {e(t)} eats</h2><p class="sub">The most common kinds of place among the {n_town:,} in {e(t)}, from {src}. Each opens the web search, filtered to {e(t)}.</p><ul class="towns">{pills}</ul></section>')
    parts.append(f'<section id="more"><h2>More Maine towns</h2>{town_links()}<p class="sub">Or by region:</p>{region_links()}</section>\n  </main>')
    uniq = list({p.id: p for p in icons + [p for k in shown for _, p in shown[k]]}.values())
    written.append(page(path, title, desc, "\n".join(parts),
                        [article_ld(url, h1, desc), bc, item_list(f"Hand-checked places in and near {t}", uniq, url)]))

# ---------------------------------------------------------------- region pages (the Maine Office of Tourism's eight, on county lines)
REGION_STATS = {}
REGION_WORD = {"lobster": "Lobster Shacks", "clams": "Clam Shacks", "sandwiches": "Italians", "sweets": "Whoopie Pies", "franco": "Franco-American Food",
               "diners": "Diners", "oysters": "Oyster Bars", "dairy": "Dairy Bars"}
for r in REGION_ORDER:
    ps = sorted([p for p in CHECKED_PLACES if p.region == r], key=lambda p: (p.city, p.name.lower()))
    n_rest = sum(REGION_TOWNS[r].values())
    path = f"regions/{REGION_SLUG[r]}.html"
    url = DOMAIN + "/" + path
    groups = [(k, [p for p in ps if p in G[k]]) for k in GUIDE_MASK]
    groups = [(k, g) for k, g in groups if g]
    other = [p for p in ps if not any(p in g for _, g in groups)]
    REGION_STATS[r] = {"restaurants": n_rest, "hand_checked": len(ps), **{k: len(g) for k, g in groups}}
    ranked = sorted(groups, key=lambda x: -len(x[1]))
    words = [REGION_WORD[k] for k, _ in ranked]
    co = checked_open(ps) if ps else f"checked in {CHECKED}"
    pairs = [(words[a], words[b]) for a in range(len(words)) for b in range(a + 1, len(words))] or [(words[0], "Restaurants")] if words else [("Restaurants", "Classics")]
    topts = []
    for w1, w2 in pairs:
        topts += [f"{r}, Maine: {w1} & {w2} | {BRAND}", f"{r}: {w1} & {w2}", f"{r}, Maine: {w1} & {w2}", f"{r} Maine Restaurants: {w1} & {w2}", f"{r}: {w1}, {w2} & More | {BRAND}",
                  f"{r} Region, Maine: {w1} & {w2}", f"{r}: {w1} & {w2} | {BRAND}", f"{r}, Maine Restaurants: {w1} & {w2}",
                  f"Maine's {r}: {w1}, {w2} & Restaurants"]
    if not words or len(words) == 1:
        topts += [f"{r}, Maine Restaurants & Hand-Checked Classics", f"{r} Restaurants, Maine | {BRAND} Region Guide"]
    topts = [o for o in topts if o.replace(BRAND, "").count("Maine") <= 1]   # not "Maine Beaches, Maine"
    title = fit(topts, 50, 60, TITLES)
    kinds_txt = and_list([plural(len(g), {"lobster": "lobster shack or roll stop", "clams": "clam shack", "sandwiches": "red snapper or Italian stop",
                                          "sweets": "whoopie pie or donut stop", "franco": "Franco-American place", "diners": "diner",
                                          "oysters": "oyster bar", "dairy": "dairy bar"}[k],
                                 {"lobster": "lobster shacks and roll stops", "clams": "clam shacks", "sandwiches": "red snapper and Italian stops",
                                  "sweets": "whoopie pie and donut stops", "franco": "Franco-American places", "diners": "diners",
                                  "oysters": "oyster bars", "dairy": "dairy bars"}[k]) for k, g in ranked][:3])
    paren = "" if counties_text(r) == r else f" ({counties_text(r)})"
    n_more = n_rest - len(ps)   # the directory's other places here (its total includes the hand-checked ones)
    n_hc = plural(len(ps), "hand-checked place")
    dopts = [f"{cap(kinds_txt)} in Maine's {r} region{paren}, {co}, by town. Free, no ratings.",
             f"{cap(kinds_txt)} in Maine's {r} region, {co}, listed by town with the season for each. Free, no ads, no ratings.",
             f"Hand-checked places in Maine's {r} region{paren}, {co}, plus {n_more:,} more restaurants in a free app.",
             f"{n_hc} in Maine's {r} region, {co}, with {n_more:,} more restaurants in the free {BRAND} app. No ratings.",
             f"{n_hc} among {n_rest:,} restaurants in Maine's {r} region{paren}, {co}, by town. Free."]
    wl = [{"Italians": "Italians", "Franco-American Food": "Franco-American food"}.get(w, w.lower()) for w in words]
    kts = [kinds_txt] + ([and_list(wl[:2]) + " and more"] if len(wl) >= 2 else []) + ([wl[0] + " and more"] if wl else []) + ["hand-checked places"]
    for kt in kts:
        for where in (f"Maine's {r} region", f"the {r} region of Maine", f"{r}, Maine"):
            for ck in (co, f"checked {CHECKED}"):
                for tail in (" Free, no ratings.", " Free, no ads, no ratings.", f" Plus {n_more:,} more restaurants in a free app.", f" With {n_more:,} more restaurants in a free app.", ""):
                    dopts.append(f"{cap(kt)} in {where}, {ck}, by town.{tail}")
                    dopts.append(f"{n_hc} in {where}, {ck}: {kt}.{tail}")
    desc = fit(dopts, 140, 160, DESCS)
    nav, bc = crumbs([("Home", "/"), ("Towns", "/cities/"), (r, "/" + path)])
    h1 = f"{r}: {' & '.join(w.lower() for w in words[:2])}" if len(words) >= 2 else f"{r} restaurants"
    towns = Counter(p.city for p in ps).most_common(3)
    facts = [(f"The {e(r)} region is the county itself." if counties_text(r) == r else f"The {e(r)} region is {e(counties_text(r))}.") + f" Of the {n_rest:,} places to eat and drink "
             f"the app knows here, the most are in {e(and_list(REGION_HINT[r]))}."]
    if ps:
        facts.append(f"Our hand-checked lists have {plural(len(ps), 'place')} here" + (f"; the towns with the most are {and_list(f'{e(t)} ({c})' for t, c in towns)}." if len(towns) > 1 else "."))
    rcuis = Counter(p.cuisine for p in REST if p.region == r and p.cuisine != "American & Other").most_common(3)
    if rcuis:
        facts.append(f"The most common kinds of place are {and_list(f'{e(k)} ({c:,})' for k, c in rcuis)}.")
    names, y, k_ = oldest_of(ps)
    if k_:
        facts.append(f"The longest at the same address {'is' if k_ == 1 else 'are'} {names}, there since {y}.")
    # the region's busiest towns, each a web search filtered to it: on a region with few hand-checked places (Aroostook has one) this
    # is most of what the page can offer, and it's different on every region page
    REGION_TOP_TOWNS = 12
    rtowns = sorted([(t, c) for t, c in REGION_TOWNS[r].items() if c >= 3], key=lambda x: (-x[1], x[0]))[:REGION_TOP_TOWNS]
    towns_sec = "" if not rtowns else (f'<section id="towns"><h2>Where to eat in the {e(r)} region</h2><p class="sub">The {len(rtowns)} towns here with the most '
                 f"places to eat and drink by the app's count; each link opens the web search for that town alone.</p>"
                 '<ul class="towns">' + "".join(f'<li><a href="{e(explore_url(g="all", town=t))}">{e(t)} ({c:,})</a></li>' for t, c in rtowns)
                 + "</ul></section>")
    cities_here = [t for t in TOWN_PAGES if REGION_OF_TOWN[t] == r]
    L = Lister()
    secs = []
    for k, g in groups:
        secs.append(f'<section id="{k}"><h2>{e(GUIDE_SHORT[k])} in the {e(r)} region</h2><p class="sub">{plural(len(g), "place")}, by town. '
                    + (f'The <a href="{guide_link(k)}">statewide guide</a> has {len(G[k])}.' if len(G[k]) > 1 else f'It\'s the only one in the <a href="{guide_link(k)}">statewide guide</a> so far.') + '</p><ol class="places">' + L.items(g) + "</ol></section>")
    if other:
        secs.append(f'<section id="icons"><h2>Icons and old favorites</h2><p class="sub">Hand-checked places here that aren\'t in the guides above: '
                    f'James Beard honorees, long-running places, inns and bakeries.</p><ol class="places">' + L.items(other) + "</ol></section>")
    body = f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{BRAND} · region guide · checked {CHECKED}</p>
    <h1>{e(h1)}</h1>
    <p class="lede">{e(cap(kinds_txt)) if kinds_txt else "Hand-checked places"} in Maine's {e(r)} region, each {co} against a {SOURCE_YEARS} source, plus the {n_rest:,} restaurants in the app's directory here.</p>
    <div class="cta-row">{store_button()}<a class="btn btn-ghost" href="{e(explore_url(g="all", view="map"))}">Search the map</a></div>
    <p class="pill">{store_note()}</p>
  </section>
  <section id="about-region">
    <h2>About this region</h2>
    <p>{" ".join(facts)}</p>
    <p class="fine">How we draw it: the Maine Office of Tourism's {e(r)} region, on county lines. Counties: {e(", ".join(REGION_COUNTIES[r]))}. A place is in it when its town is in one of those counties.{" Town pages here: " + ", ".join(f'<a href="{town_url(t)}">{e(t)}</a>' for t in cities_here) + "." if cities_here else ""}</p>
  </section>
  {towns_sec}
{chr(10).join(secs)}
  <section id="more"><h2>Other regions</h2>{region_links(skip=r)}</section>
  </main>"""
    written.append(page(path, title, desc, body, [article_ld(url, h1, desc), bc, item_list(f"Hand-checked places in Maine's {r} region", ps, url)]))

# ---------------------------------------------------------------- towns hub
nav, bc = crumbs([("Home", "/"), ("Towns", "/cities/")])
rows = "".join(f'<tr><td><a href="{town_url(t)}">{e(t)}</a></td><td class="n">{s["lobster_near"] + s["clams_near"]}</td><td class="n">{s["dairy_near"]}</td>'
               f'<td class="n">{s["hand_checked_in_town"]}</td><td class="n">{s["restaurants"]:,}</td></tr>' for t, s in TOWN_STATS.items())
rrows = "".join(f'<tr><td><a href="{region_url(r)}">{e(r)}</a></td><td>{e(", ".join(REGION_COUNTIES[r]))}</td><td class="n">{s["hand_checked"]}</td>'
                f'<td class="n">{s["restaurants"]:,}</td></tr>' for r, s in REGION_STATS.items())
title = fit([f"Maine Towns & Regions: Lobster Shacks & Dairy Bars | {BRAND}", f"Maine Towns & Regions: Lobster Shacks, Clams & Dairy Bars"], 50, 60, TITLES)
desc = fit([f"Lobster shacks, clam shacks, dairy bars and diners in and near {len(TOWN_PAGES)} Maine towns and {len(REGION_ORDER)} regions, from Kittery to Aroostook, checked in {CHECKED}.",
            f"Lobster shacks, clam shacks and dairy bars in and near {len(TOWN_PAGES)} Maine towns and {len(REGION_ORDER)} regions, each place checked in {CHECKED}. Free."], 140, 160, DESCS)
body = f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{BRAND} · by town and region</p>
    <h1>Maine towns and regions</h1>
    <p class="lede">Hand-checked lobster shacks, clam shacks, dairy bars, diners and more in and near {len(TOWN_PAGES)} Maine towns, and in the Maine Office of Tourism's {len(REGION_ORDER)} regions. Each place was checked in {CHECKED}.</p>
  </section>
  <section id="towns">
    <h2>Town pages</h2>
    <p class="sub">The {N_TOP_TOWNS} towns with the most restaurants in the app, the other towns with three or more hand-checked places, and a few coastal towns visitors look up by name. Counts are hand-checked places in or near each town (15 miles for lobster and clam shacks, 10 for dairy bars), the hand-checked places in the town itself, and the restaurants, cafés, bars and bakeries the app lists there.</p>
    <div class="tablewrap"><table><thead><tr><th scope="col">Town</th><th scope="col" class="n">Lobster, clams</th><th scope="col" class="n">Dairy bars</th><th scope="col" class="n">Checked, in town</th><th scope="col" class="n">Places</th></tr></thead><tbody>{rows}</tbody></table></div>
  </section>
  <section id="regions">
    <h2>Region pages</h2>
    <div class="tablewrap"><table><thead><tr><th scope="col">Region</th><th scope="col">Counties</th><th scope="col" class="n">Hand-checked</th><th scope="col" class="n">Restaurants</th></tr></thead><tbody>{rrows}</tbody></table></div>
    <p class="fine">Regions are the Maine Office of Tourism's, drawn on county lines; each region page says which counties. The statewide guides list their places by region: {and_list(f'<a href="{guide_link(k)}">{e(lc(GUIDE_SHORT[k]))}</a>' for k in GUIDE_PAGE)}.</p>
  </section>
  </main>"""
written.append(page("cities/index.html", title, desc, body, [bc]))

# ---------------------------------------------------------------- one page per hand-checked or honored place
TITLE_KIND = {"lobster shack": "Lobster Shack", "lobster roll": "Lobster Rolls", "clam shack": "Clam Shack", "red snapper": "Red Snapper Hot Dogs",
              "italian sandwich": "Maine Italian Sandwiches", "whoopie pie": "Whoopie Pies", "potato doughnut": "Potato Donuts",
              "blueberry pie": "Blueberry Pie", "franco american": "Franco-American Food", "diner": "Maine Diner", "oyster bar": "Oyster Bar",
              "dairy bar": "Dairy Bar & Ice Cream"}
JB_TITLE = {"America's Classic": "James Beard America's Classic", "James Beard winner": "James Beard Award Winner",
            "James Beard nominee": "James Beard Award Nominee", "James Beard semifinalist": "James Beard Semifinalist"}


def kind_labels(p):
    """Title labels for a place, most specific first. A label the name already says ("... Lobster Pound", "... Diner") is skipped."""
    ks = [TITLE_KIND[k] for k in D["kinds"] if k in TITLE_KIND and p.kinds & KIND[k]]
    low = p.name.lower()
    ks = [k for k in ks if not any(w in low for w in ("shack", "pound", "lobster", "diner", "oyster", "dairy", "ice cream", "donut", "whoopie")
                                   if w in k.lower())] or ks
    out = []
    if len(ks) >= 2:
        out.append(f"{ks[0]} & {ks[1]}")
    out += ks
    if p.jb_label:
        out.insert(0, JB_TITLE[p.jb_label])
    if p.founded:
        out += [f"At the Same Address Since {p.founded}", f"Since {p.founded}"]
    if p.ip is not None:
        out.append("Maine Icon")
    return out + ["Hand-Checked", "Maine Restaurant"]


def low_label(k):
    return k if k.startswith(("Maine", "Franco")) else k.lower()


def short_kind(p):
    return (and_list([low_label(k) for k in p.kind_names() if k != "Historic"][:2]) or ("James Beard honoree" if p.h else "icon" if p.ip is not None
            else f"since {p.founded}" if p.founded else "hand-checked"))


def place_title(p):
    town = p.city or "Maine"
    # Maine's own formula ("Amato's in Portland, Maine: ..."), not the "Name, Town: Kind | Brand" other state sites use
    locs = [f"{p.name} in {town}, Maine", f"{p.name} in {town}, ME", f"{p.name}, {town}, Maine", f"{p.name}, {town}"]
    sfxs = ("", f" · {BRAND}", f" | {BRAND} App")
    opts = [f"{loc}: {k}{sfx}" for loc in locs for k in kind_labels(p) for sfx in sfxs]   # the town matters most, then the kind, then the brand
    opts += [f"{loc}{sfx}" for loc in locs for sfx in sfxs] + [f"{p.name}: {k}{sfx}" for k in kind_labels(p) for sfx in sfxs]
    opts += [f"{p.name}, {town}: {k}, Hand-Checked {CHECKED}" for k in kind_labels(p)]
    return fit(opts, 50, 60, TITLES)


def place_desc(p):
    town = p.city or "Maine"
    leads = [f"{p.name} in {town}, Maine,", f"{p.name} in {town}, ME,", f"{p.name} in {town}"]
    kinds = [low_label(k) for k in p.kind_names() if k != "Historic"]
    facts = []
    if kinds:
        facts += [f"is on our {and_list(kinds)} {'list' if len(kinds) == 1 else 'lists'}" + (f", at its address since {p.founded}" if p.founded else ""),
                  f"is on our {and_list(kinds)} {'list' if len(kinds) == 1 else 'lists'}"]
    if p.jb_label:
        facts.append(f"is a {p.jb_label.replace('America', 'James Beard America')}" if p.h & 1 else f"is a {p.jb_label}")
    if p.founded:
        facts.append(f"has been at its address since {p.founded}")
    facts.append("is on our hand-checked list")
    ck = "checked in business" if p.seasonal else "checked open"
    links = and_list([x for x in ("address", "website" if p.site else "", "phone" if p.phone else "", "directions") if x])
    tails = [f"{cap(ck)} in {CHECKED} against a {SOURCE_YEARS} source, with {links}.", f"{cap(ck)} in {CHECKED}, with {links} and places nearby.",
             f"{cap(ck)} in {CHECKED}, with {links}.", f"Hand-checked in {CHECKED}, with {links} and nearby places.",
             f"{cap(ck)} in {CHECKED} against a {SOURCE_YEARS} source.", f"{cap(ck)} in {CHECKED}."]
    opts = []
    if p.note:   # the research note is the most specific thing we can say; use it when it fits
        note = p.note.rstrip(".") + "."
        opts += [f"{p.name} in {town}, Maine. {note}", f"{p.name} in {town}, Maine. {note} {cap(ck)} {CHECKED}.",
                 f"{p.name} in {town}. {note} {cap(ck)} in {CHECKED}.", f"{p.name}, {town}, Maine. {note}"]
        opts += [f"{p.name}, {town}: {note}", f"{p.name}, {town}: {note} {cap(ck)} in {CHECKED}.", f"{p.name} in {town}: {note} Hand-checked {CHECKED}.",
                 f"{note} {cap(ck)} in {CHECKED}, with {links}.", f"{note} Hand-checked in {CHECKED}."]
    opts += [f"{lead} {f}. {t}" for t in tails for f in facts for lead in leads]
    opts += [f"{p.name}, {p.addr}, {town}, Maine: {f}. {t}" for t in tails for f in facts]
    return fit(opts, 140, 160, DESCS)


def apple_maps(p):
    if p.lat is not None:
        return f"https://maps.apple.com/?q={urllib.parse.quote(p.name)}&ll={p.lat:.5f},{p.lon:.5f}"
    return f"https://maps.apple.com/?q={urllib.parse.quote(p.name + ', ' + p.addr + ', ' + p.city + ', ME')}"


def directions(p):
    return f"https://maps.apple.com/?daddr={p.lat:.5f},{p.lon:.5f}&dirflg=d" if p.lat is not None else apple_maps(p)


GUIDE_OF = [(k, G[k]) for k in GUIDE_MASK]
N_PLACE_PAGES = 0
for p in CHECKED_PLACES:
    path = f"places/{p.slug}.html"
    url = DOMAIN + "/" + path
    guides = [k for k, ps in GUIDE_OF if p in ps]
    on_pages = [k for k in guides if k in GUIDE_PAGE]
    parent = ((GUIDE_SHORT[on_pages[0]], "/" + GUIDE_FILE[on_pages[0]]) if on_pages else
              ("Maine icons", "/" + ICONS_FILE) if ICONS_PAGE and p in ICONS else
              (p.city, town_url(p.city)) if p.city in TOWN_PAGES else (p.region, region_url(p.region)))
    nav, bc = crumbs([("Home", "/"), parent, (p.name, "/" + path)])
    rows = []
    if guides:
        rows.append(("On our lists", ", ".join(f'<a href="{guide_link(k)}">{e(GUIDE_SHORT[k])}</a>' for k in guides)))
    if p.dish:
        rows.append(("Known for", e(p.dish)))
    if p.season:
        rows.append(("Season", e(p.season) + (" (seasonal)" if p.seasonal and "season" not in p.season.lower() else "")))
    elif p.seasonal:
        rows.append(("Season", "Seasonal; check before you go."))
    if p.founded:
        rows.append(("At this address since", f"{p.founded} (checked against the place's own history page or local news)"))
    if p.branch:
        rows.append(("A branch of", e(p.branch)))
    honors = [f"James Beard: {x}" for x in p.jbf.split("; ") if x] + [x for x in p.hon.split("; ") if x]
    if honors:
        rows.append(("Honors", "<ul>" + "".join(f"<li>{e(x)}</li>" for x in honors) + "</ul>"))
    if p.chef:
        rows.append(("Chef", e(p.chef)))
    if p.cuisine and p.cuisine != "American & Other":
        rows.append(("Kind of place", e(p.cuisine)))
    if p.t == 2 and p.j == 1:
        rows.append(("Maine liquor license (BABLO)", e(p.lk) if p.lk else "On the state's list"))
    if p.host:
        rows.append(("Host venue", e(HOST_AT[p.host][2])))
    facts_html = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows)
    addr = ", ".join(x for x in (p.addr, p.place_name) if x) + (f", ME {p.zip}" if p.zip else ", ME")
    acts = [f'<a class="btn btn-fill" href="{e(apple_maps(p))}" rel="noopener">Hours &amp; photos in Apple Maps</a>',
            f'<a class="btn btn-ghost" href="{e(directions(p))}" rel="noopener">Directions</a>']
    if p.site:
        acts.append(f'<a class="btn btn-ghost" href="{e(p.site)}" rel="noopener nofollow">Website</a>')
    if p.phone:
        acts.append(f'<a class="btn btn-ghost" href="tel:{p.phone}">Call {e(p.phone_text())}</a>')
    acts.append(f'<a class="btn btn-ghost" href="/explore/#p={p.id}">Open in the web app</a>')
    near = sorted(((miles((p.lat, p.lon), (q.lat, q.lon)), q) for q in CHECKED_PLACES if q is not p and q.lat is not None and p.lat is not None),
                  key=lambda x: (x[0], x[1].name.lower()))[:6]
    near_html = "".join(f'<li><a href="{place_url(q)}">{e(q.name)}</a><span>{e(q.place_name)} · {d:.1f} mi · {e(short_kind(q))}</span></li>' for d, q in near)
    more = [f'<a href="{guide_link(k)}{"#p-" + p.id if k in GUIDE_PAGE else ""}">{e(GUIDE_SHORT[k])}</a>' for k in guides]
    if ICONS_PAGE and p in ICONS:
        more.append(f'<a href="/{ICONS_FILE}#p-{p.id}">Maine icons</a>')
    if p in OLDEST:
        more.append(f'<a href="/{OLDEST_FILE}#p-{p.id}">Oldest restaurants</a>')
    if p.city in TOWN_PAGES:
        more.append(f'<a href="{town_url(p.city)}">{e(p.city)} page</a>')
    more.append(f'<a href="{region_url(p.region)}">{e(p.region)} page</a>')
    ck = "Checked in business" if p.seasonal else "Checked open"
    inspection = ""
    if p.lw:
        lw = p.lw
        res = "Passed" if lw["r"] == "Pass" else "Failed"
        inspection = (f'<section id="inspection"><h2>Health inspection</h2>'
                      f'<p class="result"><span class="rb rb-{"pass" if lw["r"] == "Pass" else "fail"}" aria-hidden="true">{res}</span>'
                      f'<b>City of Lewiston inspection: {res}, {nice_date(lw["d"])}</b></p>'
                      f'<p>The latest result the City of Lewiston posts for this place (read {nice_date(D["lewiston_fetched"])}).'
                      + (f" Inspected as {e(lw['n'])}." if lw["n"] else "")
                      + (f' <a href="{e(lw["u"])}" rel="noopener">The city\'s inspection report</a>.' if lw["u"] else "") + "</p>"
                      "<p class=\"fine\">Maine's official result is Pass or Fail, with no score or grade: a place fails with more than 3 critical or more "
                      "than 10 non-critical violations (10-144 CMR Ch. 201). A result describes one inspection on that day. Lewiston is the only place in "
                      "Maine that posts its results in a form we can show; for the rest, use the state's "
                      f'<a href="{STATE_HIP}" rel="noopener">health inspection search</a>.</p></section>')
    intro = p.note
    title = place_title(p)
    desc = place_desc(p)
    subject = urllib.parse.quote(f"Maine Eats: problem with {p.name}, {p.place_name or 'Maine'}")
    body = f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{e(kind_labels(p)[0])} · {e(p.place_name or "Maine")}</p>
    <h1>{e(p.name)}</h1>
    {f'<p class="lede">{e(intro)}</p>' if intro else ""}
    <p class="addr">{e(addr)}</p>
    <div class="actions">{"".join(acts)}</div>
  </section>
  <section id="checked">
    <h2>What we checked</h2>
    <dl class="facts">{facts_html}</dl>
    <p class="fine">{ck} in {CHECKED} against a {SOURCE_YEARS} source: the place's own site or menu, local news, or a town or chamber listing.{" It's seasonal, so check its season before you go." if p.seasonal else ""} Hours and menus change, so check with {e(p.name)} before you go. Hours, photos and ratings are Apple Maps' own, in its place card. To look up inspections, use the State of Maine's <a href="{STATE_HIP}" rel="noopener">health inspection search</a>. Something wrong? <a href="mailto:{EMAIL}?subject={subject}">Tell us</a>.</p>
  </section>
  {inspection}
  <section id="nearby">
    <h2>Nearby on our lists</h2>
    <ul class="near">{near_html}</ul>
    <p class="plinks">More: {" · ".join(more)}</p>
  </section>
  <section id="app" class="final">
    <h2>Save it for the drive</h2>
    <p class="sub">The free {BRAND} app has {e(p.name)} and {N_REST - 1:,} other Maine places, sorted by distance from you, with Apple Maps' live hours and photos.</p>
    <div class="cta-row">{store_button()}</div>
    <p class="pill">{store_note()}</p>
  </section>
  </main>"""
    written.append(page(path, title, desc, body, [restaurant_ld(p, url), bc], og_alt=f"{BRAND}: {p.name}, {p.place_name or 'Maine'}"))
    N_PLACE_PAGES += 1

# ---------------------------------------------------------------- web app (docs/explore/): data split + page
os.makedirs(f"{DOCS}/data", exist_ok=True)
CORE_KEYS = ["id", "n", "c", "vi", "cu", "t", "s", "a", "z", "la", "lo", "b", "ch", "v", "g", "hc", "k", "h", "ip", "fs", "f", "host", "seas", "j",
             "dish", "br"]   # br in core: "Hide chains" keeps a hand-checked original (hc, no br) and can drop its branches
DETAIL_KEYS = ["ph", "w", "note", "jbf", "hon", "sea", "chef", "lk", "lw"]   # never the license holder; the data has none
cols = {k: [] for k in CORE_KEYS}
detail = []
for p in PLACES:
    r = p.r
    for k in CORE_KEYS:
        v = r.get(k)
        if k == "vi" and v is not None and p.village != VILLAGES[v]:
            v = None   # not a real village (a township or plantation name, or the town's own name)
        if k == "host" and not p.host:
            v = None   # the pipeline's host match caught a place that isn't at the casino
        cols[k].append(round(v, 5) if k in ("la", "lo") and v is not None else v)
    d = {k: r[k] for k in DETAIL_KEYS if r.get(k)}
    # the same guards as the static pages: a phone only if it's a valid US number, a website only if it's http(s), and Lewiston's
    # result only when it's a dated Pass or Fail in Lewiston
    for k, ok in (("ph", p.phone), ("w", p.site), ("jbf", p.jbf), ("lw", p.lw)):
        if ok:
            d[k] = ok
        else:
            d.pop(k, None)
    detail.append(d or None)
core = {"generated": D["generated"], "checked": CHECKED, "license_date": D.get("license_date"), "lewiston_fetched": D.get("lewiston_fetched"),
        "cities": CITIES, "villages": VILLAGES, "cuisines": CUISINES, "brands": D["brands"], "hosts": HOSTS, "sources": D["sources"],
        "regions": REGIONS, "town_region": D["town_region"], "tags": D["tags"], "kinds": D["kinds"], "calibration": D.get("calibration", {}), "cols": cols}
json.dump(core, open(f"{DOCS}/data/core.json", "w"), separators=(",", ":"), ensure_ascii=False)
json.dump(detail, open(f"{DOCS}/data/detail.json", "w"), separators=(",", ":"), ensure_ascii=False)
json.dump(SHAPES, open(f"{DOCS}/data/me_shapes.json", "w"), separators=(",", ":"))
assert not private_words(open(f"{DOCS}/data/core.json").read() + open(f"{DOCS}/data/detail.json").read()), "a private address in the data"
assert all(p.id in set(cols["id"]) for p in CHECKED_PLACES), "every place page's #p= link must open in the web app"

EXPLORE_CSS = """
  [hidden] { display: none !important; }
  :root { --land: #f1e8d6; --sea: #dcecec; --mapline: #d6c8ad; --mapedge: #9c8a68; --dot: #0e4d5c; --dothc: #f2b705; --dotedge: #10262e; --here: #c2492f; }
  @media (prefers-color-scheme: dark) { :root { --land: #1e363d; --sea: #0b2229; --mapline: #2f4c54; --mapedge: #5b7c84; --dot: #86d3d0; --dotedge: #0c1a1f; --here: #f08a6c; } }
  .ex-hero { padding: 26px 0 6px; }
  .ex-hero h1 { font-size: clamp(30px, 6vw, 44px); }
  .ex-controls { background: var(--bg); padding: 10px 0 8px; border-bottom: 1px solid var(--rule); }
  .ex-guides { display: flex; gap: 6px; overflow-x: auto; padding-bottom: 8px; scrollbar-width: none; }
  /* more guides off to the right: the row fades out at its edge until it's scrolled to the end */
  .ex-guides.more { -webkit-mask-image: linear-gradient(90deg, #000 calc(100% - 44px), transparent); mask-image: linear-gradient(90deg, #000 calc(100% - 44px), transparent); }
  @media (min-width: 601px) { .ex-guides { flex-wrap: wrap; overflow-x: visible; } }   /* room to show each guide, also beside the panel */
  .ex-guides button, .ex-view button, .ex-small { flex: 0 0 auto; display: inline-flex; align-items: center; justify-content: center; min-height: 36px; border: 1px solid var(--ctl); background: var(--surface); color: var(--head); border-radius: 999px; padding: 6px 12px; font: 600 14px/1.2 var(--text); cursor: pointer; }
  #ex-app :disabled { opacity: .55; cursor: default; }
  .ex-guides button[aria-pressed="true"], .ex-view button[aria-pressed="true"] { background: var(--fill); color: var(--onfill); border-color: var(--fill); }
  .ex-row1 { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
  .ex-row1 input[type=search] { flex: 1 1 200px; min-width: 0; min-height: 44px; font: 16px/1.3 var(--text); padding: 10px 12px; border: 2px solid var(--ctl); border-radius: 12px; background: var(--surface); color: var(--ink); }
  .ex-row2 { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 8px; font-size: 14px; color: var(--ink2); }
  .ex-row2 label { display: inline-flex; align-items: center; gap: 6px; }
  .ex-row2 select { font: 14px/1.2 var(--text); min-height: 36px; padding: 6px 8px; border: 1px solid var(--ctl); border-radius: 8px; background: var(--surface); color: var(--ink); max-width: 46vw; }
  .ex-row2 input[type=checkbox] { accent-color: var(--fill); }
  .ex-view { margin-left: auto; display: flex; gap: 4px; }
  #ex-count { margin: 8px 0 0; font-size: 14px; color: var(--muted); min-height: 1.55em; }
  #ex-sub { margin: 4px 0 0; font-size: 14px; color: var(--ink2); min-height: 1.55em; }
  /* the list's space is held from the first paint, so nothing below it jumps when the data arrives (CLS) */
  #ex-listwrap { min-height: 100vh; }
  #ex-locmsg { font-size: 13px; color: var(--muted); margin: 4px 0 0; }
  #ex-locmsg:empty { display: none; }
  .ex-list { list-style: none; padding: 0; margin: 10px 0; }
  .ex-list li + li { border-top: 1px solid var(--rule); }
  .ex-row { width: 100%; min-height: 44px; display: flex; gap: 12px; align-items: center; text-align: left; background: none; border: 0; padding: 12px 4px; cursor: pointer; color: var(--ink); font: inherit; }
  .ex-row:hover { background: var(--surface2); }
  .ex-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; overflow-wrap: anywhere; }
  .ex-main b { font-weight: 650; }
  .ex-town { font-size: 14px; color: var(--muted); }
  .ex-metric { text-align: right; display: flex; flex-direction: column; }
  .ex-metric b { font: 800 22px/1 var(--display); color: var(--head); }
  .ex-metric small { font-size: 12px; color: var(--muted); }
  .ex-rank { flex: 0 0 34px; height: 34px; display: grid; place-items: center; font: 800 20px/1 var(--display); color: var(--head); border-radius: 8px; }
  .ex-rank.top { background: var(--buoy); color: var(--onbuoy); }
  .ex-empty { padding: 24px 4px; color: var(--muted); }
  .ex-widen { padding: 14px 4px; color: var(--muted); }   /* a search that found only a few places in a guide: the statewide offer under them */
  .ex-linkbtn { display: inline-flex; align-items: center; min-height: 44px; padding: 0 14px; margin-left: 4px; border: 1px solid var(--ctl); border-radius: 999px; background: var(--surface); color: var(--head); font: 600 15px/1.2 var(--text); cursor: pointer; }
  #ex-more { display: flex; margin: 8px auto 24px; }
  #ex-mapwrap { position: relative; height: min(70vh, 680px, calc(110vw + 40px)); margin: 10px 0 20px; border: 1px solid var(--rule); border-radius: 16px; overflow: hidden; background: var(--sea); }
  #ex-map { width: 100%; height: 100%; display: block; touch-action: none; cursor: grab; }
  .ex-zoom { position: absolute; right: 10px; top: 10px; display: flex; flex-direction: column; gap: 6px; }
  .ex-zoom button { width: 44px; height: 44px; border-radius: 10px; border: 1px solid var(--ctl); background: var(--surface); color: var(--head); font: 700 20px/1 var(--text); cursor: pointer; }
  #ex-maphint { position: absolute; left: 10px; bottom: 8px; margin: 0; font-size: 13px; background: var(--surface); padding: 3px 8px; border-radius: 999px; color: var(--ink2); }
  .ex-chooser { position: absolute; z-index: 5; width: min(280px, calc(100% - 20px)); max-height: 60%; overflow-y: auto; background: var(--surface); border: 1px solid var(--ctl); border-radius: 12px; box-shadow: 0 6px 20px rgba(16,38,46,.18); padding: 6px 8px; }
  .ex-chooser p { margin: 4px 6px 6px; font-size: 13px; color: var(--muted); }
  .ex-chooser ul { list-style: none; margin: 0; padding: 0; }
  .ex-chooser button { display: block; width: 100%; min-height: 44px; text-align: left; background: none; border: 0; border-top: 1px solid var(--rule); padding: 8px 6px; font: 15px/1.3 var(--text); color: var(--ink); cursor: pointer; }
  .ex-chooser button:hover { background: var(--surface2); }
  .ex-panel { position: fixed; z-index: 20; right: 0; top: 0; bottom: 0; width: clamp(320px, 40vw, 440px); overflow-y: auto; background: var(--surface); border-left: 1px solid var(--rule); box-shadow: -8px 0 24px rgba(16,38,46,.14); padding: 18px 20px 40px; overflow-wrap: anywhere; }
  @media (max-width: 600px) { .ex-panel { width: 100%; top: auto; height: 86vh; border-left: 0; border-top: 3px solid var(--coral); border-radius: 18px 18px 0 0; } }
  /* wider screens: the open panel is a side column, and the page moves left so it covers none of the controls */
  @media (min-width: 601px) { body.ex-open .wrap { margin-left: auto; margin-right: calc(clamp(320px, 40vw, 440px) + 12px); } }
  .ex-close { position: sticky; top: 0; float: right; width: 44px; height: 44px; border-radius: 50%; border: 1px solid var(--ctl); background: var(--surface); font: 400 24px/1 var(--text); cursor: pointer; color: var(--ink); }
  .ex-kicker { margin: 0; font-size: 12px; font-weight: 700; letter-spacing: .1em; color: var(--link); }
  .ex-panel h2 { font-size: 34px; margin: 4px 0 6px; text-transform: uppercase; }
  .ex-addr, .ex-dist { margin: 0 0 4px; color: var(--ink2); font-size: 15px; }
  .ex-actions { margin: 14px 0 8px; display: grid; gap: 8px; }
  .ex-apple { justify-content: center; }
  .ex-act-row { display: flex; gap: 8px; flex-wrap: wrap; }
  .ex-act-row a, .ex-act-row button { flex: 1 1 auto; min-width: 0; min-height: 44px; display: inline-flex; align-items: center; justify-content: center; white-space: nowrap; text-align: center; padding: 10px 12px; border: 1px solid var(--ctl); border-radius: 12px; text-decoration: none; color: var(--head); font: 600 15px/1.2 var(--text); background: var(--surface); cursor: pointer; }
  .ex-act-row button[aria-pressed="true"] { background: var(--soft); color: var(--onsoft); }
  .ex-sec { margin-top: 18px; padding: 0; border-top: 0; }
  .ex-sec h3 { font-size: 12px; letter-spacing: .1em; text-transform: uppercase; color: var(--ink2); border-bottom: 1px solid var(--rule); padding-bottom: 6px; margin-bottom: 8px; }
  .ex-sec p, .ex-sec li { font-size: 15px; color: var(--ink2); margin: 6px 0; }
  .ex-sec a { display: inline-flex; align-items: center; min-height: 44px; }
  .ex-kv { display: flex; justify-content: space-between; gap: 12px; font-size: 15px; padding: 3px 0; }
  .ex-kv span { color: var(--ink2); }
  .ex-kv b { text-align: right; }
  .ex-fine { font-size: 13px !important; color: var(--muted) !important; }
  .ex-fine a { min-height: 0 !important; display: inline !important; }
  .ex-grade { display: flex; align-items: center; gap: 12px; }
  .ex-grade b { display: block; color: var(--ink); font-size: 17px; }
  .ex-app { margin-top: 22px; font-size: 14px; color: var(--muted); }
  .ex-app a { display: inline-flex; align-items: center; min-height: 44px; }
  .ex-short { display: none; }
  body.ex-open { overflow: hidden; }
  @media (min-width: 601px) { body.ex-open { overflow: auto; } }
  @media (max-width: 600px) {
    .ex-long { display: none; }
    .ex-short { display: inline; }
    #ex-sub { min-height: 3.1em; }   /* most guides' descriptions take two lines here; hold them so the count below doesn't jump */
    /* 44 px touch targets */
    .ex-guides button, .ex-view button, .ex-small, .ex-row2 select { min-height: 44px; }
    .ex-row2 select { font-size: 16px; }   /* under 16px, iOS Safari zooms the page when a field gets focus */
    .ex-row2 label { min-height: 44px; }
    .ex-row2 input[type=checkbox] { width: 20px; height: 20px; margin: 0; }
  }
  /* phones: the search box gets the whole row (sharing it with "Use my location" cut the placeholder's "dish" at 402 px) */
  @media (max-width: 600px) { .ex-row1 input[type=search] { flex-basis: 100%; } }
"""
url = f"{DOMAIN}/explore/"
title = fit(["Search Maine Restaurants, Lobster Shacks & Clam Shacks", f"Maine Restaurant Search & Map | {BRAND}"], 50, 60, TITLES)
desc = fit([f"Search {N_REST:,} Maine restaurants by name, town, village or street, and map {len(LOBSTER)} hand-checked lobster shacks and {len(DAIRY)} dairy bars. Free.",
            f"Search {N_REST:,} Maine restaurants by name, town or street, and map {len(LOBSTER)} hand-checked lobster shacks and {len(DAIRY)} dairy bars. Free, no ads.",
            f"Search {N_REST:,} Maine restaurants by name, town, village, street or dish, and map {len(LOBSTER)} hand-checked lobster shacks and {len(DAIRY)} dairy bars. Free, no ads.",
            f"Search {N_REST:,} Maine restaurants by name, town, village, street or dish, and map {len(LOBSTER)} hand-checked lobster shacks and {len(DAIRY)} dairy bars.",
            f"Search {N_REST:,} Maine restaurants by name, town or street, and map {len(LOBSTER)} hand-checked lobster shacks, {len(CLAMS)} clam shacks and {len(DAIRY)} dairy bars. Free."], 140, 160, DESCS)
nav, bc = crumbs([("Home", "/"), ("Search", "/explore/")])
EX_GUIDES = (("lobster", "Lobster"), ("clams", "Clam shacks"), ("sandwiches", "Snappers & Italians"), ("sweets", "Whoopie pies"),
             ("franco", "Franco-American"), ("diners", "Diners"), ("oysters", "Oyster bars"), ("dairy", "Dairy bars"), ("icons", "Icons"),
             ("oldest", "Oldest"), ("near", "Near me"), ("all", "Statewide"), ("saved", "Saved"))
guide_buttons = "".join(f'<button type="button" data-g="{k}" aria-pressed="false" disabled>{e(t)}</button>' for k, t in EX_GUIDES)
# The controls are drawn from the first paint, disabled until the data arrives, with the same options explore.js fills in,
# so nothing on screen moves when it does (the list's space is held by CSS).
town_opts = '<option value="">All towns</option>' + "".join(f"<option>{e(t)}</option>" for t in sorted(TOWN_COUNT))
cuis_opts = '<option value="">All kinds</option>' + "".join(f'<option value="{e(c)}">{e(c)} ({k:,})</option>' for c, k in Counter(p.cuisine for p in REST).most_common())
sort_opts = "".join(f"<option>{s}</option>" for s in ("Featured first", "Nearest", "Oldest first", "A to Z"))
body = f"""{nav}
  <main id="main">
  <section class="ex-hero">
    <p class="kicker">{BRAND} · on the web</p>
    <h1>Search Maine restaurants</h1>
    <p class="sub"><span class="ex-long">Look up any of {N_REST:,} places to eat and drink in {N_TOWNS} Maine towns by name, town, village, road or dish, or open a hand-checked guide: {len(LOBSTER)} lobster shacks and roll stops, {len(CLAMS)} clam shacks, {len(SAND)} red snapper and Italian stops, {len(SWEETS)} whoopie pie and donut places, {len(DINERS)} diners, {len(OYSTERS)} oyster bars and {len(DAIRY)} dairy bars. It runs on the iPhone and iPad app's own data, and anything you save stays in this browser.</span><span class="ex-short">{N_REST:,} Maine places in {N_TOWNS} towns, and the hand-checked guides.</span></p>
  </section>
  <noscript><p>The search needs JavaScript. The guides work without it: {", ".join(f'<a href="/{u}">{e(lc(n))}</a>' for u, n in FOOTER_PAGES)}, and <a href="/cities/">towns and regions</a>.</p></noscript>
  <div id="ex-app" aria-busy="true">
    <div class="ex-controls">
      <div class="ex-guides" role="group" aria-label="Guides">{guide_buttons}</div>
      <div class="ex-row1">
        <label class="skip" for="ex-q">Search</label>
        <input id="ex-q" type="search" placeholder="Name, town, street, or dish" autocomplete="off" enterkeyhint="search" disabled>
        <button type="button" id="ex-locate" class="ex-small" disabled>Use my location</button>
      </div>
      <div class="ex-row2">
        <label>Sort <select id="ex-sort" aria-label="Sort" disabled>{sort_opts}</select></label>
        <select id="ex-town" aria-label="Town" disabled>{town_opts}</select>
        <select id="ex-cuisine" aria-label="Kind of place" disabled>{cuis_opts}</select>
        <label><input type="checkbox" id="ex-chains" disabled> Hide chains</label>
        <label><input type="checkbox" id="ex-conf" disabled> Confirmed only</label>
        <button type="button" id="ex-clear" class="ex-small" hidden>Clear filters</button>
        <div class="ex-view" role="group" aria-label="View"><button type="button" data-v="list" aria-pressed="true" disabled>List</button><button type="button" data-v="map" aria-pressed="false" disabled>Map</button></div>
      </div>
      <p id="ex-sub"></p>
      <p id="ex-count" aria-live="polite"></p>
      <p id="ex-locmsg"></p>
    </div>
    <div id="ex-listwrap"><ol id="ex-list" class="ex-list"><li class="ex-empty" id="ex-loading">Loading the restaurant list…</li></ol><button type="button" id="ex-more" class="ex-small" hidden></button></div>
    <div id="ex-mapwrap" hidden>
      <canvas id="ex-map" role="img" aria-label="Map of Maine's {len(SHAPES['counties'])} counties with a dot for each place in the list. The list view has the same places."></canvas>
      <div class="ex-zoom"><button type="button" id="ex-zin" aria-label="Zoom in">+</button><button type="button" id="ex-zout" aria-label="Zoom out">−</button></div>
      <div id="ex-chooser" class="ex-chooser" role="dialog" aria-labelledby="ex-chooser-h" hidden></div>
      <p id="ex-maphint"></p>
    </div>
    <p class="fine">“Confirmed only” keeps the places that hold a Maine liquor license, appear on Lewiston's inspection list, have a high-confidence map listing, or were checked by hand by us; gas-station counters, grocery delis and other non-restaurants never show. A Lewiston inspection result shows only in that place's own panel, as the city posts it; for the rest of Maine, try the state's <a href="{STATE_HIP}" rel="noopener">health inspection search</a>. County outlines: U.S. Census Bureau. See also <a href="/{OLDEST_FILE}">Maine's oldest restaurants</a>.</p>
  </div>
  <div id="ex-panel" class="ex-panel" role="complementary" aria-labelledby="ex-pname" hidden></div>
  </main>
<script>
// read by explore.js for the place panel's app link (set APP_STORE_URL in scripts/make-site.py) and the inspection search link
window.APP_STORE_URL = {json.dumps(APP_STORE_URL)};
window.STATE_HIP = {json.dumps(STATE_HIP)};
window.SUPPORT_EMAIL = {json.dumps(EMAIL)};
{open(f"{ROOT}/scripts/explore.js").read()}
</script>"""
webapp_ld = {"@context": "https://schema.org", "@type": "WebApplication", "name": f"{BRAND} web app", "url": url,
             "applicationCategory": "TravelApplication", "operatingSystem": "Any", "browserRequirements": "Requires JavaScript",
             "description": desc, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}, "publisher": ORG}
# fetch the data while the page parses; without JavaScript the (disabled) controls are hidden and the noscript note shows
explore_head = ('<link rel="preload" href="/data/core.json" as="fetch" crossorigin>\n'
                '<noscript><style>#ex-app { display: none; }</style></noscript>\n')
written.append(page("explore/index.html", title, desc, body, [webapp_ld, bc], extra_css=EXPLORE_CSS, head_extra=explore_head))

# ---------------------------------------------------------------- landing page
# App screenshots: screenshots/<name>.png (outside docs/, so the full-size captures aren't published) -> docs/img/screen-<name>.png
# (480 px) + .webp. The strip appears once they exist.
SHOT_SRC = f"{ROOT}/screenshots"
SHOTS = [("home", "Maine Eats home screen: Lobster Shacks & Rolls, Clam Shacks, Red Snappers & Italians, Whoopie Pies & Donuts, Diners, Oyster Bars and Dairy Bars guides, with a search box.", "Guides for the shore and the road."),
         ("lobster", "Lobster Shacks & Rolls list in Maine Eats, with seasonal shacks labeled.", "Lobster shacks nearest you first."),
         ("detail", "A place in Maine Eats: address, a button for hours and photos in Apple Maps, and what it's known for.", "Each place, with Apple Maps' live card."),
         ("map", "Maine Eats map of Maine with pins for lobster shacks, clam shacks and dairy bars.", "The map, by shack, diner or dairy bar.")]
if os.path.isdir(SHOT_SRC):
    os.makedirs(f"{DOCS}/img", exist_ok=True)
    for name, _, _ in SHOTS:
        src, png, webp = f"{SHOT_SRC}/{name}.png", f"{DOCS}/img/screen-{name}.png", f"{DOCS}/img/screen-{name}.webp"
        if os.path.exists(src) and (not os.path.exists(png) or os.path.getmtime(png) < os.path.getmtime(src)):
            subprocess.run(["sips", "--resampleWidth", "480", src, "--out", png], check=True, capture_output=True)
            if shutil.which("cwebp"):
                subprocess.run(["cwebp", "-quiet", "-q", "84", png, "-o", webp], check=True)


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


shot_html = []
for name, alt, cap_ in [s for s in SHOTS if os.path.exists(f"{DOCS}/img/screen-{s[0]}.png")]:
    w, h = png_size(f"{DOCS}/img/screen-{name}.png")
    source = f'<source srcset="/img/screen-{name}.webp" type="image/webp">' if os.path.exists(f"{DOCS}/img/screen-{name}.webp") else ""
    shot_html.append(f'<li><picture>{source}<img src="/img/screen-{name}.png" alt="{e(alt)}" width="{w}" height="{h}" loading="lazy" decoding="async"></picture><p>{e(cap_)}</p></li>')
SHOTS_CSS = """
  .shots { display: flex; gap: 14px; overflow-x: auto; margin: 0 -20px; padding: 4px 20px 14px; scroll-snap-type: x proximity; list-style: none; }
  .shots li { flex: 0 0 auto; width: 210px; scroll-snap-align: start; }
  .shots img { display: block; width: 210px; height: auto; border-radius: 24px; border: 1px solid var(--rule); background: var(--surface2); }
  .shots p { font-size: 14px; color: var(--muted); margin: 8px 2px 0; }
"""
screens_section = f"""
  <section id="screens">
    <h2>What it looks like</h2>
    <ul class="shots" tabindex="0" aria-label="Maine Eats app screenshots">
      {"".join(shot_html)}
    </ul>
  </section>
""" if shot_html else ""

SEAS_CLASSIC = [p for p in CLASSIC if p.seasonal]
# the lobster season, from what the shacks post (the FAQ's first answer)
LOB_SEAS = [p for p in LOBSTER if p.seasonal]
LOB_KNOWN = [p for p in LOB_SEAS if p.season]
LOB_SPRING = sum(1 for p in LOB_KNOWN if re.search(r"\b(April|May|June|Memorial Day|spring)\b", p.season, re.I))
LOB_OCT = sum(1 for p in LOB_KNOWN if re.search(r"\b(October|Oct\.?|Columbus Day)\b", p.season))
assert LOB_SPRING * 2 > len(LOB_KNOWN), "the season answer says most open in spring"
SOUTH = min((p for p in REST if p.lat is not None), key=lambda p: p.lat).city
NORTH = max((p for p in REST if p.lat is not None), key=lambda p: p.lat).city
faq = [
    ("When do Maine lobster shacks open for the season?",
     f"Mostly in spring. Of the {len(LOBSTER)} lobster places on our list, {len(LOB_SEAS)} are seasonal, and {len(LOB_KNOWN)} of those post their dates: "
     f"{LOB_SPRING} open in April, May or June and {LOB_OCT} close in October. Across our guides, {len(SEAS_CLASSIC)} of the {len(CLASSIC)} places keep "
     "a season. Shut for the winter isn't shut for good, and each place's season is shown with it."),
    ("Does Maine grade restaurants after inspections?",
     "No letter grades. A Maine inspection ends in Pass or Fail under the state food code, and the state's own results are looked up one place "
     "at a time. Lewiston posts its reports, so for Lewiston places the app and the web search show the latest posted result, its date and the "
     "city's report. We don't make up a grade of our own."),
    ("Which parts of Maine does it cover?",
     f"{SOUTH} to {NORTH}. The directory has {N_REST:,} places in {N_TOWNS} of Maine's {N_ALL_TOWNS} towns, cities, plantations and unorganized "
     f"territories, grouped by the Maine Office of Tourism's {len(REGION_ORDER)} regions. {len(TOWN_PAGES)} towns have a page of their own, and "
     "so does each region."),
    ("How does a shack or diner get on a list?",
     f"Someone looked it up. In {CHECKED} we searched out the candidates for the lobster, clam, snapper and Italian, whoopie pie, "
     f"Franco-American, diner, oyster and dairy bar lists, and kept a place only when a {SOURCE_YEARS} source (its own site or menu, Maine news, "
     f"a town or chamber page) showed it in business. The other {N_REST - len(HC):,} places in the directory come from Overture Maps' open "
     "place data, the state's liquor license list and Lewiston's inspection list."),
    ("Why are there no star ratings?",
     "Stars measure popularity, and a list here measures something else: whether the place is in business and what it's known for. We store "
     "none, and nothing is sorted by them. The \"Ratings, hours & photos\" button on a place hands you to Apple Maps, whose card carries "
     "Apple's own."),
    ("What does Maine Eats cost?",
     "Not a cent. You won't see advertising, a paywall or a login. It's built for iPhone and iPad; anyone on Android can use the web search on "
     "this site from the phone's browser."),
    ("Do I have to turn on location?",
     "Only for \"closest first\". The app works out distances on your iPhone or iPad, the website does it inside your browser, and neither "
     "one tells us where you are."),
    ("Spotted a closed shack or a missing diner?",
     f"Send the name and town to {EMAIL}. Corrections ride along with the next data update; Android requests are welcome at the same address."),
]
faq_html = "".join(f"<details><summary>{e(q)}</summary><p>{e(a)}</p></details>" for q, a in faq)
faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "@id": f"{DOMAIN}/#faq",
          "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
app_entity = {"@type": "MobileApplication", "@id": f"{DOMAIN}/#app", "name": APP_NAME, "alternateName": [BRAND, f"{BRAND}: {TAGLINE}"],
              "description": f"A free guide to {N_REST:,} Maine restaurants, with hand-checked lists of {len(LOBSTER)} lobster shacks and roll stops, "
                             f"{len(CLAMS)} clam shacks, {len(DINERS)} diners, {len(OYSTERS)} oyster bars and {len(DAIRY)} dairy bars. Sort by distance, "
                             "open Apple Maps' live place card for hours and photos, and save places for later.",
              "url": f"{DOMAIN}/", "image": f"{DOMAIN}/og.png", "operatingSystem": "iOS, iPadOS", "applicationCategory": "TravelApplication",
              "applicationSubCategory": "Food & Drink", "inLanguage": "en", "author": PERSON, "publisher": {"@id": f"{DOMAIN}/#org"},
              "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD", "category": "free"}}
if APP_STORE_URL:
    app_entity["installUrl"] = APP_STORE_URL
    app_entity["sameAs"] = [APP_STORE_URL]
if os.path.exists(f"{DOCS}/img/screen-home.png"):
    app_entity["screenshot"] = f"{DOMAIN}/img/screen-home.png"
app_ld = {"@context": "https://schema.org", "@graph": [
    app_entity,
    {**ORG, "email": EMAIL, "contactPoint": {"@type": "ContactPoint", "contactType": "customer support", "email": EMAIL, "availableLanguage": "en"}},
    {"@type": "WebSite", "@id": f"{DOMAIN}/#website", "name": BRAND, "alternateName": [f"{BRAND} app"], "url": f"{DOMAIN}/",
     "inLanguage": "en", "publisher": {"@id": f"{DOMAIN}/#org"}}]}
title = fit([f"{BRAND}: Lobster Shack, Clam Shack & Restaurant App", f"{BRAND}: Lobster Shacks, Clam Shacks & Maine Restaurants"], 50, 60, TITLES)
desc = fit([f"Free iPhone and iPad guide to {N_REST:,} Maine restaurants, with {len(LOBSTER)} hand-checked lobster shacks, {len(CLAMS)} clam shacks, and {len(DAIRY)} dairy bars.",
            f"Free iPhone and iPad guide to {N_REST:,} Maine restaurants, with hand-checked lobster shacks, clam shacks, diners and {len(DAIRY)} dairy bars.",
            f"Free iPhone and iPad guide to {N_REST:,} Maine restaurants, with {len(LOBSTER)} hand-checked lobster shacks and rolls, {len(CLAMS)} clam shacks, {len(DINERS)} diners and {len(DAIRY)} dairy bars.",
            f"A free iPhone and iPad guide to {N_REST:,} Maine restaurants, with {len(LOBSTER)} hand-checked lobster shacks, {len(CLAMS)} clam shacks, {len(DINERS)} diners and {len(DAIRY)} dairy bars.",
            f"A free iPhone and iPad guide to {N_REST:,} Maine restaurants, with hand-checked lobster shacks, clam shacks, diners, oyster bars and {len(DAIRY)} dairy bars."], 140, 160, DESCS)
guide_cards = []
GUIDE_CARD = {"lobster": f"{len(LOBSTER)} lobster pounds, shacks and roll stops, with each one's season.",
              "clams": f"{len(CLAMS)} shacks for fried clams, clam cakes and chowder.",
              "sandwiches": f"{len(SAND)} places for red snapper hot dogs and the Maine Italian.",
              "sweets": f"{len(SWEETS)} places for whoopie pies, potato donuts and blueberry pie.",
              "franco": f"{len(FRANCO)} {'place' if len(FRANCO) == 1 else 'places'} for tourtière, poutine and ployes. In the web search.",
              "diners": f"{len(DINERS)} counter-and-booth diners.",
              "oysters": f"{len(OYSTERS)} oyster bars and raw bars; {len(river_oysters(OYSTERS))} list Damariscotta River or Pemaquid oysters.",
              "dairy": f"{len(DAIRY)} dairy bars, ice cream stands and farm creameries."}
if not river_oysters(OYSTERS):
    GUIDE_CARD["oysters"] = f"{len(OYSTERS)} oyster bars and raw bars."
for k in GUIDE_MASK:
    if G[k]:
        name = GUIDE_SHORT[k] if k in GUIDE_PAGE else GUIDE_TITLE[k]
        guide_cards.append(f'<a class="card" href="{e(guide_link(k))}"><h3>{e(name)}</h3><p>{GUIDE_CARD[k]}</p></a>')
if ICONS_PAGE:
    guide_cards.append(f'<a class="card" href="/{ICONS_FILE}"><h3>Maine icons</h3><p>{len(ICONS)} places with James Beard honors or 40 years at the same address.</p></a>')
guide_cards.append(f'<a class="card" href="/{OLDEST_FILE}"><h3>Maine\'s oldest restaurants</h3><p>{len(OLDEST)} places serving at one address for 40 years or more, the first since {OLDEST[0].founded}.</p></a>')
guide_cards.append(f'<a class="card" href="{e(explore_url(g="all"))}"><h3>The whole state</h3><p>Search {N_REST:,} places in {N_TOWNS} towns: open map data, Maine liquor licenses and Lewiston\'s inspection list.</p></a>')
town_cards = "".join(f'<li><a href="{town_url(t)}">{e(t)}</a></li>' for t in TOWN_PAGES)
body = f"""  <main id="main">
  <section class="hero">
    <p class="kicker">{BRAND}: the {TAGLINE.lower()} for iPhone and iPad</p>
    <h1>{N_REST:,} Maine restaurants, from wharf lobster pounds to dairy bars</h1>
    <p class="lede">A Maine road trip turns on a few stops: the lobster pound on the wharf, the clam shack, a red snapper or an Italian, a whoopie pie, the dairy bar on the way home. {BRAND} keeps those as lists we checked by hand in {CHECKED}, inside a directory of {N_REST:,} restaurants, cafés, bars and bakeries in {N_TOWNS} towns that's one search away. It's free for iPhone and iPad.</p>
    <div class="cta-row">{store_button()}<a class="btn btn-ghost" href="/explore/">Search on the web</a><span class="pill">{store_note("Free, ad-free, account-free.")}</span></div>
    <ul class="stats" aria-label="What's in the app">
      <li><b>{len(LOBSTER)}</b><span>lobster shacks &amp; roll stops</span></li>
      <li><b>{len(CLAMS)}</b><span>clam shacks</span></li>
      <li><b>{len(DAIRY)}</b><span>dairy bars</span></li>
      <li><b>{N_REST:,}</b><span>restaurants statewide</span></li>
    </ul>
  </section>

  <section id="what">
    <h2>Built around shack season</h2>
    <p class="sub">On the Maine coast the first question about a lobster pound is often whether it's open yet. {len(LOB_SEAS)} of the {len(LOBSTER)} lobster places on our list are seasonal, and so are {sum(1 for p in DAIRY if p.seasonal)} of the {len(DAIRY)} dairy bars, so each one carries the season it posts. Next to them: whole-belly fried clams, red snappers and Italians, whoopie pies, diner breakfasts. Each place on those lists was {checked_open(HC)}, nothing is ranked by stars, and a tap opens Apple Maps' own card for today's hours and photos.</p>
  </section>

  <section id="how">
    <h2>How it works</h2>
    <ol class="steps">
      <li class="step"><div class="n" aria-hidden="true">1</div><div><h3>Pick a guide.</h3><p>{e(", ".join(GUIDE_TITLE[k] for k in GUIDE_MASK if len(G[k]) >= APP_MIN_GUIDE))}, Maine Icons or <a href="/{OLDEST_FILE}">Oldest Places</a>. Or type a name, a town, a village like Cape Neddick, or a road like Route 1.</p></div></li>
      <li class="step"><div class="n" aria-hidden="true">2</div><div><h3>Narrow it down.</h3><p>Put the closest first, keep one town or one kind of food, or flip to the map. A Seasonal tag marks the places that shut for winter.</p></div></li>
      <li class="step"><div class="n" aria-hidden="true">3</div><div><h3>Head out.</h3><p>Tap through to Apple Maps for the day's opening times and pictures, ring the shack before the drive, or keep it under Saved for the long weekend.</p></div></li>
    </ol>
  </section>
{screens_section}
  <section id="guides">
    <h2>Maine's classics, list by list</h2>
    <p class="sub">The app's hand-checked lists, each as a page you can read, bookmark and pass along.</p>
    <div class="grid2">
      {"".join(guide_cards)}
    </div>
  </section>

  <section id="towns">
    <h2>Lobster shacks and dairy bars by town</h2>
    <p class="sub">The classics in and near Maine's biggest towns and the coastal towns people drive to, plus each town's icons and oldest restaurants. <a href="/cities/">Towns and regions</a>.</p>
    <ul class="towns">{town_cards}</ul>
    <p class="sub">And by region:</p>
    {region_links()}
  </section>

  <section id="inspections">
    <h2>Health inspections: official results only</h2>
    <p class="sub">Maine's official inspection result is Pass or Fail, with no score or grade, and we don't invent grades of our own. The state's results are a one-at-a-time search, so the app shows a result only where the City of Lewiston posts it, inside that place's own details with its date and a link to the city's report. For anywhere else in Maine, look a place up in the state's <a href="{STATE_HIP}" rel="noopener">health inspection search</a>.</p>
  </section>

  <section id="pricing">
    <h2>No price, no ads, no sign-in</h2>
    <p class="sub">{BRAND} costs nothing and sells nothing. There's no subscription and no advertising, and you never make an account. The lists travel inside the app, so they still open where the signal gives out, Downeast or on the island ferry.</p>
  </section>

  <section id="privacy">
    <h2>What we keep about you: nothing</h2>
    <p class="sub">Nobody signs in, and the app reports nothing back to us. Distance sorting happens on the phone, and that's where your saved places stay. This site drops no cookies and runs no tracking scripts. The full version is the <a href="/privacy.html">privacy policy</a>.</p>
  </section>

  <section id="faq">
    <h2>Questions</h2>
    {faq_html}
  </section>

  <section id="download" class="final">
    <h2>Find the next shack</h2>
    <p class="sub">{f"{BRAND} is free on the App Store for iPhone and iPad." if APP_STORE_URL else f"The app is headed for the App Store, free for iPhone and iPad. Meanwhile the same lists are in the <a href=\"/explore/\">web search</a>."}</p>
    <div class="cta-row">{store_button()}</div>
  </section>
  </main>"""
written.append(page("index.html", title, desc, body, [app_ld, faq_ld], extra_css=SHOTS_CSS if shot_html else ""))

# ---------------------------------------------------------------- licenses (the texts travel with the data files too, as the Foursquare NOTICE asks)
LIC_SRC = f"{ROOT}/MaineEats/Resources/Licenses"
os.makedirs(f"{DOCS}/licenses", exist_ok=True)
for name in ("Apache-2.0.txt", "CDLA-Permissive-2.0.txt"):
    shutil.copyfile(f"{LIC_SRC}/{name}", f"{DOCS}/licenses/{name}")
notice_lines = [l for l in open(f"{LIC_SRC}/Foursquare-NOTICE.txt").read().split("\n")]
# the app's own copy may name another app in its notice of changes (Connecticut's was copied); ours is written here
notice_body = "\n".join(l for l in notice_lines if not l.startswith("Notice of changes")).strip()
NOTICE_CHANGES = (f"Notice of changes: {BRAND} filtered the Data to eating and drinking places in Maine, removed duplicates and closed, adult or "
                  "unverifiable listings, and reformatted it for this app and website (2026).")
FOURSQUARE_NOTICE = notice_body + "\n\n" + NOTICE_CHANGES
assert "Connecticut" not in FOURSQUARE_NOTICE and "Wisconsin" not in FOURSQUARE_NOTICE
open(f"{DOCS}/licenses/Foursquare-NOTICE.txt", "w").write(FOURSQUARE_NOTICE + "\n")
APP_NOTICE_WRONG = any(l.startswith("Notice of changes") and BRAND not in l for l in notice_lines)

# ---------------------------------------------------------------- about
cal = D.get("calibration", {}).get("statewide_liquor", {})
rate_hi = cal.get("Meta, confidence 0.95+", {}).get("matched")
rate_txt = f"{round(rate_hi * 100)}%" if rate_hi is not None else "many"
nav, bc = crumbs([("Home", "/"), ("About and sources", "/about.html")])
body = f"""{nav}
  <main id="main" class="legal">
  <section class="hero">
    <p class="kicker">About {BRAND}</p>
    <h1>Who makes {BRAND}, and how</h1>
    <p class="lede">{BRAND} is an independent app and website by {AUTHOR}: a free guide to {N_REST:,} Maine restaurants, with hand-checked lists of lobster shacks and rolls, clam shacks, red snappers and Italians, whoopie pies, diners, oyster bars and dairy bars. No account, no ads, no tracking.</p>
  </section>
  <section id="maker">
    <h2>Who makes it</h2>
    <p>{AUTHOR} makes the {BRAND} app and this site. {BRAND} is not affiliated with, endorsed by or operated by the State of Maine, Maine CDC or its Health Inspection Program, the Bureau of Alcoholic Beverages and Lottery Operations, the City of Lewiston, the James Beard Foundation, Michelin, Apple, or any restaurant, brand, team or chain.</p>
    <h2>How the lists are built</h2>
    <p>Lobster shacks, clam shacks, red snappers and Italians, whoopie pies and donuts, Franco-American food, diners, oyster bars, dairy bars and the icons are hand-checked: each was checked in {CHECKED} against a {SOURCE_YEARS} source (the place's own website or menu, local news, or a town or chamber listing), with the address checked. Research records facts only, with a source for each place: no review text and no ratings from anyone. Many coastal places are seasonal, and a winter closing isn't a closure; places the research finds closed come off the lists.</p>
    <p>The rest of the {N_REST:,} places come from Overture Maps' open place data, the State of Maine's liquor license list (current as of {e(D.get("license_date") or "")}) and the City of Lewiston's inspection list. Map listings are kept only at high confidence, and each place says how sure we are: statewide, the most confident listings matched an on-premises liquor license {rate_txt} of the time (only places that serve alcohol hold one, so a coffee shop can't match). Website links are checked, and any that no longer belong to the place are left out.</p>
    <h2 id="inspections">Health inspections</h2>
    <p>Maine's official inspection result is Pass or Fail, with no score or grade: under the state's food code rules (10-144 CMR Ch. 201), a place fails with more than 3 critical or more than 10 non-critical violations. The state's results are a one-at-a-time search, so {BRAND} shows a result only where the City of Lewiston posts it: on that place's own page and in its panel in the web search, with the date and a link to the city's report, never as a list. The city's page was read on {nice_date(D["lewiston_fetched"])}; its newest posted inspection is from {nice_date(D["lewiston_latest"])}. For anywhere in Maine, look a place up in the state's <a href="{STATE_HIP}" rel="noopener">health inspection search</a>.</p>
    <p>Ratings, reviews, hours and photos in the app are Apple Maps' own, shown live in Apple's place card; {BRAND} doesn't store or rank by them.</p>
    <h2>Updates</h2>
    <p>This build's restaurant data is from {long_date(DATA_DATE)}; the hand checks were done in {CHECKED}. The data is rebuilt when the research or the open data changes, and corrections go into the next update. Places open and close, so check before you go.</p>
    <h2 id="sources">Sources and licenses</h2>
    <ul>
      <li><b>Overture Maps Foundation</b> (<a href="https://overturemaps.org" rel="noopener">overturemaps.org</a>), release {e(D.get("overture") or "")}: restaurant listings and websites, filtered and reformatted for {BRAND}. Data from Meta, Microsoft, DAC and BrightQuery, available under the <a href="/licenses/CDLA-Permissive-2.0.txt">Community Data License Agreement – Permissive 2.0</a>. Data from Foursquare, © Foursquare Labs, Inc., available under the <a href="/licenses/Apache-2.0.txt">Apache License 2.0</a>; see the <a href="#foursquare">notice below</a>. Data from AllThePlaces, available under CC0 1.0. The same licenses cover the web search's data files.</li>
      <li><b>Maine Bureau of Alcoholic Beverages and Lottery Operations</b>: <a href="{BABLO_PAGE}" rel="noopener">liquor license data</a>, published monthly as public information; this build uses the list current as of {e(D.get("license_date") or "")}, for each premises' trade name, address and license class only, never the license holder. The State of Maine makes no warranty as to the data and does not endorse {BRAND}.</li>
      <li><b>City of Lewiston</b>: <a href="{LEWISTON_PAGE}" rel="noopener">Restaurant Inspection Reports</a>, shown as posted with their dates and linked to the city's reports. The City of Lewiston does not endorse {BRAND}.</li>
      <li><b>Maine CDC Health Inspection Program</b>: licenses and inspects Maine's eating places; its <a href="{STATE_HIP}" rel="noopener">health inspection search</a> is where to look a place up.</li>
      <li><b>Town outlines</b>: U.S. Census Bureau cartographic boundary files, 2025 (public domain): the outlines of Maine's {N_ALL_TOWNS} towns, cities, plantations and unorganized territories, used to place each restaurant in its town, and the county lines the web map draws.</li>
      <li><b>Honors</b>: James Beard Foundation awards, nominees, semifinalists and America's Classics, reported as facts and checked by hand against the foundation's own announcements. James Beard Foundation and James Beard Award are trademarks of the James Beard Foundation. There is no MICHELIN Guide for Maine. MICHELIN is a trademark of Michelin.</li>
      <li><b>Maps</b>: in the app, maps, place cards and directions are by Apple Maps.</li>
      <li><b>Research</b>: lobster shacks, clam shacks, red snappers and Italians, whoopie pies, Franco-American food, diners, oyster bars, dairy bars and years at an address are our own research, with a source recorded for each place.</li>
    </ul>
    <h2 id="foursquare">Foursquare NOTICE</h2>
    <pre class="notice">{e(FOURSQUARE_NOTICE)}</pre>
    <h2>Contact</h2>
    <p>Corrections, a missing or closed place, or anything else: <a href="mailto:{EMAIL}">{EMAIL}</a>. See also the <a href="/privacy.html">privacy policy</a> and <a href="/terms.html">terms of use</a>.</p>
  </section>
  </main>"""
about_ld = {"@context": "https://schema.org", "@type": "AboutPage", "url": f"{DOMAIN}/about.html", "name": f"About {BRAND}",
            "isPartOf": {"@type": "WebSite", "@id": f"{DOMAIN}/#website", "url": f"{DOMAIN}/", "name": BRAND}, "dateModified": LASTMOD,
            "publisher": ORG}
written.append(page("about.html", fit([f"About {BRAND}: Who Makes It and Where the Data Comes From", f"About {BRAND}: Sources, Methods and Who Makes It"], 50, 60, TITLES),
                    fit([f"{BRAND} is an independent app and website by {AUTHOR}. How the hand-checked lobster shack and clam shack lists are built, plus sources and licenses.",
                         f"{BRAND} is an independent app and website by {AUTHOR}: how the hand-checked lobster shack lists are built, and our sources and licenses."], 140, 160, DESCS),
                    body, [about_ld, bc]))

# ---------------------------------------------------------------- privacy and terms
nav, bc = crumbs([("Home", "/"), ("Privacy policy", "/privacy.html")])
body = f"""{nav}
  <main id="main" class="legal">
  <section class="hero">
    <h1>Privacy policy</h1>
    <p class="lede">Short version: the {BRAND} app collects nothing about you, and this website doesn't track you. Last updated {nice_date(PRIVACY_UPDATED)}.</p>
  </section>
  <section>
    <h2>The app</h2>
    <ul>
      <li><b>No account, no analytics, no ads.</b> The app has no sign-in, no advertising, and no analytics or crash-reporting code. We receive no data from it.</li>
      <li><b>Location.</b> If you allow it, your location is used on your device to sort places by distance and show where you are on the map. It is never sent to us. You can turn it off in Settings at any time.</li>
      <li><b>Saved places and filters</b> are stored only on your device and are deleted when you delete the app.</li>
      <li><b>Apple Maps.</b> When you open a place's ratings, hours and photos, or ask for directions, the app asks Apple Maps for that place. Apple handles that request under <a href="https://www.apple.com/legal/privacy/" rel="noopener">Apple's privacy policy</a>, as it does for any app that shows a map.</li>
      <li><b>Spotlight.</b> The app adds its hand-checked places to your device's search index so you can find them from Spotlight. That index stays on your device.</li>
      <li><b>Calls, websites, and email</b> you start from a place open in the Phone app, your browser or Mail, and are handled by them.</li>
    </ul>
    <p>On the App Store, the app's privacy label {'is' if APP_STORE_URL else 'will be'} "Data Not Collected".</p>
    <h2>This website</h2>
    <p>The site is static pages hosted on GitHub Pages. It sets no cookies and loads no analytics, fonts, maps, or scripts from anyone else. GitHub may keep standard server logs, such as IP addresses, for security; see <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement" rel="noopener">GitHub's privacy statement</a>.</p>
    <p>The <a href="/explore/">web search</a> keeps two things in your browser's local storage, on your device only: your saved places (under the key <code>me-saved</code>) and the last guide you opened (<code>me-guide</code>). Clearing your browser's site data deletes both. If you tap "Use my location", open the "Near me" guide, or sort by "Nearest", your browser asks first, and your location is used in the page to sort by distance. It is never sent to us or anyone else.</p>
    <h2>Email</h2>
    <p>If you email us, we use your message and address only to reply and to fix the listing you told us about. We don't add you to a mailing list or share your address. Mail to {EMAIL} reaches us through Cloudflare Email Routing, which forwards it to our inbox; see <a href="https://www.cloudflare.com/privacypolicy/" rel="noopener">Cloudflare's privacy policy</a>.</p>
    <h2>Children</h2>
    <p>The app collects no personal information from anyone, including children.</p>
    <h2>Changes and contact</h2>
    <p>If this policy changes, the new version will be posted here with a new date. Questions: <a href="mailto:{EMAIL}">{EMAIL}</a>.</p>
  </section>
  </main>"""
written.append(page("privacy.html", "Privacy Policy: Maine Eats Lobster Shack & Restaurant App",
                    fit([f"The {BRAND} privacy policy: the app collects no data, keeps your location and saved places on your device, and this site sets no cookies."], 140, 160, DESCS),
                    body, [bc], lastmod=PRIVACY_UPDATED))

nav, bc = crumbs([("Home", "/"), ("Terms of use", "/terms.html")])
body = f"""{nav}
  <main id="main" class="legal">
  <section class="hero">
    <h1>Terms of use</h1>
    <p class="lede">The plain-language terms for the {BRAND} app and this website. Last updated {nice_date(TERMS_UPDATED)}.</p>
  </section>
  <section>
    <h2>What the app is</h2>
    <p>{BRAND} is a free guide to restaurants in Maine, made by {AUTHOR}. It is provided as is, for personal use, without charge and without warranties of any kind.</p>
    <h2>Check before you go</h2>
    <p>Restaurants open, close, and change their hours and menus, and many lobster pounds, clam shacks and dairy bars close for the season. Dishes, seasons, and years at an address are what each place or a named source said when we checked in {CHECKED}. We work to keep the lists right, but we can't promise that any listing is current or complete. Call the restaurant before you make the trip.</p>
    <h2>Health inspections</h2>
    <p>Maine's official inspection result is Pass or Fail, and {BRAND} doesn't grade restaurants. Where the City of Lewiston posts a result, the app and the web search show the city's latest posted result for that place with its date and a link to the city's report. A result describes one inspection on that day. For the official record anywhere in Maine, see the state's <a href="{STATE_HIP}" rel="noopener">health inspection search</a>.</p>
    <h2>Other people's content</h2>
    <p>Hours, photos and other details in each place card come from Apple Maps and are Apple's and its providers', under Apple's terms. Restaurant names and trademarks belong to their owners. James Beard Foundation and James Beard Award are trademarks of the James Beard Foundation; honors are reported as facts. {BRAND} is not affiliated with, endorsed by, or operated by the State of Maine, Maine CDC or its Health Inspection Program, the Bureau of Alcoholic Beverages and Lottery Operations, the City of Lewiston, the James Beard Foundation, Michelin, Apple, or any restaurant, brand, team or chain.</p>
    <h2>Data sources and licenses</h2>
    <ul>
      <li>Overture Maps Foundation places data (overturemaps.org), release {e(D.get("overture") or "")}, filtered and reformatted for {BRAND}: data from Meta, Microsoft, DAC, and BrightQuery under the Community Data License Agreement, Permissive 2.0 (<a href="/licenses/CDLA-Permissive-2.0.txt">text</a>); data from Foursquare under the Apache License 2.0 (<a href="/licenses/Apache-2.0.txt">text</a>; <a href="/licenses/Foursquare-NOTICE.txt">NOTICE</a>); data from AllThePlaces under CC0 1.0.</li>
      <li>Maine Bureau of Alcoholic Beverages and Lottery Operations liquor license data, current as of {e(D.get("license_date") or "")}: trade name, address and license class only.</li>
      <li>City of Lewiston Restaurant Inspection Reports, shown as posted with their dates.</li>
      <li>U.S. Census Bureau cartographic boundary files (public domain).</li>
      <li>James Beard Foundation: award, nominee, semifinalist, and America's Classics history.</li>
      <li>Lobster shacks, clam shacks, red snappers and Italians, whoopie pies, diners, oyster bars, dairy bars, and years at an address: our own research, with a source recorded for each place.</li>
    </ul>
    <p>More on each source: <a href="/about.html#sources">about {BRAND}</a>.</p>
    <h2>Corrections</h2>
    <p>If a listing is wrong, or you own a restaurant and want something fixed, email <a href="mailto:{EMAIL}">{EMAIL}</a>. We fix mistakes in the next update.</p>
    <h2>Liability</h2>
    <p>To the extent the law allows, we are not liable for any loss arising from use of the app or site, including a wasted drive to a shack that's closed for the season. Maine law governs these terms.</p>
    <h2>Changes</h2>
    <p>We may update these terms; the current version and its date are always on this page. See also the <a href="/privacy.html">privacy policy</a>.</p>
  </section>
  </main>"""
written.append(page("terms.html", "Terms of Use: Maine Eats Lobster Shack & Restaurant App",
                    fit([f"The {BRAND} terms of use: a free Maine restaurant guide, provided as is. Check before you go, and see where each listing comes from.",
                         f"The {BRAND} terms of use: a free Maine restaurant guide, provided as is. Check the season before you go, and see where each listing comes from."], 140, 160, DESCS),
                    body, [bc], lastmod=TERMS_UPDATED))

body = f"""  <main id="main">
  <section class="hero">
    <h1>Page not found</h1>
    <p class="lede">Nothing lives at this address on {BRAND}: the link may be old, or a letter got lost on the way. Head back to the <a href="/">{BRAND} home page</a>, the <a href="/{GUIDE_FILE['lobster']}">lobster shack guide</a> or <a href="/cities/">towns and regions</a>, or look the place up by name.</p>
    <p><a class="btn" href="/explore/">Search Maine restaurants</a></p>
    <p>Other lists people come for: <a href="/{GUIDE_FILE['clams']}">clam shacks</a>, <a href="/{GUIDE_FILE['dairy']}">dairy bars</a> and <a href="/{OLDEST_FILE}">Maine's oldest restaurants</a>.</p>
  </section>
  </main>"""
page("404.html", f"Page not found | {BRAND}", "This page doesn't exist.", body, robots="noindex,follow")

# ---------------------------------------------------------------- plumbing
# pages that left the lists (a place no longer hand-checked, a guide or town that dropped out) are removed, so the sitemap and the
# files always agree
keep = set(written) | {"404.html"}
for sub in ("places", "regions", "cities"):
    for f in os.listdir(f"{DOCS}/{sub}"):
        if f.endswith(".html") and f"{sub}/{f}" not in keep:
            os.remove(f"{DOCS}/{sub}/{f}")
for f in os.listdir(DOCS):
    if f.endswith(".html") and f not in keep:
        os.remove(f"{DOCS}/{f}")


def order(item):
    u = item[0]
    return (u != "index.html", u.startswith("places/"), u.startswith("regions/"), u.startswith("cities/"), u)


open(f"{DOCS}/sitemap.xml", "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                       + "".join(f"  <url><loc>{DOMAIN}/{'' if u == 'index.html' else u.removesuffix('index.html')}</loc><lastmod>{m}</lastmod></url>\n"
                                                 for u, m in sorted(PAGES, key=order)) + "</urlset>\n")
open(f"{DOCS}/robots.txt", "w").write(f"User-agent: *\nAllow: /\n\nSitemap: {DOMAIN}/sitemap.xml\n")
json.dump({"name": BRAND, "short_name": SHORT, "description": f"{TAGLINE}, plus {N_REST:,} Maine restaurants.", "start_url": f"{BASE}/", "display": "browser",
           "background_color": "#fbf6ec", "theme_color": "#0E4D5C",
           "icons": [{"src": f"{BASE}/icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": f"{BASE}/icon-512.png", "sizes": "512x512", "type": "image/png"}]},
          open(f"{DOCS}/site.webmanifest", "w"), indent=2)
if CUSTOM_DOMAIN:
    open(f"{DOCS}/CNAME", "w").write(CUSTOM_DOMAIN + "\n")
elif os.path.exists(f"{DOCS}/CNAME"):
    os.remove(f"{DOCS}/CNAME")   # no custom domain yet: GitHub serves the project address
open(f"{DOCS}/.nojekyll", "w").write("")
# the share image (docs/og.png) prints the counts in its tagline, so it's redrawn (og.png only, never the app icon) when they change
OG_LINE = f"{TAGLINE} · {N_REST:,} restaurants in {N_TOWNS} towns"
assert not re.search(r"\b(every|all|best)\b|#1", OG_LINE, re.I), OG_LINE
NUMBERS = f"{ROOT}/playbook/site-numbers.json"
og_line = json.load(open(NUMBERS)).get("og_line") if os.path.exists(NUMBERS) else None
if og_line != OG_LINE or not os.path.exists(f"{DOCS}/og.png"):
    try:
        subprocess.run(["swift", "scripts/make-brand.swift", "og", OG_LINE], cwd=ROOT, check=True)
        og_line = OG_LINE
    except (OSError, subprocess.CalledProcessError) as ex:
        print(f"!! docs/og.png still shows the old counts ({ex}); run: swift scripts/make-brand.swift og")
json.dump({"generated": DATA_DATE, "domain": DOMAIN, "og_line": og_line, "restaurants": N_REST, "towns": N_TOWNS, "census_towns": N_ALL_TOWNS,
           "hand_checked": len(HC), "guides": {k: len(G[k]) for k in GUIDE_MASK}, "guide_pages": GUIDE_PAGE, "guide_stats": GUIDE_STATS,
           "icons": ICON_STATS or {"icons": len(ICONS)}, "oldest_known_year": len(OLDEST), "named_not_checked": NAMED,
           "casino_restaurants": len(CASINO), "lewiston_results": len(LEWISTON_RESULTS), "place_pages": N_PLACE_PAGES,
           "regions": REGION_STATS, "towns_pages": TOWN_STATS},
          open(NUMBERS, "w"), indent=1, ensure_ascii=False)
kinds = Counter(w.split("/")[0] if "/" in w else "top" for w in written)
print("wrote", len(written) + 1, "pages:", dict(kinds), "+ 404.html")
print(f"restaurants {N_REST:,} in {N_TOWNS} towns | " + " | ".join(f"{k} {len(G[k])}" for k in GUIDE_MASK)
      + f" | icons {len(ICONS)} | oldest {len(OLDEST)} | hand-checked {len(HC)} | Lewiston results {len(LEWISTON_RESULTS)}")
print("guide pages:", ", ".join(GUIDE_FILE[k] for k in GUIDE_PAGE), "| no page yet:", [k for k in GUIDE_FILE if k not in GUIDE_PAGE])
print("core.json", os.path.getsize(f"{DOCS}/data/core.json") // 1024, "KB | detail.json", os.path.getsize(f"{DOCS}/data/detail.json") // 1024, "KB")
for x in HOST_DROPPED:
    print("!! host label not shown (fix in pipeline/maine.py CASINOS):", x)
if APP_NOTICE_WRONG:
    print("!! MaineEats/Resources/Licenses/Foursquare-NOTICE.txt's notice of changes names another app; the site writes its own")
# the website blocklist: what each entry left out, and anything listed that's still somewhere in docs/ (a note or an honor quoting it,
# which only the data can fix; qa-site.py fails on it)
print(f"website blocklist ({os.path.relpath(BLOCKLIST_FILE, ROOT)}, {len(BLOCKLIST)} entries): "
      + ("; ".join(f"{k} ×{n} ({', '.join(BLOCKED_PLACES[k][:3])}{', …' if n > 3 else ''})" for k, n in sorted(BLOCKED.items())) or "no links left out")
      + " | matching nothing: " + (", ".join(_bl_key(b) for b in BLOCKLIST if _bl_key(b) not in BLOCKED) or "none"))
_bl_rx = [(_bl_key(b), re.compile(r"(?<![a-z0-9-])" + re.escape(_bl_key(b)) + (r"(?![a-z0-9-])" if b.get("match", "domain") == "domain" else r"/?(?![a-z0-9/_-])"), re.I))
          for b in BLOCKLIST]
for _d, _, _fs in os.walk(DOCS):
    for _f in _fs:
        if _f.endswith((".html", ".json", ".xml", ".txt", ".webmanifest", ".js", ".css")):
            _t = html.unescape(open(os.path.join(_d, _f), encoding="utf-8", errors="ignore").read().replace("\\/", "/"))
            for _k, _rx in _bl_rx:
                if _rx.search(_t) or _rx.search(urllib.parse.unquote(_t)):
                    print(f"!! {os.path.relpath(os.path.join(_d, _f), DOCS)} still names the blocklisted website {_k} (qa-site.py will fail)")
