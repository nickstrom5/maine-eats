"""QA for the website in docs/, served the way GitHub Pages will serve it (under /maine-eats/ until the custom domain is live).
Exits 1 on any problem.

Static checks, every HTML file (no browser):
  title 50-60 and description 140-160 characters (404 exempt), unique titles and descriptions, one <h1>; a Content-Security-Policy
  <meta> first in <head> whose script and style hashes match exactly this page's inline <script>/<style> blocks; the referrer <meta>;
  no inline style or event attributes, external scripts or HTML comments; JSON-LD that parses, has no raw "<" and no ratings or
  reviews, list items that point at place pages that exist, and Restaurant markup (name, street address, geo, +1 phone, http(s) url)
  on each place page; every same-site link and #anchor resolves, tel: links are digits; no overclaims ("every", "all restaurants",
  "all <number>", "best", "#1", "top-rated") in our own copy (research notes and award names quoted from the data are skipped); no
  Google, no MICHELIN claim beyond "there is no MICHELIN Guide for Maine"; no "James Beard finalist"; no private address; Lewiston's
  Pass/Fail results only on a place's own page, and there exactly as the data has them; each guide page lists exactly the
  hand-checked places of its kinds (icons: the places with iconic points; oldest: the places with a year), a guide with fewer than 5
  places has no page; town pages that say none of our places of a kind is in or near the town are true; region pages name exactly
  their counties; each page type is there; the 404 page names no canonical URL; sitemap and files agree.

Browser checks (headless Chrome via Python Playwright, 375 and 1280 px; place pages: all at 375, every tenth at 1280): HTTP 200,
  no sideways scroll, one <h1>, no console errors, no CSP violations, no requests to any other host, no broken images, and at 375 px
  every visible link, button, input and select is at least 44x44 px (a link inside a sentence is exempt, as in WCAG 2.5.8).

The web app (explore/) at 375 and 1280 px: no layout shift while the list loads and detail.json comes after the list's own data; the
  lobster guide lists exactly the hand-checked lobster places; the map draws the state and the dots; "amatos" finds Amato's and
  opens it; Save survives a reload; a #p= link opens the place; a Lewiston place shows its official result, date and report, and no
  list ever shows a result; an emoji search lists nothing; Near me sorts by distance; Back closes a place; the phone panel is a
  modal dialog and the desktop panel covers no control; Escape closes it and puts focus back on the row; the Maine search phrases
  ("lobster in bar harbor", "near cape neddick", "route 1"/"us 1", "me 3"/"route 3", the tag phrases); #g=constructor; the skip link;
  rank numbers only on ranking sorts; High-confidence only and Hide chains keep hand-checked places; Featured order from outside Maine;
  a slow drag opens nothing; stacked dots open a chooser; a failed core.json shows a retry that works; tap targets with the panel
  open; and text contrast of 4.5:1 in light and dark mode (web app, home, a guide, a place page). Also (bugs other state web apps had):
  control fonts resolve and phone fields are 16px or more, junk in our localStorage keys doesn't stop the app, no "Nearest" label
  without a location, Near me asks for a fresh fix on every tap, and a cold #g=near link sorts at once when location is allowed.
  A search inside a guide that finds nothing or only a few places there offers "Search all restaurants (N matches)", and one click
  lists the place statewide (ME-V08); the search box's placeholder fits, at 16px, at every common phone width (320-440 px).

Family and contact (2026-10-12): every page's footer links Eats Ranked (https://eatsranked.com/) and the #org Organization names it as
  parentOrganization; the contact address is nick@eatsranked.com, and the old Gmail address appears nowhere in docs/.
Copy decisions (Nick, 2026-10-13): the label is "High-confidence listing", so "Confirmed listing" (any case) appears nowhere in docs/ and
  the web app's place panel uses the new label; its filter is "High-confidence only", so "Confirmed only" (any case) appears nowhere either; and no promise of a TestFlight invite or link (only Nick's internal TestFlight group
  exists): no "we'll/you'll ... invite/TestFlight/beta", no "send you a(n) invite/link", no "early access is by invite", no "ask for
  an invite and try it", no "a TestFlight invite/link" in the copy, no "Get early access" (the button asks: "Ask for early access").
Website blocklist (pipeline/website_blocklist.json: hacked, expired or another business's websites): no listed domain (any case,
  scheme, www. or subdomain) or listed page appears anywhere in docs/, pages and data files alike; the list exists, isn't empty (a
  sentinel entry keeps it from passing vacuously) and is well-formed, and the matcher finds each domain's variants.
Claims read from the research notes: the oyster page's Damariscotta River/Pemaquid count and its farm answer, the dairy page's
  make-their-own count, the home page's oyster card, and the home page's guide list (only guides the app offers, 4+ places);
  each region page lists its busiest towns with the right counts; the oldest page says it's the 40-year list; no page uses a sentence
  of the copy template other state sites shared; no other state's app, repo or name in docs/; the privacy page names every
  localStorage key the web app writes; every page head has the apple-itunes-app tag or its commented placeholder.

Usage: .venv/bin/python scripts/qa-site.py [--docs DIR] [--workers N] [--shots DIR] [--skip-pages] [--port N]
  --docs        check another copy of docs/ (used to confirm that each check can fail)
  --port        serve on this local port (default: any free one; the shared Mac gives each session its own range)
  --workers     browsers loading pages side by side (default 3)
  --shots       also save a few screenshots there
  --skip-pages  skip the per-page browser pass (static checks and the web app only)
  --static-only no browser at all
Ported from ct-eats/scripts/qa-site.py and wi-eats/scripts/qa-site.py. Never drives anyone's own browser.
"""
import argparse
import base64
import functools
import hashlib
import html as H
import http.server
import json
import math
import os
import re
import sys
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ap = argparse.ArgumentParser()
ap.add_argument("--docs", default=os.environ.get("QA_DOCS") or os.path.join(ROOT, "docs"))
ap.add_argument("--workers", type=int, default=3)
ap.add_argument("--shots", default=os.environ.get("QA_SHOTS"))
ap.add_argument("--skip-pages", action="store_true")
ap.add_argument("--static-only", action="store_true")
ap.add_argument("--port", type=int, default=int(os.environ.get("QA_PORT") or 0))
ARGS = ap.parse_args()
DOCS = os.path.abspath(ARGS.docs)
SHOTS = ARGS.shots
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
SITEMAP = [x.text for x in ET.parse(os.path.join(DOCS, "sitemap.xml")).getroot().findall("s:url/s:loc", NS)]
HOME = urllib.parse.urlparse(SITEMAP[0])            # the landing page comes first
DOMAIN_HOST = HOME.netloc
BASE = HOME.path.rstrip("/")                         # "/maine-eats" on github.io, "" on a custom domain
PORTLAND = {"latitude": 43.6577, "longitude": -70.2584}   # Monument Square
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
BANNED_LD = {"aggregateRating", "review", "reviews", "reviewRating", "ratingValue", "reviewCount", "bestRating"}
STATE_HIP = "https://apps.web.maine.gov/online/hip_search/health-inspection-search.html"
# the guides (MaineEats/Models/Guide.swift) and their pages; a guide under MIN_PAGE places has no page yet
GUIDE_KINDS = {"lobster": ["lobster shack", "lobster roll"], "clams": ["clam shack"], "sandwiches": ["red snapper", "italian sandwich"],
               "sweets": ["whoopie pie", "potato doughnut", "blueberry pie"], "franco": ["franco american"], "diners": ["diner"],
               "oysters": ["oyster bar"], "dairy": ["dairy bar"]}
GUIDE_FILE = {"lobster": "maine-lobster-shacks.html", "clams": "maine-clam-shacks.html", "sandwiches": "maine-red-snappers-italians.html",
              "sweets": "maine-whoopie-pies-donuts.html", "franco": "maine-franco-american-food.html", "diners": "maine-diners.html",
              "oysters": "maine-oyster-bars.html", "dairy": "maine-dairy-bars.html"}
ICONS_FILE, OLDEST_FILE = "maine-icons.html", "maine-oldest-restaurants.html"
MIN_PAGE = 5
# what each page records while it runs: CSP violations and layout shifts (not caused by input)
INIT = """window.__csp = []; window.__cls = 0;
document.addEventListener('securitypolicyviolation', e => window.__csp.push(e.violatedDirective + ' ' + (e.blockedURI || 'inline')));
try { new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; })
  .observe({type: 'layout-shift', buffered: true}); } catch (e) {}"""
# sha256 digests of a private address and its pieces (user, domain): no public page may contain them. Only digests are kept,
# so this public file doesn't spell the address out.
PRIVATE_DIGESTS = {
    "4a7e25559b2ffc162afaef2b1680778c6e77d8c2982c3870595f6ee8fea7a455",
    "ff8ea15b513b5561b1c48b725aff52338eddb8ecdd46af58759e2f2c554b0582",
    "31b7679e2f02e2b0561693acc0c78f067633b6713ac53fb5980dcb0f7c2ea237",
    "928009cbd52e0a32a3542c0f41efa0ac8feef2e05974b8126f26c7d4f9b593e3",
}
# our own copy may not say these; text quoted from the data (research notes, dishes, seasons, award names) is taken out first
OVERCLAIMS = [r"\bevery\b", r"\ball (the )?(maine )?restaurants\b", r"\ball \d[\d,]*\b", r"\bbest\b", r"#1\b", r"\bnumber one\b",
              r"\btop[- ]rated\b", r"\bcomplete list\b", r"\bevery restaurant\b", r"\b(confirmed|verified) open\b"]
# the public contact address (Nick, 2026-10-12) and the one it replaced, which must appear nowhere in docs/
EMAIL = "nick@eatsranked.com"
OLD_EMAIL = "work-with-nick@" + "gmail.com"
HUB, HUB_ORG = "https://eatsranked.com/", "https://eatsranked.com/#organization"
# Nick, 2026-10-13: "High-confidence listing", never "Confirmed listing"; and the site promises no TestFlight invite or link (only his
# internal TestFlight group exists), so the early-access copy ends at an ask ("Ask for early access")
OLD_LABEL = re.compile(r"confirmed\s+listing", re.I)
NEW_LABEL = "High-confidence listing"
OLD_FILTER = re.compile(r"\bconfirmed\s+only\b", re.I)   # the web app's filter is "High-confidence only" (code comments may still say "confirmed")
PROMISES = [re.compile(r"\b(we'll|we will|we'd|we would|you'll|you will|you'd|you would)\b[^.]{0,60}\b(invites?|invitations?|testflight|beta)\b", re.I),
            re.compile(r"\b(send|email|text|mail)(s|ing)? you\b[^.]{0,40}\b(invites?|invitations?|testflight|beta|link)\b", re.I),
            re.compile(r"\bget (early access|an? (testflight|beta|invite|invitation)|the (testflight|beta)( (link|build|app))?|invited)\b", re.I),
            re.compile(r"\b(early access|access|testflight|the beta)\b[^.]{0,20}\bby invit(e|ation)\b", re.I),   # "early access is by invite"
            re.compile(r"\bask for\b[^.]{0,40}\band (then )?(try|get|use|download|install)\b", re.I),         # "ask for an invite and try it"
            re.compile(r"\btestflight\s+(invit|link)", re.I)]   # offering "a TestFlight invite/link" (a mailto body is %20-encoded, so it's left alone)
# the research notes, read strictly (the generator's RIVER_OYSTERS, AT_OYSTER_FARM, OWN_ICE_CREAM in scripts/make-site.py)
RIVER_OYSTERS = re.compile(r"\b(Damariscotta River|Pemaquid) oysters\b|\bDamariscotta River oyster farm\b")
AT_OYSTER_FARM = re.compile(r"\boyster farm\b", re.I)
OWN_ICE_CREAM = re.compile(r"(homemade|house-made|small-batch|scratch-made)\s+(?:[\w'-]+\s+){0,2}(ice cream|soft serve|hard-serve|flavors|gelato)"
                           r"|(make|makes|made|making) (its|their) own[^;.]{0,20}ice cream|makes? its ice cream|own ice cream|making [^;.]{0,40}ice cream"
                           r"|^(?:[\w'-]+\s+){0,2}ice cream maker\b", re.I)
APP_MIN_GUIDE = 4   # MaineEats/Models/AppModel.swift: a classic with fewer places isn't offered on Home
# SEO-SPEC: the App Store smart banner, commented out until the App Store record exists (then a real tag with the id)
APPLE_ITUNES_PLACEHOLDER = '<!-- <meta name="apple-itunes-app" content="app-id=APP_ID"> fill in once the App Store record exists -->'
# 4.3(a): our own site, our own text. No other Eats Ranked state's app name or repo may appear anywhere in docs/, nor another state's
# name outside the allow-list (Washington, New York and Chicago are Maine streets, a county, a town and pizza styles in the data).
OTHER_APPS = re.compile(r"\b(wi|ct|co|ca|wa|fl|id|ny|chi|mi|tx)-eats\b|chicago-restaurants-ranked|\b(Wisconsin|Connecticut|Colorado|Idaho|Florida|"
                        r"California|Washington|New York|Michigan|Texas) Eats\b|Chicago Restaurants: Ranked|Chi Ranked", re.I)
OTHER_STATES = re.compile(r"\b(Wisconsin|Connecticut|Colorado|Idaho|Florida|California|Illinois|Michigan|Texas)\b")
# sentences of the copy template the state sites once shared (cross-site audit XS-01..04): Maine's pages say it in their own words
SHARED_TEMPLATE = ["can't tell you which shacks are open for the season", "Free, and staying that way", "Your lunch plans are your business",
                   "The app's hand-checked lists, readable on the web", "restaurant guide that knows a pound from a shack",
                   "Corrections go into the next update", "Android moves up the list", "the same list sorts by distance from you",
                   "How the list was built", "and the lobster shacks worth the drive", "is a free Maine restaurant guide"]
OTHER_STATES_OK = ("Connecticut style", "Texas Roadhouse")     # the warm-butter lobster roll's name; a chain in the data
problems = []
_lock = threading.Lock()


def bad(msg):
    with _lock:
        problems.append(msg)


class Handler(http.server.SimpleHTTPRequestHandler):
    """Serves DOCS at BASE/, the way GitHub Pages serves the project site; anything outside BASE is a 404."""

    def translate_path(self, path):
        p = urllib.parse.urlsplit(path).path
        if BASE and p != BASE and not p.startswith(BASE + "/"):
            return os.path.join(DOCS, "__not_under_base__")
        return super().translate_path(path[len(BASE):] if BASE else path)

    def log_message(self, *a):
        pass


def serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", ARGS.port), functools.partial(Handler, directory=DOCS))
    srv.handle_error = lambda *a: None     # a browser dropping a connection mid-file isn't a site problem
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}"


def local_file(path):
    """The file a site path maps to, or None when it isn't under BASE or doesn't exist."""
    path = urllib.parse.unquote(path.split("#")[0].split("?")[0])
    if BASE and path != BASE and not path.startswith(BASE + "/"):
        return None
    f = os.path.join(DOCS, path[len(BASE):].lstrip("/"))
    if os.path.isfile(f):
        return f
    if os.path.isfile(os.path.join(f, "index.html")):
        return os.path.join(f, "index.html")
    return None


def html_files():
    out = []
    for d, _, fs in os.walk(DOCS):
        out += [os.path.relpath(os.path.join(d, f), DOCS) for f in fs if f.endswith(".html")]
    return sorted(out)


_ids = {}


def ids_in(f):
    if f not in _ids:
        _ids[f] = set(re.findall(r'\sid="([^"]+)"', open(f, encoding="utf-8").read()))
    return _ids[f]


def walk_keys(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k
            yield from walk_keys(v)
    elif isinstance(x, list):
        for v in x:
            yield from walk_keys(v)


def nice_date(iso):
    y, m, d = iso.split("-")
    return f"{MONTHS[int(m) - 1]} {int(d)}, {y}"


def private_words(text):
    t = text.lower()
    words = set(re.findall(r"[\w.%+-]+@[\w.-]+", t)) | set(re.findall(r"[a-z0-9]+(?:\.[a-z0-9]+)*", t)) | set(re.findall(r"[a-z0-9]+", t))
    return [w for w in words if hashlib.sha256(w.encode()).hexdigest() in PRIVATE_DIGESTS]


SHA = lambda s: "sha256-" + base64.b64encode(hashlib.sha256(s.encode()).digest()).decode()


TYPE_SYN = {"avenue": "ave", "av": "ave", "street": "st", "boulevard": "blvd", "road": "rd", "drive": "dr", "place": "pl", "court": "ct",
            "parkway": "pkwy", "highway": "hwy", "lane": "ln", "trail": "trl", "circle": "cir", "terrace": "ter", "turnpike": "tpke", "route": "rt", "rte": "rt"}
SYN = {**TYPE_SYN, "north": "n", "south": "s", "east": "e", "west": "w", "saint": "st", "mount": "mt"}
ROUTE_WORDS = {"me", "us", "rte", "route", "rt"}


def normalize(s):
    """Search.normalize: lowercase, no accents or apostrophes, "&" as "and" ("B&B" stays "bb"), everything else a single space."""
    import unicodedata
    t = "".join(c for c in unicodedata.normalize("NFD", s or "") if not unicodedata.combining(c)).lower()
    t = re.sub(r"\b([a-z0-9])\s*&\s*([a-z0-9])\b", r"\1\2", t).replace("&", " and ")
    t = re.sub(r"['’`]", "", t)
    return re.sub(r"[^\w]+|_", " ", t).strip()


def norm_addr(s):
    w = normalize(s).split()
    w = ["rt" if x in ROUTE_WORDS and i + 1 < len(w) and w[i + 1].isdigit() else x for i, x in enumerate(w)]
    return " ".join(SYN.get(x, x) for x in w)


def miles(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


# ---------------------------------------------------------------- the data the pages were built from (docs/data)
class Data:
    def __init__(self):
        self.core = json.load(open(os.path.join(DOCS, "data", "core.json")))
        self.detail = json.load(open(os.path.join(DOCS, "data", "detail.json")))
        self.shapes = json.load(open(os.path.join(DOCS, "data", "me_shapes.json")))
        C = self.C = self.core["cols"]
        self.n = len(C["id"])
        self.kbit = {k: 1 << i for i, k in enumerate(self.core["kinds"])}
        self.by_id = {C["id"][i]: i for i in range(self.n)}

    def town(self, i):
        return self.core["cities"][self.C["c"][i]] if self.C["c"][i] is not None else None

    def rest(self, i):
        return self.C["v"][i] != 1

    def guide(self, k):
        mask = sum(self.kbit[x] for x in GUIDE_KINDS[k])
        return {i for i in range(self.n) if self.rest(i) and self.C["hc"][i] == 1 and (self.C["k"][i] or 0) & mask}

    def quoted(self):
        """Strings the pages quote from the data, which our copy rules don't apply to."""
        out = set()
        for i in range(self.n):
            for v in (self.C["n"][i], self.C["dish"][i]):
                if v:
                    out.add(v)
            for k in ("note", "jbf", "hon", "sea", "chef"):
                v = (self.detail[i] or {}).get(k)
                if v:
                    out.add(v)
                    out.update(x for x in v.split("; ") if x)
        return sorted(out, key=len, reverse=True)


# ---------------------------------------------------------------- static checks
def static_checks(data, quoted):
    titles, descs = {}, {}
    files = html_files()
    core_ids = set(data.C["id"])
    for rel in files:
        s = open(os.path.join(DOCS, rel), encoding="utf-8").read()
        where = rel
        t = re.search(r"<title>(.*?)</title>", s, re.S)
        d = re.search(r'<meta name="description" content="([^"]*)"', s)
        title, desc = H.unescape(t.group(1)) if t else "", H.unescape(d.group(1)) if d else ""
        if rel != "404.html":
            if not 50 <= len(title) <= 60:
                bad(f"{where}: title is {len(title)} characters: {title}")
            if not 140 <= len(desc) <= 160:
                bad(f"{where}: description is {len(desc)} characters")
            if title in titles:
                bad(f"{where}: same title as {titles[title]}")
            if desc in descs:
                bad(f"{where}: same description as {descs[desc]}")
            titles[title], descs[desc] = rel, rel
        else:
            if 'rel="canonical"' in s or 'property="og:url"' in s:
                bad("404.html: has a canonical URL or og:url")
            if f'href="{BASE}/explore/"' not in s:
                bad("404.html: no search link")
        if len(re.findall(r"<h1[\s>]", s)) != 1:
            bad(f"{where}: {len(re.findall(r'<h1[\\s>]', s))} <h1>")
        # Content-Security-Policy: first in <head>, and hashes that match exactly
        m = re.search(r"<head>\s*<meta http-equiv=\"Content-Security-Policy\" content=\"([^\"]+)\">", s)
        if not m:
            bad(f"{where}: no Content-Security-Policy meta first in <head>")
        else:
            csp = dict((p.split(" ", 1) + [""])[:2] for p in (x.strip() for x in m.group(1).split(";")) if p)
            want = {"default-src": "'none'", "img-src": "'self' data:", "connect-src": "'self'", "base-uri": "'none'", "form-action": "'none'",
                    "manifest-src": "'self'"}
            for k, v in want.items():
                if csp.get(k) != v:
                    bad(f"{where}: CSP {k} is {csp.get(k)!r}, want {v!r}")
            for kind, blocks in (("script-src", re.findall(r"<script>(.*?)</script>", s, re.S)), ("style-src", re.findall(r"<style>(.*?)</style>", s, re.S))):
                have = set(re.findall(r"'(sha256-[^']+)'", csp.get(kind, "")))
                need = {SHA(b) for b in blocks}
                if have != need or "unsafe" in csp.get(kind, ""):
                    bad(f"{where}: CSP {kind} hashes don't match the page's inline blocks")
        if '<meta name="referrer" content="strict-origin-when-cross-origin">' not in s:
            bad(f"{where}: no referrer meta")
        markup = re.sub(r"<script>.*?</script>", "", s, flags=re.S)     # links and text built by the web app's script are checked in the browser
        if re.search(r"<[a-zA-Z][^>]*\sstyle=", markup):
            bad(f"{where}: inline style attribute (blocked by the CSP)")
        if re.search(r"<[a-zA-Z][^>]*\son[a-z]+=", markup):
            bad(f"{where}: inline event handler (blocked by the CSP)")
        if re.search(r"<script(?![^>]*application/ld\+json)[^>]*\bsrc=", s):
            bad(f"{where}: an external script")
        if "<!--" in s.replace(APPLE_ITUNES_PLACEHOLDER, ""):
            bad(f"{where}: HTML comment left in the output")
        head = s.split("</head>")[0]
        if APPLE_ITUNES_PLACEHOLDER not in head and not re.search(r'<meta name="apple-itunes-app" content="app-id=\d+">', head):
            bad(f"{where}: no apple-itunes-app smart banner tag (or its commented placeholder) in <head>")
        if 'name="twitter:image:alt"' not in s:
            bad(f"{where}: no twitter:image:alt")
        if "M16.4 12.6c0-2.5" in s:
            bad(f"{where}: draws the Apple logo")
        for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', s, re.S):
            if "<" in raw or ">" in raw:
                bad(f"{where}: raw < or > inside JSON-LD (it must be escaped as \\u003c)")
            try:
                obj = json.loads(raw)
            except ValueError as ex:
                bad(f"{where}: bad JSON-LD ({ex})")
                continue
            hit = BANNED_LD & set(walk_keys(obj))
            if hit:
                bad(f"{where}: ratings or reviews in JSON-LD: {sorted(hit)}")
            if obj.get("@type") == "ItemList":
                for it in obj.get("itemListElement", []):
                    u = urllib.parse.urlparse(it.get("url", ""))
                    if u.netloc != DOMAIN_HOST or not u.path.startswith(BASE + "/places/") or not local_file(u.path):
                        bad(f"{where}: list item {it.get('name')!r} doesn't point at a place page ({it.get('url')})")
                if obj.get("numberOfItems") != len(obj.get("itemListElement", [])):
                    bad(f"{where}: ItemList numberOfItems doesn't match its items")
            if obj.get("@type") == "Restaurant":
                a = obj.get("address", {})
                if not obj.get("name") or not a.get("streetAddress") or not obj.get("geo", {}).get("latitude"):
                    bad(f"{where}: Restaurant JSON-LD without a name, street address and geo")
                if any(v == "" for v in a.values()):
                    bad(f"{where}: Restaurant JSON-LD has an empty address field")
                if "telephone" in obj and not re.fullmatch(r"\+1[2-9]\d{9}", obj["telephone"]):
                    bad(f"{where}: telephone {obj['telephone']!r}")
                if "url" in obj and urllib.parse.urlsplit(obj["url"]).scheme not in ("http", "https"):
                    bad(f"{where}: Restaurant url {obj['url']!r}")
        # links: same-site ones resolve (anchors too), tel: is digits, nothing with an odd scheme
        for tag, ref in re.findall(r'<(a|img|link|source|script)\b[^>]*?\s(?:href|src|srcset)="([^"]*)"', markup):
            ref = H.unescape(ref)
            sp = urllib.parse.urlsplit(ref)
            scheme = sp.scheme.lower()
            if scheme in ("http", "https"):
                if tag == "a" and sp.netloc == DOMAIN_HOST and (sp.path == BASE or sp.path.startswith(BASE + "/")):
                    bad(f"{where}: absolute link to our own site {ref}")
                continue
            if scheme == "mailto":
                continue
            if scheme == "tel":
                if not re.fullmatch(r"tel:\+1[2-9]\d{9}", ref):
                    bad(f"{where}: bad tel: link {ref}")
                continue
            if scheme:
                bad(f"{where}: link with scheme {scheme}: {ref[:60]}")
                continue
            target = urllib.parse.urljoin(f"{BASE}/{rel}", ref)
            path, _, frag = target.partition("#")
            f = local_file(path) if path else os.path.join(DOCS, rel)
            if not f:
                bad(f"{where}: broken link {ref}")
            elif frag and f.endswith(".html") and "=" not in frag and frag not in ids_in(f):
                bad(f"{where}: link to a missing anchor {ref}")
            elif "=" in frag and "p=" in frag:
                pid = urllib.parse.parse_qs(frag).get("p", [""])[0]
                if pid not in core_ids:
                    bad(f"{where}: a web app link to a place that isn't in the data ({pid})")
        # copy: no overclaims (our words only), no Google, MICHELIN only as "there is no MICHELIN Guide for Maine"
        text = H.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S)))
        text = re.sub(r"\s+", " ", text)
        own = text
        for q in quoted:
            if len(q) > 3 and q in own:
                own = own.replace(q, " ")
        own = re.sub(r"Best Chef: [A-Za-z ]+", " ", own)    # the James Beard award's own name
        for rx in OVERCLAIMS:
            mm = re.search(rx, own, re.I)
            if mm:
                bad(f"{where}: overclaim {mm.group(0)!r}: …{own[max(0, mm.start() - 50):mm.end() + 30]}…")
        low = s.lower()
        if "google" in low:
            bad(f"{where}: mentions Google")
        if re.sub(r"there is no michelin guide for maine|michelin is a trademark of michelin|michelin,", "", low).count("michelin"):
            bad(f"{where}: mentions MICHELIN beyond 'there is no MICHELIN Guide for Maine'")
        if re.search(r"james beard finalist", text, re.I):
            bad(f"{where}: says 'James Beard finalist' (the foundation says nominee)")
        if private_words(s):
            bad(f"{where}: contains a private email address or part of one")
        if re.search(r"\b(permanently closed|closed for good)\b", own, re.I) and "hasn't closed for good" not in own:
            bad(f"{where}: calls a place closed")
    for d, _, fs in os.walk(DOCS):   # the data files, license texts, sitemap and manifest are public too
        for x in fs:
            if x.endswith((".json", ".txt", ".xml", ".webmanifest")) and private_words(open(os.path.join(d, x), encoding="utf-8", errors="replace").read()):
                bad(f"{os.path.relpath(os.path.join(d, x), DOCS)}: contains a private email address or part of one")
    return files


def inspection_checks(data, files):
    """Lewiston's Pass/Fail results appear only on a place's own page, and there exactly as the data has them (with the date and the
    city's report); no other page shows a result, so there's never a list or board of them."""
    C = data.C
    for rel in files:
        s = open(os.path.join(DOCS, rel), encoding="utf-8").read()
        markup = re.sub(r"<script>.*?</script>", "", s, flags=re.S)
        shows = re.findall(r"City of Lewiston inspection: (Passed|Failed)(?:, ([A-Z][a-z]{2} \d{1,2}, \d{4}))?", H.unescape(re.sub(r"<[^>]+>", "", markup)))
        badge = 'class="rb rb-' in markup
        if not rel.startswith("places/"):
            if shows or badge or re.search(r"\b(Passed|Failed)\b", H.unescape(re.sub(r"<[^>]+>", "", markup))):
                bad(f"{rel}: shows an inspection result outside a place's own page")
            continue
        m = re.search(r'href="[^"]*/explore/#p=([0-9a-f]+)"', s)
        i = data.by_id.get(m.group(1)) if m else None
        lw = (data.detail[i] or {}).get("lw") if i is not None else None
        if lw:
            want = ("Passed" if lw["r"] == "Pass" else "Failed", nice_date(lw["d"]))
            if shows != [want]:
                bad(f"{rel}: shows {shows}, but the data says {want}")
            if lw.get("u") and H.escape(lw["u"]) not in s:
                bad(f"{rel}: doesn't link the city's report {lw['u']}")
        elif shows or badge:
            bad(f"{rel}: shows an inspection result the data doesn't have")
        if STATE_HIP not in s:
            bad(f"{rel}: no link to the state's health inspection search")


ENTRY = re.compile(r'<li id="p-([^"]+)"><h3>')   # a full place entry (a later "listed above" pointer isn't one)


def guide_checks(data, files):
    """Each guide page lists exactly the hand-checked places of its kinds (a place merely named "... Lobster Pound" is not enough);
    a guide under MIN_PAGE places has no page; the icons page lists the places with iconic points, the oldest page the places with
    a year at the same address."""
    C = data.C
    pages = {}
    for k, f in GUIDE_FILE.items():
        want = data.guide(k)
        if len(want) >= MIN_PAGE:
            pages[f] = want
        elif f in files:
            bad(f"{f}: a page for a guide with only {len(want)} places")
    icons = {i for i in range(data.n) if data.rest(i) and C["ip"][i] is not None}
    if len(icons) >= MIN_PAGE:
        pages[ICONS_FILE] = icons
    long_running = int(str(data.core["generated"])[:4]) - 40   # Guide.oldest: 40 or more years at the same address
    pages[OLDEST_FILE] = {i for i in range(data.n) if data.rest(i) and C["f"][i] is not None and C["f"][i] <= long_running}
    for f, want in pages.items():
        if f not in files:
            bad(f"{f}: missing")
            continue
        s = open(os.path.join(DOCS, f), encoding="utf-8").read()
        got = [data.by_id.get(x) for x in ENTRY.findall(s)]
        if None in got:
            bad(f"{f}: lists a place that isn't in the data")
        got = set(x for x in got if x is not None)
        if got != want:
            bad(f"{f}: lists {len(got)} places, expected {len(want)} (extra {sorted(C['n'][i] for i in got - want)[:4]}, "
                f"missing {sorted(C['n'][i] for i in want - got)[:4]})")
        if any(C["hc"][i] != 1 for i in got):
            bad(f"{f}: lists places that aren't hand-checked")
        for i in got:   # each entry links to the place's own page
            if not re.search(rf'<li id="p-{C["id"][i]}"><h3><a href="{re.escape(BASE)}/places/[^"]+\.html">', s):
                bad(f"{f}: {C['n'][i]} doesn't link to its own page")
                break


TOWN_SECTIONS = {"lobster": 15, "clams": 15, "sandwiches": 10, "sweets": 10, "franco": 15, "diners": 10, "oysters": 15, "dairy": 10}
LEDE_KIND = {"lobster shacks": "lobster", "clam shacks": "clams", "Italians": "sandwiches", "whoopie pies": "sweets", "Franco-American food": "franco",
             "diners": "diners", "oyster bars": "oysters", "dairy bars": "dairy"}


def town_claims(data, files):
    """A town page may say none of our hand-checked places of a kind is in or near the town only when that's true: no hand-checked
    place of that kind in the town or within the section's radius of its center (the median of its places)."""
    C = data.C
    places = defaultdict(list)
    for i in range(data.n):
        if data.rest(i) and C["la"][i] is not None:
            places[data.town(i)].append(i)
    for rel in [f for f in files if f.startswith("cities/") and f != "cities/index.html"]:
        s = open(os.path.join(DOCS, rel), encoding="utf-8").read()
        t = H.unescape(re.search(r'<li aria-current="page">(.*?)</li>', s).group(1))   # the town, from the breadcrumb
        here = places[t]
        if not here:
            bad(f"{rel}: no places in {t!r} in the data")
            continue
        center = (sorted(C["la"][i] for i in here)[len(here) // 2], sorted(C["lo"][i] for i in here)[len(here) // 2])

        def close(k, rad, others=False):
            return sorted(C["n"][i] for i in data.guide(k) if (data.town(i) == t and not others)
                          or (data.town(i) != t and C["la"][i] is not None and miles(center, (C["la"][i], C["lo"][i])) <= rad))
        claims = []
        text = H.unescape(re.sub(r"<[^>]+>", "", s))
        # a claim about the world ("None in Augusta", "the nearest are a drive away") can't be backed by our list
        if re.search(r"\bNone in .+? or within \d+ miles", text) or any(
                not x.startswith("hand-checked ") for x in re.findall(r"\bFor ([^.]*?), the nearest are a drive away", text)):
            bad(f"{rel}: says there's none of a kind in or near {t} at all; say none of our hand-checked ones is")
        for k, body in re.findall(r'<section id="(lobster|clams|sandwiches|sweets|franco|diners|oysters|dairy)">(.*?)</section>', s, re.S):
            b = H.unescape(re.sub(r"<[^>]+>", "", body))
            for m in re.finditer(r"None of our \d+ hand-checked [^<.]*? is in (.+?) or within (\d+) miles", b):
                if m.group(1) != t:
                    bad(f"{rel}: a 'None of our …' sentence names {m.group(1)!r}")
                claims.append((k, int(m.group(2)), False))
            for m in re.finditer(r"None of our other [^.]*? is within (\d+) miles", b):
                claims.append((k, int(m.group(1)), True))
        lede = H.unescape(re.sub(r"<[^>]+>", "", re.search(r'<p class="lede">(.*?)</p>', s, re.S).group(1)))
        m = re.search(r"For hand-checked (.+?), the nearest are a drive away", lede)
        if m:
            for label in re.split(r", | and ", m.group(1)):
                if label not in LEDE_KIND:
                    bad(f"{rel}: the lede names an unknown kind {label!r}")
                    continue
                claims.append((LEDE_KIND[label], TOWN_SECTIONS[LEDE_KIND[label]], False))
        for k, rad, others in claims:
            wrong = close(k, rad, others)
            if wrong:
                bad(f"{rel}: says none of our hand-checked {k} places is in or within {rad} miles of {t}, but {wrong[:3]} are")
        if re.search(r"None of our \d+ hand-checked places is in [^<]*? yet", s):
            hc_here = [C["n"][i] for i in range(data.n) if C["hc"][i] == 1 and data.rest(i) and data.town(i) == t]
            if hc_here:
                bad(f"{rel}: says none of our hand-checked places is in {t}, but {hc_here[:3]} are")


def page_type_checks(data, files, sitemap_paths):
    need = ["index.html", OLDEST_FILE, "cities/index.html", "about.html", "privacy.html", "terms.html", "explore/index.html", "404.html"]
    for n in need:
        if n not in files:
            bad(f"missing page {n}")
    regions = [f for f in files if f.startswith("regions/")]
    if len(regions) != len(data.core["regions"]):
        bad(f"{len(regions)} region pages for {len(data.core['regions'])} regions")
    for rel in regions:   # each says which counties, exactly
        s = H.unescape(open(os.path.join(DOCS, rel), encoding="utf-8").read())
        name = H.unescape(re.search(r'<li aria-current="page">(.*?)</li>', s).group(1))
        want = sorted(c["name"] for c in data.shapes["counties"] if c["region"] == name)
        m = re.search(r"Counties: ([^.]+)\.", s)
        if not want or not m or sorted(x.strip() for x in m.group(1).split(",")) != want:
            bad(f"{rel}: doesn't name its counties {want} ({m.group(1) if m else 'none'})")
    towns = [f for f in files if f.startswith("cities/") and f != "cities/index.html"]
    if len(towns) < 10:
        bad(f"only {len(towns)} town pages")
    hub = open(os.path.join(DOCS, "cities/index.html"), encoding="utf-8").read() if "cities/index.html" in files else ""
    for c in towns + regions:
        if f'href="{BASE}/{c}"' not in hub:
            bad(f"the towns hub doesn't link {c}")
    places = [f for f in files if f.startswith("places/")]
    C = data.C
    want = {i for i in range(data.n) if data.rest(i) and (C["hc"][i] == 1 or C["ip"][i] is not None or C["h"][i])}
    seen = set()
    for f in places:
        s = open(os.path.join(DOCS, f), encoding="utf-8").read()
        m = re.search(r'href="[^"]*/explore/#p=([0-9a-f]+)"', s)
        if not m or m.group(1) not in data.by_id:
            bad(f"{f}: no #p= link the web app can open")
            continue
        i = data.by_id[m.group(1)]
        seen.add(i)
        if H.unescape(re.search(r"<h1>(.*?)</h1>", s).group(1)) != C["n"][i]:
            bad(f"{f}: its <h1> isn't the place's name {C['n'][i]!r}")
        if not re.search(r"Checked (open|in business) in \w+ \d{4}", s):
            bad(f"{f}: no hand-check note")
        if C["seas"][i] == 1 and "seasonal" not in s.lower():
            bad(f"{f}: a seasonal place whose page doesn't say so")
        if "/" + f not in sitemap_paths:
            bad(f"{f}: not in the sitemap")
    if seen != want:
        bad(f"place pages: {len(seen)} for {len(want)} hand-checked or honored places (missing {sorted(C['n'][i] for i in want - seen)[:4]})")
    if len(C["id"]) != len(set(C["id"])):
        bad("core.json has duplicate place ids")
    for k in ("holder", "licensee", "owner", "lic"):
        if k in C or any(k in (d or {}) for d in data.detail):
            bad(f"the data files carry {k!r}")


def other_state_checks():
    """No other state's app, repo or (outside the allow-list) name in any public file, comments and scripts included."""
    for d, _, fs in os.walk(DOCS):
        for x in fs:
            if not x.endswith((".html", ".json", ".txt", ".xml", ".webmanifest", ".js", ".css")):
                continue
            rel = os.path.relpath(os.path.join(d, x), DOCS)
            t = open(os.path.join(d, x), encoding="utf-8", errors="replace").read()
            m = OTHER_APPS.search(t)
            if m:
                bad(f"{rel}: names another state's app or repo: …{t[max(0, m.start() - 40):m.end() + 20]}…")
            for ok in OTHER_STATES_OK:
                t = t.replace(ok, "")
            m = OTHER_STATES.search(t)
            if m:
                bad(f"{rel}: names another state: …{t[max(0, m.start() - 40):m.end() + 20]}…")


BLOCKLIST_FILE = os.environ.get("WEBSITE_BLOCKLIST") or os.path.join(ROOT, "pipeline", "website_blocklist.json")


def blocklist_patterns(entries):
    """(name, regex) for each blocklist entry: a "domain" entry finds that domain and any subdomain (www., shop.) in any case, after any
    scheme; a "url" entry finds that one page whatever its scheme, www. or trailing slash. Neither finds a longer name that merely ends
    the same way ("notexample.com")."""
    pats = []
    for b in entries:
        if b.get("match", "domain") == "domain":
            d = b["domain"].strip().lower().removeprefix("www.").rstrip(".")
            pats.append((d, re.compile(r"(?<![a-z0-9-])" + re.escape(d) + r"(?![a-z0-9-])", re.I)))
        else:
            u = re.sub(r"^(?:https?:)?//", "", (b.get("url") or b["domain"]).strip(), flags=re.I).lower().removeprefix("www.").rstrip("/")
            pats.append((u, re.compile(r"(?<![a-z0-9-])" + re.escape(u) + r"/?(?![a-z0-9/_-])", re.I)))
    return pats


def blocklist_checks():
    """No blocklisted restaurant website (hacked, expired, another business's or a directory's page; pipeline/website_blocklist.json)
    anywhere in docs/: pages, JSON-LD, the web app's data files, everything. The list must exist and not be empty (its sentinel entry
    keeps it from passing vacuously), every entry is well-formed, and the matcher is tested on each domain entry's variants first."""
    name = os.path.relpath(BLOCKLIST_FILE, ROOT) if BLOCKLIST_FILE.startswith(ROOT + os.sep) else BLOCKLIST_FILE
    try:
        entries = json.load(open(BLOCKLIST_FILE, encoding="utf-8"))
    except FileNotFoundError:
        bad(f"{name}: missing (make-site.py drops the websites it lists; an empty check would pass anything)")
        return
    except ValueError as ex:
        bad(f"{name}: not valid JSON ({ex})")
        return
    if not isinstance(entries, list) or not entries:
        bad(f"{name}: empty or not a list (keep the sentinel entry, so this check can't pass vacuously)")
        return
    good = []
    for b in entries:
        if not isinstance(b, dict) or not b.get("domain") or b.get("match", "domain") not in ("domain", "url") or not b.get("reason"):
            bad(f"{name}: malformed entry (needs domain, match domain|url, reason): {json.dumps(b)[:120]}")
        else:
            good.append(b)
    pats = blocklist_patterns(good)
    # the matcher itself: each domain must be found in its case, www., scheme, subdomain and escaped variants, and a longer name ending
    # the same way must not be
    for (d, rx), b in zip(pats, good):
        if b.get("match", "domain") != "domain":
            continue
        for v in (f"https://{d}/", f"HTTP://WWW.{d.upper()}/menu", f"http://shop.{d}", f'"w":"https:\\/\\/www.{d}\\/"', f"href=\"//{d}\"",
                  f"{d}."):
            flat = H.unescape(v.replace("\\/", "/"))
            if not rx.search(flat):
                bad(f"{name}: the check misses {v!r} for {d}")
        if rx.search(f"https://not{d}/") or rx.search(f"https://{d}-x.com/"):
            bad(f"{name}: the check would flag a different domain ending in {d}")
    for root, _, fs in os.walk(DOCS):
        for x in fs:
            if x.endswith((".png", ".webp", ".ico", ".jpg", ".jpeg", ".gif", ".woff", ".woff2")):
                continue
            f = os.path.join(root, x)
            raw = open(f, encoding="utf-8", errors="ignore").read()
            flat = H.unescape(raw.replace("\\/", "/"))
            for k, rx in pats:
                if rx.search(flat) or rx.search(urllib.parse.unquote(flat)):
                    bad(f"{os.path.relpath(f, DOCS)}: publishes the blocklisted website {k} ({name})")


def storage_checks():
    """The privacy page names every localStorage key the web app writes (explore.js: store.set("<k>") under its prefix)."""
    js = open(os.path.join(DOCS, "explore", "index.html"), encoding="utf-8").read()
    pre = re.search(r'localStorage\.setItem\("([^"]+)" \+ k', js)
    keys = sorted({(pre.group(1) if pre else "") + k for k in re.findall(r'store\.set\("([^"]+)"', js)})
    raw = re.findall(r'localStorage\.setItem\("([^"]+)"\s*,', js)
    keys += [k for k in raw if k not in keys]
    priv = H.unescape(open(os.path.join(DOCS, "privacy.html"), encoding="utf-8").read())
    if not keys:
        bad("explore: couldn't find the localStorage keys it writes")
    for k in keys:
        if k not in priv:
            bad(f"privacy.html: doesn't name the web app's localStorage key {k!r}")
    if pre and not all(k.startswith(pre.group(1)) for k in keys):
        bad(f"explore: a localStorage key outside the site's own prefix {pre.group(1)!r}: {keys}")


def family_checks(files):
    """The Eats Ranked family link (footer + parentOrganization) on every page, and the contact address: nick@eatsranked.com in every
    mailto and in the Organization's JSON-LD, the old Gmail address nowhere in docs/ (pages, data files, license texts, manifest)."""
    for d, _, fs in os.walk(DOCS):
        for x in fs:
            if x.endswith((".html", ".json", ".txt", ".xml", ".webmanifest", ".js", ".css")):
                f = os.path.join(d, x)
                if OLD_EMAIL in open(f, encoding="utf-8", errors="replace").read().lower():
                    bad(f"{os.path.relpath(f, DOCS)}: still shows the old contact address (the site uses {EMAIL})")
    for rel in files:
        s = open(os.path.join(DOCS, rel), encoding="utf-8").read()
        foot = re.search(r"<footer>(.*?)</footer>", s, re.S)
        if not foot or f'<a href="{HUB}">Eats Ranked</a>' not in foot.group(1):
            bad(f"{rel}: the footer doesn't say it's part of Eats Ranked ({HUB})")
        for addr in re.findall(r'href="mailto:([^"?]+)', s):
            if addr != EMAIL:
                bad(f"{rel}: a mailto: link to {addr}, not {EMAIL}")
        if f"mailto:{EMAIL}" not in s:
            bad(f"{rel}: no mailto:{EMAIL} link")
        has_parent = False
        for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', s, re.S):
            try:
                obj = json.loads(raw)
            except ValueError:
                continue
            stack = [obj]
            while stack:
                n = stack.pop()
                if isinstance(n, list):
                    stack += n
                    continue
                if not isinstance(n, dict):
                    continue
                stack += list(n.values())
                if n.get("@type") == "Organization" and str(n.get("@id", "")).endswith("/#org"):
                    if (n.get("parentOrganization") or {}).get("@id") != HUB_ORG:
                        bad(f"{rel}: the #org Organization has no parentOrganization {HUB_ORG}")
                    else:
                        has_parent = True
                    for k in ("email",):
                        if k in n and n[k] != EMAIL:
                            bad(f"{rel}: Organization {k} is {n[k]}")
                    if "contactPoint" in n and n["contactPoint"].get("email") != EMAIL:
                        bad(f"{rel}: Organization contactPoint email is {n['contactPoint'].get('email')}")
                if n.get("@type") == "WebSite" and "@id" not in n and len(n) > 1:
                    bad(f"{rel}: a WebSite node without its @id (it should join the #website node)")
        if not has_parent:   # every page, places, privacy, terms and 404 included (Addendum 1, XS-08)
            bad(f"{rel}: no #org Organization with parentOrganization {HUB_ORG} in its JSON-LD")
    for rel in ("privacy.html", "terms.html", "about.html", "index.html"):
        if rel in files and EMAIL not in H.unescape(re.sub(r"<[^>]+>", " ", open(os.path.join(DOCS, rel), encoding="utf-8").read())):
            bad(f"{rel}: doesn't show {EMAIL}")
    home = open(os.path.join(DOCS, "index.html"), encoding="utf-8").read()
    if f'"email":"{EMAIL}"' not in home:
        bad(f"index.html: the Organization JSON-LD doesn't carry email {EMAIL}")


def copy_decision_checks():
    """Nick's 2026-10-13 copy decisions, over every text file in docs/ (pages, attributes, JSON-LD, the web app's code and data):
    no "Confirmed listing" in any case, the web app labels the tier "High-confidence listing", and nothing promises a TestFlight invite or
    link ("we'll send you an invite", "you'll get a TestFlight link", "Get early access"). Entities are decoded and curly apostrophes
    straightened first, so "we&#39;ll" and "we’ll" count."""
    for d, _, fs in os.walk(DOCS):
        for x in fs:
            if not x.endswith((".html", ".json", ".txt", ".xml", ".webmanifest", ".js", ".css")):
                continue
            f = os.path.join(d, x)
            rel = os.path.relpath(f, DOCS)
            t = H.unescape(open(f, encoding="utf-8", errors="replace").read()).replace("\u2019", "'")
            if OLD_LABEL.search(t):
                bad(f"{rel}: says \"Confirmed listing\" (the label is \"{NEW_LABEL}\")")
            if OLD_FILTER.search(t):
                bad(f"{rel}: says \"Confirmed only\" (the web app's filter is \"High-confidence only\")")
            for pat in PROMISES:
                for m in pat.finditer(t):
                    bad(f"{rel}: promises a TestFlight invite or early access: {m.group(0)!r} (the copy ends at an ask)")
                    break
    js = open(os.path.join(DOCS, "explore", "index.html"), encoding="utf-8").read()
    if not re.search(r'const TIER = \{[^}]*1: "' + re.escape(NEW_LABEL) + '"', js):
        bad(f"explore: the place panel's tier label isn't \"{NEW_LABEL}\"")


GUIDE_TITLE = {"lobster": "Lobster Shacks & Rolls", "clams": "Clam Shacks", "sandwiches": "Red Snappers & Italians", "sweets": "Whoopie Pies & Donuts",
               "franco": "Franco-American", "diners": "Diners", "oysters": "Oyster Bars", "dairy": "Dairy Bars"}


def claim_checks(data, files):
    """Sentences counted from the research notes say what the notes say: Damariscotta River or Pemaquid oysters on the menu (not a
    shucking contest at the Pemaquid Oyster Festival), oysters served at a farm (not a raw bar run by a farmer), ice cream made in
    house (not homemade waffle cones); the home page's guide list names only the guides the app offers; region town lists add up."""
    C = data.C
    notes = lambda i: f"{(data.detail[i] or {}).get('note') or ''} {C['dish'][i] or ''}"
    page = lambda f: open(os.path.join(DOCS, f), encoding="utf-8").read() if f in files else ""
    oy = data.guide("oysters")
    n_river = sum(1 for i in oy if RIVER_OYSTERS.search(notes(i)))
    s = page(GUIDE_FILE["oysters"])
    if s:
        txt = H.unescape(re.sub(r"<[^>]+>", "", s))
        got = re.findall(r"(\d+) of the (\d+) places here list Damariscotta River or Pemaquid oysters", txt)
        if not got or any((int(a), int(b)) != (n_river, len(oy)) for a, b in got):
            bad(f"{GUIDE_FILE['oysters']}: says {got} list Damariscotta River or Pemaquid oysters; the notes say {n_river} of {len(oy)}")
        m = re.search(r"<h3>Can I eat oysters at a farm\?</h3>\s*<p>(.*?)</p>", s, re.S)
        # the "Yes: ..." sentence names the places at a farm; a later sentence may name farmer-run raw bars, which aren't
        farm = m.group(1).split(". ")[0] if m and m.group(1).startswith("Yes:") else ""
        for pid in re.findall(r'href="#p-([0-9a-f]+)"', farm):
            i = data.by_id.get(pid)
            if i is None or not AT_OYSTER_FARM.search(notes(i)):
                bad(f"{GUIDE_FILE['oysters']}: says {C['n'][i] if i is not None else pid} serves oysters at a farm; its notes don't")
        if m and not farm and any(AT_OYSTER_FARM.search(notes(i)) for i in oy):
            bad(f"{GUIDE_FILE['oysters']}: says no place here is at a farm; the notes name one")
    dairy = data.guide("dairy")
    n_own = sum(1 for i in dairy if OWN_ICE_CREAM.search(notes(i)))
    s = page(GUIDE_FILE["dairy"])
    if s:
        got = re.findall(r"(\d+) (?:of the \d+ )?make their own", H.unescape(re.sub(r"<[^>]+>", "", s)))
        if not got or any(int(a) != n_own for a in got):
            bad(f"{GUIDE_FILE['dairy']}: says {got} make their own ice cream; the notes say {n_own}")
    home = page("index.html")
    card = re.search(r"<h3>Oyster bars</h3><p>([^<]*)</p>", home)
    if card and "Damariscotta" in card.group(1) and f"{n_river} list Damariscotta River or Pemaquid oysters" not in card.group(1):
        bad(f"index.html: the oyster card says {card.group(1)!r}; the notes say {n_river} list Damariscotta River or Pemaquid oysters")
    m = re.search(r"<h3>Pick a guide\.</h3><p>(.*?)</p>", home, re.S)
    if m:
        named = H.unescape(m.group(1))
        for k, t in GUIDE_TITLE.items():
            if len(data.guide(k)) < APP_MIN_GUIDE and re.search(rf"(^|, ){re.escape(t)}(,| or)", named):
                bad(f"index.html: 'Pick a guide' names {t}, which the app doesn't offer ({len(data.guide(k))} places)")
    # the oldest page is the 40-year list (Guide.oldest), and says so: not "every place with a known year"
    s = page(OLDEST_FILE)
    if s:
        long_running = int(str(data.core["generated"])[:4]) - 40
        n_old = sum(1 for i in range(data.n) if data.rest(i) and C["f"][i] is not None and C["f"][i] <= long_running)
        lede = H.unescape(re.sub(r"<[^>]+>", "", re.search(r'<p class="lede">(.*?)</p>', s, re.S).group(1)))
        if not re.search(rf"\b{n_old}\b[^.]*40 years or more", lede):
            bad(f"{OLDEST_FILE}: the lede doesn't say it lists the {n_old} places with 40 years or more at one address: {lede[:100]!r}")
    for rel in files:
        txt = H.unescape(re.sub(r"<[^>]+>", " ", page(rel)))
        for t in SHARED_TEMPLATE:
            if t in txt:
                bad(f"{rel}: still uses the shared template sentence {t!r}")
    # region pages: the busiest towns (3+ places, up to 12), each counted right and in this region
    counts = Counter(data.town(i) for i in range(data.n) if data.rest(i) and data.town(i))
    region_of = {t: data.core["regions"][r] for t, r in zip(data.core["cities"], data.core["town_region"]) if r is not None}
    for rel in [f for f in files if f.startswith("regions/")]:
        s = page(rel)
        name = H.unescape(re.search(r'<li aria-current="page">(.*?)</li>', s).group(1))
        want = sorted([(t, c) for t, c in counts.items() if region_of.get(t) == name and c >= 3], key=lambda x: (-x[1], x[0]))[:12]
        sec = re.search(r'<section id="towns">(.*?)</section>', s, re.S)
        got = [(urllib.parse.parse_qs(H.unescape(u)).get("town", [""])[0], int(c.replace(",", "")))
               for u, c in re.findall(r'href="[^"]*/explore/#([^"]+)">[^<]+ \(([\d,]+)\)</a>', sec.group(1))] if sec else []
        if got != want:
            bad(f"{rel}: its town list is {got[:4]}…, expected {want[:4]}… (the region's towns with 3+ places)")
        # "N more restaurants" in a region's description counts the directory's other places: its total includes the hand-checked
        # ones the page lists (ItemList); and one place is "1 hand-checked place"
        desc = H.unescape(re.search(r'<meta name="description" content="([^"]*)"', s).group(1))
        n_listed = next((json.loads(raw).get("numberOfItems") for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', s, re.S)
                         if '"ItemList"' in raw), None)
        total = sum(c for t, c in counts.items() if region_of.get(t) == name)
        for m in re.findall(r"([\d,]+) more restaurants", desc):
            if n_listed is not None and int(m.replace(",", "")) != total - n_listed:
                bad(f"{rel}: the description says {m} more restaurants; the region has {total}, {n_listed} of them on the page")
        if re.search(r"\b1 hand-checked places\b", desc):
            bad(f"{rel}: the description says '1 hand-checked places'")
    # the oyster title counts the farm among the n places, not as one more
    s = page(GUIDE_FILE["oysters"])
    if s:
        t = H.unescape(re.search(r"<title>(.*?)</title>", s).group(1))
        m = re.search(r"(\d+) Hand-Checked Raw Bars and a Farm", t)
        if m and int(m.group(1)) + 1 != len(oy):
            bad(f"{GUIDE_FILE['oysters']}: the title {t!r} counts {int(m.group(1)) + 1} places; the list has {len(oy)}")
    # a guide's lede that names its kinds of source names all of them: a few places stand on a town or chamber listing alone
    # (Polar Treat, Sea Basket), so "its own site, its menu or Maine news coverage" alone overstates
    for rel in [f for f in files if "/" not in f]:
        m = re.search(r'<p class="lede">(.*?)</p>', page(rel), re.S)
        lede = H.unescape(re.sub(r"<[^>]+>", "", m.group(1))) if m else ""
        if "going by its own site" in lede and "town or chamber" not in lede:
            bad(f"{rel}: the lede names its sources without the town and chamber listings some places rest on: {lede[:90]!r}")


def sitemap_checks(files):
    root = ET.parse(os.path.join(DOCS, "sitemap.xml")).getroot()
    locs, paths = [], set()
    for u in root.findall("s:url", NS):
        loc, lastmod = u.find("s:loc", NS).text, u.find("s:lastmod", NS)
        if lastmod is None or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", lastmod.text or ""):
            bad(f"sitemap: {loc} has no valid lastmod")
        p = urllib.parse.urlparse(loc)
        if p.netloc != DOMAIN_HOST:
            bad(f"sitemap: {loc} isn't on {DOMAIN_HOST}")
        f = local_file(p.path)
        if not f:
            bad(f"sitemap: {loc} has no file")
        else:
            paths.add("/" + os.path.relpath(f, DOCS))
        locs.append(loc)
    if len(locs) != len(set(locs)):
        bad("sitemap: duplicate URLs")
    for f in files:
        if f != "404.html" and "/" + f not in paths:
            bad(f"sitemap: {f} exists but isn't in the sitemap")
    # lastmod is the page's last real change: never older than the "Last updated" date both legal pages print (the copy, titles and
    # footer changed that day across the site), and each Article's dateModified says the same as the sitemap. The older of the two:
    # one policy can change on its own (2026-10-26: the privacy page's data updates bullet) without the rest of the site's copy
    lm_of = {u.find("s:loc", NS).text: (u.find("s:lastmod", NS).text if u.find("s:lastmod", NS) is not None else "") for u in root.findall("s:url", NS)}
    dates = []
    for legal in ("privacy.html", "terms.html"):
        upd = re.search(r"Last updated (\w{3}) (\d+), (\d{4})", H.unescape(re.sub(r"<[^>]+>", " ", open(os.path.join(DOCS, legal), encoding="utf-8").read())))
        if upd:
            dates.append(f"{upd.group(3)}-{['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'].index(upd.group(1)) + 1:02d}-{int(upd.group(2)):02d}")
    floor = min(dates) if dates else ""
    for loc, lm in lm_of.items():
        if floor and lm < floor:
            bad(f"sitemap: {loc} lastmod {lm} is older than the site's last copy change ({floor})")
        f = local_file(urllib.parse.urlparse(loc).path)
        if f:
            for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', open(f, encoding="utf-8").read(), re.S):
                dm = re.search(r'"@type":"Article".*?"dateModified":"([^"]+)"', raw)
                if dm and dm.group(1) != lm:
                    bad(f"{os.path.relpath(f, DOCS)}: Article dateModified {dm.group(1)} != sitemap lastmod {lm}")
    robots = open(os.path.join(DOCS, "robots.txt")).read()
    if f"Sitemap: {HOME.scheme}://{DOMAIN_HOST}{BASE}/sitemap.xml" not in robots:
        bad("robots.txt doesn't name the sitemap")
    man = json.load(open(os.path.join(DOCS, "site.webmanifest")))
    for ic in man.get("icons", []):
        if not local_file(ic["src"]):
            bad(f"site.webmanifest: icon {ic['src']} is missing")
    return locs, paths


# ---------------------------------------------------------------- browser checks
TAP = """(scope) => {
  const out = [];
  const root = scope ? document.querySelector(scope) : document;
  const blockOf = (el) => { let n = el.parentElement; while (n && getComputedStyle(n).display.startsWith('inline')) n = n.parentElement; return n; };
  for (const el of root.querySelectorAll('a[href], button, input:not([type=hidden]), select, textarea, summary')) {
    let t = el;
    if (el.matches('input[type=checkbox], input[type=radio]') && el.closest('label')) t = el.closest('label');
    if (t.closest('[hidden], [inert]') && !scope) continue;
    const cs = getComputedStyle(t);
    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    const r = t.getBoundingClientRect();
    if (r.width === 0 || r.height === 0 || r.right + scrollX <= 0 || r.bottom + scrollY <= 0) continue;   // not rendered, or the off-screen skip link
    if (t.tagName === 'A' && cs.display === 'inline') {     // a link inside a sentence is exempt (WCAG 2.5.8)
      const b = blockOf(t), own = t.textContent.replace(/\\s+/g, ' ').trim(), all = (b ? b.textContent : '').replace(/\\s+/g, ' ').trim();
      if (all.length > own.length + 2) continue;
    }
    if (r.width < 43.5 || r.height < 43.5) out.push(`${t.tagName.toLowerCase()}${t.id ? '#' + t.id : ''}${t.className && typeof t.className === 'string' ? '.' + t.className.split(' ')[0] : ''} "${(t.textContent || t.getAttribute('aria-label') || '').trim().slice(0, 30)}" ${Math.round(r.width)}x${Math.round(r.height)}`);
  }
  return out;
}"""
CONTRAST = """(scope) => {
  const parse = (c) => { const m = c.match(/rgba?\\(([^)]+)\\)/); if (!m) return null; const p = m[1].split(/[\\s,\\/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const bgOf = (el) => {
    const layers = [];
    for (let n = el; n; n = n.parentElement) { const c = parse(getComputedStyle(n).backgroundColor); if (c && c[3] > 0) { layers.push(c); if (c[3] >= 1) break; } }
    let base = parse(getComputedStyle(document.body).backgroundColor) || [255, 255, 255, 1];
    if (layers.length && layers[layers.length - 1][3] >= 1) base = layers.pop();
    for (const c of layers.reverse()) base = [0, 1, 2].map((i) => c[i] * c[3] + base[i] * (1 - c[3])).concat(1);
    return base;
  };
  const out = [];
  for (const root of document.querySelectorAll(scope)) {
    for (const el of [root, ...root.querySelectorAll('*')]) {
      if (![...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
      if (el.closest('[hidden], .sr, option, svg') || el.disabled || el.closest(':disabled')) continue;
      const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
      if (!r.width || !r.height || cs.visibility === 'hidden' || +cs.opacity === 0) continue;
      const fg = parse(cs.color), bg = bgOf(el);
      if (!fg) continue;
      const a = lum(fg), b = lum(bg), ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
      if (ratio < 4.5) out.push(`${el.tagName.toLowerCase()}.${(el.className || '').toString().split(' ')[0]} "${el.textContent.trim().slice(0, 24)}" ${ratio.toFixed(2)}:1`);
    }
  }
  return out;
}"""


def goto(page, url, until="load"):
    """Navigate, once more with a longer wait if the machine is busy; None if the page never loaded."""
    err = None
    for timeout in (30000, 90000):
        try:
            return page.goto(url, wait_until=until, timeout=timeout)
        except Exception as ex:
            err = ex
    bad(f"{urllib.parse.urlparse(url).path}: didn't load ({str(err).splitlines()[0][:80]})")
    return None


def page_worker(base, jobs):
    """One Playwright instance per thread (its API isn't thread-safe); jobs are (path, width)."""
    local = urllib.parse.urlparse(base).netloc
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        pages, errors, offsite = {}, [], []
        for width in (375, 1280):
            ctx = browser.new_context(viewport={"width": width, "height": 812 if width < 600 else 900})
            ctx.add_init_script(INIT)
            pg = ctx.new_page()
            pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            pg.on("pageerror", lambda ex: errors.append(str(ex)))
            pg.on("request", lambda r: offsite.append(r.url) if urllib.parse.urlparse(r.url).scheme in ("http", "https")
                  and urllib.parse.urlparse(r.url).netloc != local else None)
            pages[width] = pg
        for path, width in jobs:
            page = pages[width]
            errors.clear(); offsite.clear()
            resp = goto(page, base + path, "networkidle" if "/explore/" in path else "load")
            if not resp:
                continue
            where = f"{path} @{width}"
            if resp.status != 200:
                bad(f"{where}: HTTP {resp.status}")
                continue
            if "/explore/" in path:
                try:
                    page.wait_for_function("() => document.querySelectorAll('.ex-row').length > 0", timeout=60000)
                except Exception:
                    bad(f"{where}: the web app's list never loaded")
            over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            if over > 1:
                bad(f"{where}: scrolls sideways by {over}px")
            if page.locator("h1").count() != 1:
                bad(f"{where}: {page.locator('h1').count()} <h1>")
            for v in page.evaluate("window.__csp || []"):
                bad(f"{where}: CSP violation: {v}")
            if width == 375:
                for t in page.evaluate(TAP, None):
                    bad(f"{where}: tap target under 44px: {t}")
            imgs = page.evaluate("[...document.images].filter(i => i.complete && i.naturalWidth === 0).map(i => i.currentSrc || i.src)")
            for u in imgs:
                bad(f"{where}: image didn't load {u}")
            for u in offsite:
                bad(f"{where}: request to another site: {u}")
            for x in errors:
                bad(f"{where}: console error: {x}")
            if SHOTS and path in (BASE + "/", f"{BASE}/{GUIDE_FILE['lobster']}", f"{BASE}/cities/lewiston.html"):
                name = {BASE + "/": "home", f"{BASE}/{GUIDE_FILE['lobster']}": "lobster", f"{BASE}/cities/lewiston.html": "lewiston"}[path]
                page.screenshot(path=os.path.join(SHOTS, f"site-{name}-{width}.png"), full_page=(name != "home"))
        browser.close()


def browser_pages(base, locs, workers):
    jobs = []
    places = sorted(urllib.parse.urlparse(u).path for u in locs if "/places/" in u)
    sample = set(places[::10])
    for loc in locs:
        path = urllib.parse.urlparse(loc).path
        for width in (375, 1280):
            if "/places/" in path and width == 1280 and path not in sample:
                continue    # place pages share one template: all of them at 375 px, every tenth at 1280 px
            jobs.append((path, width))
    jobs.append((BASE + "/404.html", 375))
    chunks = [jobs[i::workers] for i in range(workers)]
    threads = [threading.Thread(target=page_worker, args=(base, c)) for c in chunks]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return len(jobs)


# ---------------------------------------------------------------- the web app
def rows(page):
    return page.evaluate("""[...document.querySelectorAll('#ex-list .ex-row')].map(b => ({
        i: +b.dataset.i, name: b.querySelector('.ex-name')?.textContent || '', town: b.querySelector('.ex-town')?.textContent || '',
        metric: b.querySelector('.ex-metric b')?.textContent || ''}))""")


def all_rows(page):
    while page.locator("#ex-more").is_visible():
        page.locator("#ex-more").click()
        page.wait_for_timeout(100)
    return rows(page)


def search(page, text):
    """Types into the search box and waits for the list to re-render (the input is debounced)."""
    before = page.locator("#ex-count").text_content()
    page.locator("#ex-q").fill(text)
    try:
        page.wait_for_function("b => document.querySelector('#ex-count').textContent !== b", arg=before, timeout=3000)
    except Exception:
        pass
    page.wait_for_timeout(250)


def close_panel(page):
    if page.locator("#ex-close").count() and page.locator("#ex-close").is_visible():
        page.locator("#ex-close").click()
        page.wait_for_timeout(200)


def pick_guide(page, g):
    page.locator(f'.ex-guides button[data-g="{g}"]').click()
    page.wait_for_timeout(250)


def webapp_checks(browser, base, width, data):
    C = data.C
    where = f"explore @{width}"
    lobster = data.guide("lobster")
    ctx = browser.new_context(viewport={"width": width, "height": 812 if width < 600 else 900}, geolocation=PORTLAND, permissions=["geolocation"])
    ctx.add_init_script(INIT)
    page = ctx.new_page()
    errors, requests = [], []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda ex: errors.append(str(ex)))
    page.on("request", lambda r: requests.append(r.url))

    def fresh(hash_):
        page.goto("about:blank")
        goto(page, base + BASE + "/explore/#" + hash_, "networkidle")
        try:
            page.wait_for_function("document.querySelector('#ex-app').getAttribute('aria-busy') === 'false'", timeout=30000)
        except Exception:
            bad(f"{where}: #{hash_} never finished loading")
        page.wait_for_timeout(300)

    # 0. the data arrives a second late, as on a phone: nothing moves when it does
    slow = lambda route: (time.sleep(1), route.continue_())
    page.route("**/data/core.json", slow)
    goto(page, base + BASE + "/explore/", "networkidle")
    try:
        page.wait_for_function("document.querySelectorAll('#ex-list .ex-row').length > 0", timeout=30000)
    except Exception:
        bad(f"{where}: the list never loaded")
        return
    finally:
        page.unroute("**/data/core.json", slow)
    page.wait_for_timeout(600)
    cls = page.evaluate("window.__cls || 0")
    if cls > 0.05:
        bad(f"{where}: layout shift while the list loaded (CLS {cls:.3f})")
    # detail.json (phones, sites, notes, inspections) comes after the list's own data, never ahead of it
    order = [u.rsplit("/", 1)[-1] for u in requests if u.endswith(("/data/core.json", "/data/detail.json"))]
    if "detail.json" in order and "core.json" in order and order.index("detail.json") < order.index("core.json"):
        bad(f"{where}: detail.json was requested before core.json")
    if width == 375:
        for t in page.evaluate(TAP, None):
            bad(f"{where}: tap target under 44px: {t}")

    # 1. the lobster guide lists exactly the hand-checked lobster places (a place merely named "... Lobster Pound" isn't enough)
    page.locator("#ex-q").fill("")
    pick_guide(page, "lobster")
    shown = {r["i"] for r in all_rows(page)}
    if shown != lobster:
        bad(f"{where}: lobster guide shows {len(shown)} places, expected the {len(lobster)} hand-checked ones; "
            f"extra {sorted(C['n'][i] for i in shown - lobster)[:5]}, missing {sorted(C['n'][i] for i in lobster - shown)[:5]}")
    # each guide's subtitle and count: no overclaims in what the script writes
    for g in ("lobster", "clams", "sandwiches", "sweets", "franco", "diners", "oysters", "dairy", "icons", "oldest", "all", "saved"):
        pick_guide(page, g)
        t = page.locator("#ex-controls, .ex-controls").first.inner_text()
        for rx in OVERCLAIMS:
            mm = re.search(rx, t, re.I)
            if mm:
                bad(f"{where}: guide {g}: overclaim {mm.group(0)!r} in {t[:100]!r}")
        if g in GUIDE_KINDS:
            want = data.guide(g)
            n = int(re.match(r"([\d,]+)", page.locator("#ex-count").text_content()).group(1).replace(",", ""))
            if n != len(want):
                bad(f"{where}: guide {g} counts {n}, expected the {len(want)} hand-checked places")

    # 2. the map draws: the land filled, and a buoy-yellow dot for each hand-checked lobster place
    pick_guide(page, "lobster")
    page.locator('.ex-view button[data-v="map"]').click()
    page.wait_for_timeout(900)
    px = page.evaluate("""() => {
        const cv = document.querySelector('#ex-map'); if (!cv || !cv.width) return null;
        const d = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data;
        let land = 0, buoy = 0;
        for (let i = 0; i < d.length; i += 4) {
          const [r, g, b, a] = [d[i], d[i + 1], d[i + 2], d[i + 3]];
          if (a < 200) continue;
          if (Math.abs(r - 241) < 6 && Math.abs(g - 232) < 6 && Math.abs(b - 214) < 6) land++;
          else if (Math.abs(r - 242) < 20 && Math.abs(g - 183) < 24 && b < 60) buoy++;
        }
        return { total: cv.width * cv.height, land, buoy, hint: document.querySelector('#ex-maphint').textContent };
    }""")
    n_pts = sum(1 for i in lobster if C["la"][i] is not None)
    if not px:
        bad(f"{where}: the map canvas has no size")
    else:
        if px["land"] < 0.05 * px["total"]:
            bad(f"{where}: the map didn't draw Maine ({px['land']} of {px['total']} px)")
        if px["buoy"] < 60:
            bad(f"{where}: the map drew no hand-checked dots ({px['buoy']} px)")
        if not px["hint"].startswith(f"{n_pts} places"):
            bad(f"{where}: map hint says {px['hint']!r}, expected {n_pts} places")
    if SHOTS and width == 375:
        page.evaluate("document.querySelector('.ex-controls').scrollIntoView()")
        page.wait_for_timeout(300)
        page.screenshot(path=os.path.join(SHOTS, "site-explore-map-375.png"))
    page.locator('.ex-view button[data-v="list"]').click()
    page.wait_for_timeout(300)

    # 3. "amatos" finds Amato's in Portland (a trailing "s" also matches its stem), and opening it shows that place
    amato = [i for i in range(data.n) if C["n"][i] == "Amato's" and data.town(i) == "Portland" and C["hc"][i] == 1]
    pick_guide(page, "all")
    search(page, "amatos")
    hits = [r for r in rows(page) if r["name"] == "Amato's" and "Portland" in r["town"]]
    if not hits:
        bad(f"{where}: search 'amatos' didn't find Amato's in Portland ({[r['name'] for r in rows(page)][:5]})")
    else:
        requests.clear()
        page.locator(f'#ex-list .ex-row[data-i="{hits[0]["i"]}"]').click()
        page.wait_for_timeout(600)
        panel = page.locator("#ex-panel")
        if not panel.is_visible() or panel.locator("#ex-pname").text_content() != "Amato's" \
                or "PORTLAND" not in (panel.locator(".ex-kicker").text_content() or "") or not panel.locator("a", has_text="Directions").count():
            bad(f"{where}: opening Amato's from the search didn't show its details")
        else:
            if page.evaluate("document.activeElement?.id") != "ex-close":
                bad(f"{where}: focus didn't move to the panel's Close button")
            if width == 375:
                for t in page.evaluate(TAP, "#ex-panel"):
                    bad(f"{where} (panel open): tap target under 44px: {t}")
            # 4. Save, then the Saved guide lists it, also after a reload (localStorage)
            panel.locator("#ex-save").click()
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            if "/explore/" not in page.url or not page.locator("#ex-panel").count():
                bad(f"{where}: closing a place left the web app ({page.url})")
                fresh("g=all&q=amatos")
            else:
                st = page.evaluate("({ hidden: document.querySelector('#ex-panel').hidden, row: document.activeElement?.classList.contains('ex-row') })")
                if not st["hidden"] or not st["row"]:
                    bad(f"{where}: Escape didn't close the panel and put focus back on the row: {st}")
            pick_guide(page, "saved")
            page.locator("#ex-q").fill("")
            page.wait_for_timeout(300)
            if hits[0]["i"] not in {r["i"] for r in rows(page)}:
                bad(f"{where}: a saved place isn't in the Saved guide")
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(600)
            if hits[0]["i"] not in {r["i"] for r in rows(page)}:
                bad(f"{where}: a saved place was gone after a reload")

    # 5. a shared link (#p=<id>) opens the place on a cold load
    if amato:
        fresh(f"g=all&p={C['id'][amato[0]]}")
        page.wait_for_timeout(500)
        if not page.locator("#ex-panel").is_visible() or page.locator("#ex-pname").text_content() != "Amato's":
            bad(f"{where}: a #p= link didn't open the place")
        close_panel(page)
    else:
        bad(f"{where}: no hand-checked Amato's in Portland in the data")

    # 6. Lewiston: a place with a posted result shows it as official, with Passed or Failed, its date and the city's report; a list
    # never shows a result
    lw = sorted([i for i in range(data.n) if data.rest(i) and (data.detail[i] or {}).get("lw")], key=lambda i: C["n"][i].lower())
    fails = [i for i in lw if data.detail[i]["lw"]["r"] == "Fail"]
    picks = ([lw[0]] if lw else []) + fails[:1]
    if not lw:
        bad(f"{where}: no Lewiston inspection results in the data")
    for i in picks:
        r = data.detail[i]["lw"]
        fresh(f"g=all&p={C['id'][i]}")
        try:
            page.wait_for_function("document.querySelector('#ex-panel').dataset.ready === '1'", timeout=8000)
        except Exception:
            pass
        sec = page.locator("#ex-panel .ex-lw")
        text = sec.inner_text() if sec.count() else ""
        res = "Passed" if r["r"] == "Pass" else "Failed"
        need = ["official", f"City of Lewiston inspection: {res}", nice_date(r["d"])]
        if not text or any(w.lower() not in text.lower() for w in need):
            bad(f"{where}: {C['n'][i]} (Lewiston) didn't show its official result with the date; wanted {need}, got {text[:160]!r}")
        if r.get("u") and not page.locator(f'#ex-panel a[href="{r["u"]}"]').count():
            bad(f"{where}: {C['n'][i]} doesn't link the city's report")
        close_panel(page)
    fresh("g=all&town=Lewiston")
    lt = page.locator("#ex-list").inner_text()
    if re.search(r"\b(Passed|Failed|inspection)\b", lt, re.I):
        bad(f"{where}: the Lewiston list shows inspection results")

    # 7. an emoji (nothing searchable) lists nothing rather than everything
    fresh("g=all")
    search(page, "🦞")
    if page.locator("#ex-list .ex-row").count():
        bad(f"{where}: an emoji search listed places")
    page.locator("#ex-q").fill("")

    # 8. Near me sorts by distance from the browser's location (the context is at Monument Square, Portland)
    pick_guide(page, "near")
    try:
        page.wait_for_function("document.querySelectorAll('#ex-list .ex-row').length > 0", timeout=8000)
    except Exception:
        pass
    rs = rows(page)
    dists = []
    for r in rs[:40]:
        m = re.match(r"([\d.]+) mi", r["metric"])
        dists.append(float(m.group(1)) if m else None)
    if not rs or None in dists:
        bad(f"{where}: Near me listed {len(rs)} places without distances")
    elif dists != sorted(dists) or dists[0] > 1:
        bad(f"{where}: Near me isn't sorted by distance from Monument Square ({dists[:6]})")

    # 8b. a "Near me" link opened cold (shared, or the guide remembered from last time) sorts by distance at once when the site
    # already has location permission (this context grants it), with no tap needed and no prompt
    fresh("g=near")
    try:
        page.wait_for_function("document.querySelectorAll('#ex-list .ex-row .ex-metric b').length > 0", timeout=8000)
    except Exception:
        pass
    m0 = [r["metric"] for r in rows(page)[:5]]
    if not m0 or not all(re.match(r"[\d.]+ mi", x) for x in m0):
        bad(f"{where}: a cold #g=near link with location allowed doesn't sort by distance ({page.locator('#ex-list').inner_text()[:80]!r})")

    # 9. Back closes an open place (opening one adds a history entry) and keeps the search; the panel is a modal dialog on a
    # phone, with the page behind it inert, and a side column on a desktop that covers none of the controls
    fresh("g=all&q=amatos")
    n0 = page.evaluate("history.length")
    page.locator("#ex-list .ex-row").first.click()
    page.wait_for_timeout(400)
    if page.evaluate("history.length") != n0 + 1 or "p=" not in page.evaluate("location.hash"):
        bad(f"{where}: opening a place didn't add a history entry")
    role, modal = page.get_attribute("#ex-panel", "role"), page.get_attribute("#ex-panel", "aria-modal")
    if width <= 600:
        if role != "dialog" or modal != "true" or not page.evaluate("document.getElementById('ex-app').inert && document.querySelector('header.site').inert"):
            bad(f"{where}: the open panel isn't a modal dialog with the page behind it inert (role={role}, aria-modal={modal})")
    else:
        if role == "dialog" or page.evaluate("document.querySelectorAll('[inert]').length"):
            bad(f"{where}: the side panel is modal on a wide screen")
        covered = page.evaluate("""[...document.querySelectorAll('.ex-guides button, #ex-q, #ex-locate, .ex-row2 select, .ex-row2 input, .ex-view button, header.site nav a')]
            .filter(el => { const r = el.getBoundingClientRect(); if (!r.width || r.bottom > innerHeight) return false;
              return !el.contains(document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2)); })
            .map(el => el.textContent.trim() || el.id)""")
        if covered:
            bad(f"{where}: with a place open, the panel covers {covered[:6]}")
    page.go_back()
    page.wait_for_timeout(600)
    if page.locator("#ex-panel").is_visible() or "/explore/" not in page.url or "p=" in page.url or "q=amatos" not in page.url:
        bad(f"{where}: Back didn't just close the place ({page.url})")
    if page.evaluate("document.querySelectorAll('[inert]').length"):
        bad(f"{where}: part of the page stayed inert after the panel closed")

    # 10. the search rules the app shares: stop words go once a town, village or tag is found, "near me" is dropped, the longest
    # town or village wins, route numbers read alike ("me 3", "route 3"), and the Maine tag phrases each find places
    fresh("g=all")

    def result(q):
        search(page, q)
        return page.locator("#ex-count").text_content(), [r["i"] for r in rows(page)][:40]
    for a, b in (("lobster in bar harbor", "lobster bar harbor"), ("near cape neddick", "cape neddick"), ("pizza near me", "pizza"),
                 ("potato donut", "potato doughnut"), ("whoopie pies", "whoopie pie")):
        ra, rb = result(a), result(b)
        if ra != rb or not ra[1]:
            bad(f"{where}: search {a!r} ({ra[0]}) doesn't give the same places as {b!r} ({rb[0]})")
    # a route and its number: "route 1", "us 1", "rte 1", "me 3" find each place whose address is on that route (US Route 1, ME-3,
    # Rte 1...) and nothing else but a place whose name says the same words
    for q, num in (("route 1", "1"), ("us 1", "1"), ("rte 1", "1"), ("me 3", "3"), ("route 3", "3")):
        on = {i for i in range(data.n) if data.rest(i) and f" rt {num} " in " " + norm_addr(C["a"][i] or "") + " "}
        search(page, q)
        got = {r["i"] for r in all_rows(page)}
        extra = [C["n"][i] for i in got - on if f" {q} " not in " " + normalize(C["n"][i]) + " "]
        if not on <= got or extra:
            bad(f"{where}: search {q!r} lists {len(got)} places; missing {sorted(C['n'][i] for i in on - got)[:3]} on Rt {num}, extra {extra[:3]}")
    search(page, "cape neddick")
    towns = {r["town"].split(" · ")[0] for r in rows(page)}
    if not towns or any(not t.startswith("Cape Neddick") for t in towns):
        bad(f"{where}: search 'cape neddick' isn't the village Cape Neddick ({sorted(towns)[:4]})")
    for q in ("lobster roll", "lobster pound", "clam shack", "fried clams", "red snapper", "hot dog", "italian sandwich", "italians", "whoopie pie",
              "potato donut", "oyster bar", "oysters", "dairy bar", "diner"):
        search(page, q)
        if not page.locator("#ex-list .ex-row").count():
            bad(f"{where}: search {q!r} found nothing")
    page.locator("#ex-q").fill("")

    # 11. a crafted hash (#g=constructor and friends) or a junk stored guide is just an unknown guide
    errors.clear()
    fresh("g=constructor&sort=toString")
    if not page.locator("#ex-list .ex-row").count():
        bad(f"{where}: #g=constructor shows no list")
    fresh("g=__proto__&q=constructor&kind=hasOwnProperty")
    page.evaluate("localStorage.setItem('me-guide', JSON.stringify('__proto__'))")
    fresh("")
    if not page.locator("#ex-list .ex-row").count():
        bad(f"{where}: a junk stored guide broke the web app")
    page.evaluate("location.hash = 'g=__proto__&p=constructor'")
    page.wait_for_timeout(300)
    for x in errors:
        bad(f"{where}: crafted hash: page error: {x}")
    errors.clear()

    # 12. the skip link moves focus without resetting the search or the filters
    fresh("g=all&q=amatos&town=Portland")
    page.locator("a.skip").focus()
    page.keyboard.press("Enter")
    page.wait_for_timeout(400)
    if page.locator("#ex-q").input_value() != "amatos" or "in Portland" not in page.locator("#ex-count").text_content():
        bad(f"{where}: the skip link reset the web app")

    # 13. rank numbers only on a ranking sort (iconic, oldest), with "Rank" for screen readers; the Icons explainer; no points shown
    fresh("g=icons")
    if not page.locator(".ex-rank").count() or not page.evaluate("document.querySelector('.ex-rank .sr')?.textContent === 'Rank '"):
        bad(f"{where}: the Icons ranking shows no rank numbers")
    if "not a rating" not in page.locator("#ex-sub").text_content():
        bad(f"{where}: the Icons guide doesn't say its order isn't a rating")
    if page.evaluate("[...document.querySelectorAll('.ex-metric small')].some(s => /pts|points/.test(s.textContent))"):
        bad(f"{where}: the Icons list shows iconic points")
    fresh("g=all")
    if page.locator(".ex-rank").count():
        bad(f"{where}: rank numbers on an A to Z list")

    # 14. "High-confidence only" keeps hand-checked places, and a hand-checked place is never called "Listing only"
    fresh("g=lobster&conf=1")
    if len(all_rows(page)) != len(lobster):
        bad(f"{where}: High-confidence only drops hand-checked lobster places ({len(rows(page))} of {len(lobster)})")
    lone = [i for i in range(data.n) if C["hc"][i] == 1 and C["t"][i] == 0 and data.rest(i)]
    if lone:
        fresh(f"g=all&p={C['id'][lone[0]]}")
        text = page.locator("#ex-panel").inner_text() if page.locator("#ex-panel").is_visible() else ""
        if "Hand-checked" not in text or "Listing only" in text:
            bad(f"{where}: {C['n'][lone[0]]} (hand-checked, a single map listing) isn't labeled Hand-checked")

    # 15. "Hide chains" never hides a hand-checked original (hc, no br), only branches; from outside Maine the classics stay in
    # Featured order rather than Nearest
    fresh("g=dairy&chains=1")
    dairy = data.guide("dairy")
    want = {i for i in dairy if not ((C["ch"][i] or 1) >= 5 and not (C["hc"][i] == 1 and not C["br"][i]))}
    got = {r["i"] for r in all_rows(page)}
    if got != want:
        bad(f"{where}: Hide chains on the dairy guide shows {len(got)} places, expected {len(want)} (originals kept)")
    page.context.set_geolocation({"latitude": 37.7749, "longitude": -122.4194})
    fresh("g=lobster")
    page.locator("#ex-locate").click()
    try:
        page.wait_for_function("document.querySelector('#ex-locmsg').textContent.includes('outside Maine')", timeout=8000)
    except Exception:
        pass
    if "Featured first" not in page.locator("#ex-count").text_content():
        bad(f"{where}: from outside Maine the lobster guide isn't in Featured order ({page.locator('#ex-count').text_content()})")
    page.context.set_geolocation(PORTLAND)

    # 16. the map: a slow drag opens nothing, and a tap on places stacked on one spot offers a chooser
    pos_js = """([la, lo]) => {
        const LAT0 = 45.2, KX = Math.cos(LAT0 * Math.PI / 180), proj = (lo, la) => [(lo + 69.0) * KX, -(la - LAT0)];
        const ME = { s: 42.97, n: 47.47, w: -71.09, e: -66.93 }, wrap = document.querySelector('#ex-mapwrap');
        const w = wrap.clientWidth, h = wrap.clientHeight, [x0, y0] = proj(ME.w, ME.n), [x1, y1] = proj(ME.e, ME.s);
        const k = Math.min(w / (x1 - x0), h / (y1 - y0)) * 0.94, cam = { k, x: (w - (x1 - x0) * k) / 2 - x0 * k, y: (h - (y1 - y0) * k) / 2 - y0 * k };
        const [px, py] = proj(lo, la), r = document.querySelector('#ex-map').getBoundingClientRect();
        return [r.left + px * cam.k + cam.x, r.top + py * cam.k + cam.y]; }"""
    fresh("g=lobster&view=map")
    page.evaluate("document.querySelector('#ex-map').scrollIntoView({block: 'center'})")
    page.wait_for_timeout(300)
    i = min(lobster)
    x, y = page.evaluate(pos_js, [C["la"][i], C["lo"][i]])
    page.mouse.move(x, y)
    page.mouse.down()
    for k in range(1, 13):
        page.mouse.move(x + k, y)
        page.wait_for_timeout(25)
    page.mouse.up()
    page.wait_for_timeout(300)
    if page.locator("#ex-panel").is_visible():
        bad(f"{where}: a slow drag on the map opened a place")
    stacks = defaultdict(list)
    for j in range(data.n):
        if data.rest(j) and C["la"][j] is not None and C["a"][j]:
            stacks[(C["la"][j], C["lo"][j], C["a"][j], C["c"][j])].append(j)
    by_town = defaultdict(list)
    for j in range(data.n):
        if data.rest(j) and C["la"][j] is not None:
            by_town[C["c"][j]].append(j)

    def alone(g):
        """No other place the town filter and an address search would also list within ~1 km, so the tap can only hit this stack."""
        la, lo, num = C["la"][g[0]], C["lo"][g[0]], C["a"][g[0]].split()[:1]
        return all(abs(C["la"][j] - la) + abs(C["lo"][j] - lo) > 0.01 for j in by_town[C["c"][g[0]]]
                   if (C["la"][j], C["lo"][j]) != (la, lo) and (C["a"][j] or "").split()[:1] == num)
    group = next((g for g in stacks.values() if 2 <= len(g) <= 4 and alone(g)), None)
    if group:
        j = group[0]
        fresh("view=map&" + urllib.parse.urlencode({"g": "all", "town": data.town(j), "q": C["a"][j]}))
        page.evaluate("document.querySelector('#ex-map').scrollIntoView({block: 'center'})")
        page.wait_for_timeout(300)
        x, y = page.evaluate(pos_js, [C["la"][j], C["lo"][j]])
        page.mouse.click(x, y)
        page.wait_for_timeout(400)
        names = page.evaluate("[...document.querySelectorAll('#ex-chooser button')].map(b => b.textContent)")
        if not page.locator("#ex-chooser").is_visible() or not {C["n"][g] for g in group} <= set(names):
            bad(f"{where}: a tap on {len(group)} places at one spot ({C['a'][j]}) didn't list them ({names})")
        else:
            page.locator("#ex-chooser button").first.click()
            page.wait_for_timeout(400)
            if not page.locator("#ex-panel").is_visible() or page.locator("#ex-pname").text_content() != names[0]:
                bad(f"{where}: picking a place from the map's chooser didn't open it")
    else:
        print(f"  (no stacked places to test the map's chooser at {width} px)")
    for x in errors:
        bad(f"{where}: console error: {x}")
    for v in page.evaluate("window.__csp || []"):
        bad(f"{where}: CSP violation: {v}")
    ctx.close()


def webapp_load_checks(browser, base):
    # a failed core.json: the error shows in #ex-loading, and retry works
    ctx = browser.new_context(viewport={"width": 375, "height": 812})
    page = ctx.new_page()
    page.route("**/data/core.json", lambda r: r.abort())
    goto(page, base + BASE + "/explore/", "networkidle")
    page.wait_for_timeout(500)
    msg = page.locator("#ex-loading").text_content() or ""
    if "couldn" not in msg or not page.locator("#ex-loading #ex-retry").count():
        bad(f"explore: a failed core.json didn't show an error with a retry ({msg!r})")
    else:
        page.unroute("**/data/core.json")
        page.locator("#ex-retry").click()
        try:
            page.wait_for_function("() => document.querySelectorAll('.ex-row').length > 0", timeout=60000)
        except Exception:
            bad("explore: retry after a failed core.json didn't load the list")
    ctx.close()
    # CLS at other window sizes
    for vw, vh in ((1280, 720), (1440, 900), (768, 1024)):
        ctx = browser.new_context(viewport={"width": vw, "height": vh})
        ctx.add_init_script(INIT)
        page = ctx.new_page()
        page.route("**/data/core.json", lambda r: (time.sleep(0.6), r.continue_()))
        goto(page, base + BASE + "/explore/", "networkidle")
        page.wait_for_function("() => document.querySelectorAll('.ex-row').length > 0", timeout=60000)
        page.wait_for_timeout(800)
        if page.evaluate("window.__cls") >= 0.05:
            bad(f"explore @{vw}x{vh}: CLS {page.evaluate('window.__cls'):.3f}")
        ctx.close()


def webapp_robustness_checks(browser, base):
    """Bugs found in other state web apps (the shared explore.js ancestry), checked here: control fonts that resolve (no invalid
    font shorthand) and fields of 16px or more on a phone, so iOS doesn't zoom; junk in our localStorage keys (the github.io origin is
    shared) never stops the app; no "Nearest" label before there's a location; and Near me asks for a fresh fix on every tap."""
    ex = base + BASE + "/explore/"

    def ready(page, what):
        try:
            page.wait_for_function("document.querySelectorAll('#ex-list .ex-row, #ex-list .ex-empty:not(#ex-loading)').length > 0 && "
                                   "document.querySelector('#ex-app').getAttribute('aria-busy') === 'false'", timeout=15000)
            return True
        except Exception:
            bad(f"explore: {what}: the web app never finished loading")
            return False
    ctx = browser.new_context(viewport={"width": 375, "height": 812})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda ex_: errors.append(str(ex_)))
    goto(page, ex + "#g=lobster", "networkidle")
    if ready(page, "fonts"):
        body = page.evaluate("getComputedStyle(document.body).fontFamily")
        for sel, minpx in (("#ex-q", 16), ("#ex-sort", 16), ("#ex-town", 16), ("#ex-cuisine", 16), (".ex-guides button", 14), ("#ex-locate", 14),
                           (".ex-view button", 14), (".ex-zoom button", 14)):
            fs, ff = page.evaluate(f"(() => {{ const c = getComputedStyle(document.querySelector({json.dumps(sel)})); return [parseFloat(c.fontSize), c.fontFamily]; }})()")
            if fs < minpx:
                bad(f"explore @375: {sel} is {fs}px (want {minpx}px or more; iOS zooms into fields under 16px)")
            if ff.split(",")[0] != body.split(",")[0]:
                bad(f"explore @375: {sel} falls back to {ff.split(',')[0]} (an invalid font shorthand?)")
    # junk values in the keys the app reads
    for key, val in (("saved", '{"x":1}'), ("saved", "5"), ("saved", "not json"), ("saved", "[null, 5, {}]"), ("guide", '{"x":1}'), ("guide", "5")):
        errors.clear()
        page.evaluate(f"localStorage.clear(); localStorage.setItem('me-{key}', {json.dumps(val)})")
        page.goto("about:blank")
        goto(page, ex + ("#g=saved" if key == "saved" else ""), "networkidle")
        if ready(page, f"me-{key} = {val}") and errors:
            bad(f"explore: localStorage me-{key} = {val} throws {errors[0][:80]}")
    page.evaluate("localStorage.clear()")
    # no location: a Nearest sort isn't claimed, and the list is in its other order
    page.goto("about:blank")
    goto(page, ex + "#g=all&sort=nearest", "networkidle")
    if ready(page, "sort=nearest without a location"):
        c = page.locator("#ex-count").text_content()
        if "· Nearest" in c:
            bad(f"explore: with no location the count says {c!r}")
    ctx.close()
    # Near me: a fresh fix on every tap (Portland, then Bangor)
    ctx = browser.new_context(viewport={"width": 1280, "height": 900}, geolocation=PORTLAND, permissions=["geolocation"])
    page = ctx.new_page()
    goto(page, ex + "#g=lobster", "networkidle")
    if ready(page, "Near me"):
        page.locator('.ex-guides button[data-g="near"]').click()
        page.wait_for_timeout(1200)
        first = page.evaluate("document.querySelector('#ex-list .ex-row .ex-town')?.textContent || ''")
        ctx.set_geolocation({"latitude": 44.8016, "longitude": -68.7712})   # West Market Square, Bangor
        page.locator('.ex-guides button[data-g="lobster"]').click()
        page.wait_for_timeout(300)
        page.locator('.ex-guides button[data-g="near"]').click()
        page.wait_for_timeout(1200)
        second = page.evaluate("document.querySelector('#ex-list .ex-row .ex-town')?.textContent || ''")
        if "Bangor" not in second:
            bad(f"explore: Near me reused an old location (first {first!r}, after moving to Bangor {second!r})")
    ctx.close()


# the search box's placeholder, measured as text in the box it shows in: the box's width, padding, border and font are pinned, and it's
# made a plain text field holding the placeholder (a search field holding text adds a clear button the placeholder never has)
PLACEHOLDER_FIT = """() => {
  const el = document.querySelector('#ex-q'), c = getComputedStyle(el);
  const keep = ['width', 'paddingLeft', 'paddingRight', 'borderLeftWidth', 'borderRightWidth', 'boxSizing', 'fontSize', 'fontFamily', 'fontWeight', 'letterSpacing'];
  const pinned = Object.fromEntries(keep.map((k) => [k, c[k]]));
  const cv = document.createElement('canvas').getContext('2d'); cv.font = c.font;
  const out = { text: el.placeholder, fontSize: parseFloat(c.fontSize), textWidth: Math.ceil(cv.measureText(el.placeholder).width),
                content: el.clientWidth - parseFloat(c.paddingLeft) - parseFloat(c.paddingRight) };
  const type = el.type, value = el.value;
  for (const k of keep) el.style[k] = pinned[k];
  el.type = 'text'; el.value = el.placeholder;
  out.scrollWidth = el.scrollWidth; out.clientWidth = el.clientWidth;
  el.value = value; el.type = type;
  for (const k of keep) el.style[k] = '';
  return out;
}"""
PHONE_WIDTHS = (320, 360, 375, 390, 402, 414, 430, 440)   # iPhone SE 1st gen to 17 Pro Max, and a common Android width


def webapp_placeholder_checks(browser, base):
    """The search box's placeholder isn't cut off on a phone (California's read "…zip or d" at 375 px; here the box shared its row with
    "Use my location" from 401 px up, which cut "dish" at 402 px), and its text stays 16px or more: its scrollWidth holding the
    placeholder is within its clientWidth, with 8px to spare for other browsers' font metrics."""
    for w in PHONE_WIDTHS:
        ctx = browser.new_context(viewport={"width": w, "height": 812})
        page = ctx.new_page()
        goto(page, base + BASE + "/explore/#g=lobster", "networkidle")
        try:
            page.wait_for_function("document.querySelector('#ex-app').getAttribute('aria-busy') === 'false'", timeout=30000)
        except Exception:
            bad(f"explore @{w}: never finished loading (placeholder check)")
            ctx.close()
            continue
        m = page.evaluate(PLACEHOLDER_FIT)
        if not m["text"]:
            bad(f"explore @{w}: the search box has no placeholder")
        if m["fontSize"] < 16:
            bad(f"explore @{w}: the search box's text is {m['fontSize']}px (16px or more, or iOS zooms in)")
        if m["scrollWidth"] > m["clientWidth"] or m["content"] - m["textWidth"] < 8:
            bad(f"explore @{w}: the search placeholder {m['text']!r} is cut off or nearly: it needs {m['textWidth']}px of a "
                f"{m['content']:.0f}px box (scrollWidth {m['scrollWidth']} vs clientWidth {m['clientWidth']})")
        ctx.close()


# a famous place that isn't in the guide the web app opens on (lobster): Duckfat, Portland's Belgian-fries shop
FAMOUS_ELSEWHERE = ("duckfat", "Duckfat", "Portland")


def webapp_widen_checks(browser, base, width, data):
    """A search inside a guide that finds nothing there, or only a few places, offers "Search all restaurants (N matches)"; one click
    switches to the Statewide list with the same words, which lists N places and the one searched for (ME-V08: a first-time visitor
    searching a famous place from the opening guide used to get "No places match")."""
    C, where = data.C, f"explore @{width}"
    q, name, town = FAMOUS_ELSEWHERE
    lobster = data.guide("lobster")
    target = [i for i in range(data.n) if C["n"][i] == name and data.town(i) == town and data.rest(i)]
    if not target or set(target) & lobster:
        bad(f"{where}: the search-all check needs {name} ({town}) in the data and outside the lobster guide; pick another famous place")
        return
    ctx = browser.new_context(viewport={"width": width, "height": 812 if width < 600 else 900})
    ctx.add_init_script(INIT)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda ex: errors.append(str(ex)))
    BTN = re.compile(r"^Search all restaurants \(([\d,]+) match(es)?\)$")

    def load(hash_):
        page.goto("about:blank")
        goto(page, base + BASE + "/explore/#" + hash_, "networkidle")
        page.wait_for_function("document.querySelector('#ex-app').getAttribute('aria-busy') === 'false'", timeout=30000)
        page.wait_for_timeout(300)

    def widen_button():
        b = page.get_by_role("button", name=BTN)
        return b if b.count() == 1 and b.is_visible() else None

    def shown_count():
        return int(re.match(r"([\d,]+)", page.locator("#ex-count").text_content()).group(1).replace(",", ""))

    # nothing in the guide: the button, then one click finds the place in the Statewide list
    load("g=lobster")
    search(page, q)
    n_guide = page.locator("#ex-list .ex-row").count()
    if n_guide:
        bad(f"{where}: {q!r} lists {n_guide} places in the lobster guide; the check needs a place outside it")
    b = widen_button()
    if not b:
        bad(f"{where}: searching {q!r} in the lobster guide finds nothing there and offers no 'Search all restaurants (N matches)' button "
            f"({page.locator('#ex-list').inner_text()[:90]!r})")
    else:
        n = int(BTN.match(b.inner_text().strip()).group(1).replace(",", ""))
        for t in page.evaluate(CONTRAST, "#ex-list"):
            bad(f"{where}: text contrast under 4.5:1 next to the search-all button: {t}")
        if width == 375:
            for t in page.evaluate(TAP, "#ex-list"):
                bad(f"{where}: tap target under 44px next to the search-all button: {t}")
        b.click()
        page.wait_for_timeout(400)
        hits = [r for r in rows(page) if r["name"] == name and town in r["town"]]
        state = page.evaluate("""({ g: document.querySelector('.ex-guides button[aria-pressed="true"]')?.dataset.g, q: document.querySelector('#ex-q').value,
                                    hash: location.hash, focus: document.activeElement?.className || '' })""")
        if not hits or state["g"] != "all" or state["q"] != q or "g=all" not in state["hash"] or f"q={q}" not in state["hash"]:
            bad(f"{where}: one click on 'Search all restaurants' didn't list {name} in the Statewide list with the same search: {state}, "
                f"rows {[r['name'] for r in rows(page)][:4]}")
        if shown_count() != n:
            bad(f"{where}: the button promised {n} matches, the Statewide list shows {shown_count()}")
        if "ex-row" not in state["focus"]:
            bad(f"{where}: after 'Search all restaurants' focus isn't on the first result (it's on {state['focus']!r})")
        if widen_button():
            bad(f"{where}: the Statewide list still offers to search all restaurants")
    # only a few in the guide: the list, and the same offer under it (a town with 1-4 lobster places and more restaurants)
    towns = Counter(data.town(i) for i in lobster)
    cands = sorted(t for t, k in towns.items() if t and 1 <= k <= 4 and sum(1 for i in range(data.n) if data.rest(i) and data.town(i) == t) > 2 * k)
    tried = False
    for t in cands[:6]:
        load("g=lobster")
        search(page, t)
        k = page.locator("#ex-list .ex-row").count()
        if not 1 <= k <= 4:
            continue
        tried = True
        b = widen_button()
        if not b:
            bad(f"{where}: searching {t!r} in the lobster guide finds {k} there and offers no 'Search all restaurants' button")
        else:
            n = int(BTN.match(b.inner_text().strip()).group(1).replace(",", ""))
            b.click()
            page.wait_for_timeout(400)
            if shown_count() != n or n <= k:
                bad(f"{where}: {t!r}: the button promised {n} matches (the guide had {k}); the Statewide list shows {shown_count()}")
        break
    if not tried:
        print(f"  (no town search with 1-4 lobster places to test the few-results offer at {width} px)")
    # a search the guide answers well, and the Statewide list itself, offer nothing
    load("g=lobster")
    search(page, "lobster")
    if widen_button():
        bad(f"{where}: 'lobster' in the lobster guide ({page.locator('#ex-list .ex-row').count()} places) still offers to search all restaurants")
    for x in errors:
        bad(f"{where}: search-all: page error: {x}")
    for v in page.evaluate("window.__csp || []"):
        bad(f"{where}: search-all: CSP violation: {v}")
    ctx.close()


def contrast_checks(browser, base, data):
    lw = sorted([i for i in range(data.n) if data.rest(i) and (data.detail[i] or {}).get("lw") and data.C["hc"][i] == 1])
    place = None
    for f in sorted(os.listdir(os.path.join(DOCS, "places"))):
        s = open(os.path.join(DOCS, "places", f), encoding="utf-8").read()
        if lw and f'#p={data.C["id"][lw[0]]}"' in s:
            place = "/places/" + f
    place = place or "/places/" + sorted(os.listdir(os.path.join(DOCS, "places")))[0]
    for scheme in ("light", "dark"):
        ctx = browser.new_context(viewport={"width": 375, "height": 812}, color_scheme=scheme)
        page = ctx.new_page()
        for url, scope in (("/explore/#g=icons", "header.site, .ex-controls, #ex-list"), ("/explore/#g=lobster", ".ex-controls, #ex-list"),
                           ("/", "header.site, main, footer"), (f"/{GUIDE_FILE['lobster']}", "main"), (place, "main"), ("/cities/portland.html", "main")):
            goto(page, base + BASE + url, "networkidle")
            if url.startswith("/explore"):
                page.wait_for_function("() => document.querySelectorAll('.ex-row').length > 0", timeout=60000)
            for t in page.evaluate(CONTRAST, scope):
                bad(f"{url} ({scheme}): text contrast under 4.5:1: {t}")
            if url == "/explore/#g=icons":
                page.locator('.ex-view button[data-v="map"]').click()
                page.wait_for_timeout(400)
                for t in page.evaluate(CONTRAST, ".ex-view, #ex-maphint, .ex-zoom"):
                    bad(f"{url} map ({scheme}): text contrast under 4.5:1: {t}")
                page.locator('.ex-view button[data-v="list"]').click()
                page.locator(".ex-row").first.click()
                page.wait_for_function("() => document.querySelector('#ex-panel .ex-sec')", timeout=30000)
                page.locator("#ex-save").click()     # the pressed Save state
                page.wait_for_timeout(300)
                for t in page.evaluate(CONTRAST, "#ex-panel"):
                    bad(f"{url} panel ({scheme}): text contrast under 4.5:1: {t}")
                page.keyboard.press("Escape")
        if lw:   # the Lewiston result block in the panel
            goto(page, base + BASE + f"/explore/#g=all&p={data.C['id'][lw[0]]}", "networkidle")
            try:
                page.wait_for_function("document.querySelector('#ex-panel .ex-lw')", timeout=15000)
                for t in page.evaluate(CONTRAST, "#ex-panel"):
                    bad(f"explore Lewiston panel ({scheme}): text contrast under 4.5:1: {t}")
            except Exception:
                bad(f"explore ({scheme}): the Lewiston panel never showed its result")
        ctx.close()


def app_data_checks(problems):
    """docs/data/app/, the app's data updates (scripts/publish_app_data.py, OTA-DATA.md): every manifest entry's hash, size and
    row count match its file, the head file's date matches, and no old copy lingers."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from publish_app_data import check_app_data, app_data_dir
    found, notes = check_app_data(DOCS, app_data_dir())
    problems.extend("app data: " + x for x in found)
    for x in notes:
        print("  note: app data:", x)


def main():
    base = serve()
    data = Data()
    quoted = data.quoted()
    files = static_checks(data, quoted)
    locs, paths = sitemap_checks(files)
    inspection_checks(data, files)
    guide_checks(data, files)
    town_claims(data, files)
    page_type_checks(data, files, paths)
    family_checks(files)
    app_data_checks(problems)
    copy_decision_checks()
    claim_checks(data, files)
    other_state_checks()
    storage_checks()
    blocklist_checks()
    n_static = len(problems)
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
    n_jobs = 0 if ARGS.skip_pages or ARGS.static_only else browser_pages(base, locs, ARGS.workers)
    if not ARGS.static_only:
        browser_webapp(base, data)
    print(f"static: {len(files)} HTML files, {n_static} problems | browser: {n_jobs} page loads at 375 and 1280 px"
          + ("" if ARGS.static_only else ", plus the web app") + f" (served at {BASE or '/'} from {DOCS})")
    for p in problems:
        print("  ✗", p)
    print("OK" if not problems else f"{len(problems)} problems")
    sys.exit(1 if problems else 0)


def browser_webapp(base, data):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        for width in (375, 1280):
            for fn in (webapp_checks, webapp_widen_checks):
                try:
                    fn(browser, base, width, data)
                except Exception as ex:   # a broken page shouldn't stop the report
                    bad(f"explore @{width}: the checks stopped: {str(ex).splitlines()[0]}")
        for fn in (webapp_load_checks, webapp_robustness_checks, webapp_placeholder_checks, lambda b, u: contrast_checks(b, u, data)):
            try:
                fn(browser, base)
            except Exception as ex:
                bad(f"explore: the checks stopped: {str(ex).splitlines()[0]}")
        browser.close()


if __name__ == "__main__":
    main()
