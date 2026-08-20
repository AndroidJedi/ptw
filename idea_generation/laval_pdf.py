"""Readable Ukrainian PDF export for a completed Idea Laval investigation."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit
from xml.sax.saxutils import escape, quoteattr

from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


PINK = colors.HexColor("#f4066e")
GREEN = colors.HexColor("#0d6248")
BLUE = colors.HexColor("#245aa6")
VIOLET = colors.HexColor("#6546a5")
GOLD = colors.HexColor("#b87310")
INK = colors.HexColor("#12201b")
MUTED = colors.HexColor("#5f6d67")
LINE = colors.HexColor("#d9ddd5")
PAPER = colors.HexColor("#f7f6f1")

PHASES = (
    ("Намір", ("OWNER_CAPTURE", "OWNER_DNA", "QUERY_PLAN"), GREEN),
    ("Докази", (
        "SERP_DISCOVERY", "COMPETITOR_SELECTION", "COMPETITOR_EVIDENCE",
        "YOUTUBE_DISCOVERY", "YOUTUBE_OBSERVATION", "COMPETITOR_DOSSIERS",
        "OPPORTUNITY_MATRIX",
    ), colors.HexColor("#177b65")),
    ("Сигнали", (
        "MARKET_SIGNAL_PLAN", "MARKET_SIGNAL_COLLECTION", "MARKET_SIGNAL_GATE",
        "TREND_QUERY_PLAN", "GOOGLE_TRENDS_RESEARCH", "TREND_GATE", "SYNTHESIS_PACKET",
    ), BLUE),
    ("Механізми", (
        "IDEA_EXPANSION", "IDEA_CLUSTERING", "IDEA_EVALUATION",
        "MECHANISM_EXTRACTION", "MECHANISM_SCORING",
    ), VIOLET),
    ("Тези", ("THESIS_SYNTHESIS", "THESIS_FALSIFICATION", "THESIS_SHORTLIST", "FINAL_SHORTLIST"), PINK),
)

STAGE_LABELS = {
    "OWNER_CAPTURE": "Початкова ідея", "OWNER_DNA": "Суть ідеї", "QUERY_PLAN": "План пошуку",
    "SERP_DISCOVERY": "Результати пошуку", "COMPETITOR_SELECTION": "Відбір конкурентів",
    "COMPETITOR_EVIDENCE": "Докази про конкурентів", "YOUTUBE_DISCOVERY": "Пошук YouTube",
    "YOUTUBE_OBSERVATION": "Поведінкові спостереження", "COMPETITOR_DOSSIERS": "Досьє конкурентів",
    "OPPORTUNITY_MATRIX": "Матриця можливостей", "MARKET_SIGNAL_PLAN": "План ринкових сигналів",
    "MARKET_SIGNAL_COLLECTION": "Релевантність доказів", "MARKET_SIGNAL_GATE": "Оцінка ринкових сигналів",
    "TREND_QUERY_PLAN": "План тренд-запитів", "GOOGLE_TRENDS_RESEARCH": "Google Trends",
    "TREND_GATE": "Оцінка трендів", "SYNTHESIS_PACKET": "Пакет синтезу",
    "IDEA_EXPANSION": "Варіанти ідей", "IDEA_CLUSTERING": "Дедуплікація ідей",
    "IDEA_EVALUATION": "Оцінка ідей", "MECHANISM_EXTRACTION": "Виділення механізмів",
    "MECHANISM_SCORING": "Підтримка механізмів", "THESIS_SYNTHESIS": "Синтез продуктових тез",
    "THESIS_FALSIFICATION": "Фальсифікація тез", "THESIS_SHORTLIST": "Рекомендація тези",
    "FINAL_SHORTLIST": "Фінальний список",
}

STATUS_LABELS = {
    "completed": "завершено", "partial": "частково", "failed": "помилка",
    "stale": "застаріло", "paused": "призупинено", "pending": "не розпочато",
    "running": "виконується", "cancelled": "скасовано",
}

SUPPORT_LABELS = {
    "source_diversity": "Різноманітність джерел",
    "cross_variant_recurrence": "Повторюваність між варіантами",
    "opportunity_support": "Підтримка можливостей",
    "market_signal_support": "Підтримка ринкових сигналів",
    "owner_dna_fit": "Відповідність задуму власника",
}


def _fonts() -> tuple[str, str]:
    regular_name = "PTW-Roboto"
    bold_name = "PTW-Roboto-Bold"
    if regular_name not in pdfmetrics.getRegisteredFontNames():
        root = Path(__file__).resolve().parents[1]
        font_dir = root / "commander" / "assets" / "fonts"
        pdfmetrics.registerFont(TTFont(regular_name, font_dir / "Roboto-Regular.ttf"))
        pdfmetrics.registerFont(TTFont(bold_name, font_dir / "Roboto-Bold.ttf"))
    return regular_name, bold_name


def _text(value: Any, limit: int = 1200) -> str:
    if isinstance(value, Mapping):
        value = value.get("uk") or value.get("en") or ""
    result = " ".join(str(value or "").split())
    return result if len(result) <= limit else result[: limit - 1].rstrip() + "…"


def _p(value: Any, style: ParagraphStyle, limit: int = 1200) -> Paragraph:
    return Paragraph(escape(_text(value, limit)), style)


def _http_url(value: Any) -> str | None:
    url = str(value or "").strip()
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    return url if parts.scheme in {"http", "https"} and bool(parts.netloc) else None


def _link(label: Any, url: Any, style: ParagraphStyle) -> Paragraph:
    safe_url = _http_url(url)
    safe_label = escape(_text(label, 180))
    if not safe_url:
        return Paragraph(safe_label, style)
    return Paragraph(f"<link href={quoteattr(safe_url)} color='#245aa6'>{safe_label}</link>", style)


def _artifact(stages: Sequence[Mapping[str, Any]], name: str) -> dict[str, Any]:
    row = next((item for item in stages if item.get("stage") == name), None)
    artifact = (row or {}).get("artifact")
    return dict(artifact) if isinstance(artifact, Mapping) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, Mapping)] if isinstance(value, list) else []


class PhaseFlow(Flowable):
    def __init__(self, stages: Sequence[Mapping[str, Any]], width: float) -> None:
        super().__init__()
        self.width = width
        self.height = 24 * mm
        self.status = {str(item.get("stage")): str(item.get("status")) for item in stages}

    def draw(self) -> None:
        gap = 3 * mm
        box_width = (self.width - gap * 4) / 5
        for index, (label, names, color) in enumerate(PHASES):
            x = index * (box_width + gap)
            processed = sum(self.status.get(name) in {"completed", "partial"} for name in names if name in self.status)
            total = sum(name in self.status for name in names)
            self.canv.setFillColor(color)
            self.canv.roundRect(x, 0, box_width, self.height, 5, fill=1, stroke=0)
            self.canv.setFillColor(colors.white)
            self.canv.setFont("PTW-Roboto-Bold", 9)
            self.canv.drawString(x + 6, self.height - 12, f"0{index + 1}")
            self.canv.setFont("PTW-Roboto-Bold", 7.4)
            self.canv.drawString(x + 6, self.height - 26, label)
            self.canv.setFont("PTW-Roboto", 6.8)
            self.canv.drawString(x + 6, 7, f"{processed}/{total} оброблено")


class ScoreBars(Flowable):
    def __init__(self, items: Sequence[tuple[str, float]], width: float, color: colors.Color = GREEN) -> None:
        super().__init__()
        self.items = list(items)
        self.width = width
        self.color = color
        self.height = max(1, len(self.items)) * 8 * mm

    def draw(self) -> None:
        label_width = self.width * .53
        bar_width = self.width - label_width - 25
        for index, (label, raw_value) in enumerate(self.items):
            value = min(1.0, max(0.0, float(raw_value or 0)))
            y = self.height - (index + 1) * 8 * mm + 7
            self.canv.setFillColor(INK)
            self.canv.setFont("PTW-Roboto", 7.2)
            self.canv.drawString(0, y, _text(label, 46))
            self.canv.setFillColor(colors.HexColor("#e5e7e2"))
            self.canv.roundRect(label_width, y - 1, bar_width, 6, 3, fill=1, stroke=0)
            self.canv.setFillColor(self.color)
            self.canv.roundRect(label_width, y - 1, bar_width * value, 6, 3, fill=1, stroke=0)
            self.canv.setFillColor(MUTED)
            self.canv.setFont("PTW-Roboto-Bold", 7)
            self.canv.drawRightString(self.width, y, f"{value:.2f}")


def _styles(regular: str, bold: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("TitleUA", parent=base["Title"], fontName=bold, fontSize=26, leading=29, textColor=INK, spaceAfter=10),
        "h1": ParagraphStyle("H1UA", parent=base["Heading1"], fontName=bold, fontSize=18, leading=21, textColor=INK, spaceBefore=5, spaceAfter=8),
        "h2": ParagraphStyle("H2UA", parent=base["Heading2"], fontName=bold, fontSize=12, leading=14, textColor=INK, spaceBefore=5, spaceAfter=5),
        "body": ParagraphStyle("BodyUA", parent=base["BodyText"], fontName=regular, fontSize=8.8, leading=12, textColor=INK, spaceAfter=4),
        "small": ParagraphStyle("SmallUA", parent=base["BodyText"], fontName=regular, fontSize=7.4, leading=9.5, textColor=MUTED),
        "tiny": ParagraphStyle("TinyUA", parent=base["BodyText"], fontName=regular, fontSize=6.6, leading=8.2, textColor=MUTED),
        "bold": ParagraphStyle("BoldUA", parent=base["BodyText"], fontName=bold, fontSize=8.8, leading=12, textColor=INK),
        "center": ParagraphStyle("CenterUA", parent=base["BodyText"], fontName=bold, fontSize=8, leading=10, textColor=INK, alignment=TA_CENTER),
        "white": ParagraphStyle("WhiteUA", parent=base["BodyText"], fontName=bold, fontSize=10, leading=13, textColor=colors.white),
    }


def _on_page(canvas: Any, document: Any) -> None:
    canvas.saveState()
    canvas.setFillColor(PAPER)
    canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    canvas.setFillColor(MUTED)
    canvas.setFont("PTW-Roboto", 6.5)
    canvas.drawString(16 * mm, 8 * mm, "PTW · Idea Laval · український звіт")
    canvas.drawRightString(A4[0] - 16 * mm, 8 * mm, str(document.page))
    canvas.restoreState()


def _table(data: list[list[Any]], widths: list[float], style: dict[str, ParagraphStyle]) -> Table:
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9ece7")),
        ("FONTNAME", (0, 0), (-1, 0), "PTW-Roboto-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "PTW-Roboto"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.2),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), .35, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def build_laval_pdf(repository: Any, run_id: str) -> bytes:
    """Build a bounded, readable report. Raw artifacts remain in JSON/MD exports."""

    regular, bold = _fonts()
    styles = _styles(regular, bold)
    run = repository.run(run_id)
    if run.get("status") != "completed":
        raise ValueError("PDF report is available only for completed Laval runs")
    owner = repository.owner(run_id)
    stages = repository.stages(run_id)
    quality = repository.llm_quality(run_id)
    cost = repository.cost(run_id)
    evidence = repository.evidence(run_id)

    competitors = _rows(_artifact(stages, "COMPETITOR_SELECTION").get("global_deduplicated"))
    competitors = [item for item in competitors if item.get("selected")][:8]
    opportunities = _rows(_artifact(stages, "OPPORTUNITY_MATRIX").get("opportunities"))[:8]
    market_scores = _rows(_artifact(stages, "MARKET_SIGNAL_GATE").get("scores"))[:8]
    observations = _rows(_artifact(stages, "YOUTUBE_OBSERVATION").get("observations"))[:8]
    mechanisms = _rows(_artifact(stages, "MECHANISM_SCORING").get("mechanisms"))[:12]
    shortlist = _artifact(stages, "THESIS_SHORTLIST")
    theses = _rows(shortlist.get("theses"))

    processed = sum(item.get("status") in {"completed", "partial"} for item in stages)
    completed = sum(item.get("status") == "completed" for item in stages)
    partial = sum(item.get("status") == "partial" for item in stages)
    mode = {
        "demo_fixture": "ДЕМО · НЕ РИНКОВИЙ ВИСНОВОК",
        "live_complete": "LIVE · ПОВНЕ ДОСЛІДЖЕННЯ",
        "live_market_signals": "LIVE · MARKET SIGNALS",
        "live_search_pending_trends": "LIVE · ІСТОРИЧНИЙ PIPELINE",
    }.get(str(run.get("evidence_mode")), "РЕЖИМ НЕ ВИЗНАЧЕНО")
    owner_text = _text(owner.get("raw_text"), 5000)
    title = _text(owner_text.split("\n", 1)[0] if owner_text else "Дослідження Idea Laval", 125)
    generated = str(run.get("completed_at") or run.get("updated_at") or "")[:19].replace("T", " ")
    actual_cost = float(cost.get("provider_actual_usd") or cost.get("total_usd") or 0)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=16 * mm, bottomMargin=14 * mm, title=f"Idea Laval — {title}",
        author="PTW Idea Laval", subject="Український звіт завершеного дослідження",
    )
    width = A4[0] - 32 * mm
    story: list[Flowable] = []

    story.extend([
        Paragraph("IDEA LAVAL · ЗАВЕРШЕНЕ ДОСЛІДЖЕННЯ", ParagraphStyle(
            "Eyebrow", parent=styles["small"], fontName=bold, textColor=PINK, fontSize=8, leading=10,
        )),
        _p(title, styles["title"], 125),
        _p(owner_text, styles["body"], 900),
        Spacer(1, 4 * mm),
        PhaseFlow(stages, width),
        Spacer(1, 5 * mm),
    ])
    summary_data = [
        [_p("Статус", styles["small"]), _p("Етапи", styles["small"]), _p("Якість моделі", styles["small"]), _p("Вартість", styles["small"])],
        [_p(mode, styles["bold"]), _p(f"{processed}/{len(stages)} оброблено · {completed} повністю · {partial} частково", styles["bold"]),
         _p(f"{quality.get('success', 0)} успішних із {quality.get('attempted', 0)} спроб", styles["bold"]), _p(f"USD {actual_cost:.4f}", styles["bold"])],
    ]
    story.append(_table(summary_data, [width * .24, width * .31, width * .28, width * .17], styles))
    story.append(Spacer(1, 5 * mm))
    conclusion = "Є тези, які пережили фальсифікацію." if any(item.get("verdict") == "survives" for item in theses) else "Жодна продуктова теза не пережила фальсифікацію на поточних доказах."
    story.append(Table([[_p("ВИСНОВОК", styles["white"]), _p(conclusion, styles["body"], 600)]], colWidths=[34 * mm, width - 34 * mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), GREEN if theses and "Жодна" not in conclusion else PINK),
        ("BACKGROUND", (1, 0), (1, 0), colors.white), ("BOX", (0, 0), (-1, -1), .6, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ])))
    story.extend([Spacer(1, 4 * mm), _p(f"Run: {run_id} · завершено: {generated or '—'} · pipeline: {run.get('pipeline_version') or 'legacy'}", styles["small"]), PageBreak()])

    story.extend([_p("Ринок: конкуренти й можливості", styles["h1"])])
    if competitors:
        story.append(_p("Відібрані конкуренти", styles["h2"]))
        data: list[list[Any]] = [["Конкурент", "Тип", "Ринки", "Оцінка"]]
        for item in competitors:
            data.append([
                _link(item.get("name") or item.get("domain"), item.get("url"), styles["body"]),
                _p(item.get("type") or "—", styles["small"]),
                _p(", ".join(map(str, item.get("countries") or [])) or "—", styles["small"]),
                _p(f"{float(item.get('score') or 0):.2f}", styles["bold"]),
            ])
        story.extend([_table(data, [width * .42, width * .2, width * .24, width * .14], styles), Spacer(1, 5 * mm)])
    if opportunities:
        story.append(_p("Найсильніші можливості", styles["h2"]))
        opp_data: list[list[Any]] = [["Можливість", "Сегмент", "Докази", "Signal"]]
        for item in opportunities:
            opp_data.append([
                _p(item.get("statement"), styles["body"], 280), _p(item.get("affected_segment"), styles["small"], 120),
                _p(str(len(item.get("evidence_ids") or [])), styles["center"]),
                _p(f"{float(item.get('aggregate_score') or 0):.2f}", styles["center"]),
            ])
        story.append(_table(opp_data, [width * .51, width * .27, width * .1, width * .12], styles))
    story.extend([Spacer(1, 4 * mm), _p("Оцінки в цьому розділі є сигналами повторюваності й покриття, а не ймовірністю успіху продукту.", styles["small"]), PageBreak()])

    story.append(_p("Сигнали й поведінка", styles["h1"]))
    if market_scores:
        by_opportunity = {str(item.get("id")): item for item in opportunities}
        bars = [(_text(by_opportunity.get(str(item.get("opportunity_id")), {}).get("statement") or "Market signal", 46), float(item.get("aggregate_score") or 0)) for item in market_scores[:6]]
        story.extend([_p("Market Signal Score", styles["h2"]), ScoreBars(bars, width, BLUE), Spacer(1, 4 * mm)])
    if observations:
        story.append(_p("Спостережувана поведінка на YouTube", styles["h2"]))
        obs_data: list[list[Any]] = [["Тип", "Спостереження", "Незалежні creators"]]
        for item in observations:
            obs_data.append([_p(item.get("observation_type"), styles["small"]), _p(item.get("statement"), styles["body"], 320), _p(str(item.get("independent_creator_count") or 0), styles["center"])])
        story.append(_table(obs_data, [width * .2, width * .65, width * .15], styles))
    story.extend([Spacer(1, 4 * mm), _p("YouTube-підтвердження рахується за унікальними каналами; популярність або дублікати одного creator не збільшують незалежну підтримку.", styles["small"]), PageBreak()])

    story.append(_p("Механізми продукту", styles["h1"]))
    if not mechanisms:
        story.append(_p("Механізми не були створені в цьому історичному pipeline.", styles["body"]))
    for index, item in enumerate(mechanisms, 1):
        dimensions = dict(item.get("support_dimensions") or {})
        bars = [(SUPPORT_LABELS.get(str(key), str(key).replace("_", " ")), float(value or 0)) for key, value in dimensions.items()]
        block: list[Flowable] = [
            _p(f"{index}. {_text(item.get('name'), 120)} · {_text(item.get('mechanism_type'), 30)}", styles["h2"]),
            _p(item.get("description"), styles["body"], 380),
        ]
        if bars:
            block.append(ScoreBars(bars, width, VIOLET))
        block.extend([_p("Support vector показує різні грані доказовості; це не прогноз успіху.", styles["tiny"]), Spacer(1, 3 * mm), HRFlowable(width="100%", color=LINE, thickness=.5)])
        story.append(KeepTogether(block))
    story.append(PageBreak())

    story.append(_p("Продуктові тези та фальсифікація", styles["h1"]))
    if not theses:
        story.append(_p("Продуктові тези відсутні. Перевірте статус і якість мовних етапів у технічному експорті.", styles["body"]))
    for index, item in enumerate(theses, 1):
        verdict = str(item.get("verdict") or "—")
        verdict_ua = {"survives": "ВИЖИЛА", "weak": "СЛАБКА", "rejected": "ВІДХИЛЕНА"}.get(verdict, verdict.upper())
        color = GREEN if verdict == "survives" else GOLD if verdict == "weak" else PINK
        header = Table([[_p(f"ТЕЗА {index}", styles["white"]), _p(item.get("title"), styles["bold"], 180), _p(verdict_ua, styles["center"])]], colWidths=[24 * mm, width - 55 * mm, 31 * mm], style=TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), color), ("BACKGROUND", (2, 0), (2, 0), colors.HexColor("#f0eee8")),
            ("BOX", (0, 0), (-1, -1), .6, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.extend([header, Spacer(1, 2 * mm), _p(f"Для кого: {_text(item.get('target_user'), 280)}", styles["body"]), _p(f"Проблема: {_text(item.get('problem'), 320)}", styles["body"])])
        loop_steps = item.get("loop_steps") or []
        if isinstance(loop_steps, list):
            story.append(_p("Петля продукту", styles["h2"]))
            story.append(_table([[str(i + 1), _p(step, styles["body"], 240)] for i, step in enumerate(loop_steps)], [12 * mm, width - 12 * mm], styles))
        assumptions = _rows(item.get("dangerous_assumptions"))
        if assumptions:
            story.append(_p("Небезпечні припущення", styles["h2"]))
            story.append(_table([[str(a.get("severity") or "").upper(), _p(a.get("statement"), styles["body"], 240)] for a in assumptions], [24 * mm, width - 24 * mm], styles))
        if item.get("fatal_objection"):
            story.append(_p(f"Критичне заперечення: {_text(item.get('fatal_objection'), 420)}", styles["bold"]))
        story.extend([_p(f"Непідтриманих HIGH: {int(item.get('unsupported_high_severity_count') or 0)} · найслабше покриття механізму: {float(item.get('weakest_mechanism_coverage') or 0):.2f}", styles["small"]), Spacer(1, 5 * mm)])
    story.append(PageBreak())

    story.append(_p("Статус усіх етапів", styles["h1"]))
    stage_data: list[list[Any]] = [["Етап", "Назва", "Статус", "Спроба", "Виконавець"]]
    for item in stages:
        stage_data.append([
            _p(f"S{int(item.get('ordinal') or 0):02d}", styles["bold"]),
            _p(STAGE_LABELS.get(str(item.get("stage")), str(item.get("stage"))), styles["body"]),
            _p(STATUS_LABELS.get(str(item.get("status")), str(item.get("status"))), styles["small"]),
            _p(str(item.get("attempt") or 0), styles["center"]),
            _p(item.get("provider") or "код", styles["small"], 70),
        ])
    story.extend([_table(stage_data, [15 * mm, width * .36, width * .2, 15 * mm, width - 30 * mm - width * .56], styles), Spacer(1, 5 * mm)])
    story.append(_p("Корисні джерела", styles["h1"]))
    wanted_ids = set()
    for item in theses + opportunities[:5] + mechanisms[:5]:
        wanted_ids.update(map(str, item.get("evidence_ids") or []))
    selected_evidence = [item for item in evidence if str(item.get("id")) in wanted_ids and _http_url(item.get("source_url"))]
    if not selected_evidence:
        selected_evidence = [item for item in evidence if _http_url(item.get("source_url"))]
    selected_evidence = selected_evidence[:18]
    if selected_evidence:
        source_data: list[list[Any]] = [["Джерело", "Тип", "Видавець / країна"]]
        for item in selected_evidence:
            source_data.append([
                _link(item.get("source_title") or item.get("source_url"), item.get("source_url"), styles["body"]),
                _p(item.get("source_type") or "—", styles["small"]),
                _p(" · ".join(filter(None, [str(item.get("publisher") or ""), str(item.get("country") or "")])), styles["small"]),
            ])
        story.append(_table(source_data, [width * .55, width * .17, width * .28], styles))
        story.append(_p("Сині назви джерел є клікабельними. До звіту включено лише bounded добірку найкорисніших посилань; повний lineage доступний у JSON/Markdown export.", styles["small"]))
    else:
        story.append(_p("Для цього запуску немає корисних HTTP(S)-посилань. Fixture-джерела навмисно не подаються як ринкові докази.", styles["body"]))

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buffer.getvalue()
