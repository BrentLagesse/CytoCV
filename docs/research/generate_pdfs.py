from __future__ import annotations

import re
from pathlib import Path

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
LEFT = 54
TOP = 744
BOTTOM = 54
LINE_HEIGHT = 14
FONT_SIZE = 11
TITLE_SIZE = 18


def escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def normalize_markdown_line(line: str) -> str:
    value = line.rstrip()
    value = re.sub(r"^#{1,6}\s*", "", value)
    value = value.replace("**", "")
    value = value.replace("`", "")
    value = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", value)
    if value.startswith("- "):
        value = "- " + value[2:]
    return value


def wrap_line(text: str, width: int = 92) -> list[str]:
    if not text:
        return [""]
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def iter_text_lines(markdown_text: str) -> tuple[str, list[str]]:
    raw_lines = markdown_text.splitlines()
    title = "CytoCV Research Document"
    body: list[str] = []
    for raw in raw_lines:
        normalized = normalize_markdown_line(raw)
        if normalized and title == "CytoCV Research Document":
            title = normalized
            continue
        body.extend(wrap_line(normalized))
    return title, body


def build_content_stream(title: str, page_lines: list[str], page_number: int) -> bytes:
    commands = ["BT", f"/F2 {TITLE_SIZE} Tf", f"1 0 0 1 {LEFT} {TOP} Tm", f"({escape_pdf_text(title)}) Tj"]
    commands.extend([f"/F1 {FONT_SIZE} Tf"])
    y = TOP - 30
    for line in page_lines:
        commands.append(f"1 0 0 1 {LEFT} {y} Tm")
        commands.append(f"({escape_pdf_text(line)}) Tj")
        y -= LINE_HEIGHT
    commands.append(f"1 0 0 1 {PAGE_WIDTH - 100} 30 Tm")
    commands.append(f"(Page {page_number}) Tj")
    commands.append("ET")
    return "\n".join(commands).encode("latin-1", errors="replace")


def build_pdf(title: str, lines: list[str], destination: Path) -> None:
    lines_per_page = int((TOP - BOTTOM - 30) / LINE_HEIGHT)
    pages = [lines[i : i + lines_per_page] for i in range(0, len(lines), lines_per_page)] or [[]]

    objects: list[bytes] = []

    def add_object(payload: bytes) -> int:
        objects.append(payload)
        return len(objects)

    font1_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    font2_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")

    content_ids: list[int] = []
    page_ids: list[int] = []
    pages_id_placeholder = len(objects) + 1 + (len(pages) * 2)

    for index, page_lines in enumerate(pages, start=1):
        stream = build_content_stream(title, page_lines, index)
        content_id = add_object(
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream"
        )
        content_ids.append(content_id)
        page_id = add_object(
            (
                f"<< /Type /Page /Parent {pages_id_placeholder} 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 {font1_id} 0 R /F2 {font2_id} 0 R >> >> "
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
        title, lines = iter_text_lines(source.read_text(encoding="utf-8"))
        build_pdf(title, lines, destination)


if __name__ == "__main__":
    main()
