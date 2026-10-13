"""Every host the research cites, checked against its robots.txt: a source is usable only if its host lets ClaudeBot, Claude-User
and anthropic-ai fetch that path and doesn't answer with a bot check. One robots.txt request per host, cached for 7 days.

    ../.venv/bin/python check_sources.py            # report -> data/research/source_hosts.json, exit 1 if any record cites a blocked URL
    ../.venv/bin/python check_sources.py URL ...    # before using a new source: "usable" or why not, per URL
"""
import glob, json, os, re, subprocess, sys, time, urllib.parse, urllib.robotparser
from datetime import date, datetime
import requests

R = os.path.join(os.path.dirname(__file__), "..", "data", "research")
CACHE = os.path.join(R, "source_hosts.json")
AGENTS = ("ClaudeBot", "Claude-User", "anthropic-ai")
UA = "MaineEatsSourceCheck/1.0 (+work-with-nick@gmail.com)"
# official data portals we read through their APIs: their robots.txt governs crawling the HTML site, not the documented API
API_HOSTS = set()


def records():
    for f in sorted(glob.glob(f"{R}/app/*.json")) + sorted(glob.glob(f"{R}/*.json")):
        if f.endswith("source_hosts.json") or f.endswith("geocode_census.json") or f.endswith("geocode_todo.json"):
            continue
        d = json.load(open(f))
        if isinstance(d, dict):
            d = d.get("places") or d.get("restaurants") or []
        for x in d:
            if isinstance(x, dict):
                yield os.path.relpath(f, R), x


def host(u):
    return urllib.parse.urlsplit(u).netloc.lower().removeprefix("www.")


def check_host(h):
    for attempt in range(2):
        c = _check_host(h)
        if c["verdict"] != "unreachable":
            return c
        time.sleep(3)
    return c


def _get(url):
    """(status, content type, body) of one GET with our own user agent. Some servers reset Python's TLS client but answer curl
    (michelinmedia.com): curl is the same plain request with the same honest user agent, not a workaround for a bot check."""
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=20, allow_redirects=True)
        return r.status_code, r.headers.get("content-type", ""), r.text[:200_000]
    except requests.RequestException as e:
        if not isinstance(e, requests.ConnectionError) or "reset" not in str(e).lower():
            raise
    out = subprocess.run(["curl", "-sL", "--max-time", "20", "-A", UA, "-o", "-", "-w", "\n%{http_code} %{content_type}", url],
                         capture_output=True, text=True, timeout=40)
    body, _, tail = out.stdout.rpartition("\n")
    code, _, ctype = tail.partition(" ")
    if not code.isdigit() or code == "000":
        raise requests.ConnectionError(f"curl exit {out.returncode}")
    return int(code), ctype, body[:200_000]


def _check_host(h):
    err = None
    for scheme_host in (f"https://www.{h}", f"https://{h}"):
        try:
            status, ctype, body = _get(scheme_host + "/robots.txt")
        except (requests.RequestException, subprocess.SubprocessError) as e:
            err = type(e).__name__
            continue
        challenge = bool(re.search(r"Just a moment|cf-chl|captcha|Attention Required", body[:3000], re.I))
        if status in (401, 403, 429, 503) or challenge:
            return {"status": status, "verdict": "bot check", "rules": None}
        if status >= 400 or "html" in ctype and "<html" in body[:500].lower():
            return {"status": status, "verdict": "ok", "rules": None}          # no robots.txt: nothing disallowed
        return {"status": status, "verdict": "ok", "rules": body}
    return {"status": None, "verdict": "unreachable", "rules": None, "error": err}


def refresh(cache, hosts, quiet=False):
    fresh = date.today().toordinal() - 7
    for i, h in enumerate(hosts):
        c = cache.get(h)
        if c and c["verdict"] != "unreachable" and date.fromisoformat(c["checked"]).toordinal() >= fresh:
            continue
        cache[h] = dict(check_host(h), checked=date.today().isoformat())
        time.sleep(0.5)
        if i % 25 == 0 and not quiet:
            print(f"  {i}/{len(hosts)}", flush=True)
    tmp = CACHE + ".tmp"
    json.dump(cache, open(tmp, "w"), indent=1)
    os.replace(tmp, CACHE)


def why_not(cache, u):
    """None when the URL is usable, else the reason."""
    h = host(u)
    if h in API_HOSTS:
        return None
    c = cache[h]
    if c["verdict"] != "ok":
        return c["verdict"]
    if c.get("rules"):
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(c["rules"].splitlines())
        blocked = [a for a in AGENTS if not rp.can_fetch(a, u)]
        if blocked:
            return "robots.txt disallows " + ", ".join(blocked)
    return None


def main():
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    if len(sys.argv) > 1:
        refresh(cache, sorted({host(u) for u in sys.argv[1:]} - API_HOSTS), quiet=True)
        reasons = {u: why_not(cache, u) for u in sys.argv[1:]}
        for u, why in reasons.items():
            print(("usable  " if why is None else f"NO ({why})  ") + u)
        sys.exit(1 if any(reasons.values()) else 0)
    urls = {}
    for f, x in records():
        for s in x.get("sources") or []:
            urls.setdefault(s, []).append((f, x.get("name")))
    refresh(cache, sorted({host(u) for u in urls} - API_HOSTS))
    bad = {}
    for u, where in urls.items():
        why = why_not(cache, u)
        if why:
            bad[u] = (why, where)
    print(f"{len(urls)} source URLs on {len({host(u) for u in urls})} hosts; {len(bad)} unusable")
    by_host = {}
    for u, (why, where) in bad.items():
        by_host.setdefault((host(u), why), []).extend(where)
    for (h, why), where in sorted(by_host.items()):
        names = sorted({f"{n} ({f})" for f, n in where})
        print(f"- {h}: {why} | {len(names)} records: {'; '.join(names[:12])}{' …' if len(names) > 12 else ''}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
