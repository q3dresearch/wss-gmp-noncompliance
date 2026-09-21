# wss-gmp-noncompliance — EudraGMDP GMP non-compliance statements

Which pharmaceutical manufacturing sites EU national inspectorates found
non-compliant with Good Manufacturing Practice, where, and when.

**Status: paused, with one baseline capture taken by hand.** Read
[registry/eudragmdp.noncompliance.yml](registry/eudragmdp.noncompliance.yml)
before doing anything.

## Why this exists

The register carries **eleven columns and not one of them is a status**. A
statement that is later resolved has nowhere to be marked resolved, so it must
either be edited in place or disappear. Either way the register as it stood on a
given date is not recoverable from the publisher afterwards.

It also moves: **78 rows on 2026-09-15, 79 on 2026-09-22.**

## Why it is paused

The engine cannot express this source. It is a Struts application needing a
four-step handshake:

1. `GET` the search form — yields a session cookie **and** a form action URL
   with an embedded `jsessionid`
2. `POST` the search to *that* action URL, not the bare path. Posting to the
   bare path returns the shell every time and looks like a failed search
3. walk pages with `?ctrl=searchGMPNCResultControlList&action=Page&param=N`
4. `param` is an **absolute zero-based page index, not a step** — sending
   `param=1` repeatedly returns page 2 forever

`Endpoint` has `url`, `method`, `body` and `url_from`, but `url_from` is a
JSON-path extractor and nothing carries cookies between fetches. Either the
engine grows a session handshake, or this stays a scripted capture outside it.

## The baseline

`raw/` holds all eight result pages plus the search form as served on
**2026-09-22**; `examples/gmp_noncompliance.csv` is the parse — 79 rows, 11
columns. It was taken **before** the remaining questions were answered, because
the previous candidate in this fleet (UNOLS STRS) was retired five days after
being screened and two decades of it were lost to a deferred capture.

## Two traps, both already paid for

**The unique key is `(Report Number, EudraGMDP Document Reference Number)`.**
Report Number alone is not unique — 79 rows carry 71 report numbers, because one
report can name several sites. Diffing on it alone manufactures six permanent
phantom revisions.

**The date filter is not understood.** `fromDate=1990-01-01` with
`toDate=<today>` returns the whole register, but narrow ranges return 0. Do not
use it to partition captures until someone explains it.

## Licence

Code: MIT ([LICENSE](LICENSE)). **The data is not CC-BY-4.0 and carries no
onward licence from this repository** — see [LICENSE-DATA](LICENSE-DATA). EMA's
reproduction terms could not be established; attribute the European Medicines
Agency, not this repo.
