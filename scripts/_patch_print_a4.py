# -*- coding: utf-8 -*-
"""Patch buildPrintHtml in web/app.js for A4-fit print layout."""
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "web" / "app.js"
text = path.read_text(encoding="utf-8")
start = text.find("    const page = paperCssSize(paper, orient);\n    return `<!DOCTYPE html>")
end = text.find("  function openPrint(previewOnly)", start)
if start < 0 or end < 0:
    raise SystemExit(f"markers not found start={start} end={end}")

new = r'''    const page = paperCssSize(paper, orient);
    const isLand = orient === "landscape";
    const pageMargin = "8mm";
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
    font-size: ${isLand ? "9pt" : "8.5pt"};
    line-height: 1.35;
    overflow-x: hidden;
  }
  .sheet {
    width: 100%;
    max-width: 100%;
  }
  .title-bar {
    background: #0f172a;
    color: #fff;
    text-align: center;
    padding: ${isLand ? "8px 8px 7px" : "9px 8px 8px"};
    margin: 0 0 6px;
  }
  .title-bar h1 {
    margin: 0;
    font-size: ${isLand ? "13pt" : "14pt"};
    font-weight: 700;
    letter-spacing: -0.02em;
  }
  .title-bar p {
    margin: 2px 0 0;
    font-size: 7.5pt;
    color: #cbd5e1;
    font-weight: 500;
  }
  table.meta, table.trips, table.summary-box, table.sign {
    width: 100%;
    max-width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
  }
  table.meta {
    margin-bottom: 5px;
    font-size: ${isLand ? "8.5pt" : "8pt"};
  }
  table.meta th, table.meta td {
    border: 1px solid #cbd5e1;
    padding: 4px 5px;
    vertical-align: middle;
    word-break: keep-all;
    overflow-wrap: anywhere;
  }
  table.meta th {
    background: #f1f5f9;
    color: #334155;
    font-weight: 700;
    width: 15%;
    text-align: center;
    white-space: nowrap;
  }
  table.meta td { width: 35%; }
  table.summary-box {
    margin-bottom: 6px;
    font-size: ${isLand ? "8.5pt" : "8pt"};
  }
  table.summary-box th, table.summary-box td {
    border: 1px solid #cbd5e1;
    padding: 5px 6px;
    vertical-align: middle;
    word-break: keep-all;
    overflow-wrap: anywhere;
  }
  table.summary-box th {
    background: #f1f5f9;
    color: #334155;
    font-weight: 700;
    width: 15%;
    text-align: center;
  }
  table.trips {
    font-size: ${isLand ? "8pt" : "7.5pt"};
    margin-bottom: 2px;
  }
  table.trips th, table.trips td {
    border: 1px solid #cbd5e1;
    padding: 3px 3px;
    vertical-align: middle;
    word-break: keep-all;
    overflow-wrap: anywhere;
  }
  table.trips th {
    background: #1e293b;
    color: #fff;
    font-weight: 700;
    text-align: center;
  }
  table.trips tr.zebra td { background: #f8fafc; }
  table.trips td.c { text-align: center; }
  table.trips tr.total td {
    background: #eef2ff;
    font-weight: 700;
    border-top: 1.5px solid #0f172a;
  }
  table.sign {
    width: 42%;
    max-width: 200px;
    margin-left: auto;
    margin-top: 10px;
    font-size: 8pt;
  }
  table.sign th, table.sign td {
    border: 1px solid #cbd5e1;
    padding: 4px 6px;
    text-align: center;
  }
  table.sign th {
    background: #f1f5f9;
    color: #334155;
    font-weight: 700;
  }
  table.sign td {
    height: 36px;
    color: #94a3b8;
  }
  .foot {
    margin-top: 6px;
    font-size: 7pt;
    color: #64748b;
    text-align: right;
  }
  @media print {
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
  }
  @media screen {
    body {
      background: #e2e8f0;
      padding: 12px;
    }
    .sheet {
      background: #fff;
      width: ${isLand ? "297mm" : "210mm"};
      min-height: ${isLand ? "210mm" : "297mm"};
      max-width: 100%;
      margin: 0 auto;
      padding: 8mm;
      box-shadow: 0 4px 24px rgba(15, 23, 42, 0.12);
    }
  }
</style>
</head>
<body>
  <div class="sheet">
  <div class="title-bar">
    <h1>${escapeHtml(formTitle)}</h1>
    <p>업무용 차량 운행 기록 · 제출용 · ${escapeHtml(paper || "A4")}</p>
  </div>
  <table class="meta">
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
  </table>
  <table class="trips">
    <colgroup>
      <col style="width:5%" />
      <col style="width:8%" />
      <col style="width:8%" />
      <col style="width:17%" />
      <col style="width:17%" />
      <col style="width:12%" />
      <col style="width:7%" />
      <col style="width:10%" />
      <col style="width:16%" />
    </colgroup>
    <thead>
      <tr>
        <th>순번</th>
        <th>출발</th>
        <th>도착</th>
        <th>출발지</th>
        <th>도착지</th>
        <th>목적</th>
        <th>거리</th>
        <th>시간</th>
        <th>비고</th>
      </tr>
    </thead>
    <tbody>
      ${
        rows ||
        `<tr><td colspan="9" style="text-align:center;padding:12px;color:#64748b">운행 구간 없음</td></tr>`
      }
      <tr class="total">
        <td class="c">합계</td>
        <td></td><td></td><td></td><td></td><td></td>
        <td class="c">${escapeHtml(distTotal)}</td>
        <td class="c">${escapeHtml(String(netDur === "—" ? "" : netDur))}</td>
        <td></td>
      </tr>
    </tbody>
  </table>
  <table class="sign">
    <tr><th>작성자</th><th>확인자</th></tr>
    <tr><td>(서명)</td><td>(서명)</td></tr>
  </table>
  <div class="foot no-print">미리보기 · ${escapeHtml(paper)} ${isLand ? "가로" : "세로"} · 인쇄 시 여백 최소 권장</div>
  </div>
  <script>
    window.onload = function () {
      setTimeout(function () { window.focus(); window.print(); }, 250);
    };
  <\/script>
</body>
</html>`;
'''

path.write_text(text[:start] + new + text[end:], encoding="utf-8", newline="\n")
print("ok", "old", end - start, "new", len(new))
