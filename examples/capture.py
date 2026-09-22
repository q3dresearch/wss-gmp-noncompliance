"""Scripted capture. EudraGMDP is a Struts app the engine cannot drive.

WHY THIS EXISTS AND WHY IT IS NOT A SECOND ENGINE. The search needs a
four-step handshake -- GET the form to obtain a session cookie and an action
URL carrying a jsessionid, POST the search to that action URL, then walk a
session-stateful result list. `wss capture` takes a fixed endpoint list and
carries no cookies between fetches, and the engine is deliberately not growing
a session primitive for one source. So the handshake lives here and everything
downstream of the bytes -- gates, sha, dedupe, the raw layout, the manifest
row -- is the engine's own code, imported. Nothing about the archive format is
reimplemented, which is the part that has to stay uniform across the fleet.

WHAT IT FETCHES, AND WHY BOTH. `action=ExportList` returns the WHOLE register
as one .xls and is strictly richer than the HTML: 17 columns against 11,
including `Last Updated Date` (populated on all 79 rows, 68 distinct values),
`DUNS Number`, `Site NCA Reference`, and the address split into four fields
instead of one concatenation. `Last Updated Date` matters more than the rest
put together -- this register has no status column, so a resolved statement
must either be edited in place or vanish, and that column is what dates an
in-place edit. The .xls also states `Total Records: N`, which is a count from
the publisher rather than one we inferred.

The HTML pages are captured too, because that is what the shipped `gmpnc.v1`
parser reads and because a second representation of the same register is worth
having when the question is what the publisher quietly changed.

PAGING IS AN ABSOLUTE ZERO-BASED PAGE INDEX, not a step: `action=Page&param=2`
is the third page, from wherever you are. Treating it as "next" fetches the
same page repeatedly -- that happened, eight times. The page count is derived
from the export's own record count rather than guessed.
"""
import datetime as dt
import hashlib
import http.cookiejar
import math
import re
import socket
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from wss import gates as wgates
from wss import manifest as wmanifest
from wss import registry as wregistry
from wss import storage as wstorage

_o = socket.getaddrinfo   # this host black-holes IPv6; urllib waits out a full TCP timeout
socket.getaddrinfo = lambda h, p, f=0, t=0, pr=0, fl=0: _o(h, p, socket.AF_INET, t, pr, fl)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "eudragmdp.gmp.noncompliance"
BASE = "https://eudragmdp.ema.europa.eu"
SEARCH = f"{BASE}/inspections/gmpc/searchGMPNonCompliance.do"
CTRL = "ctrl=searchGMPNCResultControlList"
FROM_DATE = "1990-01-01"      # narrow ranges return 0; this returns the register
PER_PAGE = 10
DELAY = 6
MAX_PAGES = 200


def contact():
    import os
    c = os.environ.get("WSS_CONTACT", "").strip()
    if not c:
        sys.exit("WSS_CONTACT is not set — captures identify themselves in the User-Agent.")
    return f"wss/{SOURCE_ID} (+{c})"


class Session:
    def __init__(self, ua):
        self.ua = ua
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def fetch(self, url, data=None, referer=None):
        h = {"User-Agent": self.ua}
        if referer:
            h["Referer"] = referer
        if data is not None:
            h["Content-Type"] = "application/x-www-form-urlencoded"
        r = self.op.open(urllib.request.Request(url, data=data, headers=h), timeout=120)
        return r.getcode(), r.headers, r.read()


def record(source, store, url, status, headers, body, fetched, ext, gate_spec):
    """Gate, dedupe and write exactly as `wss capture` would."""
    ctype = headers.get("Content-Type", "")
    prev = wmanifest.last_capture(ROOT, SOURCE_ID, url)
    res = wgates.run_gates(status_code=status, content_type=ctype, body=body,
                           gates=gate_spec,
                           prev_content_length=int(prev["content_length"]) if prev and prev.get("content_length") else None)
    sha = hashlib.sha256(body).hexdigest()
    row = {"source_id": SOURCE_ID, "url": url, "fetched_at": fetched.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "http_status": status, "content_type": ctype, "content_length": len(body),
           "content_sha256": sha, "etag": headers.get("ETag", ""),
           "last_modified": headers.get("Last-Modified", "")}
    if not res.ok:
        ref = wstorage.quarantine_path(SOURCE_ID, fetched, sha, ext)
        wstorage.LocalGitStore(ROOT).write(ref, body)
        row |= {"outcome": "quarantined", "raw_ref": ref, "reason": res.reason}
        wmanifest.append_row(ROOT, row)
        return "quarantined"
    if prev and prev.get("content_sha256") == sha:
        row |= {"outcome": "unchanged", "raw_ref": prev["raw_ref"]}
        wmanifest.append_row(ROOT, row)
        return "unchanged"
    ref = wstorage.raw_path(SOURCE_ID, fetched, sha, ext)
    store.write(ref, body)
    row |= {"outcome": "changed" if prev else "first_capture", "raw_ref": ref}
    wmanifest.append_row(ROOT, row)
    return row["outcome"]


def declared_total(xls: bytes):
    """The publisher's own record count, and the rows it actually shipped."""
    import xlrd
    sh = xlrd.open_workbook(file_contents=xls).sheet_by_index(0)
    said = None
    for r in range(min(8, sh.nrows)):
        m = re.search(r"Total Records:\s*(\d+)", str(sh.cell_value(r, 0)))
        if m:
            said = int(m.group(1))
    hr = next(r for r in range(sh.nrows)
              if "Report Number" in " ".join(str(sh.cell_value(r, c)) for c in range(sh.ncols)))
    got = sum(1 for r in range(hr + 1, sh.nrows)
              if any(str(sh.cell_value(r, c)).strip() for c in range(sh.ncols)))
    return said, got


def main():
    ua = contact()
    source = next(s for s in wregistry.load_registry(ROOT) if s.source_id == SOURCE_ID)
    store = wstorage.store_for(source, ROOT)
    s = Session(ua)
    out = []

    status, headers, body = s.fetch(SEARCH)
    action = re.search(r"""action\s*=\s*['"]([^'"]+)""",
                       re.search(r"<form\b[^>]*>", body.decode("utf8", "replace"), re.I).group(0)).group(1)
    if "jsessionid" not in action:
        sys.exit("  form carried no jsessionid — the handshake shape changed, not capturing")
    print(f"  session established, action {action[:70]}...", flush=True)

    time.sleep(DELAY)
    post = urllib.parse.urlencode({"formid": "frmGMPCSearch", "fromDate": FROM_DATE,
                                   "toDate": dt.date.today().isoformat(),
                                   "btnSearchGMPNC": "clicked"}).encode()
    status, headers, body = s.fetch(BASE + action, data=post, referer=SEARCH)
    fetched = dt.datetime.now(dt.timezone.utc)
    out.append(("page 0", record(source, store, f"{SEARCH}?{CTRL}&action=Page&param=0",
                                 status, headers, body, fetched, "html", source.gates)))

    # The export first: its record count is what sizes the page walk.
    time.sleep(DELAY)
    xurl = f"{SEARCH}?{CTRL}&action=ExportList"
    status, headers, xls = s.fetch(xurl, referer=SEARCH)
    said, got = declared_total(xls)
    print(f"  export: {len(xls):,} bytes, declares {said} records, ships {got} rows", flush=True)
    if said is not None and said != got:
        sys.exit(f"  export disagrees with itself ({said} declared, {got} shipped) — not capturing")
    xgates = {"expect_status": 200, "min_bytes": 8000,
              "content_type_any": ["application/vnd.ms-excel"], "max_shrink_pct": 40}
    out.append(("export", record(source, store, xurl, status, headers, xls,
                                 dt.datetime.now(dt.timezone.utc), "xls", xgates)))

    pages = min(MAX_PAGES, math.ceil((got or PER_PAGE) / PER_PAGE))
    for i in range(1, pages):
        time.sleep(DELAY)
        u = f"{SEARCH}?{CTRL}&action=Page&param={i}"
        status, headers, body = s.fetch(u, referer=SEARCH)
        out.append((f"page {i}", record(source, store, u, status, headers, body,
                                        dt.datetime.now(dt.timezone.utc), "html", source.gates)))

    from collections import Counter
    c = Counter(o for _, o in out)
    for what, o in out:
        print(f"    {o:14s} {what}")
    print(f"\n  {SOURCE_ID}: {len(out)} artefact(s) — " +
          ", ".join(f"{k}={v}" for k, v in sorted(c.items())))
    if c.get("quarantined"):
        sys.exit(1)


if __name__ == "__main__":
    main()
