"""Every report number EudraGMDP has ever shown, from the Wayback mementos.

WHY THE COUNT CHECK IS THE WHOLE SCRIPT. The results table sits in a page full
of other tables, and the EMA copyright footer parses as a record if you only
ask for non-empty cells -- the first version of this counted 195 report
numbers that way. The page states its own row count ("8 items"), so a data row
is one with the SAME CELL COUNT AS THE HEADER ROW and the parse is only
believed when parsed == stated. It now agrees on 98 of 98 pages that state a
count.

41 mementos state no count. 33 of them yield no rows at all -- they are form
pages -- and 8 yield exactly ten rows each on an older layout. Those 8 are
reported separately rather than folded in, because nothing in the page
confirms them.

FIVE HEADER LAYOUTS, AND ONE OF THEM HAD A STATUS COLUMN. The eight mementos
from 2014 carry `Status` between `Issue Date` and `Last Update Date` -- and it
is EMPTY on all 62 rows they hold. By 2015-03-23 the column is gone. So the
register once modelled a status, never populated it, and removed it, which is a
stronger version of "there is no status column" rather than a contradiction of
it. Columns are therefore resolved BY NAME here, never by position.

THE KEY IS NOT THE REPORT NUMBER. One report can name several sites, so a
report number appears more than once in a single capture; that is why the
live register carries 79 rows under 71 numbers. This script counts DISTINCT
NUMBERS EVER SEEN, which is the right unit for "what has been removed".
"""
import csv, html, json, pathlib, re, datetime as dt

ROOT = pathlib.Path(__file__).resolve().parents[1]
CELL = re.compile(r"<t([dh])\b[^>]*>(.*?)</t\1>", re.S | re.I)
ROW  = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S | re.I)
ITEMS = re.compile(r"(\d+)\s*items?")


def _text(x):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x))).strip()


def parse(page):
    m = ITEMS.search(page)
    stated = int(m.group(1)) if m else None
    rows = [[_text(c[1]) for c in CELL.findall(r)] for r in ROW.findall(page)]
    idx = width = site = None
    out = []
    for cells in rows:
        if idx is None:
            for i, c in enumerate(cells):
                if c.lower().startswith("report number"):
                    idx, width = i, len(cells)
                    # SITE NAME BY HEADER, NEVER BY POSITION. There are FIVE header
                    # layouts across the 139 mementos, and in 104 of them the column
                    # after Report Number is `EudraGMDP Document Reference Number`,
                    # not `Site Name`. Taking idx+1 filled a third of this file with
                    # document references where company names belong.
                    site = next((j for j, h in enumerate(cells)
                                 if h.strip().lower() == "site name"), None)
                    break
            continue
        if len(cells) == width and cells[idx]:
            out.append((cells[idx], cells[site] if site is not None else ""))
    return out, stated


def main():
    seen, agree, stated_n, unverified = {}, 0, 0, 0
    for f in sorted((ROOT / "raw" / "wayback").glob("*.html")):
        recs, stated = parse(f.read_text(errors="replace"))
        if stated is not None:
            stated_n += 1
            agree += (len(recs) == stated)
        elif recs:
            unverified += 1
        for num, site in recs:
            if num not in seen:
                seen[num] = [f.stem, site, False]
            # "verified" means SOME page whose row count the publisher confirmed
            # showed this number -- not merely the page we first saw it on.
            if stated is not None:
                seen[num][2] = True
    print(f"  mementos: {len(list((ROOT/'raw'/'wayback').glob('*.html')))}")
    print(f"  pages stating a count: {stated_n}; parsed == stated: {agree}/{stated_n}")
    if agree != stated_n:
        raise SystemExit("  parse disagrees with the publisher's own count -- not writing")

    live = {r["Report Number"] for r in
            csv.DictReader(open(ROOT / "examples" / "gmp_noncompliance.csv"))}
    dest = ROOT / "examples" / "report_numbers_ever_seen.csv"
    with dest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["report_number", "first_seen_stamp", "first_seen_datetime",
                    "first_seen_site", "page_count_verified",
                    "in_live_register_2026_09_23"])
        for num, (stamp, site, ver) in sorted(seen.items(), key=lambda kv: kv[1][0]):
            when = dt.datetime.strptime(stamp, "%Y%m%d%H%M%S").strftime("%a, %d %b %Y %H:%M:%S GMT")
            w.writerow([num, stamp, when, site, "yes" if ver else "no",
                        "yes" if num in live else "no"])
    ver = {n for n, (_, _, v) in seen.items() if v}
    print(f"\n  distinct report numbers ever seen : {len(seen)}  ({len(ver)} on count-verified pages)")
    print(f"  live register today               : {len(live)}")
    print(f"  ABSENT from the live register     : {len(set(seen) - live)}  "
          f"({len(ver - live)} count-verified)")
    print(f"  the headline is the count-verified pair: {len(ver)} ever seen, {len(ver - live)} absent")
    print(f"  written to {dest}")


if __name__ == "__main__":
    main()
