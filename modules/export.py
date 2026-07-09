"""
운행일지 내보내기: Excel / PDF / DOCX (한컴 호환)
⚠️ 워터마크 절대 금지 — Free/Pro 모두 완전 클린 문서 (회사 제출 가능)
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

import pandas as pd

from modules.validator import format_minutes_kr


# ────────────────────────────────────────────────────────
# 공통 헬퍼
# ────────────────────────────────────────────────────────


def _trips_dataframe(log: dict) -> pd.DataFrame:
    rows = []
    for i, t in enumerate(log.get("trips") or [], start=1):
        rows.append(
            {
                "순번": i,
                "출발시각": t.get("depart_time", ""),
                "도착시각": t.get("arrive_time", ""),
                "출발지": t.get("from", ""),
                "도착지": t.get("to", ""),
                "운행목적": t.get("purpose", ""),
                "거리(km)": t.get("distance_km", ""),
                "순수운행": t.get("duration_display", ""),
                "점심제외(분)": t.get("lunch_excluded_minutes", 0),
                "비고": t.get("memo", ""),
            }
        )
    return pd.DataFrame(rows)


def _meta(log: dict) -> dict[str, str]:
<<<<<<< HEAD
    meta = {
=======
    return {
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
        "작성일": str(log.get("date") or datetime.now().strftime("%Y-%m-%d")),
        "차량번호": str(log.get("vehicle") or ""),
        "운전자": str(log.get("driver_name") or ""),
        "회사명": str(log.get("company_name") or ""),
<<<<<<< HEAD
        "최초 누적(km)": str(log.get("odometer_start") if log.get("odometer_start") is not None else ""),
        "종료 누적(km)": str(log.get("odometer_end") if log.get("odometer_end") is not None else ""),
        "총 거리(km)": str(log.get("total_distance_km") or ""),
        "총 운행시간": format_minutes_kr(int(log.get("total_net_minutes") or 0)),
        "점심 제외시간": format_minutes_kr(int(log.get("total_lunch_excluded_minutes") or 0)),
        "점심 장소": str(log.get("lunch_place") or ""),
        "요약": str(log.get("summary") or ""),
    }
    return meta
=======
        "총 거리(km)": str(log.get("total_distance_km") or ""),
        "총 운행시간": format_minutes_kr(int(log.get("total_net_minutes") or 0)),
        "점심 제외시간": format_minutes_kr(int(log.get("total_lunch_excluded_minutes") or 0)),
        "요약": str(log.get("summary") or ""),
    }
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)


def _filename_base(log: dict) -> str:
    d = str(log.get("date") or datetime.now().strftime("%Y-%m-%d")).replace("-", "")
    v = str(log.get("vehicle") or "vehicle").replace(" ", "")
    return f"운행일지_{d}_{v}"


# ────────────────────────────────────────────────────────
# Excel (클린 — 워터마크 없음)
# ────────────────────────────────────────────────────────


def export_excel(log: dict) -> tuple[bytes, str]:
    """openpyxl 기반 .xlsx — 회사 제출용 서식."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "운행일지"

    navy = "0B1F3A"
    teal = "0D9488"
    thin = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )
    header_fill = PatternFill("solid", fgColor=navy)
    header_font = Font(bold=True, color="FFFFFF", name="맑은 고딕", size=11)
    title_font = Font(bold=True, color=navy, name="맑은 고딕", size=16)
    label_font = Font(bold=True, name="맑은 고딕", size=10)
    cell_font = Font(name="맑은 고딕", size=10)
    accent_fill = PatternFill("solid", fgColor="F0FDFA")

    # 제목
    ws.merge_cells("A1:J1")
    ws["A1"] = "차량 운행일지"
    ws["A1"].font = title_font
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 32

    meta = _meta(log)
    # 메타 정보 2~3행
    meta_items = [
        ("작성일", meta["작성일"]),
        ("차량번호", meta["차량번호"]),
        ("운전자", meta["운전자"]),
        ("회사명", meta["회사명"]),
        ("총 거리(km)", meta["총 거리(km)"]),
        ("총 운행시간", meta["총 운행시간"]),
    ]
    row = 3
    col = 1
    for label, val in meta_items:
        cell_l = ws.cell(row=row, column=col, value=label)
        cell_v = ws.cell(row=row, column=col + 1, value=val)
        cell_l.font = label_font
        cell_v.font = cell_font
        cell_l.fill = accent_fill
        for c in (cell_l, cell_v):
            c.border = thin
            c.alignment = Alignment(vertical="center")
        col += 2
        if col > 6:
            col = 1
            row += 1

    row = 6
    ws.cell(row=row, column=1, value="운행 요약").font = label_font
    ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=6)
    ws.cell(row=row, column=2, value=meta["요약"]).font = cell_font

    # 테이블 헤더
    headers = [
        "순번",
        "출발시각",
        "도착시각",
        "출발지",
        "도착지",
        "운행목적",
        "거리(km)",
        "순수운행",
        "점심제외(분)",
        "비고",
    ]
    header_row = 8
    for i, h in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=i, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin

    df = _trips_dataframe(log)
    for r_idx, rec in enumerate(df.to_dict(orient="records"), start=1):
        for c_idx, h in enumerate(headers, start=1):
            val = rec.get(h, "")
            cell = ws.cell(row=header_row + r_idx, column=c_idx, value=val)
            cell.font = cell_font
            cell.border = thin
            cell.alignment = Alignment(
                horizontal="center" if c_idx in (1, 2, 3, 7, 9) else "left",
                vertical="center",
                wrap_text=True,
            )

    # 합계 행
    total_row = header_row + len(df) + 1
    ws.cell(row=total_row, column=1, value="합계").font = label_font
    ws.cell(row=total_row, column=7, value=log.get("total_distance_km", "")).font = label_font
    for c in range(1, 11):
        ws.cell(row=total_row, column=c).border = thin
        ws.cell(row=total_row, column=c).fill = accent_fill

    # 서명란 (클린 — 워터마크/서비스명 없음)
    sig_row = total_row + 3
    ws.cell(row=sig_row, column=7, value="작성자: _______________").font = cell_font
    ws.cell(row=sig_row + 1, column=7, value="확인자: _______________").font = cell_font

    widths = [6, 10, 10, 16, 16, 14, 10, 12, 12, 18]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # ⚠️ 워터마크/헤더서비스명/푸터 광고 문구 일절 넣지 않음
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), f"{_filename_base(log)}.xlsx"


# ────────────────────────────────────────────────────────
# PDF (클린 — 워터마크 없음)
# ────────────────────────────────────────────────────────


def export_pdf(log: dict) -> tuple[bytes, str]:
    """reportlab PDF. 한글은 시스템 폰트 또는 내장 대체."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    font_name = _register_korean_font()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="차량 운행일지",  # 문서 메타 — 서비스 워터마크 아님
        author=str(log.get("driver_name") or ""),
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "KRTitle",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=18,
        textColor=colors.HexColor("#0B1F3A"),
        alignment=TA_CENTER,
        spaceAfter=12,
    )
    body = ParagraphStyle(
        "KRBody",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#0F172A"),
    )
    small = ParagraphStyle(
        "KRSmall",
        parent=body,
        fontSize=9,
        textColor=colors.HexColor("#334155"),
    )

    meta = _meta(log)
    story: list[Any] = []
    story.append(Paragraph("차량 운행일지", title_style))
    story.append(Spacer(1, 4 * mm))

    meta_data = [
        [
            Paragraph(f"<b>작성일</b>  {meta['작성일']}", body),
            Paragraph(f"<b>차량번호</b>  {meta['차량번호']}", body),
        ],
        [
            Paragraph(f"<b>운전자</b>  {meta['운전자']}", body),
            Paragraph(f"<b>회사명</b>  {meta['회사명']}", body),
        ],
        [
            Paragraph(f"<b>총 거리</b>  {meta['총 거리(km)']} km", body),
            Paragraph(f"<b>총 운행시간</b>  {meta['총 운행시간']}", body),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[90 * mm, 90 * mm])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0FDFA")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#0D9488")),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#99F6E4")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"<b>운행 요약</b>  {meta['요약']}", body))
    story.append(Spacer(1, 5 * mm))

    # 본문 테이블
    headers = ["순번", "출발", "도착", "출발지", "도착지", "목적", "km", "운행", "비고"]
    data = [[Paragraph(f"<b>{h}</b>", small) for h in headers]]
    for i, t in enumerate(log.get("trips") or [], start=1):
        data.append(
            [
                Paragraph(str(i), small),
                Paragraph(str(t.get("depart_time", "")), small),
                Paragraph(str(t.get("arrive_time", "")), small),
                Paragraph(str(t.get("from", "")), small),
                Paragraph(str(t.get("to", "")), small),
                Paragraph(str(t.get("purpose", "")), small),
                Paragraph(str(t.get("distance_km", "")), small),
                Paragraph(str(t.get("duration_display", "")), small),
                Paragraph(str(t.get("memo", "")), small),
            ]
        )

    col_w = [12 * mm, 14 * mm, 14 * mm, 28 * mm, 28 * mm, 24 * mm, 14 * mm, 20 * mm, 26 * mm]
    table = Table(data, colWidths=col_w, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B1F3A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    # 헤더 Paragraph가 흰색이어야 함
    for cell in data[0]:
        pass  # Paragraph 색은 스타일로 제어 어려워 배경만 navy

    story.append(table)
    story.append(Spacer(1, 12 * mm))
    story.append(Paragraph("작성자: ________________    확인자: ________________", body))
    # ⚠️ 워터마크 / "Powered by" / 서비스 로고 텍스트 없음

    doc.build(story)
    return buf.getvalue(), f"{_filename_base(log)}.pdf"


def _register_korean_font() -> str:
    """Windows/Mac/Linux 한글 폰트 등록. 실패 시 Helvetica."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os

    candidates = [
        # Windows
        r"C:\Windows\Fonts\malgun.ttf",
        r"C:\Windows\Fonts\malgunbd.ttf",
        r"C:\Windows\Fonts\NanumGothic.ttf",
        # macOS
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/Library/Fonts/AppleGothic.ttf",
        # Linux
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                name = "KRFont"
                pdfmetrics.registerFont(TTFont(name, path, subfontIndex=0))
                return name
            except Exception:
                continue
    return "Helvetica"


# ────────────────────────────────────────────────────────
# DOCX (한컴 오피스 호환 — 클린)
# ────────────────────────────────────────────────────────


def export_docx(log: dict) -> tuple[bytes, str]:
    """
    python-docx 기반 .docx
    한글과 컴퓨터(한컴) 오피스에서 정상 개방되는 표준 OOXML.
    워터마크/머리글 광고 없음.
    """
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    doc = Document()

    # 여백
    for section in doc.sections:
        section.top_margin = Cm(1.8)
        section.bottom_margin = Cm(1.8)
        section.left_margin = Cm(1.8)
        section.right_margin = Cm(1.8)

    def set_run_font(run, size=10, bold=False, color=None, font="맑은 고딕"):
        run.bold = bold
        run.font.size = Pt(size)
        run.font.name = font
        r = run._element
        r.rPr.rFonts.set(qn("w:eastAsia"), font)
        if color:
            run.font.color.rgb = RGBColor(*color)

    # 제목
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tr = title.add_run("차량 운행일지")
    set_run_font(tr, size=18, bold=True, color=(11, 31, 58))

    meta = _meta(log)
    info = doc.add_paragraph()
    ir = info.add_run(
        f"작성일: {meta['작성일']}    차량번호: {meta['차량번호']}    "
        f"운전자: {meta['운전자']}    회사명: {meta['회사명']}"
    )
    set_run_font(ir, size=10)

    info2 = doc.add_paragraph()
    ir2 = info2.add_run(
        f"총 거리: {meta['총 거리(km)']} km    총 운행시간: {meta['총 운행시간']}    "
        f"점심 제외: {meta['점심 제외시간']}"
    )
    set_run_font(ir2, size=10)

    sum_p = doc.add_paragraph()
    sr = sum_p.add_run(f"운행 요약: {meta['요약']}")
    set_run_font(sr, size=10, bold=True)

    # 표
    headers = [
        "순번",
        "출발시각",
        "도착시각",
        "출발지",
        "도착지",
        "운행목적",
        "거리(km)",
        "순수운행",
        "비고",
    ]
    trips = log.get("trips") or []
    table = doc.add_table(rows=1 + len(trips), cols=len(headers))
    table.style = "Table Grid"

    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        run = p.add_run(h)
        set_run_font(run, size=9, bold=True, color=(255, 255, 255))
        # 헤더 배경 (navy)
        _set_cell_shading(cell, "0B1F3A")

    for r_idx, t in enumerate(trips):
        vals = [
            str(r_idx + 1),
            str(t.get("depart_time", "")),
            str(t.get("arrive_time", "")),
            str(t.get("from", "")),
            str(t.get("to", "")),
            str(t.get("purpose", "")),
            str(t.get("distance_km", "")),
            str(t.get("duration_display", "")),
            str(t.get("memo", "")),
        ]
        for c_idx, val in enumerate(vals):
            cell = table.rows[r_idx + 1].cells[c_idx]
            cell.text = ""
            p = cell.paragraphs[0]
            run = p.add_run(val)
            set_run_font(run, size=9)

    doc.add_paragraph()
    sig = doc.add_paragraph()
    sig.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    srun = sig.add_run("작성자: _______________      확인자: _______________")
    set_run_font(srun, size=10)

    # ⚠️ 워터마크 / 머리글 / 바닥글 서비스 문구 없음 (한컴 호환 클린 문서)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue(), f"{_filename_base(log)}.docx"


def _set_cell_shading(cell, hex_color: str) -> None:
    """셀 배경색 설정 (OOXML)."""
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), hex_color)
    shd.set(qn("w:val"), "clear")
    tcPr.append(shd)


# ────────────────────────────────────────────────────────
<<<<<<< HEAD
# 메모리 전용 빌더 (서버 디스크 저장 없음)
# ────────────────────────────────────────────────────────


def build_excel_bytes(log: dict) -> tuple[bytes, str]:
    """
    Excel (.xlsx) — 메모리에서 생성.
    openpyxl 서식 + pandas DataFrame 구간 데이터 기반.
    디스크에 파일을 쓰지 않음.
    """
    return export_excel(log)


def build_excel_bytes_pandas(log: dict) -> tuple[bytes, str]:
    """
    pandas 전용 간단 Excel (참고용/폴백).
    BytesIO 만 사용 — 서버 저장 없음.
    """
    import io

    df = _trips_dataframe(log)
    meta = _meta(log)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # 요약 시트
        meta_df = pd.DataFrame([{"항목": k, "내용": v} for k, v in meta.items()])
        meta_df.to_excel(writer, sheet_name="요약", index=False)
        # 구간 시트
        if df.empty:
            pd.DataFrame(columns=["순번", "출발시각", "도착시각", "출발지", "도착지"]).to_excel(
                writer, sheet_name="운행구간", index=False
            )
        else:
            df.to_excel(writer, sheet_name="운행구간", index=False)
    return buf.getvalue(), f"{_filename_base(log)}.xlsx"


def build_pdf_bytes(log: dict) -> tuple[bytes, str]:
    """PDF — reportlab, 한글 폰트(맑은고딕) 자동, 메모리 전용."""
    return export_pdf(log)


def build_docx_bytes(log: dict) -> tuple[bytes, str]:
    """DOCX — python-docx 회사 양식형, 메모리 전용."""
    return export_docx(log)


def build_all_download_files(log: dict) -> dict[str, Any]:
    """
    세 형식을 한 번에 메모리에서 생성.
    반환: {
      "excel": (bytes, filename) | None,
      "pdf": ...,
      "docx": ...,
      "errors": {"excel": str, ...}
    }
    """
    out: dict[str, Any] = {
        "excel": None,
        "pdf": None,
        "docx": None,
        "errors": {},
    }
    try:
        out["excel"] = build_excel_bytes(log)
    except Exception as e:
        # 폴백: pandas 간단 엑셀
        try:
            out["excel"] = build_excel_bytes_pandas(log)
        except Exception as e2:
            out["errors"]["excel"] = f"{e} / fallback: {e2}"
    try:
        out["pdf"] = build_pdf_bytes(log)
    except Exception as e:
        out["errors"]["pdf"] = str(e)
    try:
        out["docx"] = build_docx_bytes(log)
    except Exception as e:
        out["errors"]["docx"] = str(e)
    return out


# ────────────────────────────────────────────────────────
# Streamlit 다운로드 버튼 3종 (반응형 · 메모리 · spinner)
# ────────────────────────────────────────────────────────


def _log_fingerprint(log: dict) -> str:
    """세션 캐시 키용 — 동일 log면 재생성 생략."""
    import hashlib
    import json

    raw = json.dumps(log, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def render_download_buttons(log: dict) -> None:
    """
    Excel / PDF / DOCX 다운로드 UI.

    - 서버 디스크 저장 없음 (bytes 메모리)
    - PC: 가로 3열 / 모바일: CSS로 세로 스택
    - st.spinner 로 생성 중 표시 후 버튼 활성화
    """
    import streamlit as st

    st.markdown(
        """
<div class="rl-download-zone">
  <p class="rl-dz-title">문서 다운로드</p>
  <p class="rl-dz-cap">서버에 저장하지 않습니다 · 브라우저로 바로 다운로드 · Excel · PDF · DOCX</p>
</div>
        """,
        unsafe_allow_html=True,
    )

    if not log or not isinstance(log, dict):
        st.info("다운로드할 운행일지 데이터가 없습니다. 먼저 일지를 생성해 주세요.")
        return

    fp = _log_fingerprint(log)
    cache_key = "download_bundle"
    cache_fp_key = "download_bundle_fp"

    # 동일 결과면 재생성 없이 캐시 사용
    need_build = (
        st.session_state.get(cache_fp_key) != fp
        or not st.session_state.get(cache_key)
    )

    if need_build:
        with st.spinner("Excel · PDF · DOCX 파일을 준비하는 중… (서버에 저장하지 않습니다)"):
            bundle = build_all_download_files(log)
        st.session_state[cache_key] = bundle
        st.session_state[cache_fp_key] = fp
    else:
        bundle = st.session_state[cache_key]

    errors = bundle.get("errors") or {}
    excel = bundle.get("excel")
    pdf = bundle.get("pdf")
    docx = bundle.get("docx")

    ready = sum(1 for x in (excel, pdf, docx) if x)
    if ready == 3:
        st.success("다운로드 준비가 완료되었습니다. 원하는 형식을 눌러 받으세요.")
    elif ready > 0:
        st.warning(f"일부 형식만 준비되었습니다. ({ready}/3)")
    else:
        st.error("파일 생성에 실패했습니다.")

    # PC 가로 3열 / 모바일 CSS 스택 (styles.py @media)
    c1, c2, c3 = st.columns(3)

    with c1:
        if excel:
            data, name = excel
            st.download_button(
                label="📊 Excel 다운로드",
                data=data,
                file_name=name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key=f"dl_excel_{fp[:8]}",
                type="primary",
            )
        else:
            st.button("📊 Excel 실패", disabled=True, use_container_width=True, key="dl_excel_dis")
            if errors.get("excel"):
                st.caption(errors["excel"][:120])

    with c2:
        if pdf:
            data, name = pdf
            st.download_button(
                label="📕 PDF 다운로드",
                data=data,
                file_name=name,
                mime="application/pdf",
                use_container_width=True,
                key=f"dl_pdf_{fp[:8]}",
                type="primary",
            )
        else:
            st.button("📕 PDF 실패", disabled=True, use_container_width=True, key="dl_pdf_dis")
            if errors.get("pdf"):
                st.caption(errors["pdf"][:120])

    with c3:
        if docx:
            data, name = docx
            st.download_button(
                label="📝 DOCX 다운로드",
                data=data,
                file_name=name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                key=f"dl_docx_{fp[:8]}",
                type="primary",
            )
        else:
            st.button("📝 DOCX 실패", disabled=True, use_container_width=True, key="dl_docx_dis")
            if errors.get("docx"):
                st.caption(errors["docx"][:120])

    st.caption(
        "파일은 메모리에서만 생성되며 서버 디스크에 저장되지 않습니다. "
        "모바일에서는 버튼이 세로로 배치됩니다."
    )


def clear_download_cache() -> None:
    """일지 재생성 시 호출 — 세션 다운로드 캐시 초기화."""
    try:
        import streamlit as st

        for k in ("download_bundle", "download_bundle_fp"):
            if k in st.session_state:
                del st.session_state[k]
    except Exception:
        pass
=======
# Streamlit 다운로드 버튼 3종
# ────────────────────────────────────────────────────────


def render_download_buttons(log: dict) -> None:
    """Excel / PDF / DOCX 다운로드 버튼 — Free·Pro 동일 클린 파일."""
    import streamlit as st

    st.markdown("#### 문서 다운로드")
    st.caption("워터마크 없는 제출용 파일입니다.")

    c1, c2, c3 = st.columns(3)
    try:
        x_bytes, x_name = export_excel(log)
        with c1:
            st.download_button(
                label="Excel",
                data=x_bytes,
                file_name=x_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="dl_excel",
            )
    except Exception as e:
        with c1:
            st.error(f"Excel 생성 오류: {e}")

    try:
        p_bytes, p_name = export_pdf(log)
        with c2:
            st.download_button(
                label="PDF",
                data=p_bytes,
                file_name=p_name,
                mime="application/pdf",
                use_container_width=True,
                key="dl_pdf",
            )
    except Exception as e:
        with c2:
            st.error(f"PDF 생성 오류: {e}")

    try:
        d_bytes, d_name = export_docx(log)
        with c3:
            st.download_button(
                label="DOCX",
                data=d_bytes,
                file_name=d_name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                key="dl_docx",
            )
    except Exception as e:
        with c3:
            st.error(f"DOCX 생성 오류: {e}")
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
