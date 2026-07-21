"""
홍보 문구 생성기 (외부 연동 · 결제 없음)

사이트 분석 결과(SiteProfile) 기반 범용 문구.
특정 서비스에 종속되지 않습니다.
"""

from __future__ import annotations

import random
from typing import Any, Sequence

# site_analyzer.SiteProfile 과 동일 필드만 사용 (순환 import 방지)
try:
    from site_analyzer import SiteProfile  # noqa: F401
except ImportError:
    SiteProfile = None  # type: ignore

# ---------------------------------------------------------------------------
# 범용 블록 뱅크 (제품 미지정 시 · 분석 전 안내 톤)
# ---------------------------------------------------------------------------

TITLE_BANK: list[str] = [
    "이런 불편, 아직도 손으로 해결하고 계신가요?",
    "반복 업무 줄여 줄 도구 하나 공유합니다",
    "가볍게 시작해 볼 만한 서비스 소개",
    "시간 아껴 주는 워크플로 도구 정리",
    "비슷한 고민 있으시면 한 번 보시면 좋아요",
    "업무 효율 올려 줄 링크 공유",
    "써 보고 괜찮아서 남겨 둡니다",
    "관심 있으실 수 있는 도구 짧게 소개",
]

OPENINGS: list[str] = [
    "반복되는 정리·작성·제출 때문에 시간이 늘 부족하다고 느끼는 분 계신가요.",
    "비슷한 도구를 찾다가 정리해 본 내용입니다.",
    "필요할 것 같아 짧게 공유합니다.",
    "지인에게 설명하듯 핵심만 적어 둡니다.",
    "업무 흐름을 조금 편하게 만드는 방법을 정리해 봤습니다.",
]

PROBLEMS: list[str] = [
    "문제는 기능보다 매번 손보는 시간·양식·복붙이 쌓인다는 점입니다.",
    "같은 일을 반복하다 보면 본업보다 정리에 시간이 더 가기도 합니다.",
    "도구는 많은데 실제로 루틴에 붙는 건 의외로 적습니다.",
    "처음부터 완벽하게 쓰기보다, 가볍게 시작해도 되는지가 중요하더라고요.",
]

WHAT_IT_DOES_HEADERS: list[str] = [
    "대략 이런 흐름입니다",
    "쓰는 방법 (간단)",
    "핵심만 정리하면",
    "이렇게 쓰면 됩니다",
]

STEPS_POOL: list[str] = [
    "사이트에 접속해 핵심 기능을 확인",
    "필요한 정보만 입력·선택",
    "결과물을 확인한 뒤 업무에 적용",
    "(선택) 팀·요금·연동 옵션 살펴보기",
    "도움말·FAQ로 세부 설정 확인",
]

FEATURE_BULLETS: list[str] = [
    "핵심 기능을 빠르게 파악할 수 있음",
    "반복 작업을 줄이는 데 초점",
    "개인·팀 모두 활용 가능한 경우가 많음",
    "웹에서 바로 시작 가능",
    "자세한 요금·플랜은 사이트에서 확인",
]

PRICING_LINES: list[str] = [
    "요금·체험 구간은 사이트에서 최신 정보를 확인해 주세요.",
    "무료/체험이 있는 제품이 많습니다. 유료 전환 전에 한도만 확인하세요.",
    "가격은 시점마다 달라질 수 있어, 공식 페이지 기준이 안전합니다.",
]

VALUE_LINES: list[str] = [
    "핵심만 입력하면 결과로 정리해 주는 흐름이 특징입니다.",
    "처음부터 복잡한 설정 없이 시작할 수 있는 편입니다.",
    "비슷한 수작업을 줄이고 싶을 때 참고해 볼 만합니다.",
]

CLOSINGS: list[str] = [
    "※ 서비스 소개 목적입니다. 커뮤니티 규정에 맞게 이용 부탁드립니다.",
    "※ 본 글은 소개 목적입니다. 실제 사용 전 내용을 확인해 주세요.",
    "질문 있으면 댓글로 남겨 주세요.",
    "필요하신 분만 참고해 주세요.",
    "광고가 불편하시면 알려 주세요. 규정에 맞게 수정하겠습니다.",
]

SHORT_LINES: list[str] = [
    "반복 업무 줄여 줄 도구 공유",
    "가볍게 시작하기 좋은 서비스",
    "핵심만 쓰고 결과 확인",
    "자세한 내용은 사이트에서",
    "궁금하면 댓글 주세요",
]

SYNONYM_MAP: list[tuple[str, list[str]]] = [
    ("공유합니다", ["공유합니다", "남겨 둡니다", "정리해 둡니다"]),
    ("정리해", ["정리해", "적어", "남겨"]),
    ("바로", ["바로", "곧바로", "바로"]),
    ("핵심", ["핵심", "요점", "포인트"]),
]

STYLES = (
    "랜덤",
    "문제 공감형",
    "가격 강조형",
    "사용 방법형",
    "짧은 버전",
)


def list_styles() -> list[str]:
    return list(STYLES)


def _pick(seq: Sequence[str], rng: random.Random) -> str:
    return seq[rng.randrange(len(seq))]


def _pick_n(seq: Sequence[str], n: int, rng: random.Random) -> list[str]:
    items = list(seq)
    rng.shuffle(items)
    return items[: max(1, min(n, len(items)))]


def _maybe_synonyms(text: str, rng: random.Random, p: float = 0.45) -> str:
    out = text
    for src, alts in SYNONYM_MAP:
        if src in out and rng.random() < p:
            out = out.replace(src, _pick(alts, rng), 1)
    return out


def _join_paras(parts: list[str]) -> str:
    return "\n\n".join(p.strip() for p in parts if p and p.strip())


def _dedupe_lines(text: str) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for para in text.split("\n\n"):
        key = para.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(para)
    return "\n\n".join(out)


def _hint_analyze() -> str:
    return (
        "※ 아직 홍보 대상 사이트 분석 전입니다.\n"
        "개요 화면에서 제품 주소를 넣고 「분석 + 홍보글 생성」을 누르면\n"
        "내 서비스 이름·소개·링크로 문구가 맞춰집니다."
    )


def _style_problem(rng: random.Random) -> tuple[str, str]:
    title = _pick(TITLE_BANK, rng)
    bullets = _pick_n(FEATURE_BULLETS, rng.randint(3, 5), rng)
    bullet_block = "\n".join(f"· {b.lstrip('· ').strip()}" for b in bullets)
    parts = [
        _pick(OPENINGS, rng),
        _pick(PROBLEMS, rng) if rng.random() < 0.75 else "",
        _pick(VALUE_LINES, rng),
        bullet_block,
        _hint_analyze(),
        _pick(CLOSINGS, rng),
    ]
    body = _dedupe_lines(_join_paras(parts))
    return _maybe_synonyms(title, rng), _maybe_synonyms(body, rng)


def _style_price(rng: random.Random) -> tuple[str, str]:
    title = _pick(
        [
            "가격 대비 써 볼 만한 도구 공유",
            "가볍게 시작하기 좋은 서비스 소개",
            _pick(TITLE_BANK, rng),
        ],
        rng,
    )
    parts = [
        _pick(OPENINGS, rng),
        _pick(PRICING_LINES, rng),
        _pick(VALUE_LINES, rng),
        _hint_analyze(),
        _pick(CLOSINGS, rng),
    ]
    body = _join_paras(parts)
    return _maybe_synonyms(title, rng), _maybe_synonyms(body, rng)


def _style_howto(rng: random.Random) -> tuple[str, str]:
    title = _pick(
        [
            "이렇게 시작하면 됩니다 (사용 흐름)",
            "처음 쓰는 분용 간단 흐름 공유",
            _pick(TITLE_BANK, rng),
        ],
        rng,
    )
    header = _pick(WHAT_IT_DOES_HEADERS, rng)
    steps = _pick_n(STEPS_POOL, rng.randint(3, 4), rng)
    step_block = header + "\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
    parts = [
        _pick(OPENINGS, rng),
        _pick(PROBLEMS, rng) if rng.random() < 0.5 else "",
        step_block,
        _hint_analyze(),
        _pick(CLOSINGS, rng),
    ]
    body = _join_paras(parts)
    return _maybe_synonyms(title, rng), _maybe_synonyms(body, rng)


def _style_short(rng: random.Random) -> tuple[str, str]:
    title = _pick(
        [
            "유용할 수 있는 도구 한 줄 공유",
            "짧게 남겨 두는 추천 링크",
            _pick(TITLE_BANK, rng),
        ],
        rng,
    )
    lines = _pick_n(SHORT_LINES, rng.randint(3, 4), rng)
    lines.append("→ 제품 주소는 사이트 분석 후 자동으로 채워집니다")
    body = "\n".join(lines)
    return title, body


def _profile_fields(profile: Any) -> dict[str, Any]:
    if profile is None:
        return {}
    if isinstance(profile, dict):
        return profile
    if hasattr(profile, "to_dict"):
        return profile.to_dict()
    return {
        "url": getattr(profile, "url", ""),
        "final_url": getattr(profile, "final_url", ""),
        "title": getattr(profile, "title", ""),
        "brand": getattr(profile, "brand", ""),
        "description": getattr(profile, "description", ""),
        "keywords": getattr(profile, "keywords", []) or [],
        "headings": getattr(profile, "headings", []) or [],
        "highlights": getattr(profile, "highlights", []) or [],
        "category": getattr(profile, "category", "일반") or "일반",
    }


def generate_from_profile(
    profile: Any,
    style: str = "랜덤",
    *,
    seed: int | None = None,
) -> tuple[str, str]:
    """분석된 사이트 프로필로 범용 홍보 제목·본문 생성."""
    fields = _profile_fields(profile)
    url = (fields.get("final_url") or fields.get("url") or "").strip()
    brand = (fields.get("brand") or fields.get("title") or "이 서비스").strip()
    title_page = (fields.get("title") or brand).strip()
    desc = (fields.get("description") or "").strip()
    category = (fields.get("category") or "일반").strip()
    highlights = list(fields.get("highlights") or [])
    keywords = list(fields.get("keywords") or [])
    headings = list(fields.get("headings") or [])

    if not url and not brand:
        return generate_post(style, seed=seed)

    rng = random.Random(seed)
    resolved = style
    if not resolved or resolved == "랜덤":
        resolved = _pick(
            ["문제 공감형", "가격 강조형", "사용 방법형", "짧은 버전"],
            rng,
        )

    intro = desc
    if not intro and highlights:
        intro = str(highlights[0])
    if not intro and headings:
        intro = str(headings[0])
    if not intro:
        intro = f"{brand} — {category} 관련 웹사이트/서비스를 소개합니다."

    points: list[str] = []
    for h in highlights + headings + keywords:
        h = str(h).strip()
        if not h or len(h) < 2:
            continue
        if h == brand or h in points:
            continue
        points.append(h)
        if len(points) >= 5:
            break
    if not points:
        points = [p for p in (f"{category} 카테고리", brand, url) if p]

    bullet = "\n".join(f"· {p}" for p in points[:5] if p)

    title_bank = [
        f"{brand} 소개 — 한 번 살펴보시면 좋을 것 같아요",
        f"{title_page[:40]} 공유",
        f"이런 서비스 찾고 계셨다면: {brand}",
        f"{brand} ({category}) 짧게 소개합니다",
        f"{brand} 써 보신 분 계신가요? 소개 글",
        f"유용할 수 있는 링크 공유: {brand}",
    ]
    if category and category != "일반":
        title_bank.append(f"{category} 관심 있으시면 {brand} 참고")

    openings = [
        f"오늘은 {brand}를 간단히 소개해 봅니다.",
        f"{category} 관련해서 눈에 띄어 정리해 둡니다.",
        f"필요할 것 같아 공유합니다. 이름: {brand}",
        f"{intro[:120]}",
    ]
    closings = [
        "※ 서비스·사이트 소개 목적입니다. 커뮤니티 규정에 맞게 이용해 주세요.",
        "자세한 내용은 아래 사이트에서 확인해 주세요.",
        "질문 있으면 댓글로 남겨 주세요.",
        "광고성 글이 불편하시면 알려 주세요. 규정에 맞게 수정하겠습니다.",
    ]

    if resolved == "짧은 버전":
        title = _pick([f"{brand} 공유", f"{brand} — {category}", title_bank[0]], rng)
        lines = [brand, intro[:100] if intro else category, url]
        body = "\n".join(x for x in lines if x)
        return title.strip(), body.strip()

    if resolved == "사용 방법형":
        title = _pick(
            [f"{brand} 사용·방문 흐름 공유", f"{brand} 이렇게 보면 됩니다", _pick(title_bank, rng)],
            rng,
        )
        steps = [
            f"사이트 접속: {url}" if url else "사이트 접속",
            f"첫 화면에서 «{headings[0]}» 등을 확인" if headings else "메인에서 핵심 기능·메뉴 확인",
            "관심 기능·상품·글을 살펴본 뒤 필요하면 가입·문의",
            "자세한 안내는 사이트 공지·FAQ 참고",
        ]
        step_block = "대략 이런 흐름입니다\n" + "\n".join(
            f"{i}. {s}" for i, s in enumerate(steps, 1)
        )
        body = _join_paras(
            [
                _pick(openings, rng),
                intro if intro != openings[0] else "",
                step_block,
                f"핵심 포인트\n{bullet}",
                f"사이트: {url}" if url else "",
                _pick(closings, rng),
            ]
        )
        return title.strip(), _dedupe_lines(body).strip()

    if resolved == "가격 강조형":
        title = _pick(
            [f"{brand} 요금·혜택 한눈에", f"{brand} 소개 (가격·혜택 위주)", _pick(title_bank, rng)],
            rng,
        )
        body = _join_paras(
            [
                _pick(openings, rng),
                intro,
                f"한눈에 보기\n{bullet}",
                "가격·플랜은 사이트에서 최신 정보를 확인해 주세요. (이 글 작성 시점과 다를 수 있습니다.)",
                f"바로 가기: {url}" if url else "",
                _pick(closings, rng),
            ]
        )
        return title.strip(), _dedupe_lines(body).strip()

    title = _pick(title_bank, rng)
    empathy = _pick(
        [
            f"{category} 쪽에서 쓸 만한 곳을 찾다가 {brand}를 알게 되었습니다.",
            "비슷한 고민 있으신 분께 참고가 될까 싶어 적어 둡니다.",
            "지인에게 설명하듯 짧게 정리해 봅니다.",
        ],
        rng,
    )
    body = _join_paras(
        [
            _pick(openings, rng),
            empathy,
            intro,
            f"이름: {brand}\n분류: {category}\n{bullet}",
            f"사이트: {url}" if url else "",
            _pick(closings, rng),
        ]
    )
    return title.strip(), _dedupe_lines(body).strip()


def generate_post(
    style: str = "랜덤",
    *,
    seed: int | None = None,
    profile: Any = None,
) -> tuple[str, str]:
    """
    제목, 본문 반환. 외부 연동 없음.

    profile 이 있으면 해당 사이트 기준 범용 문구.
    없으면 분석 유도용 범용 문구.
    """
    if profile is not None:
        fields = _profile_fields(profile)
        if fields.get("url") or fields.get("brand") or fields.get("title"):
            return generate_from_profile(profile, style, seed=seed)

    rng = random.Random(seed)
    resolved = style
    if not resolved or resolved == "랜덤":
        resolved = _pick(
            ["문제 공감형", "가격 강조형", "사용 방법형", "짧은 버전"],
            rng,
        )

    if resolved == "가격 강조형":
        title, body = _style_price(rng)
    elif resolved == "사용 방법형":
        title, body = _style_howto(rng)
    elif resolved == "짧은 버전":
        title, body = _style_short(rng)
    else:
        title, body = _style_problem(rng)

    if resolved != "짧은 버전" and rng.random() < 0.35:
        paras = [p for p in body.split("\n\n") if p.strip()]
        if len(paras) >= 3:
            head, mid, tail = paras[0], paras[1:-1], paras[-1]
            rng.shuffle(mid)
            body = "\n\n".join([head, *mid, tail])

    return title.strip(), _dedupe_lines(body).strip()


def generate_batch(n: int = 5, style: str = "랜덤") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for i in range(n * 3):
        t, b = generate_post(style, seed=random.randint(0, 10**9) + i)
        key = t + "\n" + b
        if key in seen:
            continue
        seen.add(key)
        out.append((t, b))
        if len(out) >= n:
            break
    return out
