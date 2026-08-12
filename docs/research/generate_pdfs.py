from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

PAGE_WIDTH, PAGE_HEIGHT = LETTER
LEFT_MARGIN = 0.9 * inch
RIGHT_MARGIN = 0.9 * inch
TOP_MARGIN = 0.9 * inch
BOTTOM_MARGIN = 0.75 * inch
RESEARCH_SERIES_LABEL = "CytoCV Research Documentation"
LICENSE_FOOTER = "AGPL-3.0-or-later"
OUTPUT_STEMS = (
    "methods-and-system-description",
    "reproducibility-and-validation",
    "figure-catalog",
)
PDF_OUTPUT_DIR_NAME = "pdfs"

TEXT = colors.HexColor("#1f2933")
MUTED_TEXT = colors.HexColor("#52606d")
ACCENT = colors.HexColor("#5273a5")
ACCENT_FILL = colors.HexColor("#eef3fb")
TABLE_GRID = colors.HexColor("#b4c2d9")
LINK_HEX = "#5273A5"

FONT_REGULAR = "CytoCVSans"
FONT_BOLD = "CytoCVSans-Bold"
FONT_ITALIC = "CytoCVSans-Italic"
FONT_MONO = "Courier"


@dataclass(frozen=True)
class HeadingBlock:
    level: int
    text: str


@dataclass(frozen=True)
class ParagraphBlock:
    text: str


@dataclass(frozen=True)
class ListBlock:
    ordered: bool
    items: list[str]


@dataclass(frozen=True)
class TableBlock:
    headers: list[str]
    rows: list[list[str]]


Block = HeadingBlock | ParagraphBlock | ListBlock | TableBlock


def register_fonts() -> None:
    font_dir = Path("C:/Windows/Fonts")
    font_map = {
        FONT_REGULAR: font_dir / "arial.ttf",
        FONT_BOLD: font_dir / "arialbd.ttf",
        FONT_ITALIC: font_dir / "ariali.ttf",
    }
    registered = set(pdfmetrics.getRegisteredFontNames())
    for font_name, font_path in font_map.items():
        if font_name in registered:
            continue
        if not font_path.exists():
            raise FileNotFoundError(f"Required font file not found: {font_path}")
        pdfmetrics.registerFont(TTFont(font_name, str(font_path)))


def normalize_markdown(markdown_text: str) -> str:
    return markdown_text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")


def collapse_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def is_table_separator(value: str) -> bool:
    return bool(re.match(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$", value))


def split_table_row(value: str) -> list[str]:
    text = value.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    return [part.strip() for part in text.split("|")]


def parse_markdown(markdown_text: str) -> tuple[str, list[Block]]:
    lines = normalize_markdown(markdown_text).splitlines()
    blocks: list[Block] = []
    title = "CytoCV Research Document"
    index = 0

    while index < len(lines) and not lines[index].strip():
        index += 1

    if index < len(lines) and lines[index].startswith("# "):
        title = collapse_spaces(lines[index][2:])
        index += 1

    while index < len(lines):
        raw = lines[index].rstrip()
        stripped = raw.strip()

        if not stripped:
            index += 1
            continue

        heading = re.match(r"^(#{2,6})\s+(.*)$", raw)
        if heading:
            blocks.append(
                HeadingBlock(
                    level=len(heading.group(1)),
                    text=collapse_spaces(heading.group(2)),
                )
            )
            index += 1
            continue

        if "|" in raw and index + 1 < len(lines) and is_table_separator(lines[index + 1]):
            headers = split_table_row(raw)
            index += 2
            rows: list[list[str]] = []
            while index < len(lines):
                row_raw = lines[index].rstrip()
                if not row_raw.strip() or "|" not in row_raw:
                    break
                row = split_table_row(row_raw)
                if len(row) < len(headers):
                    row.extend([""] * (len(headers) - len(row)))
                rows.append(row[: len(headers)])
                index += 1
            blocks.append(TableBlock(headers=headers, rows=rows))
            continue

        if stripped.startswith("- "):
            items: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("- "):
                items.append(collapse_spaces(lines[index].strip()[2:]))
                index += 1
            blocks.append(ListBlock(ordered=False, items=items))
            continue

        numbered = re.match(r"^\d+\.\s+(.*)$", stripped)
        if numbered:
            items: list[str] = []
            while index < len(lines):
                match = re.match(r"^\d+\.\s+(.*)$", lines[index].strip())
                if not match:
                    break
                items.append(collapse_spaces(match.group(1)))
                index += 1
            blocks.append(ListBlock(ordered=True, items=items))
            continue

        paragraph_lines = [stripped]
        index += 1
        while index < len(lines):
            candidate = lines[index].rstrip()
            candidate_stripped = candidate.strip()
            if not candidate_stripped:
                break
            if re.match(r"^(#{2,6})\s+", candidate):
                break
            if candidate_stripped.startswith("- "):
                break
            if re.match(r"^\d+\.\s+", candidate_stripped):
                break
            if "|" in candidate and index + 1 < len(lines) and is_table_separator(lines[index + 1]):
                break
            paragraph_lines.append(candidate_stripped)
            index += 1
        blocks.append(ParagraphBlock(text=collapse_spaces(" ".join(paragraph_lines))))

    return title, blocks


INLINE_PATTERN = re.compile(
    r"\[([^\]]+)\]\(([^)]+)\)"
    r"|`([^`]+)`"
    r"|\*\*([^*]+)\*\*"
    r"|\*([^*]+)\*"
)


def render_inline(text: str) -> str:
    value = collapse_spaces(text)
    parts: list[str] = []
    last_index = 0
    for match in INLINE_PATTERN.finditer(value):
        parts.append(html.escape(value[last_index: match.start()]))
        if match.group(1) is not None:
            label = html.escape(match.group(1).strip())
            url = match.group(2).strip()
            if re.match(r"^https?://", url):
                parts.append(
                    f'<link href="{html.escape(url, quote=True)}" color="{LINK_HEX}">{label}</link>'
                )
            else:
                parts.append(label)
        elif match.group(3) is not None:
            parts.append(f'<font name="{FONT_MONO}">{html.escape(match.group(3).strip())}</font>')
        elif match.group(4) is not None:
            parts.append(f"<b>{html.escape(match.group(4).strip())}</b>")
        elif match.group(5) is not None:
            parts.append(f"<i>{html.escape(match.group(5).strip())}</i>")
        last_index = match.end()
    parts.append(html.escape(value[last_index:]))
    return "".join(parts)


def plain_text(value: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", value)
    text = text.replace("**", "").replace("*", "").replace("`", "")
    return collapse_spaces(text)


def build_styles() -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle(
            "title",
            fontName=FONT_BOLD,
            fontSize=24,
            leading=28,
            textColor=TEXT,
            spaceAfter=6,
        ),
        "series": ParagraphStyle(
            "series",
            fontName=FONT_ITALIC,
            fontSize=10.5,
            leading=12,
            textColor=MUTED_TEXT,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            fontName=FONT_REGULAR,
            fontSize=10.5,
            leading=15,
            textColor=TEXT,
            spaceAfter=10,
        ),
        "h2": ParagraphStyle(
            "h2",
            fontName=FONT_BOLD,
            fontSize=17,
            leading=21,
            textColor=TEXT,
            spaceBefore=16,
            spaceAfter=8,
            keepWithNext=1,
        ),
        "h3": ParagraphStyle(
            "h3",
            fontName=FONT_BOLD,
            fontSize=12.5,
            leading=16,
            textColor=TEXT,
            spaceBefore=12,
            spaceAfter=6,
            keepWithNext=1,
        ),
        "list_item": ParagraphStyle(
            "list_item",
            fontName=FONT_REGULAR,
            fontSize=10.5,
            leading=15,
            textColor=TEXT,
            leftIndent=18,
            firstLineIndent=-14,
            spaceAfter=4,
        ),
        "table_header": ParagraphStyle(
            "table_header",
            fontName=FONT_BOLD,
            fontSize=9.25,
            leading=11.5,
            textColor=TEXT,
            spaceAfter=0,
        ),
        "table_body": ParagraphStyle(
            "table_body",
            fontName=FONT_REGULAR,
            fontSize=9.1,
            leading=11.3,
            textColor=TEXT,
            spaceAfter=0,
        ),
    }


def estimate_col_widths(headers: list[str], rows: list[list[str]], total_width: float) -> list[float]:
    def visual_weight(value: str) -> float:
        text = plain_text(value)
        if not text:
            return 8.0
        compact = min(len(text), 38)
        tokens = [token for token in re.split(r"[\s/(),.-]+", text) if token]
        longest = max((len(token) for token in tokens), default=0)
        return max(10.0, min(44.0, compact + max(longest - 12, 0)))

    weights: list[float] = []
    column_count = len(headers)
    for column_index in range(column_count):
        column_values = [headers[column_index]]
        column_values.extend(
            row[column_index]
            for row in rows
            if column_index < len(row)
        )
        weight = max((visual_weight(value) for value in column_values), default=12.0)
        weights.append(weight)

    if column_count == 3:
        weights[-1] *= 1.15
    if column_count >= 4:
        weights[-1] *= 1.25
        weights[-2] *= 0.8

    total = sum(weights) or float(column_count)
    return [total_width * (weight / total) for weight in weights]


def build_table(block: TableBlock, styles: dict[str, ParagraphStyle], total_width: float) -> LongTable:
    data: list[list[Paragraph]] = [
        [Paragraph(render_inline(cell), styles["table_header"]) for cell in block.headers]
    ]
    for row in block.rows:
        data.append([Paragraph(render_inline(cell), styles["table_body"]) for cell in row])

    table = LongTable(
        data,
        colWidths=estimate_col_widths(block.headers, block.rows, total_width),
        repeatRows=1,
        hAlign="LEFT",
        splitByRow=1,
    )
    table.setStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), ACCENT_FILL),
            ("TEXTCOLOR", (0, 0), (-1, -1), TEXT),
            ("LINEABOVE", (0, 0), (-1, 0), 0.8, TABLE_GRID),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, TABLE_GRID),
            ("LINEBELOW", (0, -1), (-1, -1), 0.8, TABLE_GRID),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, TABLE_GRID),
            ("BOX", (0, 0), (-1, -1), 0.8, TABLE_GRID),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]
    )
    return table


def build_list(block: ListBlock, styles: dict[str, ParagraphStyle]) -> list:
    flowables: list = []
    for index, item in enumerate(block.items, start=1):
        prefix = f"{index}. " if block.ordered else "&bull; "
        flowables.append(Paragraph(prefix + render_inline(item), styles["list_item"]))
    flowables.append(Spacer(1, 0.04 * inch))
    return flowables


def build_story(title: str, blocks: list[Block], styles: dict[str, ParagraphStyle], doc_width: float) -> list:
    story: list = [
        Paragraph(html.escape(title), styles["title"]),
        Paragraph(RESEARCH_SERIES_LABEL, styles["series"]),
        HRFlowable(width="100%", thickness=0.8, color=ACCENT),
        Spacer(1, 0.18 * inch),
    ]

    for block in blocks:
        if isinstance(block, HeadingBlock):
            style_name = "h2" if block.level <= 2 else "h3"
            story.append(Paragraph(render_inline(block.text), styles[style_name]))
        elif isinstance(block, ParagraphBlock):
            story.append(Paragraph(render_inline(block.text), styles["body"]))
        elif isinstance(block, ListBlock):
            story.extend(build_list(block, styles))
        elif isinstance(block, TableBlock):
            story.append(build_table(block, styles, doc_width))
            story.append(Spacer(1, 0.12 * inch))

    return story


def _draw_footer(canvas, doc) -> None:
    footer_rule_y = 0.68 * inch
    footer_text_y = 0.44 * inch
    canvas.setStrokeColor(TABLE_GRID)
    canvas.setLineWidth(0.6)
    canvas.line(doc.leftMargin, footer_rule_y, PAGE_WIDTH - doc.rightMargin, footer_rule_y)
    canvas.setFillColor(MUTED_TEXT)
    canvas.setFont(FONT_REGULAR, 8.2)
    canvas.drawString(doc.leftMargin, footer_text_y, f"{RESEARCH_SERIES_LABEL} | {LICENSE_FOOTER}")
    canvas.drawRightString(PAGE_WIDTH - doc.rightMargin, footer_text_y, str(canvas.getPageNumber()))


def on_first_page(title: str):
    def _on_first_page(canvas, doc) -> None:
        canvas.setTitle(title)
        canvas.setAuthor("CytoCV project")
        canvas.setSubject(RESEARCH_SERIES_LABEL)
        canvas.setCreator("docs/research/generate_pdfs.py")
        _draw_footer(canvas, doc)

    return _on_first_page


def on_later_pages(title: str):
    def _on_later_pages(canvas, doc) -> None:
        canvas.setStrokeColor(TABLE_GRID)
        canvas.setLineWidth(0.6)
        header_rule_y = PAGE_HEIGHT - 0.72 * inch
        canvas.line(doc.leftMargin, header_rule_y, PAGE_WIDTH - doc.rightMargin, header_rule_y)
        canvas.setFillColor(MUTED_TEXT)
        canvas.setFont(FONT_BOLD, 8.2)
        canvas.drawString(doc.leftMargin, PAGE_HEIGHT - 0.56 * inch, title)
        _draw_footer(canvas, doc)

    return _on_later_pages


def build_pdf(title: str, blocks: list[Block], destination: Path) -> None:
    register_fonts()
    styles = build_styles()
    doc = SimpleDocTemplate(
        str(destination),
        pagesize=LETTER,
        invariant=True,
        leftMargin=LEFT_MARGIN,
        rightMargin=RIGHT_MARGIN,
        topMargin=TOP_MARGIN,
        bottomMargin=BOTTOM_MARGIN,
    )
    story = build_story(title, blocks, styles, doc.width)
    doc.build(
        story,
        onFirstPage=on_first_page(title),
        onLaterPages=on_later_pages(title),
    )


def main() -> None:
    base = Path(__file__).resolve().parent
    output_dir = base / PDF_OUTPUT_DIR_NAME
    output_dir.mkdir(parents=True, exist_ok=True)

    for stem in OUTPUT_STEMS:
        source = base / f"{stem}.md"
        destination = output_dir / f"{stem}.pdf"
        title, blocks = parse_markdown(source.read_text(encoding="utf-8-sig"))
        build_pdf(title, blocks, destination)


if __name__ == "__main__":
    main()
