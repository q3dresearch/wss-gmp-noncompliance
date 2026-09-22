"""Parser for schema_id `gmpnc.v1` — EudraGMDP GMP non-compliance statements.

WHAT MOVES HERE IS NOT A NUMBER

This register has eleven columns in its HTML and not one of them is a status.
A statement that is resolved, withdrawn or superseded has nowhere to be marked
so -- it must either be edited in place or leave the register. Both are silent.
The backfill already showed the second happening: 56 of 64 report numbers
visible in Wayback captures are absent from the 79 the register lists today,
and a search with fromDate=2013-01-01 returns none of them.

So the observation is *a statement being listed*, and the two things worth
recording against it are that it was there at all and when the publisher last
touched it.

  listed           1 on every capture. Its ABSENCE in a later capture is the
                   finding -- a statement that stops being emitted has been
                   removed from the register, and the bytes proving it was
                   there are in the archive.
  last_updated_at  the publisher's own edit stamp. This is what makes an
                   IN-PLACE edit visible, and it is the single reason the .xls
                   export is parsed instead of the HTML: the HTML does not
                   carry it. Populated on all 79 rows, 68 distinct values.

THE EXPORT, NOT THE PAGES. `action=ExportList` returns the whole register in
one .xls with 17 columns against the HTML's 11, adding Last Updated Date, DUNS
Number, Site NCA Reference and a four-field address. The capture also stores
the 8 HTML pages as a second representation for auditing, and this parser
yields NOTHING for them -- parsing both would double every statement. Their
bytes are in the archive if that ever needs revisiting.

THE KEY IS A PAIR. `(Report Number, EudraGMDP Document Reference Number)`.
Report Number alone is not unique: 79 rows carry 71 report numbers because one
report can name several sites. Keying on it alone manufactures six permanent
phantom revisions.

IDENTIFIERS ARE EMITTED AS METRICS because they are join keys, not decoration.
OMS Location Identifier and DUNS Number are how a site here is matched to a
site in another register, and a value that is present in one capture and blank
in the next is itself a change worth seeing.
"""
import io

from wss import derive

PARSER_VERSION = "1"
SCHEMA_ID = "gmpnc.v1"

# Column in the export -> metric name. Everything here is a string value; the
# register carries no quantities.
FIELDS = {
    "Last Updated Date": "last_updated_at",
    "Issue Date": "issued_at",
    "Inspection End Date": "inspection_ended_at",
    "Country": "country",
    "City": "city",
    "Site Name": "site_name",
    "OMS Location Identifier": "oms_location_id",
    "DUNS Number": "duns_number",
    "MIA Number": "mia_number",
    "Site NCA Reference": "site_nca_reference",
}


def _cell(sheet, r, c):
    v = sheet.cell_value(r, c)
    if isinstance(v, float) and v == int(v):
        v = int(v)          # xlrd hands back 187173.0 for a reference number
    return str(v).strip()


def parse(body: bytes, ctx: derive.ParseContext):
    # The 8 HTML pages are a second representation of the same statements;
    # yielding for them would double every row.
    if not ctx.raw_ref.split("?")[0].rstrip(".gz").endswith(".xls"):
        return

    import xlrd        # legacy BIFF: neither the stdlib nor openpyxl reads it

    sheet = xlrd.open_workbook(file_contents=body).sheet_by_index(0)
    header = None
    for r in range(sheet.nrows):
        row = [_cell(sheet, r, c) for c in range(sheet.ncols)]
        if header is None:
            if "Report Number" in row:
                header = {name: i for i, name in enumerate(row) if name}
            continue
        report = row[header["Report Number"]] if "Report Number" in header else ""
        doc = (row[header["EudraGMDP Document Reference Number"]]
               if "EudraGMDP Document Reference Number" in header else "")
        if not report:
            continue                      # trailing blank rows and the footer
        entity = f"{report}:{doc}" if doc else report

        yield derive.Observation(entity_id=entity, metric="listed", value=1, unit="count")
        for column, metric in FIELDS.items():
            if column not in header:
                continue                  # the export gained or lost a column
            value = row[header[column]]
            if value:
                yield derive.Observation(entity_id=entity, metric=metric, value=value)


derive.register(SCHEMA_ID, parse, PARSER_VERSION)
