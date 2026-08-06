# -*- coding: utf-8 -*-
"""Spacious, readable A4 print form — enlarge cells, stop label clipping."""
from pathlib import Path
import re

path = Path(__file__).resolve().parents[1] / "web" / "app.js"
text = path.read_text(encoding="utf-8")

# --- replace from const page = ... through </style> ---
start = text.find("    const page = paperCssSize(paper, orient);")
end = text.find("</style>\n</head>", start)
if start < 0 or end < 0:
    raise SystemExit(f"markers fail {start} {end}")
end = end + len("</style>\n</head>")

new = r'''    const page = paperCssSize(paper, orient);
    const isLand = orient === "landscape";
    const pageMargin = "10mm";
    return `<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8" />
<title>${escapeHtml(formTitle)}</title>
<style>
  @page {
    size: ${page};
    margin: ${pageMargin};
  }
  * { box-sizing: border-box; }
  html, body {
    width: 100%;
    max-width: 100%;
    margin: 0;
    padding: 0;
    background: #fff;
  }
  body {
    font-family: "Malgun Gothic", "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
    color: #0f172a;
    font-size: 10pt;
    line-height: 1.4;
    overflow-x: hidden;
  }
  .sheet {
    width: 100%;
    max-width: 100%;
    min-height: 100%;
    display: flex;
    flex-direction: column;
    gap: 0;
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
    min-height: 0;
  }
  .sheet-foot {
    flex: 0 0 auto;
    margin-top: 10px;
  }
  .title-bar {
    background: #0f172a;
    color: #fff;
    text-align: center;
    padding: 14px 12px 12px;
    margin: 0 0 10px;
    border-radius: 2px;
  }
  .title-bar h1 {
    margin: 0;
    font-size: 18pt;
    font-weight: 700;
    letter-spacing: -0.02em;
  }
  .title-bar p {
    margin: 4px 0 0;
    font-size: 9pt;
    color: #cbd5e1;
    font-weight: 500;
  }
  table.meta, table.trips, table.summary-box, table.sign {
    width: 100%;
    max-width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
  }
  /* 상단 정보 — 칸 넓고 높게 */
  table.meta {
    margin-bottom: 8px;
    font-size: 10pt;
  }
  table.meta col.lab { width: 18%; }
  table.meta col.val { width: 32%; }
  table.meta th, table.meta td {
    border: 1px solid #94a3b8;
    padding: 10px 12px;
    vertical-align: middle;
    height: 38px;
  }
  table.meta th {
    background: #f1f5f9;
    color: #1e293b;
    font-weight: 700;
    text-align: center;
    font-size: 9.5pt;
    letter-spacing: -0.02em;
    white-space: normal;
    word-break: keep-all;
    line-height: 1.25;
  }
  table.meta td {
    background: #fff;
    color: #0f172a;
    font-size: 10.5pt;
    padding-left: 14px;
  }
  table.summary-box {
    margin-bottom: 10px;
    font-size: 10pt;
  }
  table.summary-box th, table.summary-box td {
    border: 1px solid #94a3b8;
    padding: 12px 14px;
    vertical-align: middle;
    min-height: 44px;
  }
  table.summary-box th {
    background: #f1f5f9;
    color: #1e293b;
    font-weight: 700;
    width: 18%;
    text-align: center;
    font-size: 9.5pt;
  }
  table.summary-box td {
    font-size: 10.5pt;
    line-height: 1.45;
  }
  /* 구간 표 — 행 높이 크게, 헤더 또렷하게 */
  table.trips {
    flex: 1 1 auto;
    height: 100%;
    font-size: 9.5pt;
  }
  table.trips thead th {
    background: #1e293b;
    color: #fff;
    font-weight: 700;
    text-align: center;
    padding: 10px 6px;
    border: 1px solid #334155;
    font-size: 9.5pt;
  }
  table.trips tbody {
    height: 100%;
  }
  table.trips tbody tr {
    height: calc((100% - 0px) / var(--trip-rows, 12));
    min-height: 28px;
  }
  table.trips td {
    border: 1px solid #94a3b8;
    padding: 8px 6px;
    vertical-align: middle;
    word-break: keep-all;
    overflow-wrap: anywhere;
  }
  table.trips tr.zebra td { background: #f8fafc; }
  table.trips tr.blank td {
    color: transparent;
    background: #fff;
  }
  table.trips tr.blank.zebra td { background: #f8fafc; }
  table.trips td.c { text-align: center; }
  table.trips tr.total td {
    background: #eef2ff;
    font-weight: 700;
    border-top: 2px solid #0f172a;
    padding: 10px 6px;
    height: 36px;
    color: #0f172a;
  }
  table.sign {
    width: 52%;
    max-width: 280px;
    margin-left: auto;
    font-size: 10pt;
  }
  table.sign th, table.sign td {
    border: 1px solid #94a3b8;
    padding: 8px 10px;
    text-align: center;
  }
  table.sign th {
    background: #f1f5f9;
    color: #1e293b;
    font-weight: 700;
  }
  table.sign td {
    height: 52px;
    color: #94a3b8;
    font-size: 9.5pt;
  }
  .foot {
    margin-top: 8px;
    font-size: 8pt;
    color: #64748b;
    text-align: right;
  }
  @media print {
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
  }
  @media screen {
    body {
      background: #e2e8f0;
      padding: 16px;
    }
    .sheet {
      background: #fff;
      width: ${isLand ? "297mm" : "210mm"};
      height: ${isLand ? "210mm" : "297mm"};
      min-height: ${isLand ? "210mm" : "297mm"};
      max-width: 100%;
      margin: 0 auto;
      padding: 12mm 11mm;
      box-sizing: border-box;
      box-shadow: 0 8px 32px rgba(15, 23, 42, 0.14);
    }
  }
</style>
</head>'''

text = text[:start] + new + text[end:]

# Meta table: add colgroup + shorter clear labels that still read professionally
old_meta = """  <table class="meta">
    <tr>
      <th>작성일</th><td>${escapeHtml(String(log.date || "—"))}</td>
      <th>차량번호</th><td>${escapeHtml(String(log.vehicle || "—"))}</td>
    </tr>
    <tr>
      <th>운전자</th><td>${escapeHtml(String(log.driver_name || "—"))}</td>
      <th>회사명</th><td>${escapeHtml(String(log.company_name || "—"))}</td>
    </tr>
    <tr>
      <th>누적 주행거리</th><td>${escapeHtml(odoTxt)}</td>
      <th>총 운행거리</th><td>${escapeHtml(distTotal ? distTotal + " km" : "—")}</td>
    </tr>
    <tr>
      <th>총 운행시간</th><td>${escapeHtml(String(netDur))}</td>
      <th>주유</th><td>${escapeHtml(fuelTxt)}</td>
    </tr>
  </table>
  <table class="summary-box">
    <tr>
      <th>운행 요약</th>
      <td>${escapeHtml(String(log.summary || ""))}</td>
    </tr>
  </table>"""

new_meta = """  <table class="meta">
    <colgroup>
      <col class="lab" /><col class="val" /><col class="lab" /><col class="val" />
    </colgroup>
    <tr>
      <th>작성일</th><td>${escapeHtml(String(log.date || "—"))}</td>
      <th>차량번호</th><td>${escapeHtml(String(log.vehicle || "—"))}</td>
    </tr>
    <tr>
      <th>운전자</th><td>${escapeHtml(String(log.driver_name || "—"))}</td>
      <th>회사명</th><td>${escapeHtml(String(log.company_name || "—"))}</td>
    </tr>
    <tr>
      <th>누적거리</th><td>${escapeHtml(odoTxt)}</td>
      <th>총 거리</th><td>${escapeHtml(distTotal ? distTotal + " km" : "—")}</td>
    </tr>
    <tr>
      <th>운행시간</th><td>${escapeHtml(String(netDur))}</td>
      <th>주유</th><td>${escapeHtml(fuelTxt)}</td>
    </tr>
  </table>
  <table class="summary-box">
    <tr>
      <th>운행 요약</th>
      <td>${escapeHtml(String(log.summary || ""))}</td>
    </tr>
  </table>"""

if old_meta not in text:
    raise SystemExit("meta block not found")
text = text.replace(old_meta, new_meta, 1)

# Trip header labels slightly clearer
text = text.replace(
    """        <th>출발</th>
        <th>도착</th>
        <th>출발지</th>
        <th>도착지</th>
        <th>목적</th>
        <th>거리</th>
        <th>시간</th>
        <th>비고</th>""",
    """        <th>출발시각</th>
        <th>도착시각</th>
        <th>출발지</th>
        <th>도착지</th>
        <th>운행목적</th>
        <th>거리(km)</th>
        <th>운행시간</th>
        <th>비고</th>""",
    1,
)

# Wider place columns in colgroup
text = text.replace(
    """    <colgroup>
      <col style="width:5%" />
      <col style="width:8%" />
      <col style="width:8%" />
      <col style="width:17%" />
      <col style="width:17%" />
      <col style="width:12%" />
      <col style="width:7%" />
      <col style="width:10%" />
      <col style="width:16%" />
    </colgroup>""",
    """    <colgroup>
      <col style="width:5%" />
      <col style="width:9%" />
      <col style="width:9%" />
      <col style="width:16%" />
      <col style="width:16%" />
      <col style="width:13%" />
      <col style="width:8%" />
      <col style="width:11%" />
      <col style="width:13%" />
    </colgroup>""",
    1,
)

# Bigger signature
text = text.replace(
    """  <table class="sign">
    <tr><th>작성자</th><th>확인자</th></tr>
    <tr><td>(서명)</td><td>(서명)</td></tr>
  </table>""",
    """  <table class="sign">
    <tr><th>작성자</th><th>확인자</th></tr>
    <tr><td>( 서 명 )</td><td>( 서 명 )</td></tr>
  </table>""",
    1,
)

path.write_text(text, encoding="utf-8", newline="\n")
print("print spacious ok")
