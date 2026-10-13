"""Merges the link sweep's batch files into pipeline/website_blocklist.json, the list of restaurant websites the site never links.

Usage (from me-eats/): .venv/bin/python scripts/merge-blocklist.py [--dry-run] batch-1-me.json [batch-2-me.json ...]
then re-run scripts/make-site.py (it drops each listed website from every page and the web app's data, and prints how many links each
entry left out) and scripts/qa-site.py (it fails if a listed website is still anywhere in docs/).

A batch file is a JSON list of entries: {"domain", "match": "domain" (that domain and every subdomain) | "url" (one page: "url", else
"domain" holding the path), "place", "reason", "severity", "evidence", "found"}. Existing entries are kept as they are, in order (the
sentinel stays first). A new entry is added unless the list already has its domain (or, for a "url" entry, that page, or a domain entry
covering it). Only Maine's batches are taken (batch-<N>-me.json); a file named for another state is refused.
"""
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LIST = os.environ.get("WEBSITE_BLOCKLIST") or os.path.join(ROOT, "pipeline", "website_blocklist.json")   # another file only for tests
KEYS = ("domain", "url", "match", "place", "reason", "severity", "evidence", "found", "note")


def bare_domain(d):
    d = re.sub(r"^(?:https?:)?//", "", str(d).strip(), flags=re.I).split("/")[0].split("?")[0].split("#")[0].split(":")[0]
    return d.lower().removeprefix("www.").rstrip(".")


def url_key(u):
    return re.sub(r"^(?:https?:)?//", "", str(u).strip(), flags=re.I).lower().removeprefix("www.").rstrip("/")


def key(b):
    return ("url", url_key(b.get("url") or b["domain"])) if b.get("match") == "url" else ("domain", bare_domain(b["domain"]))


def covered(b, domains):
    """A "url" entry whose page is on a domain the list already blocks."""
    host = bare_domain(b.get("url") or b["domain"])
    return b.get("match") == "url" and any(host == d or host.endswith("." + d) for d in domains)


def main(argv):
    dry = "--dry-run" in argv
    files = [a for a in argv if a != "--dry-run"]
    if not files:
        sys.exit(__doc__)
    entries = json.load(open(LIST, encoding="utf-8"))
    assert isinstance(entries, list) and entries, f"{LIST} must be a non-empty list (it starts with a sentinel entry)"
    have = {key(b) for b in entries}
    added, dupes, skipped = [], [], []
    for f in files:
        m = re.search(r"batch-[^/]*?-([a-z]{2,3})\.json$", f)
        if m and m.group(1) != "me":
            sys.exit(f"{f}: a batch for another state ({m.group(1)}); only batch-<N>-me.json belongs here")
        for raw in json.load(open(f, encoding="utf-8")):
            b = {k: raw[k] for k in KEYS if raw.get(k) not in (None, "")}
            b.setdefault("match", "domain")
            if not b.get("place") and raw.get("name"):   # the Chicago-style shape names the place "name"
                b["place"] = raw["name"] + (f" ({raw['address']})" if raw.get("address") else "")
            if not b.get("domain") and b.get("url"):
                b["domain"] = bare_domain(b["url"])
            if not b.get("domain") or b["match"] not in ("domain", "url") or not b.get("reason"):
                skipped.append(f"{f}: malformed {json.dumps(raw)[:100]}")
                continue
            if b["match"] == "domain":
                b["domain"] = bare_domain(b["domain"])
            domains = {k[1] for k in have if k[0] == "domain"}
            if key(b) in have or covered(b, domains):
                dupes.append(key(b)[1])
                continue
            entries.append({k: b[k] for k in KEYS if k in b})
            have.add(key(b))
            added.append(f"{key(b)[1]} ({b.get('severity', '?')}, {b.get('place', '?')})")
    print(f"{len(added)} added, {len(dupes)} already listed, {len(skipped)} malformed; {len(entries)} entries in all")
    for x in added:
        print("  +", x)
    for x in dupes:
        print("  =", x)
    for x in skipped:
        print("  !", x)
    if not dry and added:
        open(LIST, "w", encoding="utf-8").write("[\n" + ",\n".join("  " + json.dumps(b, ensure_ascii=False) for b in entries) + "\n]\n")
        print(f"wrote {os.path.relpath(LIST, ROOT) if LIST.startswith(ROOT + os.sep) else LIST}; now run scripts/make-site.py and scripts/qa-site.py")
    sys.exit(1 if skipped else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
