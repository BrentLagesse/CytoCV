from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from pathlib import Path

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
LEFT = 54
RIGHT = 54
TOP = 742
BOTTOM = 54
CONTENT_WIDTH = PAGE_WIDTH - LEFT - RIGHT
TITLE_SIZE = 22
SUBTITLE_SIZE = 10
HEADER_SIZE = 9
PARAGRAPH_SIZE = 10.5
PARAGRAPH_LEADING = 14
TABLE_SIZE = 9.5
TABLE_LEADING = 12
TABLE_PADDING = 6
RESEARCH_SERIES_LABEL = "CytoCV Research Documentation"


def escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def normalize_inline(value: str) -> str:
    text = value.strip()
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
    text = text.replace("**", "").replace("*", "").replace("`", "")
    text = text.replace("–", "-").replace("—", "-")
    return text


def is_table_separator(value: str) -> bool:
    return bool(re.match(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$", value))


def split_table_row(value: str) -> list[str]:
    text = value.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    return [normalize_inline(part) for part in text.split("|")]


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


def parse_markdown(markdown_text: str) -> tuple[str, list[Block]]:
    lines = markdown_text.splitlines()
    index = 0
    title = "CytoCV Research Document"
    blocks: list[Block] = []

    if lines and lines[0].startswith("# "):
        title = normalize_inline(lines[0][2:])
        index = 1

    while index < len(lines):
        raw = lines[index].rstrip()
        stripped = raw.strip()

        if not stripped:
            index += 1
            continue

        heading = re.match(r"^(#{2,6})\s+(.*)$", raw)
        if heading:
            blocks.append(HeadingBlock(level=len(heading.group(1)), text=normalize_inline(heading.group(2))))
            index += 1
            continue

        if (
            "|" in raw
            and index + 1 < len(lines)
            and is_table_separator(lines[index + 1])
        ):
            headers = split_table_row(raw)
            index += 2
            rows: list[list[str]] = []
            while index < len(lines):
                row_raw = lines[index].rstrip()
                if "|" not in row_raw or not row_raw.strip():
                    break
                row = split_table_row(row_raw)
                if len(row) < len(headers):
                    row.extend([""] * (len(headers) - len(row)))
                elif len(row) > len(headers):
                    row = row[: len(headers)]
                rows.append(row)
                index += 1
            blocks.append(TableBlock(headers=headers, rows=rows))
            continue

        if stripped.startswith("- "):
            items: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("- "):
                items.append(normalize_inline(lines[index].strip()[2:]))
                index += 1
            blocks.append(ListBlock(ordered=False, items=items))
            continue

        numbered = re.match(r"^\d+\.\s+(.*)$", stripped)
        if numbered:
            items: list[str] = []
            while index < len(lines):
                candidate = lines[index].strip()
                match = re.match(r"^\d+\.\s+(.*)$", candidate)
                if not match:
                    break
                items.append(normalize_inline(match.group(1)))
                index += 1
            blocks.append(ListBlock(ordered=True, items=items))
            continue

        paragraph_lines = [normalize_inline(stripped)]
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
            paragraph_lines.append(normalize_inline(candidate_stripped))
            index += 1
        blocks.append(ParagraphBlock(text=" ".join(part for part in paragraph_lines if part)))

    return title, blocks


def wrap_text(text: str, width: float, font_size: float) -> list[str]:
    average_char_width = max(font_size * 0.52, 1.0)
    max_chars = max(int(width / average_char_width), 12)
    wrapped = textwrap.wrap(
        text,
        width=max_chars,
        break_long_words=False,
        break_on_hyphens=False,
    )
    return wrapped or [""]


@dataclass(frozen=True)
class FontSpec:
    font_key: str
    size: float
    leading: float


class PDFRenderer:
    def __init__(self, title: str) -> None:
        self.title = title
        self.pages: list[list[str]] = []
        self.page_number = 0
        self.current_commands: list[str] = []
        self.y = TOP
        self._new_page()

    def _text(self, x: float, y: float, text: str, font_key: str, size: float) -> None:
        safe = escape_pdf_text(text)
        self.current_commands.append(
            f"BT /{font_key} {size:.2f} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm ({safe}) Tj ET"
        )

    def _line(self, x1: float, y1: float, x2: float, y2: float, width: float = 0.8) -> None:
        self.current_commands.append(
            f"q {width:.2f} w 0.68 0.72 0.80 RG {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S Q"
        )

    def _rect(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        *,
        fill_rgb: tuple[float, float, float] | None = None,
        stroke_rgb: tuple[float, float, float] = (0.72, 0.76, 0.84),
    ) -> None:
        if fill_rgb is not None:
            self.current_commands.append(
                "q "
                f"{fill_rgb[0]:.2f} {fill_rgb[1]:.2f} {fill_rgb[2]:.2f} rg "
                f"{stroke_rgb[0]:.2f} {stroke_rgb[1]:.2f} {stroke_rgb[2]:.2f} RG "
                f"{x:.2f} {y:.2f} {width:.2f} {height:.2f} re B Q"
            )
        else:
            self.current_commands.append(
                f"q {stroke_rgb[0]:.2f} {stroke_rgb[1]:.2f} {stroke_rgb[2]:.2f} RG "
                f"{x:.2f} {y:.2f} {width:.2f} {height:.2f} re S Q"
            )

    def _new_page(self) -> None:
        self.page_number += 1
        self.current_commands = []
        self.pages.append(self.current_commands)
        if self.page_number == 1:
            self._text(LEFT, PAGE_HEIGHT - 72, self.title, "F2", TITLE_SIZE)
            self._text(LEFT, PAGE_HEIGHT - 92, RESEARCH_SERIES_LABEL, "F3", SUBTITLE_SIZE)
            self._line(LEFT, PAGE_HEIGHT - 104, PAGE_WIDTH - RIGHT, PAGE_HEIGHT - 104, width=1.0)
            self._text(PAGE_WIDTH - RIGHT - 34, 32, f"{self.page_number}", "F1", HEADER_SIZE)
            self.y = PAGE_HEIGHT - 126
        else:
            self._text(LEFT, PAGE_HEIGHT - 42, self.title, "F2", HEADER_SIZE)
            self._line(LEFT, PAGE_HEIGHT - 50, PAGE_WIDTH - RIGHT, PAGE_HEIGHT - 50, width=0.6)
            self._text(PAGE_WIDTH - RIGHT - 34, 32, f"{self.page_number}", "F1", HEADER_SIZE)
            self.y = PAGE_HEIGHT - 72

    def _ensure_space(self, required_height: float) -> None:
        if self.y - required_height < BOTTOM:
            self._new_page()

    def add_heading(self, text: str, level: int) -> None:
        if level <= 2:
            font = FontSpec("F2", 15, 18)
            before = 16
            after = 8
        else:
            font = FontSpec("F2", 12.5, 15)
            before = 10
            after = 6
        self._ensure_space(before + font.leading + after)
        self.y -= before
        self._text(LEFT, self.y, text, font.font_key, font.size)
        self.y -= font.leading + after

    def add_paragraph(self, text: str) -> None:
        lines = wrap_text(text, CONTENT_WIDTH, PARAGRAPH_SIZE)
        needed = 4 + len(lines) * PARAGRAPH_LEADING + 6
        self._ensure_space(needed)
        self.y -= 4
        for line in lines:
            self._text(LEFT, self.y, line, "F1", PARAGRAPH_SIZE)
            self.y -= PARAGRAPH_LEADING
        self.y -= 6

    def add_list(self, items: list[str], ordered: bool) -> None:
        for position, item in enumerate(items, start=1):
            prefix = f"{position}. " if ordered else "- "
            indent = 16
            first_width = CONTENT_WIDTH - indent
            wrapped = wrap_text(item, first_width, PARAGRAPH_SIZE)
            needed = 2 + len(wrapped) * PARAGRAPH_LEADING + 2
            self._ensure_space(needed)
            self.y -= 2
            self._text(LEFT, self.y, prefix, "F1", PARAGRAPH_SIZE)
            self._text(LEFT + indent, self.y, wrapped[0], "F1", PARAGRAPH_SIZE)
            self.y -= PARAGRAPH_LEADING
            for line in wrapped[1:]:
                self._text(LEFT + indent, self.y, line, "F1", PARAGRAPH_SIZE)
                self.y -= PARAGRAPH_LEADING
            self.y -= 2

    def _table_column_widths(self, headers: list[str], rows: list[list[str]]) -> list[float]:
        weights: list[int] = []
        column_count = len(headers)
        for index in range(column_count):
            values = [headers[index]] + [row[index] for row in rows if index < len(row)]
            longest = max((len(value) for value in values), default=8)
            weights.append(max(longest, 8))
        total = sum(weights) or column_count
        return [CONTENT_WIDTH * (weight / total) for weight in weights]

    def _table_row_height(self, row: list[str], widths: list[float], bold: bool) -> tuple[float, list[list[str]]]:
        wrapped_cells: list[list[str]] = []
        max_lines = 1
        font_size = TABLE_SIZE
        for cell, width in zip(row, widths):
            wrapped = wrap_text(cell, max(width - (TABLE_PADDING * 2), 24), font_size)
            wrapped_cells.append(wrapped)
            max_lines = max(max_lines, len(wrapped))
        row_height = (max_lines * TABLE_LEADING) + (TABLE_PADDING * 2)
        return row_height, wrapped_cells

    def add_table(self, headers: list[str], rows: list[list[str]]) -> None:
        widths = self._table_column_widths(headers, rows)

        def draw_row(row: list[str], *, is_header: bool) -> None:
            nonlocal widths
            row_height, wrapped_cells = self._table_row_height(row, widths, bold=is_header)
            self._ensure_space(row_height + 2)
            top = self.y
            bottom = top - row_height
            x = LEFT
            for index, width in enumerate(widths):
                fill = (0.93, 0.95, 0.98) if is_header else None
                self._rect(x, bottom, width, row_height, fill_rgb=fill)
                lines = wrapped_cells[index]
                text_y = top - TABLE_PADDING - TABLE_SIZE
                font = "F2" if is_header else "F1"
                for line in lines:
                    self._text(x + TABLE_PADDING, text_y, line, font, TABLE_SIZE)
                    text_y -= TABLE_LEADING
                x += width
            self.y = bottom - 2

        self.y -= 4
        draw_row(headers, is_header=True)
        for row in rows:
            if len(row) < len(headers):
                row = row + [""] * (len(headers) - len(row))
            draw_row(row[: len(headers)], is_header=False)
        self.y -= 6

    def render_blocks(self, blocks: list[Block]) -> None:
        for block in blocks:
            if isinstance(block, HeadingBlock):
                self.add_heading(block.text, block.level)
            elif isinstance(block, ParagraphBlock):
                self.add_paragraph(block.text)
            elif isinstance(block, ListBlock):
                self.add_list(block.items, block.ordered)
            elif isinstance(block, TableBlock):
                self.add_table(block.headers, block.rows)


def build_pdf(title: str, blocks: list[Block], destination: Path) -> None:
    renderer = PDFRenderer(title)
    renderer.render_blocks(blocks)

    objects: list[bytes] = []

    def add_object(payload: bytes) -> int:
        objects.append(payload)
        return len(objects)

    font_regular = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    font_bold = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    font_italic = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique >>")

    page_ids: list[int] = []
    content_ids: list[int] = []
    pages_id_placeholder = len(objects) + 1 + (len(renderer.pages) * 2)

    for commands in renderer.pages:
        stream_text = "\n".join(commands).encode("latin-1", errors="replace")
        content_id = add_object(
            b"<< /Length " + str(len(stream_text)).encode("ascii") + b" >>\nstream\n" + stream_text + b"\nendstream"
        )
        content_ids.append(content_id)
        page_id = add_object(
            (
                f"<< /Type /Page /Parent {pages_id_placeholder} 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 {font_regular} 0 R /F2 {font_bold} 0 R /F3 {font_italic} 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            ).encode("ascii")
        )
        page_ids.append(page_id)

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    pages_id = add_object(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii"))
    catalog_id = add_object(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("ascii"))

    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    destination.write_bytes(output)


def main() -> None:
    base = Path(__file__).resolve().parent
    for stem in (
        "methods-and-system-description",
        "reproducibility-and-validation",
        "figure-catalog",
    ):
        source = base / f"{stem}.md"
        destination = base / f"{stem}.pdf"
        title, blocks = parse_markdown(source.read_text(encoding="utf-8"))
        build_pdf(title, blocks, destination)


if __name__ == "__main__":
    main()
