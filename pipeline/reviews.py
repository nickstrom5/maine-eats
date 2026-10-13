"""Maine signals from Google reviews written up to Sep 2021 (UCSD Google Local, review-Maine.json.gz)
-> data/me/review_signals.parquet. Web leaderboard only: the app uses none of this.

For each Google listing: how many reviews mention a lobster roll (or a lobster pound/shack), fried or whole-belly clams, a red
snapper hot dog, a Maine Italian sandwich, a whoopie pie, a potato doughnut, poutine / tourtière / ployes, oysters, blueberry pie,
or ice cream / a dairy bar, and the average star rating of just those reviews. The file is streamed from UCSD and never stored.
"""
import os, re, gzip, json, time, collections, urllib.request
import pandas as pd
from common import ME

URL = "https://mcauleylab.ucsd.edu/public_datasets/gdrive/googlelocal/review-Maine.json.gz"
SIG = {
    "lobster": re.compile(r"\blobster rolls?\b|\blobster (?:pound|shack|dinner)s?\b|\bwhole lobsters?\b|\bsteamed lobsters?\b"),
    "clams": re.compile(r"\bfried clams?\b|\bwhole[- ]belly\b|\bclam strips?\b|\bclam cakes?\b|\bsteamers\b"),
    "snapper": re.compile(r"\bred snappers?\b|\bred hot ?dogs?\b|\bsnapper dogs?\b"),
    "italian": re.compile(r"\bitalian sandwich(?:es)?\b|\bmaine italians?\b|\ban italian\b"),
    "whoopie": re.compile(r"\bwhoopie pies?\b|\bwhoopies?\b"),
    "donut": re.compile(r"\bpotato (?:donuts?|doughnuts?)\b"),
    "franco": re.compile(r"\bpoutine\b|\btourti[eè]re\b|\bployes?\b|\bcretons\b|\bmeat pie\b"),
    "oyster": re.compile(r"\boysters?\b"),
    "blueberry": re.compile(r"\bblueberry pie\b|\bblueberry (?:cobbler|crisp|cake)\b|\bwild blueberr"),
    "icecream": re.compile(r"\bice cream\b|\bsoft serve\b|\bdairy bar\b|\bsundaes?\b"),
}
PRE = re.compile(r"lobster|clam|whole[- ]belly|steamers|snapper|red hot ?dog|italian|whoopie|potato d|poutine|tourti|ploye|creton|meat pie|oyster|blueberr|ice cream|soft serve|dairy bar|sundae", re.I)

t = time.time()
cnt = collections.defaultdict(collections.Counter)
n = hit = 0
req = urllib.request.Request(URL, headers={"User-Agent": "me-eats data pipeline (work-with-nick@gmail.com)"})
with urllib.request.urlopen(req, timeout=120) as resp, gzip.open(resp, "rt") as f:
    for line in f:
        n += 1
        if not PRE.search(line):
            continue
        d = json.loads(line)
        txt = (d.get("text") or "").lower()
        if not txt:
            continue
        g, rt = d.get("gmap_id"), d.get("rating")
        for k, rx in SIG.items():
            if rx.search(txt):
                c = cnt[g]; c[k] += 1
                if rt:
                    c[k + "_sum"] += rt
                hit += 1
        if n % 1_000_000 == 0:
            print(n, "reviews", round(time.time() - t), "s", flush=True)
rows = []
for g, c in cnt.items():
    row = {"gmap_id": g}
    for k in SIG:
        row["n_" + k] = c[k]
        row["r_" + k] = round(c[k + "_sum"] / c[k], 3) if c[k] else None
    rows.append(row)
pd.DataFrame(rows).to_parquet(os.path.join(ME, "review_signals.parquet"))
print("reviews read:", n, "| mentions:", hit, "| listings with a mention:", len(rows), "|", round(time.time() - t), "s")
