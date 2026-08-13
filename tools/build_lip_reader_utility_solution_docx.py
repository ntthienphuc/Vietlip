from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageDraw, ImageFont, ImageOps
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
DOC_EVIDENCE_DIR = ROOT / "assets" / "doc_evidence"
WORK_DIR = ROOT / ".docx_work" / "generated"
DEFAULT_OUTPUT = (
    ROOT
    / "output"
    / "Ho_so_Giai_phap_huu_ich_Doc_moi_tieng_Viet_AI.docx"
)

NAVY = "173A55"
BLUE = "2D6A8E"
TEAL = "20756C"
PALE_BLUE = "EAF3F7"
PALE_TEAL = "E9F5F2"
PALE_GOLD = "F7F1DF"
PALE_RED = "F9EAEA"
INK = "1E2933"
MUTED = "60717E"
LINE = "AFC2CD"
WHITE = "FFFFFF"
GREEN = "2C7A63"
RED = "A54343"
GOLD = "9A7120"


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_text(cell, text: str, *, bold: bool = False, color: str = INK,
                  size: float = 11.5, align=WD_ALIGN_PARAGRAPH.LEFT) -> None:
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = align
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.08
    r = p.add_run(text)
    r.bold = bold
    r.font.name = "Times New Roman"
    r.font.size = Pt(size)
    r.font.color.rgb = RGBColor.from_string(color)
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def set_cell_margins(cell, top=80, start=120, bottom=80, end=120) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for side, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{side}"))
        if node is None:
            node = OxmlElement(f"w:{side}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def set_row_cant_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    cant_split = tr_pr.find(qn("w:cantSplit"))
    if cant_split is None:
        tr_pr.append(OxmlElement("w:cantSplit"))


def set_table_borders(table, color=LINE, size=6) -> None:
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        node = borders.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}")
            borders.append(node)
        node.set(qn("w:val"), "single")
        node.set(qn("w:sz"), str(size))
        node.set(qn("w:space"), "0")
        node.set(qn("w:color"), color)


def set_table_geometry(table, widths_cm: Sequence[float], indent_dxa: int = 120) -> None:
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_pr = table._tbl.tblPr
    layout = tbl_pr.find(qn("w:tblLayout"))
    if layout is None:
        layout = OxmlElement("w:tblLayout")
        tbl_pr.append(layout)
    layout.set(qn("w:type"), "fixed")

    total_dxa = int(round(sum(widths_cm) / 2.54 * 1440))
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(total_dxa))
    tbl_w.set(qn("w:type"), "dxa")

    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), str(indent_dxa))
    tbl_ind.set(qn("w:type"), "dxa")

    grid = table._tbl.tblGrid
    for old in list(grid):
        grid.remove(old)
    for width_cm in widths_cm:
        width_dxa = int(round(width_cm / 2.54 * 1440))
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width_dxa))
        grid.append(col)

    for row in table.rows:
        for idx, cell in enumerate(row.cells):
            width_dxa = int(round(widths_cm[min(idx, len(widths_cm) - 1)] / 2.54 * 1440))
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_w = tc_pr.find(qn("w:tcW"))
            if tc_w is None:
                tc_w = OxmlElement("w:tcW")
                tc_pr.append(tc_w)
            tc_w.set(qn("w:w"), str(width_dxa))
            tc_w.set(qn("w:type"), "dxa")
            set_cell_margins(cell)


def set_paragraph_keep(paragraph, *, keep_next=False, keep_lines=True, page_break_before=False):
    p_pr = paragraph._p.get_or_add_pPr()
    for tag, enabled in (
        ("keepNext", keep_next),
        ("keepLines", keep_lines),
        ("pageBreakBefore", page_break_before),
    ):
        existing = p_pr.find(qn(f"w:{tag}"))
        if enabled and existing is None:
            p_pr.append(OxmlElement(f"w:{tag}"))
        elif not enabled and existing is not None:
            p_pr.remove(existing)


def set_alt_text(shape, title: str, description: str) -> None:
    doc_pr = shape._inline.docPr
    doc_pr.set("title", title)
    doc_pr.set("descr", description)


def add_field(paragraph, instruction: str) -> None:
    run = paragraph.add_run()
    fld_char_begin = OxmlElement("w:fldChar")
    fld_char_begin.set(qn("w:fldCharType"), "begin")
    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = instruction
    fld_char_separate = OxmlElement("w:fldChar")
    fld_char_separate.set(qn("w:fldCharType"), "separate")
    display = OxmlElement("w:t")
    display.text = "1"
    fld_char_separate.append(display)
    fld_char_end = OxmlElement("w:fldChar")
    fld_char_end.set(qn("w:fldCharType"), "end")
    run._r.extend([fld_char_begin, instr_text, fld_char_separate, fld_char_end])


def configure_numbering(document: Document) -> tuple[int, int]:
    numbering = document.part.numbering_part.element
    abstract_ids = [
        int(node.get(qn("w:abstractNumId")))
        for node in numbering.findall(qn("w:abstractNum"))
    ]
    num_ids = [int(node.get(qn("w:numId"))) for node in numbering.findall(qn("w:num"))]
    next_abs = max(abstract_ids, default=0) + 1
    next_num = max(num_ids, default=0) + 1

    def make_abstract(abs_id: int, fmt: str, lvl_text: str, nsid_value: str,
                      font: str | None = None):
        abstract = OxmlElement("w:abstractNum")
        abstract.set(qn("w:abstractNumId"), str(abs_id))
        nsid = OxmlElement("w:nsid")
        nsid.set(qn("w:val"), nsid_value)
        abstract.append(nsid)
        multi = OxmlElement("w:multiLevelType")
        multi.set(qn("w:val"), "singleLevel")
        abstract.append(multi)
        tmpl = OxmlElement("w:tmpl")
        tmpl.set(qn("w:val"), nsid_value[::-1])
        abstract.append(tmpl)
        lvl = OxmlElement("w:lvl")
        lvl.set(qn("w:ilvl"), "0")
        start = OxmlElement("w:start")
        start.set(qn("w:val"), "1")
        num_fmt = OxmlElement("w:numFmt")
        num_fmt.set(qn("w:val"), fmt)
        text = OxmlElement("w:lvlText")
        text.set(qn("w:val"), lvl_text)
        suff = OxmlElement("w:suff")
        suff.set(qn("w:val"), "space")
        lvl_jc = OxmlElement("w:lvlJc")
        lvl_jc.set(qn("w:val"), "left")
        p_pr = OxmlElement("w:pPr")
        tabs = OxmlElement("w:tabs")
        tab = OxmlElement("w:tab")
        tab.set(qn("w:val"), "num")
        tab.set(qn("w:pos"), "540")
        tabs.append(tab)
        ind = OxmlElement("w:ind")
        ind.set(qn("w:left"), "540")
        ind.set(qn("w:hanging"), "280")
        p_pr.extend([tabs, ind])
        lvl.extend([start, num_fmt, text, suff, lvl_jc, p_pr])
        if font:
            r_pr = OxmlElement("w:rPr")
            r_fonts = OxmlElement("w:rFonts")
            r_fonts.set(qn("w:ascii"), font)
            r_fonts.set(qn("w:hAnsi"), font)
            r_pr.append(r_fonts)
            lvl.append(r_pr)
        abstract.append(lvl)
        first_num_index = next(
            (idx for idx, child in enumerate(numbering) if child.tag == qn("w:num")),
            len(numbering),
        )
        numbering.insert(first_num_index, abstract)

    def make_num(num_id: int, abs_id: int, restart=True):
        num = OxmlElement("w:num")
        num.set(qn("w:numId"), str(num_id))
        abs_ref = OxmlElement("w:abstractNumId")
        abs_ref.set(qn("w:val"), str(abs_id))
        num.append(abs_ref)
        if restart:
            override = OxmlElement("w:lvlOverride")
            override.set(qn("w:ilvl"), "0")
            start_override = OxmlElement("w:startOverride")
            start_override.set(qn("w:val"), "1")
            override.append(start_override)
            num.append(override)
        numbering.append(num)

    make_abstract(next_abs, "bullet", "•", "A17B24C9", "Times New Roman")
    bullet_num = next_num
    make_num(bullet_num, next_abs)
    make_abstract(
        next_abs + 1,
        "decimal",
        "%1.",
        "C42D91E7",
        "Times New Roman",
    )
    decimal_num = next_num + 1
    make_num(decimal_num, next_abs + 1)
    return bullet_num, decimal_num


def apply_num(paragraph, num_id: int, level: int = 0) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    num_pr = p_pr.find(qn("w:numPr"))
    if num_pr is None:
        num_pr = OxmlElement("w:numPr")
        p_pr.append(num_pr)
    ilvl = num_pr.find(qn("w:ilvl"))
    if ilvl is None:
        ilvl = OxmlElement("w:ilvl")
        num_pr.append(ilvl)
    ilvl.set(qn("w:val"), str(level))
    num_id_node = num_pr.find(qn("w:numId"))
    if num_id_node is None:
        num_id_node = OxmlElement("w:numId")
        num_pr.append(num_id_node)
    num_id_node.set(qn("w:val"), str(num_id))


def configure_document() -> tuple[Document, int, int]:
    doc = Document()
    props = doc.core_properties
    props.title = (
        "Hệ thống và phương pháp nhận dạng lời nói tiếng Việt từ chuyển động môi"
    )
    props.subject = "Hồ sơ kỹ thuật giải pháp hữu ích Lip Reader"
    props.author = "Nhóm phát triển Lip Reader"
    props.last_modified_by = "Nhóm phát triển Lip Reader"
    props.comments = "Hồ sơ kỹ thuật hoàn thiện cho bản phát hành hiện tại."
    props.keywords = (
        "đọc môi tiếng Việt; visual speech recognition; Auto-AVSR; "
        "LLM có kiểm soát; ứng dụng di động"
    )
    props.category = "Hồ sơ kỹ thuật"

    section = doc.sections[0]
    # Match the accepted VSL/WebGIS dossier geometry exactly: US Letter,
    # 3 cm binding margin, 2 cm outer margin, and 2.2 cm top/bottom.
    section.page_width = Inches(8.5)
    section.page_height = Inches(11.0)
    section.left_margin = Cm(3.0)
    section.right_margin = Cm(2.0)
    section.top_margin = Cm(2.2)
    section.bottom_margin = Cm(2.2)
    section.header_distance = Inches(0.5)
    section.footer_distance = Inches(0.5)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(13)
    normal.font.color.rgb = RGBColor(0, 0, 0)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    normal.paragraph_format.first_line_indent = Cm(0)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.0
    normal.paragraph_format.widow_control = True

    style_specs = {
        "Title": (26, NAVY, False, WD_ALIGN_PARAGRAPH.JUSTIFY, 0, 15),
        "Heading 1": (15, "365F91", True, WD_ALIGN_PARAGRAPH.JUSTIFY, 24, 6),
        "Heading 2": (14, "4F81BD", True, WD_ALIGN_PARAGRAPH.JUSTIFY, 10, 6),
        "Heading 3": (13, "4F81BD", True, WD_ALIGN_PARAGRAPH.JUSTIFY, 10, 6),
        "Caption": (9, "4F81BD", True, WD_ALIGN_PARAGRAPH.CENTER, 0, 6),
    }
    for name, (size, color, bold, alignment, before, after) in style_specs.items():
        style = styles[name]
        style.font.name = "Times New Roman"
        style.font.size = Pt(size)
        style.font.bold = bold
        style.font.color.rgb = RGBColor.from_string(color)
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
        style.paragraph_format.alignment = alignment
        style.paragraph_format.first_line_indent = Cm(0)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.line_spacing = 1.0
        style.paragraph_format.keep_with_next = name.startswith("Heading")

    for list_name in ("List Bullet", "List Number"):
        list_style = styles[list_name]
        list_style.font.name = "Times New Roman"
        list_style.font.size = Pt(13)
        list_style.font.color.rgb = RGBColor.from_string(INK)
        list_style._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
        list_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        list_style.paragraph_format.left_indent = Cm(0.95)
        list_style.paragraph_format.first_line_indent = Cm(-0.5)
        list_style.paragraph_format.space_after = Pt(4)
        list_style.paragraph_format.line_spacing = 1.05
        list_style.paragraph_format.widow_control = True

    for custom_name in ("Cover Eyebrow", "Cover Meta", "Callout", "Figure Note", "Claim"):
        if custom_name not in styles:
            styles.add_style(custom_name, WD_STYLE_TYPE.PARAGRAPH)

    eyebrow = styles["Cover Eyebrow"]
    eyebrow.font.name = "Times New Roman"
    eyebrow.font.size = Pt(12)
    eyebrow.font.bold = True
    eyebrow.font.color.rgb = RGBColor.from_string(BLUE)
    eyebrow.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    eyebrow.paragraph_format.space_after = Pt(10)
    eyebrow.paragraph_format.first_line_indent = Cm(0)

    meta = styles["Cover Meta"]
    meta.font.name = "Times New Roman"
    meta.font.size = Pt(11.5)
    meta.font.color.rgb = RGBColor.from_string(MUTED)
    meta.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.paragraph_format.first_line_indent = Cm(0)
    meta.paragraph_format.space_after = Pt(4)

    callout = styles["Callout"]
    callout.font.name = "Times New Roman"
    callout.font.size = Pt(13)
    callout.font.color.rgb = RGBColor(0, 0, 0)
    callout.font.bold = False
    callout.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    callout.paragraph_format.first_line_indent = Cm(0)
    callout.paragraph_format.left_indent = Cm(0.45)
    callout.paragraph_format.right_indent = Cm(0.25)
    callout.paragraph_format.space_before = Pt(4)
    callout.paragraph_format.space_after = Pt(8)
    callout.paragraph_format.line_spacing = 1.0

    note = styles["Figure Note"]
    note.font.name = "Times New Roman"
    note.font.size = Pt(10.5)
    note.font.italic = True
    note.font.color.rgb = RGBColor.from_string(MUTED)
    note.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    note.paragraph_format.first_line_indent = Cm(0)
    note.paragraph_format.space_after = Pt(7)
    note.paragraph_format.line_spacing = 1.0

    claim = styles["Claim"]
    claim.font.name = "Times New Roman"
    claim.font.size = Pt(13)
    claim.font.color.rgb = RGBColor.from_string(INK)
    claim.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    claim.paragraph_format.first_line_indent = Cm(0)
    claim.paragraph_format.left_indent = Cm(0.95)
    claim.paragraph_format.first_line_indent = Cm(-0.5)
    claim.paragraph_format.space_after = Pt(7)
    claim.paragraph_format.line_spacing = 1.2

    header = section.header
    hp = header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    hp.paragraph_format.space_after = Pt(0)
    # The VSL exemplar deliberately leaves the header blank.

    footer = section.footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fr = fp.add_run("Trang ")
    fr.font.name = "Times New Roman"
    fr.font.size = Pt(9)
    fr.font.color.rgb = RGBColor.from_string(MUTED)
    add_field(fp, "PAGE")

    bullet_num, decimal_num = configure_numbering(doc)
    return doc, bullet_num, decimal_num


def add_para(doc: Document, text: str, *, bold_prefix: str | None = None,
             style: str | None = None, align=None, indent=True):
    p = doc.add_paragraph(style=style)
    if align is not None:
        p.alignment = align
    if not indent:
        p.paragraph_format.first_line_indent = Cm(0)
    if bold_prefix and text.startswith(bold_prefix):
        r1 = p.add_run(bold_prefix)
        r1.bold = True
        p.add_run(text[len(bold_prefix):])
    else:
        p.add_run(text)
    set_paragraph_keep(p, keep_lines=True)
    return p


def add_bullets(doc: Document, items: Iterable[str], num_id: int):
    for item in items:
        p = add_para(doc, item, indent=False)
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        apply_num(p, num_id)
        p.paragraph_format.left_indent = Cm(0.95)
        p.paragraph_format.first_line_indent = Cm(-0.5)
        p.paragraph_format.space_after = Pt(4)


def add_callout(doc: Document, text: str, fill=PALE_BLUE, border=BLUE):
    """Add an unframed emphasis paragraph.

    ``fill`` and ``border`` remain in the signature so older call sites keep
    their semantic severity, but the dossier intentionally renders no shaded
    box or border. This matches the formal Sign/VSL dossier treatment.
    """
    p = doc.add_paragraph(style="Callout")
    p.add_run(text)
    set_paragraph_keep(p, keep_lines=True)
    return p


def add_table(doc: Document, headers: Sequence[str], rows: Sequence[Sequence[str]],
              widths: Sequence[float], *, header_fill=NAVY, font_size=11.2):
    table = doc.add_table(rows=1, cols=len(headers))
    set_table_geometry(table, widths)
    set_table_borders(table)
    hdr = table.rows[0]
    set_repeat_table_header(hdr)
    set_row_cant_split(hdr)
    for idx, text in enumerate(headers):
        set_cell_shading(hdr.cells[idx], header_fill)
        set_cell_text(
            hdr.cells[idx], text, bold=True, color=WHITE, size=font_size,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )
    for row_idx, values in enumerate(rows):
        row = table.add_row()
        set_row_cant_split(row)
        cells = row.cells
        for idx, value in enumerate(values):
            if row_idx % 2 == 1:
                set_cell_shading(cells[idx], "F7FAFB")
            set_cell_text(cells[idx], str(value), size=font_size)
        set_table_geometry(table, widths)
    table.rows[-1]._tr.get_or_add_trPr()
    spacer = doc.add_paragraph()
    spacer.paragraph_format.first_line_indent = Cm(0)
    spacer.paragraph_format.space_after = Pt(1)
    return table


def add_picture(doc: Document, image_path: Path, caption: str, *,
                width_in: float = 5.85, note: str | None = None):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(2)
    set_paragraph_keep(p, keep_next=True, keep_lines=True)
    run = p.add_run()
    shape = run.add_picture(str(image_path), width=Inches(width_in))
    set_alt_text(shape, caption, caption)
    cap = doc.add_paragraph(caption, style="Caption")
    set_paragraph_keep(cap, keep_next=bool(note), keep_lines=True)
    if note:
        n = doc.add_paragraph(note, style="Figure Note")
        set_paragraph_keep(n, keep_lines=True)


def enforce_times_new_roman(doc: Document) -> None:
    """Set explicit Times New Roman font mappings on every Word text run."""

    def set_rfonts(r_pr) -> None:
        r_fonts = r_pr.find(qn("w:rFonts"))
        if r_fonts is None:
            r_fonts = OxmlElement("w:rFonts")
            r_pr.insert(0, r_fonts)
        for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
            r_fonts.set(qn(f"w:{attr}"), "Times New Roman")
        r_fonts.set(qn("w:hint"), "default")

    def paragraphs_in(container):
        for paragraph in container.paragraphs:
            yield paragraph
        for table in container.tables:
            for row in table.rows:
                for cell in row.cells:
                    yield from paragraphs_in(cell)

    containers = [doc]
    for section in doc.sections:
        containers.extend([section.header, section.footer])
    for container in containers:
        for paragraph in paragraphs_in(container):
            for run in paragraph.runs:
                run.font.name = "Times New Roman"
                r_pr = run._element.get_or_add_rPr()
                set_rfonts(r_pr)

    # Word can source paragraph marks, list labels and empty layout runs from
    # styles/numbering even when every visible run already has an explicit font.
    for style in doc.styles:
        if not hasattr(style, "font") or not hasattr(style._element, "get_or_add_rPr"):
            continue
        style.font.name = "Times New Roman"
        r_pr = style._element.get_or_add_rPr()
        set_rfonts(r_pr)

    numbering = doc.part.numbering_part.element
    for level in numbering.findall(f".//{qn('w:lvl')}"):
        r_pr = level.find(qn("w:rPr"))
        if r_pr is None:
            r_pr = OxmlElement("w:rPr")
            level.append(r_pr)
        set_rfonts(r_pr)


def font(size: int, bold=False):
    path = Path(
        "C:/Windows/Fonts/timesbd.ttf"
        if bold
        else "C:/Windows/Fonts/times.ttf"
    )
    return ImageFont.truetype(str(path), size)


def pc(value):
    if isinstance(value, str) and len(value) in (6, 8) and not value.startswith("#"):
        return f"#{value}"
    return value


def rounded_box(draw: ImageDraw.ImageDraw, box, fill, outline=LINE, radius=22, width=3):
    draw.rounded_rectangle(box, radius=radius, fill=pc(fill), outline=pc(outline), width=width)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt, max_width: int) -> list[str]:
    lines: list[str] = []
    for explicit_line in text.splitlines() or [""]:
        words = explicit_line.split()
        current = ""
        if not words:
            lines.append("")
            continue
        for word in words:
            trial = word if not current else f"{current} {word}"
            if draw.textlength(trial, font=fnt) <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


def draw_centered_text(draw, box, title, body, fill=INK):
    x1, y1, x2, y2 = box
    title_font = font(29, True)
    body_font = font(22)
    lines = wrap_text(draw, body, body_font, x2 - x1 - 42)
    total = 35 + len(lines) * 29
    y = y1 + (y2 - y1 - total) / 2
    bbox = draw.textbbox((0, 0), title, font=title_font)
    draw.text(((x1 + x2 - (bbox[2] - bbox[0])) / 2, y), title, font=title_font, fill=pc(fill))
    y += 42
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=body_font)
        draw.text(((x1 + x2 - (bbox[2] - bbox[0])) / 2, y), line, font=body_font, fill=pc(MUTED))
        y += 29


def arrow(draw, start, end, color=BLUE, width=5):
    draw.line([start, end], fill=pc(color), width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    head = 15
    for delta in (2.55, -2.55):
        p = (
            end[0] + head * math.cos(angle + delta),
            end[1] + head * math.sin(angle + delta),
        )
        draw.line([end, p], fill=pc(color), width=width)


def new_canvas(title: str, subtitle: str = ""):
    im = Image.new("RGB", (1500, 900), pc(WHITE))
    draw = ImageDraw.Draw(im)
    draw.rectangle((0, 0, 1500, 105), fill=pc(NAVY))
    draw.text((55, 24), title, font=font(34, True), fill=pc(WHITE))
    if subtitle:
        draw.text((57, 68), subtitle, font=font(18), fill="#D8E8F0")
    return im, draw


def generate_diagrams() -> dict[str, Path]:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    generated: dict[str, Path] = {}

    im, d = new_canvas(
        "Kiến trúc tổng thể",
        "Điện thoại gửi video hoặc luồng khung hình; server giữ bằng chứng thị giác bất biến",
    )
    boxes = [
        ((55, 260, 285, 555), PALE_BLUE, "ỨNG DỤNG", "Camera / thư viện\nPhụ đề trực tiếp\n3 chế độ xử lý"),
        ((350, 210, 650, 605), PALE_TEAL, "API FASTAPI", "WebSocket + HTTP\nCửa sổ chồng lấn\nQueue + dọn tệp"),
        ((715, 175, 1020, 640), PALE_GOLD, "AUTO-AVSR", "Căn chỉnh mặt\nROI miệng 96×96\nConformer + CTC\nN-best"),
        ((1085, 220, 1445, 595), PALE_RED, "LLM TÙY CHỌN", "Chỉ nhận văn bản\nChọn nguyên N-best\nhoặc gợi ý riêng\nKhông sửa bằng chứng"),
    ]
    for box, fill, title, body in boxes:
        rounded_box(d, box, fill)
        draw_centered_text(d, box, title, body)
    arrow(d, (285, 405), (350, 405))
    arrow(d, (650, 405), (715, 405))
    arrow(d, (1020, 405), (1085, 405))
    d.text((420, 735), "Đầu ra: visual transcript + N-best + metadata + review_required", font=font(27, True), fill=pc(NAVY))
    path = WORK_DIR / "fig_01_architecture.png"
    im.save(path, quality=95)
    generated["architecture"] = path

    im, d = new_canvas("Tiền xử lý hình học theo thời gian", "Chuẩn hóa chuyển động môi trước suy luận")
    labels = [
        ("1", "Giải mã video", "MP4 → khung hình"),
        ("2", "Mốc khuôn mặt", "MediaPipe landmarks"),
        ("3", "Làm mượt", "Giảm rung theo thời gian"),
        ("4", "Căn chỉnh", "Affine theo mean face"),
        ("5", "ROI miệng", "96×96 xám, 25 fps"),
        ("6", "Chuẩn hóa", "Center crop 88 + normalize"),
    ]
    for i, (num, title, body) in enumerate(labels):
        x = 55 + (i % 3) * 485
        y = 170 + (i // 3) * 310
        box = (x, y, x + 390, y + 210)
        rounded_box(d, box, PALE_BLUE if i < 3 else PALE_TEAL)
        d.ellipse((x + 18, y + 18, x + 78, y + 78), fill=pc(BLUE))
        d.text((x + 39, y + 29), num, anchor="mm", font=font(26, True), fill=pc(WHITE))
        d.text((x + 95, y + 34), title, font=font(26, True), fill=pc(NAVY))
        for j, line in enumerate(wrap_text(d, body, font(21), 330)):
            d.text((x + 30, y + 112 + j * 28), line, font=font(21), fill=pc(MUTED))
        if i not in (2, 5):
            arrow(d, (x + 400, y + 105), (x + 465, y + 105))
    arrow(d, (1230, 390), (1230, 465))
    path = WORK_DIR / "fig_02_preprocessing.png"
    im.save(path, quality=95)
    generated["preprocessing"] = path

    im, d = new_canvas("Giải mã và bảo toàn bằng chứng", "Điểm giải mã là điểm xếp hạng tương đối, không phải xác suất đúng")
    rounded_box(d, (70, 180, 460, 670), PALE_GOLD)
    draw_centered_text(d, (70, 180, 460, 670), "BỘ GIẢI MÃ", "Attention + CTC\nBeam width = 10\nSinh N-best = 10")
    rounded_box(d, (555, 145, 965, 705), PALE_BLUE)
    d.text((610, 190), "N-BEST BẤT BIẾN", font=font(30, True), fill=pc(NAVY))
    entries = [
        ("#1", "em khen thân mến trong bài học...", "−18.42"),
        ("#2", "em khen thân mến trong bài học...", "−18.77"),
        ("#3", "em khen thân mến trong bài họp...", "−19.21"),
    ]
    for i, (rank, text, score) in enumerate(entries):
        y = 270 + i * 120
        rounded_box(d, (595, y, 925, y + 90), WHITE, LINE, 14, 2)
        d.text((615, y + 16), rank, font=font(22, True), fill=pc(BLUE))
        d.text((665, y + 16), text, font=font(17), fill=pc(INK))
        d.text((805, y + 52), f"score {score}", font=font(16), fill=pc(MUTED))
    rounded_box(d, (1060, 210, 1430, 640), PALE_RED, RED)
    draw_centered_text(d, (1060, 210, 1430, 640), "RÀO CHẮN", "visual_transcript\nkhông bị ghi đè\n\nreview_required = true")
    arrow(d, (460, 425), (555, 425))
    arrow(d, (965, 425), (1060, 425), RED)
    path = WORK_DIR / "fig_03_evidence.png"
    im.save(path, quality=95)
    generated["evidence"] = path

    im, d = new_canvas("Ba chế độ sử dụng", "Mức tự do tăng dần nhưng bằng chứng thị giác luôn được giữ riêng")
    modes = [
        (PALE_BLUE, BLUE, "VISUAL ONLY", "Hiển thị top-1 + N-best\nKhông gọi LLM\nRủi ro thấp nhất"),
        (PALE_TEAL, TEAL, "CONTEXT SELECT", "LLM chỉ chọn nguyên văn\nmột ứng viên N-best\nCó lý do lựa chọn"),
        (PALE_RED, RED, "LLM ASSIST", "Tạo bản gợi ý tự do riêng\nCần đồng ý rủi ro\nKhông thay visual transcript"),
    ]
    for i, (fill, outline, title, body) in enumerate(modes):
        x = 65 + i * 485
        box = (x, 205, x + 405, 650)
        rounded_box(d, box, fill, outline, 24, 4)
        draw_centered_text(d, box, title, body, outline)
    d.text((300, 748), "Video không gửi cho LLM • Chỉ N-best và ngữ cảnh văn bản đi qua ranh giới này", font=font(26, True), fill=pc(NAVY))
    path = WORK_DIR / "fig_04_modes.png"
    im.save(path, quality=95)
    generated["modes"] = path

    im, d = new_canvas("Triển khai không GPU và mở rộng tải", "Một worker mô hình trên CPU; dùng hàng đợi khi tăng tải")
    rounded_box(d, (65, 205, 390, 655), PALE_BLUE)
    draw_centered_text(d, (65, 205, 390, 655), "CLIENT", "Upload clip ngắn\nPolling/job ID\nTimeout rõ ràng")
    rounded_box(d, (485, 155, 850, 705), PALE_TEAL)
    draw_centered_text(
        d,
        (485, 155, 850, 705),
        "API + QUEUE",
        "Xác thực\nQueue hữu hạn trong tiến trình\nMột worker model\nPolling / hủy job",
    )
    rounded_box(d, (945, 115, 1435, 745), PALE_GOLD)
    draw_centered_text(d, (945, 115, 1435, 745), "WORKER VSR", "CPU: chạy được\nGPU: tăng thông lượng\nNạp sẵn mô hình\nGiới hạn theo tài nguyên")
    arrow(d, (390, 430), (485, 430))
    arrow(d, (850, 430), (945, 430))
    d.text((285, 800), "Bản hiện tại: queue asyncio tối đa 8 job • Mở rộng: broker bền vững + object storage TTL", font=font(22, True), fill=pc(NAVY))
    path = WORK_DIR / "fig_05_deployment.png"
    im.save(path, quality=95)
    generated["deployment"] = path

    im, d = new_canvas("Vòng đời dữ liệu và quyền riêng tư", "Giảm thiểu dữ liệu theo mặc định")
    stages = [
        (PALE_BLUE, "ĐIỆN THOẠI", "Người dùng chọn clip\nvà chế độ"),
        (PALE_TEAL, "TẠM TRÊN SERVER", "Kiểm tra header,\nthời lượng, kích thước"),
        (PALE_GOLD, "SUY LUẬN", "Khung miệng trong RAM\nmodel sinh N-best"),
        (PALE_RED, "XÓA BẮT BUỘC", "finally cleanup\nCache-Control: no-store"),
    ]
    for i, (fill, title, body) in enumerate(stages):
        x = 55 + i * 365
        box = (x, 240, x + 300, 610)
        rounded_box(d, box, fill)
        draw_centered_text(d, box, title, body)
        if i < len(stages) - 1:
            arrow(d, (x + 300, 425), (x + 355, 425))
    d.text((350, 720), "LLM (nếu bật) chỉ nhận văn bản • Lịch sử nằm cục bộ trên thiết bị", font=font(27, True), fill=pc(NAVY))
    path = WORK_DIR / "fig_06_privacy.png"
    im.save(path, quality=95)
    generated["privacy"] = path

    return generated


def make_phone_plate(left: Path, right: Path, title: str, labels: tuple[str, str], output: Path):
    canvas = Image.new("RGB", (1600, 1200), "#F3F7F9")
    d = ImageDraw.Draw(canvas)
    d.rectangle((0, 0, 1600, 110), fill=pc(NAVY))
    d.text((55, 27), title, font=font(34, True), fill=pc(WHITE))
    for idx, (src, label) in enumerate(((left, labels[0]), (right, labels[1]))):
        phone = Image.open(src).convert("RGB")
        available_h = 950
        scale = min(650 / phone.width, available_h / phone.height)
        phone = phone.resize((int(phone.width * scale), int(phone.height * scale)), Image.Resampling.LANCZOS)
        phone = ImageOps.expand(phone, border=5, fill=pc(NAVY))
        x = 95 + idx * 780 + (650 - phone.width) // 2
        y = 165
        canvas.paste(phone, (x, y))
        bbox = d.textbbox((0, 0), label, font=font(24, True))
        d.text((x + (phone.width - (bbox[2] - bbox[0])) / 2, 1135), label, font=font(24, True), fill=pc(NAVY))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, quality=95)


def add_cover(doc: Document):
    p = doc.add_paragraph("HỒ SƠ MÔ TẢ GIẢI PHÁP HỮU ÍCH")
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.first_line_indent = Cm(0)
    for run in p.runs:
        run.bold = True
        run.font.name = "Times New Roman"
        run.font.size = Pt(13)
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(6)
    line2 = p.add_run(
        "NHẬN DẠNG LỜI NÓI TIẾNG VIỆT TỪ CHUYỂN ĐỘNG MÔI "
        "TRÊN THIẾT BỊ DI ĐỘNG, KẾT HỢP SUY LUẬN THỊ GIÁC "
        "VÀ HỖ TRỢ NGỮ CẢNH CÓ KIỂM SOÁT"
    )
    line2.bold = True
    line2.font.name = "Times New Roman"
    line2.font.size = Pt(13)
    line2.font.color.rgb = RGBColor(0, 0, 0)
    for r in p.runs:
        r._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")

    # Keep the front matter minimal, matching the VSL dossier rather than a
    # marketing cover.
    for _ in range(2):
        doc.add_paragraph()
    doc.add_page_break()


def add_toc(doc: Document):
    doc.add_heading("MỤC LỤC", level=1)
    entries = [
        ("I.", "Tên giải pháp hữu ích"),
        ("II.", "Lĩnh vực kỹ thuật được đề cập"),
        ("III.", "Tình trạng kỹ thuật và vấn đề cần giải quyết"),
        ("IV.", "Bản chất kỹ thuật của giải pháp"),
        ("V.", "Mô tả vắn tắt các hình vẽ"),
        ("VI.", "Mô tả chi tiết phương án thực hiện"),
        ("VII.", "Phương pháp đánh giá và kết quả kiểm chứng"),
        ("VIII.", "Hiệu quả có thể đạt được"),
        ("IX.", "Yêu cầu bảo hộ dự kiến"),
        ("X.", "Tóm tắt giải pháp hữu ích"),
        ("XI.", "Thuật ngữ, nguồn tham khảo và điều kiện hoàn thiện"),
    ]
    for label, text in entries:
        p = add_para(doc, f"{label} {text}", indent=False)
        p.paragraph_format.space_after = Pt(6)
    doc.add_page_break()


def build_document(output: Path) -> None:
    doc, bullet_num, decimal_num = configure_document()
    diagrams = generate_diagrams()
    plates = {
        "home_settings": DOC_EVIDENCE_DIR / "fig7_home_settings.png",
        "modes_visual": DOC_EVIDENCE_DIR / "fig8_modes_visual.png",
        "assist_history": DOC_EVIDENCE_DIR / "fig9_assist_history.png",
        "live_captions": DOC_EVIDENCE_DIR / "fig10_live_captions.png",
    }
    for plate in plates.values():
        if not plate.is_file():
            raise FileNotFoundError(f"Missing document evidence: {plate}")

    add_cover(doc)
    add_toc(doc)

    doc.add_heading("I. TÊN GIẢI PHÁP HỮU ÍCH", level=1)
    add_para(
        doc,
        "Hệ thống và phương pháp nhận dạng lời nói tiếng Việt từ chuyển động môi "
        "trên thiết bị di động, kết hợp suy luận thị giác và hỗ trợ ngữ cảnh có kiểm soát.",
        indent=False,
    )

    doc.add_heading("II. LĨNH VỰC KỸ THUẬT ĐƯỢC ĐỀ CẬP", level=1)
    for text in [
        "Giải pháp thuộc lĩnh vực xử lý tín hiệu hình ảnh, thị giác máy tính, học sâu, "
        "nhận dạng lời nói thị giác (visual speech recognition – VSR), xử lý ngôn ngữ tự "
        "nhiên và triển khai suy luận trên hệ thống di động – máy chủ.",
        "Cụ thể hơn, giải pháp liên quan đến việc tiếp nhận một đoạn video khuôn mặt, "
        "ổn định và chuẩn hóa chuỗi ảnh vùng miệng, suy luận chuỗi ký hiệu ngôn ngữ bằng "
        "mô hình nghe nhìn được vận hành ở chế độ chỉ-thị-giác, lưu giữ tập giả thuyết "
        "N-best làm bằng chứng kỹ thuật, rồi tùy chọn dùng mô hình ngôn ngữ qua một ranh "
        "giới kiểm soát để lựa chọn hoặc đề xuất câu dễ đọc hơn mà không ghi đè kết quả gốc.",
        "Giải pháp còn đề cập đến vận hành trong môi trường không có bộ xử lý đồ họa "
        "(GPU), quản lý đồng thời một mô hình có kích thước lớn, dọn dữ liệu video tạm, "
        "cung cấp phụ đề thị giác gần thời gian thực trên thiết bị di động, công bố trạng "
        "thái sẵn sàng và biểu diễn rõ mức rủi ro của mỗi chế độ cho người sử dụng.",
    ]:
        add_para(doc, text)

    doc.add_heading("III. TÌNH TRẠNG KỸ THUẬT VÀ VẤN ĐỀ CẦN GIẢI QUYẾT", level=1)
    doc.add_heading("1. Đặc thù của nhận dạng lời nói bằng hình ảnh môi", level=2)
    for text in [
        "Khác với nhận dạng giọng nói bằng âm thanh, VSR phải suy ra chuỗi từ chỉ từ "
        "chuyển động nhìn thấy được ở môi và phần dưới khuôn mặt. Nhiều âm vị tiếng Việt "
        "có hình môi gần giống nhau; thanh điệu và các tín hiệu phát âm trong khoang miệng "
        "không phải lúc nào cũng quan sát được. Vì vậy, cùng một chuỗi ảnh có thể tương "
        "thích với nhiều câu chữ, đặc biệt khi video ngắn hoặc thiếu ngữ cảnh.",
        "Sai số còn phát sinh từ góc quay lệch, rung máy, khuôn mặt quá nhỏ, ánh sáng yếu, "
        "tốc độ khung hình không ổn định, che miệng và khác biệt hình thái khuôn mặt. Nếu "
        "ROI miệng được cắt độc lập ở từng khung hình, nhiễu hình học có thể lớn hơn chuyển "
        "động phát âm thật và làm giảm khả năng tổng quát của mô hình.",
        "Các hệ thống chỉ trả về một câu duy nhất thường khiến người dùng hiểu nhầm rằng "
        "câu đó là chắc chắn. Trong khi đó, điểm beam-search là đại lượng xếp hạng nội bộ, "
        "không tự động tương đương với xác suất đúng đã hiệu chuẩn.",
    ]:
        add_para(doc, text)

    doc.add_heading("2. Hạn chế của cách hậu xử lý bằng mô hình ngôn ngữ không kiểm soát", level=2)
    for text in [
        "Mô hình ngôn ngữ có thể biến một chuỗi từ thiếu tự nhiên thành câu trôi chảy, "
        "nhưng cũng có thể thêm chủ thể, đối tượng hoặc nội dung không xuất hiện trong "
        "bằng chứng thị giác. Nếu kết quả sau LLM thay thế trực tiếp kết quả VSR, người dùng "
        "không còn cách phân biệt nội dung quan sát được với nội dung được suy diễn.",
        "Việc gửi nguyên video đến một dịch vụ LLM còn tạo thêm bề mặt rủi ro dữ liệu. "
        "Trong nhiều kịch bản, LLM chỉ cần thấy các ứng viên văn bản và ngữ cảnh do người "
        "dùng nhập; không cần nhận video hay khung khuôn mặt.",
    ]:
        add_para(doc, text)

    doc.add_heading("3. Hạn chế triển khai", level=2)
    add_bullets(doc, [
        "Chạy một mô hình thị giác dung lượng lớn trên CPU có thể chậm hơn thời lượng video, nhưng vẫn khả thi cho clip ngắn nếu mô hình được nạp sẵn và giới hạn số yêu cầu đồng thời.",
        "Nhân nhiều worker web có thể vô tình nạp nhiều bản sao mô hình vào RAM, gây hoán trang hoặc hết bộ nhớ.",
        "Mô hình clip-level hiện tại cần toàn bộ đoạn video trước khi giải mã; chia đoạn tùy tiện có thể làm mất ngữ cảnh và tạo ranh giới từ sai.",
        "Phụ đề liên tục từ một mô hình clip-level cần kiểm soát độ trễ, vùng chồng lấn và việc chốt từ để tránh câu nhấp nháy hoặc lặp nội dung tại biên đoạn.",
        "Một giao diện chỉ có nút “dịch” không truyền đạt được độ bất định, nguồn của câu chữ và điều kiện lỗi.",
        "Dữ liệu video khuôn mặt là dữ liệu nhạy cảm; lưu tạm không giới hạn hoặc ghi log nội dung sẽ làm tăng rủi ro vận hành.",
    ], bullet_num)
    add_callout(
        doc,
        "Vấn đề kỹ thuật tổng hợp cần giải quyết là: làm ổn định đầu vào hình học, "
        "duy trì nhiều giả thuyết có truy vết, tận dụng ngữ cảnh mà không che khuất bằng "
        "chứng, đồng thời vận hành được cả trên server CPU và giao diện di động thực tế.",
        fill=PALE_RED,
        border=RED,
    )

    doc.add_heading("IV. BẢN CHẤT KỸ THUẬT CỦA GIẢI PHÁP", level=1)
    doc.add_heading("1. Mục đích", level=2)
    add_bullets(doc, [
        "Nhận một đoạn video có khuôn mặt và tạo ra câu tiếng Việt dự đoán từ chuyển động môi mà không sử dụng âm thanh.",
        "Giảm biến thiên do rung, tỉ lệ, góc quay và vị trí khuôn mặt bằng căn chỉnh theo chuỗi thời gian.",
        "Cung cấp top-1 và N-best cùng metadata nguồn để người dùng có thể rà soát.",
        "Cho phép ba mức sử dụng ngữ cảnh với rủi ro tăng dần và sự đồng ý rõ ràng.",
        "Đảm bảo LLM không thể ghi đè trường kết quả thị giác gốc trong giao thức dữ liệu.",
        "Chạy được trên máy chủ không GPU, có đường nâng cấp lên GPU hoặc hàng đợi job.",
        "Tạo phụ đề thị giác liên tục khi người dùng đang quay mà không buộc tải lại toàn bộ video sau mỗi lần cập nhật.",
        "Giảm lưu giữ video bằng dọn tệp bắt buộc và chỉ lưu lịch sử văn bản cục bộ trên điện thoại.",
    ], bullet_num)

    doc.add_heading("2. Khái niệm sáng tạo trung tâm", level=2)
    for text in [
        "Giải pháp tạo một “đường bằng chứng thị giác bất biến”. Đầu ra của bộ giải mã "
        "VSR gồm visual_transcript và danh sách N-best được đóng gói trước khi gọi LLM. "
        "Các bước sau chỉ được phép thêm trường selected_candidate hoặc assisted_transcript; "
        "không được sửa visual_transcript. Ứng dụng hiển thị hai lớp này tách biệt.",
        "Ranh giới LLM được tổ chức theo chính sách. Ở chế độ Visual only, hệ thống không "
        "gọi LLM. Ở Context select, LLM chỉ được trả về chỉ số của một ứng viên nguyên văn "
        "trong N-best. Ở LLM assist, LLM được phép sinh một câu gợi ý riêng sau khi người "
        "dùng chấp nhận cảnh báo; câu này luôn mang nhãn hỗ trợ và đi kèm lý do.",
        "Cơ chế trên cho phép khai thác năng lực ngôn ngữ để xử lý mơ hồ nhưng vẫn bảo toàn "
        "khả năng truy vết, khôi phục và so sánh với kết quả thị giác ban đầu.",
    ]:
        add_para(doc, text)
    add_picture(doc, diagrams["architecture"], "Hình 1. Kiến trúc tổng thể của giải pháp.", width_in=6.05)

    doc.add_heading("3. Các mô-đun cấu thành", level=2)
    component_rows = [
        ("M1", "Thu nhận", "Camera hoặc tệp MP4; lấy mẫu khung hình có backpressure; hướng dẫn giữ mặt thẳng."),
        (
            "M2",
            "Kiểm tra đầu vào",
            "Kiểu tệp, chữ ký/header, kích thước, giới hạn 2–45 giây và tối đa 1.125 khung.",
        ),
        ("M3", "Giải mã khung", "Đọc video, chuẩn hóa tốc độ lấy mẫu và phát hiện khung lỗi."),
        ("M4", "Mốc khuôn mặt", "Auto-AVSR MediaPipe full/short-range; FaceMesh cứu hộ; kiểm tra hướng."),
        ("M5", "Ổn định thời gian", "Làm mượt quỹ đạo landmark để giảm rung cục bộ."),
        ("M6", "Căn chỉnh", "Ước lượng biến đổi affine theo các điểm neo và mean face chuẩn."),
        ("M7", "ROI miệng", "Cắt vùng miệng 96×96 xám ở 25 fps, center-crop 88 và normalize."),
        ("M8", "Bộ mã hóa VSR", "Mô hình Auto-AVSR với frontend thị giác và Conformer."),
        ("M9", "Bộ giải mã", "Hybrid attention/CTC beam-search, beam 10, sinh mười giả thuyết."),
        ("M10", "Cổng chính sách LLM", "Không gọi, chọn nguyên N-best hoặc sinh gợi ý tách biệt."),
        ("M11", "API và điều phối", "HTTP, WebSocket, cửa sổ chồng lấn, queue hữu hạn, preload model và dọn tệp."),
        ("M12", "Ứng dụng di động", "Phụ đề trên camera, chế độ, đồng ý rủi ro, kết quả phân tầng và lịch sử cục bộ."),
    ]
    add_table(doc, ["Mã", "Mô-đun", "Chức năng kỹ thuật"], component_rows, [1.25, 3.35, 10.95])

    doc.add_heading("4. Chuẩn hóa hình học chuỗi vùng miệng", level=2)
    for text in [
        "Với mỗi khung hình, mô-đun M4 chạy detector MediaPipe chính chủ trong Auto-AVSR. "
        "Full-range là đường chính; short-range được chạy và ghép theo từng frame khi còn "
        "thiếu. FaceMesh chỉ làm tầng cứu hộ, quy đổi về đúng bốn điểm mắt, mũi và tâm miệng "
        "mà VideoProcess của Auto-AVSR yêu cầu.",
        "Hệ thống kiểm tra hình học mắt–mũi–miệng, không chỉ tin tỷ lệ phát hiện. Khi mặt bị "
        "xoay do metadata hoặc encoder điện thoại, các phương án 90°, 270° và 180° được "
        "xếp hạng theo số landmark đúng hướng, độ phủ full-range và tổng độ phủ. Trong "
        "trường hợp nhiều mặt, detector chọn bounding box có diện tích thực lớn nhất.",
        "Mô-đun M6 ước lượng biến đổi affine đưa khuôn mặt quan sát về một hệ tọa độ chuẩn "
        "được định nghĩa bởi mean face. Việc dùng cùng một chuẩn cho cả chuỗi làm cho ROI "
        "miệng ít trôi hơn so với crop theo bounding box độc lập ở từng khung.",
        "Sau căn chỉnh, hệ thống lấy ROI miệng 96×96, chuyển xám, chuẩn hóa về 25 khung/giây, "
        "center-crop còn 88×88 và áp dụng thống kê normalize tương thích mô hình phát hành. Các "
        "khoảng mất dấu được VideoProcess nội suy khi còn đủ neo; nếu không thể căn chỉnh, "
        "server trả mã face_tracking_failed, face_orientation_failed hoặc mouth_crop_failed "
        "cùng request_id thay vì một lỗi 422 không có chẩn đoán.",
    ]:
        add_para(doc, text)
    add_picture(
        doc,
        diagrams["preprocessing"],
        "Hình 2. Chuỗi tiền xử lý và chuẩn hóa hình học.",
        width_in=5.2,
    )
    add_callout(
        doc,
        "Tài sản mean face được đóng gói trong bản dùng thử hiện tại có nguồn từ gói nghiên cứu BBC/LRS. "
        "Trước phát hành thương mại cần tái tạo từ dữ liệu có quyền sử dụng hoặc có văn "
        "bản cho phép phù hợp; đây là điều kiện phát hành, không phải tùy chọn.",
        fill=PALE_GOLD,
        border=GOLD,
    )

    doc.add_heading("5. Suy luận VSR và tập giả thuyết", level=2)
    for text in [
        "Tensor video sau chuẩn hóa được đưa vào frontend thị giác và mạng Conformer của "
        "Auto-AVSR. Bộ giải mã kết hợp điểm attention và CTC trong beam-search. Trong "
        "phương án hiện tại, beam width là 10 và hệ thống giữ mười ứng viên xếp hạng cao, "
        "đúng cấu hình đánh giá đã được khóa trước khi mở tập kiểm thử.",
        "Mỗi ứng viên gồm rank, text và decoder score. Server đánh dấu phiên bản mô hình, "
        "thiết bị tính toán, precision, số khung đầu vào, số khung sau chuẩn hóa và thời "
        "gian từng giai đoạn. Trường review_required luôn bằng true vì score chưa được "
        "hiệu chuẩn thành xác suất đúng.",
        "Tập N-best được đóng băng trước hậu xử lý. Ngoài top-1, hệ thống tính một gợi ý "
        "đồng thuận theo nguyên tắc minimum Bayes risk gần đúng: mỗi ứng viên được xem là "
        "một giả thuyết, trọng số được chuẩn hóa từ decoder score, và ứng viên có tổng "
        "khoảng cách chỉnh sửa từ kỳ vọng nhỏ nhất được chọn làm medoid. Gợi ý này chỉ là "
        "chẩn đoán yêu cầu, không phải xác suất đã hiệu chuẩn và không thay transcript. "
        "Bản phát hành hiện tại không cache transcript hoặc video giữa các request. Nếu triển khai cache "
        "trong tương lai, khóa phải gắn với băm nội dung và phiên bản pipeline, đồng thời "
        "tuân theo TTL và chính sách quyền riêng tư.",
    ]:
        add_para(doc, text)
    add_picture(doc, diagrams["evidence"], "Hình 3. Cơ chế giải mã N-best và bảo toàn bằng chứng.", width_in=6.05)

    doc.add_heading("6. Cổng hỗ trợ ngữ cảnh có kiểm soát", level=2)
    policy_rows = [
        ("Visual only", "Không", "visual_transcript + N-best", "Thấp nhất; vẫn cần rà soát."),
        ("Context select", "N-best + ngữ cảnh chữ", "Chỉ một ứng viên N-best nguyên văn", "LLM có thể chọn sai nhưng không bịa câu mới."),
        ("LLM assist", "N-best + ngữ cảnh chữ", "assisted_transcript riêng + lý do", "Có nguy cơ bổ sung nội dung; cần đồng ý rõ ràng."),
    ]
    add_table(doc, ["Chế độ", "Dữ liệu gửi LLM", "Đầu ra được phép", "Cách thể hiện rủi ro"], policy_rows, [3.0, 3.7, 4.3, 4.55])
    for text in [
        "Cổng M10 dựng prompt có schema JSON cố định và kiểm tra đáp ứng. Với Context "
        "select, selected_index phải nằm trong miền ứng viên; server tự lấy nguyên văn câu "
        "ở chỉ số đó thay vì tin một trường selected_text do LLM tạo. Nếu chỉ số không hợp "
        "lệ, server bỏ kết quả LLM và vẫn trả visual transcript.",
        "Với LLM assist, người dùng phải bật đồng ý rủi ro. Video không đi qua cổng này. "
        "assisted_transcript, provider, model, runtime và reason được trả riêng để giao diện "
        "ghi rõ nguồn. Sau schema, một validator hậu nghiệm từ chối câu có token mới không "
        "nằm trong N-best/ngữ cảnh, tỷ lệ token mới vượt 35% hoặc độ giống ứng viên thấp hơn "
        "0,45. Khi LLM không sẵn sàng hoặc bị từ chối, API vẫn trả kết quả VSR.",
        "Trước bước sinh tự do, một cổng an toàn kiểm tra đầu ra thị giác có ít thông tin "
        "hoặc lặp bất thường. Ở bản phát hành hiện tại, chuỗi có ít nhất tám token và tỷ lệ token "
        "duy nhất không quá 0,20 không được gửi sang bước viết lại; server giữ nguyên "
        "visual_transcript và ghi lý do phòng vệ tương ứng. Ngưỡng này là cấu hình có phiên bản, "
        "không phải độ tin cậy đã hiệu chuẩn.",
    ]:
        add_para(doc, text)
    add_picture(doc, diagrams["modes"], "Hình 4. Ba chế độ và mức tự do của LLM.", width_in=6.05)
    add_callout(
        doc,
        "Cơ chế định tuyến chọn lọc chỉ được giữ như hướng xử lý chất lượng theo lô. Nó "
        "không nằm trong đường xử lý yêu cầu của bản phát hành, không tự gọi mô hình kiểm "
        "chứng và không thay đổi kết quả thị giác. Giao thức, số liệu và giới hạn công bố "
        "được trình bày riêng tại Mục VII.",
        fill=PALE_GOLD,
        border=GOLD,
    )

    doc.add_heading("7. Phụ đề thị giác liên tục", level=2)
    for text in [
        "Khi người dùng bật phụ đề trực tiếp và bắt đầu quay, ứng dụng vẫn ghi MP4 cục bộ "
        "đồng thời lấy mẫu tối đa tám khung hình mỗi giây. Mỗi lần chỉ có một tác vụ nén "
        "JPEG chạy; nếu thiết bị chưa nén xong khung trước thì khung mới không được xếp "
        "hàng. Cơ chế latest-only này giữ camera phản hồi và tạo backpressure ngay tại nguồn.",
        "Kênh WebSocket truyền các khung JPEG đã xoay đúng hướng. Server bắt đầu giải mã "
        "khi có tối thiểu hai giây dữ liệu, sau đó dùng cửa sổ sáu giây chồng lấn một giây. "
        "Các giả thuyết liên tiếp được so theo tiền tố từ để chỉ đánh dấu phần ổn định; "
        "các cửa sổ hoàn tất được nối bằng phần hậu tố–tiền tố trùng nhau. Phần đã chốt "
        "không bị âm thầm viết lại trong giao diện.",
        "Bộ đệm server là bộ đệm cuộn: sau khi chốt một cửa sổ, các khung không còn cần "
        "thiết bị được loại bỏ nhưng tổng số khung nhận vẫn được đếm tuyệt đối để thi hành "
        "giới hạn năm phút. Thông báo lỗi giống nhau được hạn tần suất; một đoạn không đủ "
        "mặt có thể bị bỏ qua mà phiên và video cục bộ vẫn tiếp tục.",
        "Đây là phụ đề gần thời gian thực dùng nhiều lần suy luận của mô hình toàn ngữ cảnh, "
        "không phải mô hình causal. Muốn đạt độ trễ thấp ổn định như hệ thống hội nghị trên "
        "GPU hoặc thiết bị biên, cần huấn luyện kiến trúc streaming với attention theo khối, "
        "convolution nhân quả và tiêu chí ổn định ranh giới. Bản hiện tại không tuyên bố "
        "đã biến checkpoint clip-level thành mô hình causal.",
        "LLM không được gọi trên từng phụ đề tạm vì có thể tăng độ trễ và khuếch đại suy "
        "diễn. Với video không quá 45 giây, người dùng có thể xử lý đầy đủ sau khi dừng và "
        "chọn Context select hoặc LLM assist theo cơ chế đồng ý đã mô tả.",
    ]:
        add_para(doc, text)

    doc.add_heading("8. Triển khai CPU, GPU và mở rộng tải", level=2)
    for text in [
        "Server không GPU vẫn chạy được bằng PyTorch CPU. Mô hình được nạp một "
        "lần khi worker khởi động; endpoint readiness chỉ báo sẵn sàng sau khi mô hình và "
        "tài sản tiền xử lý hợp lệ. Một semaphore giới hạn một lượt suy luận nặng tại một "
        "thời điểm, tránh tranh chấp RAM và suy giảm đột ngột.",
        "GPU là tùy chọn tăng tốc, không phải điều kiện đúng của giao thức. Khi phát hiện "
        "GPU, worker có thể chọn thiết bị và độ chính xác số phù hợp rồi công bố trong metadata. "
        "Thiết bị di động không cần chứa mô hình lớn và chỉ thực hiện thu nhận, upload, "
        "hiển thị và lưu lịch sử.",
        "Bản phát hành hiện tại đã hiện thực hàng đợi bất đồng bộ hữu hạn trong một tiến trình: POST /v1/jobs "
        "cấp job_id, ứng dụng polling GET /v1/jobs/{job_id}, có hủy job, giới hạn mặc định "
        "tám job chờ và dọn trạng thái sau 1.800 giây. Khi tải vượt một máy, hợp đồng API "
        "giữ nguyên nhưng queue được thay bằng broker bền vững, video tạm chuyển sang object "
        "storage có TTL và worker scale theo RAM/GPU. Không tăng web worker tùy tiện vì mỗi "
        "tiến trình có thể nạp thêm một bản sao mô hình lớn.",
    ]:
        add_para(doc, text)
    add_picture(doc, diagrams["deployment"], "Hình 5. Phương án chạy CPU và mở rộng bằng hàng đợi.", width_in=6.05)

    doc.add_heading("9. Quyền riêng tư và an toàn lỗi", level=2)
    add_bullets(doc, [
        "Tệp upload được ghi vào thư mục tạm có phạm vi job và xóa khi hoàn tất, lỗi, hủy hoặc server đóng.",
        "Response đặt Cache-Control: no-store; log không ghi khung hình hoặc nội dung video.",
        "LLM chỉ nhận N-best và ngữ cảnh văn bản do người dùng cung cấp.",
        "Lịch sử kết quả được lưu cục bộ trên thiết bị và có thể xóa bởi người dùng.",
        "Timeout, video không có mặt, video quá dài, model chưa sẵn sàng và lỗi LLM được mã hóa riêng.",
        "Kết quả không được mô tả là phụ đề chắc chắn; giao diện luôn nhắc review_required.",
    ], bullet_num)
    add_picture(doc, diagrams["privacy"], "Hình 6. Vòng đời dữ liệu tối thiểu hóa lưu giữ.", width_in=6.05)

    doc.add_heading("V. MÔ TẢ VẮN TẮT CÁC HÌNH VẼ", level=1)
    figure_rows = [
        ("Hình 1", "Kiến trúc ứng dụng–API–Auto-AVSR–cổng LLM và đầu ra có truy vết."),
        ("Hình 2", "Các bước landmark, làm mượt, căn chỉnh mean face và ROI miệng."),
        ("Hình 3", "Tạo N-best, điểm xếp hạng và trường visual_transcript bất biến."),
        ("Hình 4", "Ba chế độ Visual only, Context select và LLM assist."),
        ("Hình 5", "Triển khai CPU/GPU và phương án hàng đợi job khi tăng tải."),
        ("Hình 6", "Vòng đời video tạm và ranh giới dữ liệu LLM."),
        ("Hình 7", "Màn hình chính và trang trạng thái máy chủ của ứng dụng Android."),
        ("Hình 8", "Trang chọn chế độ và cách trình bày kết quả Visual-only."),
        ("Hình 9", "Cách trình bày kết quả LLM Assist và lịch sử cục bộ."),
        ("Hình 10", "Phụ đề trực tiếp được đặt ngay trên khung camera trong khi quay."),
    ]
    add_table(doc, ["Ký hiệu", "Nội dung"], figure_rows, [2.2, 13.35])

    doc.add_heading("VI. MÔ TẢ CHI TIẾT PHƯƠNG ÁN THỰC HIỆN", level=1)
    doc.add_heading("1. Ứng dụng di động", level=2)
    for text in [
        "Phương án thực hiện dùng Flutter để tạo ứng dụng Android. Màn hình chính hiển thị "
        "khung hình khuôn mặt và vùng miệng mục tiêu, hướng dẫn ánh sáng, khoảng cách và "
        "thời lượng clip. Người dùng có thể quay bằng camera, chọn MP4 từ thư viện hoặc "
        "bật phụ đề trực tiếp cho một phiên nói liên tục đến năm phút.",
        "Trong lúc quay, câu đang nhận dạng được đặt trên một nền tương phản ngay trong "
        "khung camera để người dùng không phải cuộn màn hình. Giao diện chỉ hiển thị phần "
        "cuối của bản ghi dài trên lớp phủ nhưng vẫn giữ toàn bộ nội dung trong thẻ phụ đề "
        "để sao chép sau khi dừng. Nếu mất mạng hoặc không theo dõi được mặt, ứng dụng báo "
        "trạng thái bằng ngôn ngữ hành động và tiếp tục lưu video.",
        "Trang cài đặt nhận địa chỉ server, kiểm tra trạng thái sẵn sàng, rồi hiển thị "
        "thiết bị suy luận, cấu hình tính toán, phiên bản pipeline và trạng thái LLM. "
        "Trong môi trường phát triển có thể dùng đường hầm cục bộ; bản phát hành công khai "
        "phải dùng HTTPS, tên miền hợp lệ và chính sách an toàn mạng chặt hơn.",
        "Trước upload, ứng dụng cho chọn chế độ. Khi chọn LLM assist, một cảnh báo nêu rõ "
        "LLM có thể tạo câu tự nhiên nhưng thêm nội dung không có trong hình; người dùng "
        "phải đồng ý. Ngữ cảnh không dùng ở chế độ Visual only và là trường bắt buộc ở "
        "hai chế độ LLM; ứng dụng không tự lấy ngữ cảnh từ dữ liệu khác.",
    ]:
        add_para(doc, text)
    add_picture(
        doc, plates["home_settings"], "Hình 7. Màn hình chính và trạng thái hệ thống trên ứng dụng Android.",
        width_in=6.0,
        note=(
            "Giao diện cho phép cấu hình máy chủ, kiểm tra trạng thái sẵn sàng và xem "
            "cấu hình suy luận trước khi gửi yêu cầu."
        ),
    )
    add_picture(
        doc,
        plates["live_captions"],
        "Hình 10. Lớp phụ đề trực tiếp trên khung camera trong khi quay.",
        width_in=2.65,
        note=(
            "Nội dung hoặc trạng thái mới nhất xuất hiện ngay trên video; đồng hồ và nút "
            "dừng vẫn luôn nhìn thấy để người dùng kiểm soát phiên."
        ),
    )

    doc.add_page_break()
    doc.add_heading("2. Giao thức yêu cầu và đáp ứng", level=2)
    api_rows = [
        (
            "WS /v1/realtime",
            "Lệnh start/stop và chuỗi khung JPEG lấy mẫu từ camera",
            "ready; partial; segment_final; session_final; notice; giới hạn phiên.",
        ),
        (
            "POST /v1/jobs",
            "multipart video; input_kind; mode; context_hint; accept_llm_risk",
            "HTTP 202, job_id, trạng thái queued, thời điểm tạo và URL truy vấn.",
        ),
        (
            "GET/DELETE /v1/jobs/{id}",
            "job_id",
            "Vị trí hàng đợi/tiến độ/kết quả; hoặc xác nhận yêu cầu hủy và dọn tệp.",
        ),
        (
            "POST /v1/transcriptions",
            "multipart video; input_kind; mode; context_hint; accept_llm_risk",
            "Đường tương thích đồng bộ: transcript, alternatives, consensus, diagnostics và assisted transcript tùy chọn.",
        ),
        (
            "GET /healthz",
            "Không",
            "Trạng thái API/mô hình/LLM, thiết bị tính toán, độ dài và sức chứa hàng đợi.",
        ),
    ]
    add_table(doc, ["Điểm cuối", "Đầu vào", "Đầu ra"], api_rows, [3.5, 5.1, 6.95])
    add_para(
        doc,
        "Trong giao thức hiện thực, trường transcript là kết quả thị giác bất biến về mặt "
        "logic; alternatives là tập N-best; processing_mode là chế độ; status luôn bằng "
        "review_required; consensus_transcript là medoid N-best chẩn đoán; assisted_transcript "
        "là gợi ý tùy chọn. Đáp ứng còn có request_id, "
        "model_id, elapsed_ms, num_frames và diagnostics. Các lỗi xác thực đầu "
        "vào dùng mã 4xx; model chưa sẵn sàng dùng 503; lỗi LLM không làm thất bại kết quả "
        "VSR nếu đường bằng chứng đã hoàn tất.",
    )

    doc.add_heading("3. Thực hiện phụ đề trực tiếp", level=2)
    add_bullets(doc, [
        "Ứng dụng vừa ghi MP4 vừa lấy mẫu khung camera ở tám fps; mỗi thời điểm chỉ nén một khung và bỏ khung đến sau khi bộ mã hóa đang bận.",
        "Khung được thu nhỏ, xoay theo hướng cảm biến, nén JPEG và truyền qua WebSocket bảo mật khi server dùng HTTPS.",
        "Server dùng cùng pipeline căn chỉnh khuôn mặt–vùng môi và cùng mô hình phát hành như đường xử lý video đầy đủ.",
        "Giả thuyết tạm được phát từ mốc hai giây; cửa sổ sáu giây chồng lấn một giây tạo đoạn chốt có ngữ cảnh mà vẫn giới hạn độ trễ.",
        "Local agreement chỉ đánh dấu tiền tố lặp lại qua hai giả thuyết; bộ nối cửa sổ loại phần trùng chính xác hoặc gần đúng nhưng không sửa phần đã chốt.",
        "Bộ đệm cuộn, giới hạn kích thước khung, giới hạn năm phút, semaphore mô hình và thông báo hạn tần suất bảo vệ tài nguyên server.",
        "Lệnh stop chờ xử lý phần còn lại, trả session_final rồi đóng kênh; nếu kênh lỗi, video cục bộ vẫn là đường phục hồi.",
    ], bullet_num)

    doc.add_heading("4. Thực hiện tiền xử lý", level=2)
    add_bullets(doc, [
        "Đọc metadata và từ chối clip ngoài giới hạn trước khi giải mã toàn bộ.",
        "Lấy khung theo timestamp, quy đổi về 25 fps và giữ thứ tự thời gian.",
        "Chạy Auto-AVSR MediaPipe full-range, ghép short-range và dùng FaceMesh cứu hộ khi cần.",
        "Kiểm tra hình học hướng mặt; thử 90°, 270° và 180° khi landmark không thẳng đứng.",
        "Làm mượt quỹ đạo neo bằng bộ lọc thời gian có hệ số được cố định theo phiên bản pipeline.",
        "Ước lượng affine về mean face; áp cùng hệ tọa độ cho crop vùng miệng.",
        "Chuyển xám, resize 96×96, center-crop 88×88, normalize và tạo tensor T×1×88×88.",
        "Ghi số khung trước/sau và lỗi chất lượng vào metadata, không ghi ảnh vào log.",
    ], bullet_num)

    doc.add_heading("5. Thực hiện suy luận và giải mã", level=2)
    for text in [
        "Worker giữ mô hình phát hành trong bộ nhớ. Luồng inference được bao bởi chế độ "
        "không gradient. Với CPU, tensor và mô hình dùng độ chính xác số ổn định; với GPU "
        "có thể dùng cấu hình tăng tốc đã được xác minh. Bộ giải mã nhận biểu diễn theo thời gian và tạo beam.",
        "Sau khi chuẩn hóa token, hệ thống loại ứng viên trùng lặp, xếp hạng, lấy tối đa mười "
        "ứng viên và chọn hạng 1 làm visual_transcript. Không áp sửa chính tả ngầm vào "
        "trường này. Sau đó một phép minimum-risk trên chính N-best chọn medoid có expected "
        "word edit risk thấp nhất làm consensus_transcript. Nó giúp phát hiện top-1 đơn độc "
        "nhưng không sở hữu transcript và không được gọi là confidence. Nếu cần hậu xử lý "
        "ký tự cố định, phiên bản thuật toán phải được ghi "
        "trong pipeline_version và áp giống nhau cho mọi ứng viên.",
    ]:
        add_para(doc, text)

    doc.add_heading("6. Thực hiện cổng LLM", level=2)
    for text in [
        "Cấu hình phát hành mặc định dùng một mô hình ngôn ngữ cục bộ cỡ 7B tham số với "
        "giới hạn ngữ cảnh và đầu ra rõ ràng. Cấu hình cục bộ giúp văn bản không rời máy "
        "chủ vận hành; giao thức vẫn cho phép nhà cung cấp khác nếu chính sách dữ liệu chấp nhận.",
        "Prompt chỉ chứa vai trò, quy tắc chế độ, N-best, score dưới dạng thông tin xếp hạng "
        "và ngữ cảnh người dùng. Output phải là JSON. Bộ kiểm tra schema không tin tưởng "
        "trực tiếp text của LLM. Ở Context select, mọi ký tự của câu chọn phải đối chiếu với "
        "ứng viên. Ở LLM assist, server kiểm tra cả độ dài, độ giống N-best, tỷ lệ token mới "
        "và việc token mới có xuất hiện trong ngữ cảnh trước khi gắn provenance.",
        "Cổng safety gate chạy trước LLM assist để nhận biết transcript lặp hoặc nghèo thông "
        "tin. Khi điều kiện phòng vệ được kích hoạt, hệ thống không yêu cầu LLM suy diễn, "
        "không tạo câu mới; assisted_transcript được giữ bằng visual_transcript và đáp ứng "
        "ghi nguồn là cổng phòng vệ cùng mã lý do. "
        "Cách xử lý này ngăn một chuỗi lặp như “lời lời …” bị biến thành một câu trôi chảy "
        "nhưng không có căn cứ trong video.",
        "Timeout tách LLM khỏi đường VSR. Khi vượt timeout, client "
        "nhận visual_transcript và trạng thái dự phòng thay vì chờ vô hạn.",
    ]:
        add_para(doc, text)

    doc.add_heading("7. Biểu diễn kết quả và lịch sử", level=2)
    for text in [
        "Giao diện kết quả đặt bản gợi ý LLM, nếu có, trong một thẻ cảnh báo riêng; phía "
        "dưới vẫn hiển thị kết quả thị giác và các ứng viên. Provider, model, thời gian và "
        "lý do được trình bày cạnh bản gợi ý.",
        "Mỗi mục lịch sử trên điện thoại ghi timestamp, số khung, mode, visual transcript "
        "và assisted transcript nếu có. Không cần giữ video để xem lại kết quả văn bản. "
        "Người dùng có quyền xóa lịch sử.",
    ]:
        add_para(doc, text)
    add_picture(
        doc, plates["modes_visual"], "Hình 8. Lựa chọn ba chế độ và kết quả Visual-only.",
        width_in=6.0,
        note=(
            "Bản thị giác được giữ cùng các ứng viên thay thế và nhãn cần rà soát; "
            "nội dung hiển thị trong hình chỉ nhằm minh họa bố cục giao diện."
        ),
    )
    add_picture(
        doc, plates["assist_history"], "Hình 9. Kết quả LLM Assist và lịch sử cục bộ.",
        width_in=6.0,
        note=(
            "LLM được ghi nguồn, thời gian và lý do; bản thị giác vẫn hiện "
            "riêng bên dưới. Nội dung hiển thị không được dùng như một phép đo độ chính xác."
        ),
    )

    doc.add_heading("8. Vận hành trong môi trường triển khai", level=2)
    add_bullets(doc, [
        "Bản phát hành Windows được cung cấp dưới dạng bộ cài; mô hình và tài sản đi kèm được kiểm tra toàn vẹn trước khi kích hoạt.",
        "Tài sản mô hình dung lượng lớn có thể được tách thành các gói dữ liệu có checksum nhưng vẫn được bộ cài quản lý như một sản phẩm thống nhất.",
        "Mô hình ngôn ngữ cục bộ là thành phần tùy chọn; Visual-only vẫn hoạt động khi không cài thành phần này hoặc khi không có Internet.",
        "Chỉ chạy một worker VSR trên máy CPU RAM hạn chế; tách worker LLM nếu tranh chấp bộ nhớ.",
        "Dùng HTTPS, giới hạn upload, rate limit, authentication và reverse proxy có timeout phù hợp.",
        "Ứng dụng mặc định dùng API job bất đồng bộ; client hiển thị đang xếp hàng, đang xử lý, hoàn tất hoặc đã hủy và có đường tương thích đồng bộ khi cần.",
        "Theo dõi latency theo giai đoạn, lỗi landmark, hàng đợi, RAM, model load và tỷ lệ fallback LLM.",
        "Không thu thập video trong quá trình vận hành làm dữ liệu huấn luyện nếu chưa có đồng ý riêng và cơ chế xóa.",
        "APK dùng khóa phân phối nội bộ riêng, không dùng debug signing. Bản Play Store phải dùng khóa phát hành được quản trị độc lập.",
        "Installer Windows hiện chưa có chữ ký mã; trước phát hành rộng cần ký Authenticode để giảm cảnh báo SmartScreen.",
    ], bullet_num)
    add_callout(
        doc,
        "Kiểm chứng đóng gói xác nhận bộ cài quản lý đúng tài sản mô hình, máy chủ có thể "
        "nạp mô hình ở chế độ CPU, ứng dụng trao đổi được với API bất đồng bộ, ba chế độ "
        "tuân thủ đúng hợp đồng đầu ra và lỗi thành phần ngôn ngữ không làm mất kết quả thị giác. "
        "Đây là kiểm thử chức năng phần mềm, không phải phép đo độ chính xác nhận dạng.",
        fill=PALE_TEAL,
        border=TEAL,
    )

    doc.add_heading("VII. PHƯƠNG PHÁP ĐÁNH GIÁ VÀ KẾT QUẢ KIỂM CHỨNG", level=1)
    doc.add_heading("1. Nguyên tắc đánh giá và khóa dữ liệu", level=2)
    add_para(
        doc,
        "Bằng chứng định lượng của giải pháp được lấy từ benchmark có phép chia độc lập "
        "người nói. Một người chỉ xuất hiện trong đúng một tập huấn luyện, validation hoặc "
        "test. Tập validation dùng để chọn cấu hình và khóa chính sách; tập test được giữ "
        "sau tường lửa dữ liệu và chỉ mở cho đánh giá cuối. Cách tổ chức này đo khả năng "
        "tổng quát sang khuôn mặt, cách phát âm và nguồn hình ảnh chưa xuất hiện khi huấn luyện, "
        "thay vì chỉ đo các đoạn mới của người đã thấy."
    )
    add_para(
        doc,
        "Kết quả trên một vài video minh họa không được dùng để suy rộng chất lượng mô hình. "
        "Các ảnh giao diện trong hồ sơ chỉ chứng minh cách tổ chức chức năng và cách phân biệt "
        "nguồn kết quả. Mọi tuyên bố về độ chính xác bên dưới đều dựa trên tập đánh giá có "
        "câu tham chiếu, giao thức cố định và mẫu số được công bố rõ ràng."
    )

    doc.add_heading("2. Quy mô benchmark độc lập người nói", level=2)
    split_rows = [
        ("Huấn luyện", "92.396", "11", "408", "155,45", "Chỉ dùng để tối ưu tham số mô hình."),
        ("Validation", "11.573", "4", "62", "19,26", "Chọn cấu hình và khóa chính sách."),
        ("Test", "11.304", "4", "61", "18,12", "Đánh giá cuối trên người nói chưa thấy."),
    ]
    add_table(
        doc,
        ["Tập", "Số đoạn", "Người nói", "Nguồn", "Số giờ", "Vai trò"],
        split_rows,
        [2.7, 2.3, 2.1, 2.0, 1.8, 4.65],
        font_size=10.5,
    )
    add_para(
        doc,
        "Các tập không dùng chung người nói. Văn bản được chuẩn hóa theo cùng một quy tắc; "
        "tokenizer chỉ được fit trên tập huấn luyện. Các đoạn vượt giới hạn khung hình và "
        "các lỗi dữ liệu được xử lý theo quy tắc định trước, không thay đổi sau khi xem test."
    )

    doc.add_heading("3. Kết quả nhận dạng thị giác", level=2)
    recognition_rows = [
        ("Mô hình thị giác chính", "57,7829%", "40,0704%", "Chủ sở hữu kết quả top-1."),
        ("Mô hình kiểm chứng kiến trúc", "58,2603%", "40,4050%", "Chỉ dùng đối chiếu; không tự ghi đè kết quả chính."),
    ]
    add_table(
        doc,
        ["Cấu hình", "Validation WER", "Test WER", "Vai trò"],
        recognition_rows,
        [4.6, 3.1, 2.8, 5.05],
    )
    for text in [
        "WER test 40,0704% của mô hình chính được tính trên toàn bộ 11.304 đoạn, theo chế độ "
        "luôn trả kết quả. Đây là bằng chứng định lượng chính của phiên bản mô hình hiện tại. "
        "WER validation và test không nên được so như hai lần đo trên cùng phân phối vì thành "
        "phần nguồn và độ khó của hai tập khác nhau.",
        "Trên validation, oracle@10 của mô hình chính đạt 53,8286% so với top-1 57,7829%, "
        "tạo khoảng cải thiện lý thuyết 3,9542 điểm phần trăm. Tuy nhiên câu tham chiếu xuất "
        "hiện nguyên vẹn trong N-best chỉ ở 0,4320% số đoạn. Vì vậy N-best hữu ích cho rà "
        "soát và chọn lọc, nhưng không đủ để bảo đảm một tầng ngôn ngữ luôn sửa đúng câu."
    ]:
        add_para(doc, text)

    doc.add_heading("4. Đánh giá định tuyến chọn lọc", level=2)
    add_para(
        doc,
        "Một cơ chế định tuyến theo giá trị kỳ vọng đã được đánh giá dưới ngân sách gọi mô "
        "hình kiểm chứng xấp xỉ 49%. Cơ chế chỉ quyết định chấp nhận hoặc chuyển đoạn sang "
        "rà soát; nó không thay nội dung top-1 của mô hình thị giác. Các phương án trong bảng "
        "được đối sánh trên cùng giao thức giải mã test."
    )
    selective_rows = [
        ("Luôn trả kết quả", "0,00%", "100,0000%", "40,0934%"),
        ("Định tuyến theo rủi ro", "48,82%", "89,2427%", "35,7134%"),
        ("Định tuyến theo giá trị kỳ vọng", "48,82%", "85,2088%", "34,3595%"),
    ]
    add_table(
        doc,
        ["Phương án", "Tỷ lệ gọi kiểm chứng", "Coverage", "Selective WER"],
        selective_rows,
        [5.2, 3.7, 3.0, 3.65],
    )
    add_para(
        doc,
        "Ở cùng ngân sách 48,82%, định tuyến theo giá trị kỳ vọng giảm selective WER 1,3540 "
        "điểm phần trăm so với định tuyến theo rủi ro, nhưng coverage thấp hơn. Phương án đạt "
        "85,2088% coverage, thiếu 0,6447 điểm phần trăm, tương đương 73 đoạn, so với ngưỡng "
        "đã khóa. Vì vậy kết quả này được giữ như bằng chứng về khả năng xếp hạng rủi ro và "
        "hướng phát triển xử lý theo lô; không được bật như bộ định tuyến vận hành cho từng "
        "yêu cầu ở phiên bản hiện tại."
    )

    doc.add_heading("5. Vai trò của lớp hỗ trợ ngôn ngữ", level=2)
    for text in [
        "Các thử nghiệm về mô hình ngôn ngữ và reranker cho thấy tín hiệu cải thiện nhỏ hoặc "
        "không vượt được cổng an toàn đã định trước. Hồ sơ do đó không tuyên bố LLM cải thiện "
        "WER của mô hình thị giác trên benchmark test.",
        "Ba chế độ trong sản phẩm là ba chính sách sử dụng khác nhau: Visual-only giữ nguyên "
        "bằng chứng thị giác; Context select chỉ chọn nguyên văn một ứng viên N-best; LLM assist "
        "tạo một gợi ý riêng có provenance và sự đồng ý của người dùng. Bản gợi ý không được "
        "gộp vào số liệu WER của mô hình và không trở thành nguồn sự thật."
    ]:
        add_para(doc, text)

    doc.add_heading("6. Kiểm chứng chức năng phần mềm", level=2)
    functional_rows = [
        ("Đóng gói và khởi động", "Đã xác nhận", "Bộ cài quản lý server, mô hình thị giác và thành phần LLM tùy chọn."),
        ("Chế độ CPU", "Đã xác nhận", "Máy chủ nạp mô hình và phục vụ yêu cầu khi không có GPU."),
        ("Tiền xử lý khuôn mặt", "Đã xác nhận", "Có kiểm tra hướng mặt, căn chỉnh theo chuỗi và mã lỗi rõ ràng."),
        ("Ba chính sách đầu ra", "Đã xác nhận", "Visual-only, Context select và LLM assist giữ đúng ranh giới dữ liệu."),
        ("An toàn lỗi", "Đã xác nhận", "Lỗi hoặc timeout LLM không làm mất kết quả thị giác."),
        ("Hàng đợi và dọn dữ liệu", "Đã xác nhận", "Job có trạng thái, có thể hủy và tệp tạm được dọn theo vòng đời."),
        ("Phụ đề trực tiếp", "Đã xác nhận", "Điện thoại vừa quay vừa gửi khung; server trả partial, đoạn chốt và session_final."),
    ]
    add_table(doc, ["Nhóm chức năng", "Trạng thái", "Phạm vi xác nhận"], functional_rows, [4.0, 3.0, 8.55])
    add_para(
        doc,
        "Kiểm chứng chức năng trả lời câu hỏi hệ thống có vận hành đúng giao thức hay không; "
        "nó không thay thế đánh giá độ chính xác. Thời gian xử lý phụ thuộc độ dài video, "
        "cấu hình CPU/GPU, tải hàng đợi và trạng thái mô hình ngôn ngữ, nên hồ sơ không suy "
        "rộng latency từ một vài yêu cầu đơn lẻ."
    )

    doc.add_heading("7. Kết luận đánh giá và phạm vi công bố", level=2)
    add_callout(
        doc,
        "Kết quả định lượng chính là WER 40,0704% trên 11.304 đoạn test độc lập người nói. "
        "Mức lỗi này chưa đủ để công bố hệ thống như phụ đề tự động đáng tin. Giải pháp được "
        "định vị là công cụ tạo bản nháp và hỗ trợ giao tiếp có người dùng rà soát; LLM là "
        "lớp hỗ trợ tùy chọn, không phải bằng chứng tăng độ chính xác.",
        fill=PALE_RED,
        border=RED,
    )
    add_para(
        doc,
        "Nếu cần công bố chất lượng trong điều kiện camera thực tế, phải xây dựng một tập đánh "
        "giá hiện trường riêng, có nhiều người nói chưa xuất hiện trong huấn luyện, nhiều thiết "
        "bị, góc quay, ánh sáng và khoảng cách. Tiêu chí loại mẫu, câu tham chiếu, metric và "
        "ngưỡng chấp nhận phải được khóa trước khi mở tập này. Tập hiện trường mới không được "
        "dùng để tinh chỉnh rồi đồng thời báo như kết quả test cuối."
    )

    doc.add_heading("VIII. HIỆU QUẢ CÓ THỂ ĐẠT ĐƯỢC", level=1)
    effect_rows = [
        ("Ổn định đầu vào", "Căn chỉnh theo mean face và làm mượt chuỗi giảm trôi ROI miệng."),
        ("Minh bạch", "Top-1, N-best, score và provenance giúp truy vết nguồn câu chữ."),
        ("Kiểm soát LLM", "Ba chính sách tách biệt; LLM không sửa trường bằng chứng."),
        ("Khả dụng phần cứng", "Chạy được trên CPU; GPU chỉ là tăng tốc."),
        ("An toàn lỗi", "LLM lỗi không làm mất kết quả VSR; video tạm được dọn bắt buộc."),
        ("Khả năng mở rộng", "Queue hữu hạn đã chạy trên một máy; giữ API khi thay bằng broker bền vững."),
        ("Đồng thuận chẩn đoán", "Medoid N-best theo expected word edit risk hỗ trợ rà soát mà không sửa top-1."),
        ("Trải nghiệm tự nhiên", "Người dùng chủ động chọn mức tự nhiên và mức rủi ro phù hợp."),
        ("Phụ đề liên tục", "WebSocket, backpressure, cửa sổ chồng lấn và local agreement cập nhật câu ngay khi quay."),
    ]
    add_table(doc, ["Hiệu quả", "Cơ chế tạo ra hiệu quả"], effect_rows, [4.3, 11.25])
    add_para(
        doc,
        "Hiệu quả của giải pháp không nằm ở việc tuyên bố loại bỏ hoàn toàn sai số VSR, "
        "mà ở việc kết hợp chuẩn hóa hình học, nhiều giả thuyết, rào chắn LLM, thông tin "
        "nguồn và triển khai chịu lỗi thành một quy trình có thể kiểm tra được.",
    )

    doc.add_heading("IX. YÊU CẦU BẢO HỘ DỰ KIẾN", level=1)
    add_callout(
        doc,
        "Các điểm yêu cầu dưới đây là phạm vi kỹ thuật đề xuất. Phạm vi cuối cùng cần được "
        "điều chỉnh sau tra cứu đối chứng, đánh giá tính mới/trình độ sáng tạo và tư vấn "
        "của đại diện sở hữu công nghiệp.",
        fill=PALE_GOLD,
        border=GOLD,
    )
    claims = [
        "Một hệ thống nhận dạng lời nói thị giác tiếng Việt, bao gồm: ứng dụng di động tiếp nhận video; mô-đun chuẩn hóa chuỗi ảnh vùng miệng; mô hình nhận dạng lời nói thị giác sinh tập giả thuyết N-best; cổng hỗ trợ ngữ cảnh; và mô-đun đáp ứng, trong đó cổng hỗ trợ ngữ cảnh không được phép ghi đè một trường kết quả thị giác được đóng băng trước khi cổng được gọi.",
        "Hệ thống theo yêu cầu 1, trong đó mô-đun chuẩn hóa xác định mốc khuôn mặt theo từng khung, làm mượt quỹ đạo mốc theo thời gian, ước lượng biến đổi affine về một khuôn mặt chuẩn và cắt vùng miệng trong cùng hệ tọa độ chuẩn.",
        "Hệ thống theo yêu cầu 2, trong đó vùng miệng được chuyển xám, đưa về 96×96 điểm ảnh ở 25 khung/giây, center-crop về 88×88 và normalize theo thống kê tương thích mô hình.",
        "Hệ thống theo bất kỳ yêu cầu nào từ 1 đến 3, trong đó mô hình nhận dạng bao gồm frontend thị giác, bộ mã hóa Conformer và bộ giải mã kết hợp attention với CTC.",
        "Hệ thống theo yêu cầu 4, trong đó bộ giải mã dùng beam-search để tạo ít nhất hai ứng viên, mỗi ứng viên có thứ hạng, chuỗi văn bản và điểm giải mã.",
        "Hệ thống theo yêu cầu 5, trong đó điểm giải mã được biểu diễn là điểm xếp hạng tương đối và đáp ứng mang cờ yêu cầu người dùng rà soát.",
        "Hệ thống theo yêu cầu 1, trong đó cổng hỗ trợ ngữ cảnh hoạt động ở một trong ba chế độ gồm không sử dụng mô hình ngôn ngữ, chọn một ứng viên có sẵn, và tạo một bản gợi ý riêng.",
        "Hệ thống theo yêu cầu 7, trong đó ở chế độ chọn ứng viên, đầu ra của mô hình ngôn ngữ chỉ hợp lệ khi chỉ số nằm trong tập N-best và văn bản trả về khớp nguyên văn ứng viên tương ứng.",
        "Hệ thống theo yêu cầu 7, trong đó ở chế độ tạo bản gợi ý riêng, hệ thống yêu cầu tín hiệu đồng ý của người dùng trước khi gọi mô hình ngôn ngữ.",
        "Hệ thống theo yêu cầu 9, trong đó bản gợi ý được lưu trong một trường khác với trường kết quả thị giác và được gắn nhà cung cấp, tên mô hình, thời gian xử lý và lý do.",
        "Hệ thống theo bất kỳ yêu cầu nào từ 7 đến 10, trong đó dữ liệu đưa tới mô hình ngôn ngữ không chứa video hoặc khung hình mà chỉ chứa các giả thuyết văn bản và ngữ cảnh chữ.",
        "Hệ thống theo yêu cầu 1, trong đó khi mô hình ngôn ngữ lỗi hoặc vượt timeout, đáp ứng vẫn chứa trường kết quả thị giác và tập N-best.",
        "Hệ thống theo yêu cầu 1, trong đó máy chủ nạp trước tài sản mô hình và dùng semaphore giới hạn số lượt suy luận đồng thời nhằm vận hành trên bộ xử lý trung tâm không có GPU.",
        "Hệ thống theo yêu cầu 13, trong đó endpoint readiness chỉ báo sẵn sàng sau khi mô hình và tài sản tiền xử lý đã được kiểm tra.",
        "Hệ thống theo yêu cầu 13 hoặc 14, trong đó metadata đáp ứng ghi thiết bị tính toán, cấu hình số học, phiên bản mô hình, phiên bản pipeline, số khung và thời gian theo giai đoạn.",
        "Hệ thống theo yêu cầu 1, trong đó tệp video upload được đặt trong phạm vi tạm của một job và được xóa bằng thao tác dọn bắt buộc khi job hoàn tất, lỗi, bị hủy hoặc máy chủ đóng.",
        "Hệ thống theo yêu cầu 16, trong đó đáp ứng được đánh dấu không lưu cache và log không chứa khung hình video.",
        "Hệ thống theo yêu cầu 1, trong đó ứng dụng di động hiển thị kết quả thị giác, tập ứng viên và bản gợi ý ngôn ngữ trong các vùng giao diện phân biệt.",
        "Hệ thống theo yêu cầu 18, trong đó lịch sử văn bản được lưu cục bộ trên thiết bị mà không cần lưu lại video.",
        "Hệ thống theo yêu cầu 9 hoặc 10, trong đó trước khi tạo bản gợi ý riêng, một cổng an toàn tính chỉ số đa dạng của chuỗi kết quả thị giác và bỏ qua bước sinh bằng mô hình ngôn ngữ khi chuỗi có mức lặp vượt ngưỡng được cấu hình, đồng thời trả nguyên kết quả thị giác cùng mã lý do.",
        "Một phương pháp nhận dạng lời nói thị giác tiếng Việt, gồm các bước: nhận video; xác thực video; chuẩn hóa chuỗi vùng miệng; suy luận tạo N-best; đóng băng một kết quả thị giác; tùy chọn đưa N-best và ngữ cảnh chữ qua cổng chính sách; và trả kết quả thị giác cùng đầu ra tùy chọn tách biệt.",
        "Phương pháp theo yêu cầu 21, trong đó cổng chính sách xác minh schema của đầu ra mô hình ngôn ngữ và quay về kết quả thị giác khi schema hoặc quy tắc chế độ không được thỏa mãn.",
        "Phương pháp theo yêu cầu 21 hoặc 22, trong đó các tác vụ suy luận được đưa vào hàng đợi hữu hạn, API cấp định danh job, và một hoặc nhiều worker xử lý job theo giới hạn tài nguyên; hàng đợi có thể được thay bằng broker bền vững mà không đổi hợp đồng API.",
        "Một vật mang tin đọc được bởi máy tính chứa chỉ thị làm cho hệ thống thực hiện phương pháp theo bất kỳ yêu cầu nào từ 21 đến 23.",
        "Hệ thống theo yêu cầu 1, trong đó ứng dụng vừa ghi video cục bộ vừa lấy mẫu khung hình theo cơ chế backpressure, máy chủ giải mã các cửa sổ chồng lấn và trả phụ đề tạm cùng phụ đề đã chốt qua một kênh hai chiều.",
        "Hệ thống theo yêu cầu 25, trong đó máy chủ duy trì bộ đệm khung hình cuộn, đánh dấu tiền tố từ ổn định qua các giả thuyết liên tiếp, nối phần trùng tại biên cửa sổ và không viết lại phần văn bản đã chốt.",
    ]
    for claim_text in claims:
        p = doc.add_paragraph(style="Claim")
        apply_num(p, decimal_num)
        p.paragraph_format.left_indent = Cm(0.95)
        p.paragraph_format.first_line_indent = Cm(-0.5)
        p.paragraph_format.space_after = Pt(7)
        p.paragraph_format.line_spacing = 1.2
        p.add_run(claim_text)
        set_paragraph_keep(p, keep_lines=True)

    doc.add_heading("X. TÓM TẮT GIẢI PHÁP HỮU ÍCH", level=1)
    add_para(
        doc,
        "Giải pháp mô tả một hệ thống và phương pháp đọc môi tiếng Việt từ video trên "
        "thiết bị di động. Video được xác thực, trích mốc khuôn mặt, làm mượt theo thời "
        "gian, căn chỉnh affine về khuôn mặt chuẩn và chuyển thành chuỗi ROI miệng chuẩn "
        "hóa. Mô hình VSR tạo kết quả top-1 và tập N-best. Trường kết quả thị giác được "
        "đóng băng trước hậu xử lý. Người dùng chọn Visual only, Context select hoặc LLM "
        "assist; trong đó LLM chỉ nhận văn bản, chỉ được chọn nguyên ứng viên hoặc tạo bản "
        "gợi ý riêng có nhãn và sự đồng ý. Một safety gate bỏ qua bước sinh tự do khi kết "
        "quả thị giác lặp hoặc ít thông tin. Khi LLM lỗi, kết quả VSR vẫn được trả. Server "
        "có thể chạy CPU bằng cách nạp sẵn mô hình và giới hạn đồng thời, đồng thời hỗ trợ "
        "mở rộng qua hàng đợi job hữu hạn, định danh job và polling. Một consensus medoid "
        "từ N-best được trả như chỉ dấu rà soát, không thay top-1. Tệp video tạm được dọn bắt buộc và giao diện luôn hiển "
        "thị nguồn, độ bất định và yêu cầu rà soát. Khi phụ đề trực tiếp được bật, ứng dụng "
        "gửi khung lấy mẫu có backpressure qua WebSocket; server giải mã cửa sổ sáu giây "
        "chồng lấn một giây, giữ tiền tố ổn định, nối văn bản đã chốt và dùng bộ đệm cuộn "
        "để hỗ trợ phiên liên tục đến năm phút mà video vẫn được lưu cục bộ.",
    )

    doc.add_heading("XI. THUẬT NGỮ, NGUỒN THAM KHẢO VÀ ĐIỀU KIỆN HOÀN THIỆN", level=1)
    doc.add_heading("1. Thuật ngữ", level=2)
    glossary = [
        ("VSR", "Visual Speech Recognition – nhận dạng lời nói từ hình ảnh."),
        ("ROI", "Region of Interest – vùng ảnh quan tâm, ở đây là vùng miệng."),
        ("N-best", "Tập nhiều giả thuyết được bộ giải mã xếp hạng."),
        ("WER", "Word Error Rate – tỷ lệ lỗi từ so với câu tham chiếu."),
        ("CTC", "Connectionist Temporal Classification."),
        ("LLM", "Mô hình ngôn ngữ lớn."),
        ("Safety gate", "Cổng phòng vệ bỏ qua suy diễn LLM khi đầu vào lặp hoặc ít thông tin."),
        ("Mean face", "Tập tọa độ mốc khuôn mặt chuẩn dùng làm đích căn chỉnh."),
        ("Provenance", "Thông tin nguồn gốc của một kết quả hoặc phép biến đổi."),
        ("WebSocket", "Kênh hai chiều duy trì trong suốt phiên phụ đề trực tiếp."),
        ("Local agreement", "Quy tắc chỉ chốt tiền tố từ lặp lại qua các giả thuyết liên tiếp."),
        ("Causal", "Kiến trúc chỉ dùng thông tin hiện tại và quá khứ khi tạo đầu ra trực tuyến."),
    ]
    add_table(doc, ["Thuật ngữ", "Diễn giải"], glossary, [3.5, 12.05])

    doc.add_heading("2. Nguồn kỹ thuật tham khảo", level=2)
    references = [
        "Ma, P. và cộng sự, Auto-AVSR: Audio-Visual Speech Recognition with Automatic Labels, arXiv:2303.14307, https://arxiv.org/abs/2303.14307.",
        "Kho mã Auto-AVSR chính thức, giấy phép Apache-2.0, https://github.com/mpc001/auto_avsr.",
        "Google MediaPipe Face Mesh, tài liệu canonical face và landmark, https://chuoling.github.io/mediapipe/solutions/face_mesh.html.",
        "VSP-LLM: Visual Speech Processing with Large Language Models, Findings of EMNLP 2024, https://aclanthology.org/2024.findings-emnlp.666.pdf.",
        "VALLR: Visual ASR Language Model for Lip Reading, ICCV 2025, https://openaccess.thecvf.com/content/ICCV2025/html/Thomas_VALLR_Visual_ASR_Language_Model_for_Lip_Reading_ICCV_2025_paper.html.",
        "Ma, P. và cộng sự, Streaming Audio-Visual Speech Recognition with Alignment Regularization, arXiv:2211.02133, https://arxiv.org/abs/2211.02133.",
        "Macháček, D. và cộng sự, Turning Whisper into Real-Time Transcription System, arXiv:2307.14743, https://arxiv.org/abs/2307.14743.",
        "FastAPI, tài liệu WebSocket, https://fastapi.tiangolo.com/advanced/websockets/.",
        "Flutter, gói camera và luồng ảnh camera, https://pub.dev/packages/camera.",
        "Prabhavalkar, R. và cộng sự, Minimum Word Error Rate Training for Attention-based Sequence-to-Sequence Models, arXiv:1712.01818, https://arxiv.org/abs/1712.01818.",
        "FastAPI, Background Tasks và mô hình xử lý công việc hậu đáp ứng, https://fastapi.tiangolo.com/tutorial/background-tasks/.",
        "Python, asyncio Queue — hàng đợi bất đồng bộ có giới hạn, https://docs.python.org/3/library/asyncio-queue.html.",
        "ONNX Runtime, Model Optimizations — lượng tử hóa và tối ưu đồ thị, https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html.",
        "Ollama, tài liệu triển khai Windows, https://docs.ollama.com/windows.",
        "Ollama Library, danh mục mô hình ngôn ngữ cục bộ, https://ollama.com/library.",
        "Báo cáo huấn luyện, đánh giá độc lập người nói và kiểm chứng phần mềm của dự án.",
    ]
    # Keep the final source block clear of the page-number footer.
    add_bullets(doc, references, bullet_num)

    doc.add_page_break()
    doc.add_heading("3. Điều kiện trước khi phát hành thương mại hoặc nộp đơn", level=2)
    readiness_rows = [
        ("Tra cứu sáng chế", "Bắt buộc", "Tra cứu đối chứng và điều chỉnh yêu cầu bảo hộ."),
        ("Mean face", "Bắt buộc", "Tái tạo từ dữ liệu có quyền hoặc xin phép sử dụng."),
        ("Ký ứng dụng Android", "Bắt buộc", "Thay khóa phân phối nội bộ bằng khóa Play Store được quản trị và bảo vệ."),
        ("Ký bộ cài Windows", "Bắt buộc", "Ký Authenticode cho Setup.exe trước khi phát hành rộng."),
        ("Đánh giá hiện trường", "Bắt buộc", "Lập tập độc lập có người nói chưa thấy, nhiều thiết bị, góc quay và ánh sáng."),
        ("Hiệu chỉnh độ tin cậy", "Khuyến nghị cao", "Đo độ hiệu chỉnh; không biến điểm thô thành phần trăm tin cậy."),
        ("Bảo mật khi công khai", "Trước khi mở ra Internet", "HTTPS, xác thực, giới hạn tần suất, xóa dữ liệu và kiểm thử xâm nhập."),
        ("Chính sách LLM", "Bắt buộc", "Duy trì đồng ý, truy vết nguồn, giới hạn thời gian và đường dự phòng."),
        ("Đánh giá phụ đề liên tục", "Trước phát hành rộng", "Đo độ trễ đầu-cuối, độ ổn định câu, RAM và tỷ lệ bỏ khung trên CPU/GPU và nhiều thiết bị."),
    ]
    add_table(doc, ["Hạng mục", "Mức độ", "Việc cần hoàn tất"], readiness_rows, [4.0, 3.0, 8.55])

    enforce_times_new_roman(doc)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)
    print(output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    build_document(args.output.resolve())


if __name__ == "__main__":
    main()
