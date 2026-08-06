# -*- coding: utf-8 -*-
"""Make print sheet fill full A4 even with blank trip rows."""
from pathlib import Path
import re

path = Path(__file__).resolve().parents[1] / "web" / "app.js"
text = path.read_text(encoding="utf-8")

old_sheet_css = """  .sheet {
    width: 100%;
    max-width: 100%;
  }"""
new_sheet_css = """  .sheet {
    width: 100%;
    max-width: 100%;
    min-height: 100%;
    display: flex;
    flex-direction: column;
  }
  .sheet-body {
    flex: 1 1 auto;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
  .trips-wrap {
    flex: 1 1 auto;
    display: flex;
    flex-direction: column;
    min-height: 120px;
  }
  table.trips {
    flex: 1 1 auto;
    height: 100%;
  }
  table.trips tbody {
    height: 100%;
  }
  table.trips tbody tr {
    height: calc(100% / var(--trip-rows, 12));
  }
  table.trips tr.blank td {
    color: transparent;
  }
  .sheet-foot {
    flex: 0 0 auto;
    margin-top: 8px;
  }"""
if old_sheet_css not in text:
    raise SystemExit("sheet css not found")
text = text.replace(old_sheet_css, new_sheet_css, 1)

old_print = """  @media print {
    html, body {
      width: 100%;
      height: auto;
      margin: 0 !important;
      padding: 0 !important;
    }
    body {
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }
    .sheet { page-break-inside: auto; }
    table.trips tr { page-break-inside: avoid; }
    .no-print { display: none !important; }
  }"""
new_print = """  @media print {
    html, body {
      width: 100%;
      height: 100%;
      margin: 0 !important;
      padding: 0 !important;
    }
    body {
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
      height: 100%;
    }
    .sheet {
      min-height: calc(100vh - 0.1px);
      height: 100%;
      page-break-inside: avoid;
      box-sizing: border-box;
    }
    table.trips tr { page-break-inside: avoid; }
    .no-print { display: none !important; }
  }"""
if old_print not in text:
    raise SystemExit("print media not found")
text = text.replace(old_print, new_print, 1)

# screen sheet size → fixed A4 box height
text2, n = re.subn(
    r"""    \.sheet \{\n      background: #fff;\n      width: \$\{isLand \? "297mm" : "210mm"\};\n      min-height: \$\{isLand \? "210mm" : "297mm"\};\n      max-width: 100%;\n      margin: 0 auto;\n      padding: 8mm;\n      box-shadow: 0 4px 24px rgba\(15, 23, 42, 0\.12\);\n    \}""",
    """    .sheet {
      background: #fff;
      width: ${isLand ? "297mm" : "210mm"};
      height: ${isLand ? "210mm" : "297mm"};
      min-height: ${isLand ? "210mm" : "297mm"};
      max-width: 100%;
      margin: 0 auto;
      padding: 8mm;
      box-sizing: border-box;
      box-shadow: 0 4px 24px rgba(15, 23, 42, 0.12);
    }""",
    text,
    count=1,
)
if n != 1:
    raise SystemExit(f"screen sheet css replace failed n={n}")
text = text2

old_body = """  <div class=\"sheet\">
  <div class=\"title-bar\">"""
new_body = """  <div class=\"sheet\" style=\"--trip-rows: ${nTripRows}\">
  <div class=\"title-bar\">"""
if old_body not in text:
    raise SystemExit("body open not found")
text = text.replace(old_body, new_body, 1)

old_trips = """  <table class=\"trips\">"""
new_trips = """  <div class=\"sheet-body\"><div class=\"trips-wrap\">
  <table class=\"trips\">"""
if old_trips not in text:
    raise SystemExit("trips table not found")
text = text.replace(old_trips, new_trips, 1)

old_sign = """  <table class=\"sign\">"""
new_sign = """  </div>
  <div class=\"sheet-foot\">
  <table class=\"sign\">"""
if old_sign not in text:
    raise SystemExit("sign not found")
text = text.replace(old_sign, new_sign, 1)

old_end = """  <div class=\"foot no-print\">미리보기 · ${escapeHtml(paper)} ${isLand ? \"가로\" : \"세로\"} · 인쇄 시 여백 최소 권장</div>
  </div>"""
new_end = """  <div class=\"foot no-print\">미리보기 · ${escapeHtml(paper)} ${isLand ? \"가로\" : \"세로\"} · A4 꽉 채움</div>
  </div></div>
  </div>"""
if old_end not in text:
    raise SystemExit("end not found")
text = text.replace(old_end, new_end, 1)

path.write_text(text, encoding="utf-8", newline="\n")
print("ok full-page fill")
