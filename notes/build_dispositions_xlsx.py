#!/usr/bin/env python3
"""Build a standalone dispositions workbook (and CSV) from notes/dispositions.md.

The tracker (PRISM_Tracker.xlsx) is only READ: its styles.xml and theme are copied so the new sheet matches its
formatting. Nothing is written to the tracker; the author merges the new sheet by hand.

Usage: python build_dispositions_xlsx.py <dispositions.md> <tracker_copy.xlsx> <out.xlsx> [<out.csv>]
"""
import csv
import datetime as dt
import re
import sys
import zipfile
from xml.sax.saxutils import escape

STATUSES = ("Fixed", "Partially fixed", "Not fixed", "No change warranted")
FIELDS = ("Requests", "Changed / rationale", "Evidence", "Remaining", "Suggested response")
HEAD = ("ID", "Reviewer", "Status", "Requests and their dispositions", "What changed, or why the current approach is kept",
        "Supporting evidence", "Remaining work, blocker and pass criterion", "Suggested reviewer response")
WIDTHS = (8, 9, 17, 60, 50, 55, 50, 55)


def parse(md):
    txt = open(md, encoding="utf-8").read()
    rows = []
    for block in re.split(r"^## ", txt, flags=re.M)[1:]:
        head, _, body = block.partition("\n")
        m = re.match(r"(R\d\.(?:\d+|M\d|m\d|R)) \| (.+)$", head.strip())
        if not m:
            continue
        rid, status = m.groups()
        if status not in STATUSES:
            raise ValueError(f"{rid}: bad status {status!r}")
        vals = {}
        for f in FIELDS:
            fm = re.search(r"^- " + re.escape(f) + r": (.+)$", body, re.M)
            if not fm:
                raise ValueError(f"{rid}: missing field {f}")
            vals[f] = fm.group(1).strip()
        rows.append((rid, f"Reviewer {rid[1]}", status) + tuple(vals[f] for f in FIELDS))
    ids = [r[0] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate IDs")
    return rows


def col(i):
    return "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[i]


def cell(ref, text, style):
    return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{escape(str(text))}</t></is></c>'


def sheet_dispositions(rows):
    n = len(rows) + 1
    counts = {s: sum(r[2] == s for r in rows) for s in STATUSES}
    out = ['<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
           f'<dimension ref="A1:K{n}"/>',
           '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" '
           'state="frozen"/><selection pane="bottomLeft" activeCell="A2" sqref="A2"/></sheetView></sheetViews>',
           '<sheetFormatPr defaultRowHeight="15"/><cols>']
    for i, w in enumerate(WIDTHS, 1):
        out.append(f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>')
    out.append('<col min="10" max="10" width="22" customWidth="1"/><col min="11" max="11" width="8" customWidth="1"/>')
    out.append('</cols><sheetData>')
    totals = [("Status totals", "Count")] + [(s, counts[s]) for s in STATUSES] + [("Total", sum(counts.values())),
                                                                                     ("IDs listed", len(rows))]
    for r_i in range(1, n + 1):
        cells = []
        if r_i == 1:
            cells += [cell(f"{col(c)}1", h, 1) for c, h in enumerate(HEAD)]
        else:
            row = rows[r_i - 2]
            cells += [cell(f"{col(c)}{r_i}", v, 2 if c == 0 else 3) for c, v in enumerate(row)]
        if r_i <= len(totals):
            label, val = totals[r_i - 1]
            if r_i == 1:
                cells += [cell(f"J{r_i}", label, 1), cell(f"K{r_i}", val, 1)]
            else:
                cells.append(cell(f"J{r_i}", label, 10))
                if label in STATUSES:
                    f = f'COUNTIF($C$2:$C${n},J{r_i})'
                elif label == "Total":
                    f = "SUM(K2:K5)"
                else:
                    f = f"COUNTA($A$2:$A${n})"
                cells.append(f'<c r="K{r_i}" s="10"><f>{escape(f)}</f><v>{val}</v></c>')
        out.append(f'<row r="{r_i}">' + "".join(cells) + "</row>")
    out.append("</sheetData>")
    out.append(f'<autoFilter ref="A1:H{n}"/>')
    out.append('<dataValidations count="1"><dataValidation type="list" allowBlank="1" showErrorMessage="1" '
               f'sqref="C2:C{n}"><formula1>"{",".join(STATUSES)}"</formula1></dataValidation></dataValidations>')
    out.append('<pageMargins left="0.75" right="0.75" top="1" bottom="1" header="0.5" footer="0.5"/></worksheet>')
    return "".join(out)


def sheet_about(rows, source_note):
    lines = [
        ("PRISM reviewer dispositions", 1),
        (f"Generated {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC from notes/dispositions.md (branch phase-e-review) by notes/build_dispositions_xlsx.py.", 3),
        ("One row per tracker comment ID (73). Status definitions:", 3),
        ("Fixed: all required changes complete and verified; any other request in the row has an evidence-backed rationale.", 3),
        ("Partially fixed: at least one substantive request resolved, another open.", 3),
        ("Not fixed: substantive work or verification remains and no substantive request is resolved.", 3),
        ("No change warranted: fully addressed by a documented rationale, a clarification-only answer or a verified guardrail.", 3),
        ("The manuscript was not edited in this pass: requests whose remedy is manuscript text stay open (proposals in notes/manuscript_proposals.md).", 3),
        ("Figures and provenance: notes/number_audit.md. The Erlang-B relative error and the end-to-end integer-search saving are both 1.92% and unrelated.", 3),
        (source_note, 3),
        ("This file is standalone. PRISM_Tracker.xlsx was read, not modified; merge this sheet into it by hand.", 3),
    ]
    out = ['<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
           f'<dimension ref="A1:A{len(lines)}"/><sheetFormatPr defaultRowHeight="15"/>',
           '<cols><col min="1" max="1" width="140" customWidth="1"/></cols><sheetData>']
    for i, (t, s) in enumerate(lines, 1):
        out.append(f'<row r="{i}">{cell(f"A{i}", t, s)}</row>')
    out.append('</sheetData><pageMargins left="0.75" right="0.75" top="1" bottom="1" header="0.5" footer="0.5"/></worksheet>')
    return "".join(out)


def build(md, tracker, out_xlsx, out_csv=None):
    rows = parse(md)
    tz = zipfile.ZipFile(tracker)          # read only
    styles, theme = tz.read("xl/styles.xml"), tz.read("xl/theme/theme1.xml")
    import hashlib
    src = hashlib.sha256(open(tracker, "rb").read()).hexdigest().upper()
    note = f"Styles and theme copied from the tracker (SHA-256 of the copy read: {src})."
    n = len(rows) + 1
    parts = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '<Override PartName="/xl/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
            '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
            '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
            '</Types>'),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
            '</Relationships>'),
        "xl/workbook.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<bookViews><workbookView activeTab="0"/></bookViews><sheets>'
            '<sheet name="Dispositions" sheetId="1" r:id="rId1"/><sheet name="About" sheetId="2" r:id="rId2"/></sheets>'
            f'<definedNames><definedName name="_xlnm._FilterDatabase" localSheetId="0" hidden="1">Dispositions!$A$1:$H${n}</definedName></definedNames>'
            '<calcPr calcId="124519" fullCalcOnLoad="1"/></workbook>'),
        "xl/_rels/workbook.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>'
            '</Relationships>'),
        "xl/worksheets/sheet1.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + sheet_dispositions(rows),
        "xl/worksheets/sheet2.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + sheet_about(rows, note),
        "docProps/core.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<dc:title>PRISM reviewer dispositions</dc:title><dc:creator>notes/build_dispositions_xlsx.py</dc:creator>'
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ}</dcterms:created>'
            '</cp:coreProperties>'),
        "docProps/app.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
            '<Application>Microsoft Excel</Application></Properties>'),
    }
    with zipfile.ZipFile(out_xlsx, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            z.writestr(name, data if isinstance(data, bytes) else data.encode("utf-8"))
        z.writestr("xl/styles.xml", styles)
        z.writestr("xl/theme/theme1.xml", theme)
    if out_csv:
        with open(out_csv, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(HEAD)
            w.writerows(rows)
    return rows


if __name__ == "__main__":
    rows = build(*sys.argv[1:5])
    print(len(rows), "rows;", {s: sum(r[2] == s for r in rows) for s in STATUSES})
