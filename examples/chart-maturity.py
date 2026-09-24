#!/usr/bin/env python3
"""What you can ask this repo, and when.

**Why this plate exists.** Every other figure here reports something already
found in a single capture. None of them tell a reader what the ONGOING capture
buys, or when. That matters most for the questions this repo cannot answer yet:
a reader has no way to tell "nobody has done the work" from "the data does not
exist until March".

So this reads the question table in the README, the cadence in the registry and
the first capture in the manifest, and puts each question where it becomes
answerable. It is a PLAN drawn as a plan. It measures nothing about the world.
"""
import csv, datetime as dt, pathlib, re, sys
import plate
from plate import INK, INK2, MUTED, RULE, GRID, FAINT

W = 880
NOW, SOON, NODATE = "#2f6f5e", "#c08a3e", "#8a8880"
PER = {"hourly": 1 / 24, "daily": 1.0, "weekly": 7.0, "monthly": 30.44, "quarterly": 91.31}


def demd(t: str) -> str:
    """Strip the markdown a README cell carries. The status was cleaned and the
    QUESTION TEXT was not, so '**Why doesn\'t someone else just make it?**' went
    into the SVG with its asterisks -- caught by plateaudit, not by me."""
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)     # [label](url) -> label
    t = re.sub(r"[*_`]+", "", t)
    return re.sub(r"\s+", " ", t).strip()


def questions(readme: str):
    out = []
    for line in readme.splitlines():
        m = re.match(r"^\|\s*(Q\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$", line)
        if not m:
            continue
        qid, text, status = m.groups()
        text = demd(text)
        flat = demd(status)
        low = flat.lower()
        if low.startswith("answered"):
            kind, n = "answered", 0.0
        elif (c := re.search(r"needs?\s*~?\s*(\d+)\+?\s*captures?", low)):
            kind, n = "captures", float(c.group(1))
        elif (c := re.search(r"needs?\s*~?\s*(\d+)\s*(year|month|week)", low)):
            mult = {"year": 365.0, "month": 30.44, "week": 7.0}[c.group(2)]
            kind, n = "days", float(c.group(1)) * mult
        elif low.startswith("needs"):
            kind, n = "captures", 2.0          # "needs captures", unquantified
        else:
            kind, n = "open", None
        out.append(dict(id=qid, text=text, flat=flat, kind=kind, n=n))
    return out


def main():
    here = pathlib.Path(__file__).resolve()
    repo = here.parents[1]
    qs = questions((repo / "README.md").read_text())
    cad = next((m.group(1) for y in (repo / "registry").glob("*.yml")
                if (m := re.search(r"^\s*cadence:\s*(\w+)", y.read_text(), re.M))), "monthly")
    days = set()
    for f in sorted((repo / "manifest").rglob("*.csv")):
        for row in csv.DictReader(f.open()):
            if row.get("fetched_at"):
                days.add(row["fetched_at"][:10])
    first = dt.date.fromisoformat(min(days)) if days else dt.date.today()
    have = len(days)
    step = PER[cad]

    # horizon per question, in days from the FIRST capture
    for q in qs:
        if q["kind"] == "answered":     q["at"] = 0.0
        elif q["kind"] == "captures":   q["at"] = max(0.0, (q["n"] - 1)) * step
        elif q["kind"] == "days":       q["at"] = q["n"]
        else:                           q["at"] = None
    dated = [q for q in qs if q["at"] is not None]
    undated = [q for q in qs if q["at"] is None]
    # Counted BEFORE the title is written. The title was a hardcoded f-string
    # with no interpolation -- correct for this repo and wrong for every other
    # one this script is copied into, which is the whole point of the script.
    nd = sum(1 for q in qs if q["kind"] == "answered")
    nn, no = len(dated) - nd, len(undated)
    if not qs:
        title = "This repo has no question table yet."
    elif no == 0:
        title = f"All {len(qs)} questions here are answered or on a clock."
    elif nd == 0:
        title = f"Nothing here is answered yet: {nn} wait on the capture, {no} are not on a clock."
    else:
        title = (f"{nd} of {len(qs)} questions are answered now; "
                 f"{nn} wait on the capture; {no} are not on a clock at all.")
    span = max([q["at"] for q in dated] + [step * 4]) * 1.06

    # A FIXED LABEL COLUMN, not labels beside their marks. Placed beside the mark,
    # the last dated question ran off the canvas and the two undated ones had their
    # text on the far left with their marks in the far-right gutter -- 700px apart
    # and reading as unrelated.
    QX, TX, PL, GUT = 28, 54, 366, 88      # id col, text col, plot left, no-date gutter
    PR = W - 34 - GUT
    rows = sorted(qs, key=lambda q: (q["at"] is None, q["at"] or 0, q["id"]))
    RH = 30
    s = plate.open_svg(W, 10, title,
        subtitle=f"Each question placed where the capture makes it answerable. Cadence is {cad}; "
                 f"first capture {first.isoformat()}; {have} distinct capture day"
                 f"{'s' if have != 1 else ''} so far.")
    f, y = plate.frame(W, 88,
        who="Someone deciding whether to use this repo now or wait for it",
        decide="Whether the question they came with is answerable today, later, or not by waiting",
        wrong="A question moves earlier than its mark without new captures — then the wait was "
              "never about data and the plan is wrong")
    s += f

    top = y + 30
    bot = top + len(rows) * RH
    X = lambda d: PL + (PR - PL) * d / span

    # THE AXIS UNIT FOLLOWS THE SPAN. Hard-coded months gave the hourly repo a
    # single "0" tick across a four-hour span, under a label reading "months from
    # first capture" -- an axis that named a unit it never drew.
    for size, unit, lab in ((1 / 24, "hour", "hours"), (1.0, "day", "days"),
                            (7.0, "week", "weeks"), (30.44, "month", "months")):
        if span / size <= 14:
            break
    m = 0
    while m * size <= span:
        gx = X(m * size)
        s.append(f'<line x1="{gx:.1f}" y1="{top-8:.1f}" x2="{gx:.1f}" y2="{bot+6:.1f}" stroke="{GRID}"/>')
        s.append(plate.txt(gx, bot + 20, m, size=10, fill=MUTED, anchor="middle"))
        m += 1
    s.append(plate.txt(X(span) + 6, bot + 20, f"{lab} from first capture", size=9,
                       fill=MUTED, anchor="start"))
    s.append(f'<line x1="{PL}" y1="{bot+2:.1f}" x2="{PR}" y2="{bot+2:.1f}" stroke="{RULE}"/>')

    # the "no date" gutter is fenced off, because those questions are NOT late --
    # they are not on a clock at all, and putting them at the axis end would read
    # as "answerable eventually".
    fx = PR + 24
    s.append(f'<line x1="{fx:.1f}" y1="{top-14:.1f}" x2="{fx:.1f}" y2="{bot+6:.1f}" '
             f'stroke="{RULE}" stroke-dasharray="3 3"/>')
    s.append(plate.txt(fx + 10, top - 20, "NO DATE", size=8.5, fill=MUTED, weight="700", spacing="0.9"))

    for i, q in enumerate(rows):
        ry = top + i * RH + RH / 2
        s.append(plate.txt(QX, ry + 4, q["id"], size=10.5, fill=INK2, weight="600"))
        txt = q["text"] if len(q["text"]) <= 50 else q["text"][:47] + "…"
        s.append(plate.txt(TX, ry + 4, txt, size=10.5, fill=INK2))
        if i:
            s.append(f'<line x1="{QX}" y1="{ry-RH/2:.1f}" x2="{PR}" y2="{ry-RH/2:.1f}" stroke="{GRID}"/>')
        if q["at"] is None:
            s.append(f'<circle cx="{fx+30:.1f}" cy="{ry:.1f}" r="5.5" fill="none" '
                     f'stroke="{NODATE}" stroke-width="2"/>')
        else:
            qx = X(q["at"])
            col = NOW if q["at"] <= 0 else SOON
            if q["at"] > 0:                       # the wait, drawn as a wait
                s.append(f'<line x1="{X(0):.1f}" y1="{ry:.1f}" x2="{qx:.1f}" y2="{ry:.1f}" '
                         f'stroke="{FAINT}" stroke-width="2"/>')
            s.append(f'<circle cx="{qx:.1f}" cy="{ry:.1f}" r="5.5" fill="{col}" '
                     f'stroke="{plate.SURFACE}" stroke-width="1.6"/>')

    ky = bot + 44
    # The legend names the SAME unit the axis drew. It said "month" while the
    # hourly repo's axis was in hours.
    for i, (lab, col, fill) in enumerate((("answered from what is already captured", NOW, True),
                                          (f"answerable once the capture reaches that {unit}", SOON, True),
                                          ("not on a clock — needs a method, not more captures", NODATE, False))):
        kx = 28 + i * 286
        s.append(f'<circle cx="{kx+6:.1f}" cy="{ky-4:.1f}" r="5.5" '
                 f'{"fill=\'%s\'" % col if fill else "fill=\'none\' stroke=\'%s\' stroke-width=\'2\'" % col}/>')
        s += plate.wrap(kx + 18, ky, lab, size=9.5, fill=MUTED, chars=34, leading=12)

    sy = ky + 34
    s += plate.halo(28, sy, f"{no} of {len(qs)} questions will not be answered by waiting.",
                    size=12.5, fill=INK)
    s += plate.wrap(28, sy + 19,
        f"{nd} are answered from captures already held and {nn} need"
        f"{'s' if nn == 1 else ''} the series to reach a stated length. The other {no} are open for a different reason — no method, or no field in the "
        f"source that could carry the answer. Waiting does not move them, so they are drawn off "
        f"the axis rather than at the end of it.",
        size=10.5, fill=MUTED, chars=126, leading=13)

    H = int(sy + 19 + 3 * 13 + 74)
    s.append(f'<line x1="28" y1="{H-60:.1f}" x2="{W-28}" y2="{H-60:.1f}" stroke="{RULE}"/>')
    s += plate.wrap(28, H - 44,
        f"Read from this repo, not typed: questions and their status from the README table, cadence "
        f"from registry/, first capture from manifest/. A month is 30.44 days. THIS PLATE MEASURES "
        f"NOTHING ABOUT THE WORLD — it is the capture plan drawn as a plan, and it is wrong the "
        f"moment the table says something the capture does not deliver.",
        size=10, fill=MUTED, chars=134, leading=13)
    s.append("</svg>")
    svg = ("\n".join(s).replace('height="10"', f'height="{H}"')
                       .replace(f'viewBox="0 0 {W} 10"', f'viewBox="0 0 {W} {H}"'))
    assert 'height="10"' not in svg
    out = here.parent / "charts" / "maturity.svg"
    out.write_text(svg, encoding="utf-8")
    print(f"  wrote {out.name}  {len(qs)} questions: {nd} answered, {nn} clocked, {no} no date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
