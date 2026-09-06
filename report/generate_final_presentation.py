# -*- coding: utf-8 -*-
"""
Generate the Final Year Project presentation (Project 309 - taoFPGA).
Transformer Accelerator on FPGA.

Sources: report/taoFPGA_Project_Book.docx, report/First_Project_Report_Group_309.pdf,
figures in report/figures/. Structure follows "Guidelines for Final Presentation.pdf".

Output: report/taoFPGA_Final_Presentation.pptx (export to PDF separately).
Run on the dev machine: `python generate_final_presentation.py`
(needs python-pptx and Pillow).
"""
import os
import re
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.oxml.ns import qn
from pptx.dml.color import RGBColor
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures")

# ----------------------------------------------------------------------------
# Design system
# ----------------------------------------------------------------------------
INK      = RGBColor(0x1B, 0x24, 0x30)   # dark slate
PAPER    = RGBColor(0xF7, 0xF7, 0xF4)   # off-white (matches figure bg)
BLUE     = RGBColor(0x20, 0x77, 0xE0)   # data / DSP / hardware
ORANGE   = RGBColor(0xE8, 0x70, 0x3A)   # compute / CPU
MUTED    = RGBColor(0x5B, 0x65, 0x70)   # secondary text
PANEL    = RGBColor(0xEC, 0xEE, 0xF1)   # light panel
GREEN    = RGBColor(0x2E, 0x9E, 0x5B)   # positive delta
WHITE    = RGBColor(0xFF, 0xFF, 0xFF)
LINE     = RGBColor(0xC9, 0xCE, 0xD6)

FONT   = "Segoe UI"
MONO   = "Consolas"

prs = Presentation()
prs.slide_width  = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]

SW, SH = 13.333, 7.5
PROJECT = "PROJECT 309"
_slide_no = [1]


def _set(tf, text, size, color, bold=False, font=FONT, align=PP_ALIGN.LEFT,
         italic=False, spacing=None):
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    if spacing:
        p.line_spacing = spacing
    run = p.add_run()
    run.text = text
    f = run.font
    f.size = Pt(size); f.name = font; f.bold = bold; f.italic = italic
    f.color.rgb = color
    return p


def box(slide, x, y, w, h, fill=None, line=None, line_w=1.0, shadow=False,
        rounded=False, radius=0.06):
    shp = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h))
    if rounded:
        try:
            shp.adjustments[0] = radius
        except Exception:
            pass
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid(); shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line; shp.line.width = Pt(line_w)
    shp.shadow.inherit = False
    return shp


def text(slide, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         spacing=1.0):
    """runs: list of dicts or list of paragraphs (list of run-dicts)."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    if runs and isinstance(runs[0], dict):
        runs = [runs]
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = para[0].get("align", align) if para else align
        p.line_spacing = spacing
        sb = para[0].get("space_before") if para else None
        if sb is not None:
            p.space_before = Pt(sb)
        for rd in para:
            r = p.add_run()
            r.text = rd["t"]
            r.font.name = rd.get("font", FONT)
            r.font.size = Pt(rd.get("s", 18))
            r.font.bold = rd.get("b", False)
            r.font.italic = rd.get("i", False)
            r.font.color.rgb = rd.get("c", INK)
    return tb


def bullets(slide, items, x, y, w, h, size=18, color=INK, spacing=1.12,
            gap=6):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, it in enumerate(items):
        if isinstance(it, tuple):
            lvl, txt = (it if len(it) == 2 else (0, it[0]))
        else:
            lvl, txt = 0, it
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = spacing
        p.space_before = Pt(gap if i else 0)
        p.space_after = Pt(0)
        bullet = "     – " if lvl else "▸  "
        r = p.add_run(); r.text = bullet
        r.font.name = FONT; r.font.size = Pt(size)
        r.font.color.rgb = BLUE if not lvl else MUTED
        r.font.bold = not lvl
        r = p.add_run(); r.text = txt
        r.font.name = FONT; r.font.size = Pt(size - (1 if lvl else 0))
        r.font.color.rgb = color if not lvl else MUTED
    return tb


def base(slide, title, kicker=None, dark=False):
    _slide_no[0] += 1
    bg = box(slide, -0.06, -0.06, SW + 0.12, SH + 0.12,
             fill=INK if dark else PAPER)
    # title bar
    box(slide, -0.06, -0.06, SW + 0.12, 1.12, fill=INK)
    box(slide, -0.06, 1.06, SW + 0.12, 0.05, fill=BLUE)
    tf = slide.shapes.add_textbox(Inches(0.6), Inches(0.06), Inches(9.9),
                                  Inches(1.0)).text_frame
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.word_wrap = True
    if kicker:
        p = tf.paragraphs[0]
        r = p.add_run(); r.text = kicker.upper()
        r.font.name = FONT; r.font.size = Pt(11); r.font.bold = True
        r.font.color.rgb = BLUE
        p2 = tf.add_paragraph()
    else:
        p2 = tf.paragraphs[0]
    r = p2.add_run(); r.text = title
    r.font.name = FONT; r.font.size = Pt(26); r.font.bold = True
    r.font.color.rgb = WHITE
    # project-number chip (every slide)
    chip = box(slide, SW - 2.35, 0.30, 1.75, 0.52, fill=None, line=BLUE,
               line_w=1.25, rounded=True, radius=0.5)
    ctf = chip.text_frame
    ctf.margin_top = 0; ctf.margin_bottom = 0
    _set(ctf, PROJECT, 11, WHITE, bold=True, align=PP_ALIGN.CENTER)
    ctf.vertical_anchor = MSO_ANCHOR.MIDDLE
    # footer
    tf = slide.shapes.add_textbox(Inches(0.6), Inches(SH - 0.44), Inches(10),
                                  Inches(0.34)).text_frame
    _set(tf, "taoFPGA  ·  Transformer Accelerator on FPGA  ·  Project 309",
         9, MUTED)
    tf = slide.shapes.add_textbox(Inches(SW - 1.4), Inches(SH - 0.44),
                                  Inches(0.9), Inches(0.34)).text_frame
    _set(tf, f"{_slide_no[0]:02d}", 9, MUTED, align=PP_ALIGN.RIGHT)
    return slide


def add_slide():
    return prs.slides.add_slide(BLANK)


def picture(slide, path, x, y, w, h, frame=True):
    im = Image.open(path); iw, ih = im.size
    ar = iw / ih; box_ar = w / h
    if ar > box_ar:
        dw = w; dh = w / ar
    else:
        dh = h; dw = h * ar
    px = x + (w - dw) / 2; py = y + (h - dh) / 2
    if frame:
        box(slide, px - 0.06, py - 0.06, dw + 0.12, dh + 0.12, fill=WHITE,
            line=LINE, line_w=1.0)
    slide.shapes.add_picture(path, Inches(px), Inches(py), Inches(dw),
                             Inches(dh))
    return (px, py, dw, dh)


def caption(slide, txt, x, y, w):
    tf = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w),
                                  Inches(0.5)).text_frame
    _set(tf, txt, 10.5, MUTED, italic=True)
    tf.word_wrap = True


def simple_table(slide, data, x, y, w, h, col_w=None, header=True,
                 fs=12, first_bold=False):
    rows, cols = len(data), len(data[0])
    gt = slide.shapes.add_table(rows, cols, Inches(x), Inches(y), Inches(w),
                                Inches(h)).table
    if col_w:
        for i, cw in enumerate(col_w):
            gt.columns[i].width = Inches(cw)
    for r in range(rows):
        for cidx in range(cols):
            cell = gt.cell(r, cidx)
            cell.margin_left = Inches(0.09); cell.margin_right = Inches(0.09)
            cell.margin_top = Inches(0.045); cell.margin_bottom = Inches(0.045)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            val = data[r][cidx]
            cell.text = ""
            para = cell.text_frame.paragraphs[0]
            para.line_spacing = 1.0
            rr = para.add_run(); rr.text = str(val)
            rr.font.name = FONT; rr.font.size = Pt(fs)
            if header and r == 0:
                cell.fill.solid(); cell.fill.fore_color.rgb = INK
                rr.font.color.rgb = WHITE; rr.font.bold = True
            else:
                cell.fill.solid()
                cell.fill.fore_color.rgb = WHITE if (r % 2) else PANEL
                rr.font.color.rgb = INK
                if first_bold and cidx == 0:
                    rr.font.bold = True
                if cidx == cols - 1 and str(val).strip().startswith(("-", "+", "−")):
                    rr.font.color.rgb = GREEN
                    rr.font.bold = True
    if header:
        gt.rows[0].height = Inches(0.42)
    for r in range(1 if header else 0, rows):
        gt.rows[r].height = Inches(0.34)
    return gt


def notes(slide, txt):
    slide.notes_slide.notes_text_frame.text = txt


# ----------------------------------------------------------------------------
# Math typography  (italic variables, real super/subscripts, Greek symbols)
# ----------------------------------------------------------------------------
MATH_FUNCS = {"max", "min", "exp", "ln", "log", "clip", "round", "floor",
              "softmax", "GELU", "gelu", "GOP", "GOPS"}


def _emit(p, txt, size, color, italic=False, bold=False, baseline=0, font=FONT):
    r = p.add_run(); r.text = txt
    r.font.name = font; r.font.size = Pt(size)
    r.font.italic = italic; r.font.bold = bold
    r.font.color.rgb = color
    if baseline:
        r._r.get_or_add_rPr().set("baseline", str(int(baseline)))
    return r


def _auto_math(p, s, size, color, baseline, bold):
    for tok in re.findall(r"[A-Za-z]+|\d+\.\d+|\d+|\s+|[^A-Za-z0-9\s]", s):
        if tok.isspace():
            _emit(p, tok, size, color, False, bold, baseline)
        elif tok[0].isalpha():
            is_fn = tok.lower() in {f.lower() for f in MATH_FUNCS}
            ital = (len(tok) == 1) and not is_fn
            _emit(p, tok, size, color, ital, bold, baseline)
        else:
            _emit(p, tok, size, color, False, bold, baseline)


def _render_segs(p, segs, size, color, baseline=0, bold=False):
    """segs: a str (plain prose) or a list of (kind, value) tuples.
    kinds: t=prose roman, m=math (italic vars), rm=roman, it=italic,
    bd=bold roman, ^=superscript, _=subscript (value may be str or seglist)."""
    if isinstance(segs, str):
        segs = [("t", segs)]
    for seg in segs:
        kind, val = seg[0], seg[1]
        if kind == "t":
            _emit(p, val, size, color, False, bold, baseline)
        elif kind == "m":
            _auto_math(p, val, size, color, baseline, bold)
        elif kind == "rm":
            _emit(p, val, size, color, False, bold, baseline)
        elif kind == "it":
            _emit(p, val, size, color, True, bold, baseline)
        elif kind == "bd":
            _emit(p, val, size, color, False, True, baseline)
        elif kind == "^":
            inner = val if not isinstance(val, str) else [("m", val)]
            _render_segs(p, inner, size * 0.80, color, baseline + 33000, bold)
        elif kind == "_":
            inner = val if not isinstance(val, str) else [("m", val)]
            _render_segs(p, inner, size * 0.80, color, baseline - 20000, bold)


def mathbox(slide, x, y, w, h, segs, size=14, color=INK, align=PP_ALIGN.LEFT,
            anchor=MSO_ANCHOR.TOP, spacing=1.14, para_gap=5):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True; tf.vertical_anchor = anchor
    lines = segs if (segs and isinstance(segs[0], list)) else [segs]
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align; p.line_spacing = spacing
        if i:
            p.space_before = Pt(para_gap)
        _render_segs(p, ln, size, color)
    return tb


def mbullets(slide, items, x, y, w, h, size=12.5, color=INK, spacing=1.16,
             gap=8):
    """Bulleted list where each item may carry math segments.
    item: str (prose) | seglist | (level, str|seglist) with level in {0,1}."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    for i, it in enumerate(items):
        lvl, segs = 0, it
        if isinstance(it, tuple) and len(it) == 2 and it[0] in (0, 1):
            lvl, segs = it
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = spacing
        p.space_before = Pt(gap if i else 0)
        _emit(p, ("      –  " if lvl else "▸  "), size,
              MUTED if lvl else BLUE, bold=not lvl)
        _render_segs(p, segs, size - (1 if lvl else 0),
                     MUTED if lvl else color)
    return tb


# ----------------------------------------------------------------------------
# Verilog / RTL syntax highlighting
# ----------------------------------------------------------------------------
VL_KW = {"always", "reg", "wire", "begin", "end", "posedge", "negedge",
         "signed", "assign", "module", "endmodule", "input", "output",
         "parameter", "localparam", "if", "else", "logic", "genvar",
         "generate", "endgenerate", "for", "integer", "case", "endcase"}
C_KW   = RGBColor(0x0B, 0x5F, 0xB5)   # keywords        - blue
C_ATTR = RGBColor(0xA8, 0x62, 0x00)   # (* pragmas *)   - amber
C_COM  = RGBColor(0x63, 0x7C, 0x63)   # // comments     - muted green
C_NUM  = RGBColor(0x12, 0x84, 0x67)   # numeric literals- teal
C_STR  = RGBColor(0xB5, 0x2E, 0x2E)   # "strings"       - red
C_ID   = RGBColor(0x22, 0x2B, 0x38)   # identifiers     - near-ink
C_OP   = RGBColor(0x7A, 0x84, 0x90)   # operators       - grey

_VTOK = re.compile(
    r"(//[^\n]*)|(\(\*.*?\*\))|(\"[^\"]*\")|"
    r"(\d+'[bhdBHD][0-9a-fA-F_xXzZ]+|\d+)|"
    r"([A-Za-z_][A-Za-z0-9_$]*)|(\s+)|([^\sA-Za-z0-9_]+)")


def _vl_spans(line):
    out = []
    for m in _VTOK.finditer(line):
        com, attr, st, num, ident, ws, op = m.groups()
        if com is not None:
            out.append((com, C_COM, True))
        elif attr is not None:
            out.append((attr, C_ATTR, False))
        elif st is not None:
            out.append((st, C_STR, False))
        elif num is not None:
            out.append((num, C_NUM, False))
        elif ident is not None:
            out.append((ident, C_KW if ident in VL_KW else C_ID, False))
        elif ws is not None:
            out.append((ws, C_ID, False))
        else:
            out.append((op, C_OP, False))
    return out or [(" ", C_ID, False)]


def code_highlight(tf, lines, size=9.5, spacing=1.12):
    tf.word_wrap = True
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = spacing
        for txt, col, ital in _vl_spans(ln):
            r = p.add_run(); r.text = txt
            r.font.name = MONO; r.font.size = Pt(size)
            r.font.color.rgb = col; r.font.italic = ital


# ----------------------------------------------------------------------------
# Large stat callout card
# ----------------------------------------------------------------------------
def stat_card(slide, x, y, w, h, value, label, accent=BLUE, dark=False,
              value_size=30, label_size=10.5):
    fill = INK if dark else WHITE
    txtc = WHITE if dark else INK
    card = box(slide, x, y, w, h, fill=fill, line=accent, line_w=1.4,
               rounded=True, radius=0.14)
    box(slide, x, y, 0.11, h, fill=accent)
    tb = slide.shapes.add_textbox(Inches(x + 0.22), Inches(y),
                                  Inches(w - 0.34), Inches(h)).text_frame
    tb.word_wrap = True
    tb.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tb.paragraphs[0]; p.line_spacing = 1.0
    r = p.add_run(); r.text = value
    r.font.name = FONT; r.font.size = Pt(value_size); r.font.bold = True
    r.font.color.rgb = accent
    p2 = tb.add_paragraph(); p2.line_spacing = 1.05; p2.space_before = Pt(2)
    r = p2.add_run(); r.text = label
    r.font.name = FONT; r.font.size = Pt(label_size)
    r.font.color.rgb = txtc if dark else MUTED
    return card


# ----------------------------------------------------------------------------
# Waveform annotation overlays  (boxes / arrows / labels on a fitted picture)
# ----------------------------------------------------------------------------
GOLD = RGBColor(0xF3, 0x9C, 0x12)


def _ov(rect, fx, fy):
    px, py, dw, dh = rect
    return (px + fx * dw, py + fy * dh)


def annot_box(slide, rect, f, color=GOLD, width=2.0):
    x1, y1 = _ov(rect, f[0], f[1])
    x2, y2 = _ov(rect, f[2], f[3])
    return box(slide, x1, y1, x2 - x1, y2 - y1, fill=None, line=color,
               line_w=width, rounded=True, radius=0.16)


def annot_arrow(slide, rect, fx1, fy1, fx2, fy2, color=GOLD, width=2.25):
    x1, y1 = _ov(rect, fx1, fy1)
    x2, y2 = _ov(rect, fx2, fy2)
    cn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1),
                                    Inches(y1), Inches(x2), Inches(y2))
    cn.line.color.rgb = color
    cn.line.width = Pt(width)
    cn.shadow.inherit = False
    ln = cn.line._get_or_add_ln()
    ln.append(ln.makeelement(qn("a:tailEnd"),
                             {"type": "triangle", "w": "lg", "len": "lg"}))
    return cn


def annot_label(slide, rect, fx, fy, w_in, text, color=GOLD, size=9.5,
                anchor="l"):
    x, y = _ov(rect, fx, fy)
    if anchor == "c":
        x -= w_in / 2
    elif anchor == "r":
        x -= w_in
    pill = box(slide, x, y, w_in, 0.32, fill=color, rounded=True, radius=0.5)
    pill.line.fill.background()
    tf = pill.text_frame
    tf.margin_top = 0; tf.margin_bottom = 0
    tf.margin_left = Inches(0.06); tf.margin_right = Inches(0.06)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    _set(tf, text, size, WHITE, bold=True, align=PP_ALIGN.CENTER)
    return pill


# ============================================================================
# 1 - TITLE
# ============================================================================
s = add_slide()
box(s, -0.06, -0.06, SW + 0.12, SH + 0.12, fill=INK)
box(s, 0, 2.02, SW, 0.06, fill=BLUE)
box(s, 0, 4.30, SW, 0.02, fill=RGBColor(0x33, 0x3E, 0x4C))
text(s, 0.9, 0.72, 11.5, 0.5,
     [{"t": "FINAL YEAR PROJECT  ·  COMPUTER ENGINEERING – HARDWARE & CHIP DESIGN",
       "s": 13, "b": True, "c": BLUE}])
text(s, 0.9, 1.15, 11.6, 1.0,
     [{"t": "taoFPGA", "s": 54, "b": True, "c": WHITE}])
text(s, 0.9, 2.35, 11.6, 1.5,
     [{"t": "Architecture, Implementation, and Evaluation of a Quantized "
            "Transformer Processing Core on an Edge FPGA",
       "s": 21, "c": RGBColor(0xC7, 0xD0, 0xDC)}])
text(s, 0.9, 4.55, 11.6, 1.2, [
    [{"t": "Eliran Turgeman", "s": 17, "b": True, "c": WHITE},
     {"t": "   316372002        ", "s": 14, "c": MUTED},
     {"t": "Shay Rask", "s": 17, "b": True, "c": WHITE},
     {"t": "   314951658", "s": 14, "c": MUTED}],
])
text(s, 0.9, 5.35, 11.6, 1.2, [
    [{"t": "Academic supervisor:  ", "s": 13, "c": MUTED},
     {"t": "Dr. Leonid Yavits", "s": 13, "b": True, "c": RGBColor(0xC7,0xD0,0xDC)}],
    [{"t": "Project mentor:  ", "s": 13, "c": MUTED},
     {"t": "David Freud", "s": 13, "b": True, "c": RGBColor(0xC7,0xD0,0xDC)}],
])
chip = box(s, 0.9, 6.45, 2.0, 0.55, fill=None, line=BLUE, line_w=1.5,
           rounded=True, radius=0.5)
_set(chip.text_frame, "PROJECT 309", 12, WHITE, bold=True,
     align=PP_ALIGN.CENTER)
chip.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
text(s, SW - 5.9, 6.5, 5.0, 0.5,
     [{"t": "Final presentation  ·  Bar-Ilan University, Faculty of Engineering",
       "s": 11, "c": MUTED, "align": PP_ALIGN.RIGHT}])
notes(s, "Greeting + introductions. We are Eliran Turgeman and Shay Rask, "
         "Computer Engineering, hardware & chip design track. Supervisor Dr. "
         "Leonid Yavits, mentor David Freud. Project 309: taoFPGA, a quantized "
         "INT8 Transformer processing core taken from fixed-point math all the "
         "way to real silicon on a $200 Zynq board. 15 minutes; Shay takes "
         "background/architecture, Eliran takes verification/results.")

# ============================================================================
# 2 - OUTLINE
# ============================================================================
s = add_slide(); base(s, "Outline", kicker="Where we are going")
items = [
    ("1  Background & motivation – the edge-AI compute dilemma", BLUE),
    ("2  Problem statement, objectives & scope", MUTED),
    ("3  Methodology – a verify-every-layer co-design flow", MUTED),
    ("4  Core hardware architecture (systolic array + fixed-point Softmax/GELU)", MUTED),
    ("5  Technical contribution – a synthesis attribute that silently did nothing", ORANGE),
    ("6  Results: kernel speedup, silicon verification, honest workload analysis", MUTED),
    ("7  Planning vs. execution, challenges, budget & roadmap", MUTED),
    ("8  Conclusions & recommendations", MUTED),
]
tf = s.shapes.add_textbox(Inches(0.9), Inches(1.55), Inches(11.5),
                          Inches(5.4)).text_frame
tf.word_wrap = True
for i, (t, c) in enumerate(items):
    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
    p.line_spacing = 1.15; p.space_before = Pt(11 if i else 0)
    r = p.add_run(); r.text = t
    r.font.name = FONT; r.font.size = Pt(18)
    r.font.bold = c in (BLUE, ORANGE)
    r.font.color.rgb = INK if c is MUTED else c
notes(s, "30-second roadmap. Flag slide 5 as the self-contained technical "
         "contribution the guidelines ask for - it stands on its own even if "
         "you have not read the report.")

# ============================================================================
# 3 - BACKGROUND
# ============================================================================
s = add_slide(); base(s, "Background: the edge-AI compute dilemma",
                       kicker="1 · Significance & justification")
mbullets(s, [
    "Transformers are the state of the art in both NLP and computer vision "
    "(Vision Transformers, ViT).",
    "Their computational profile is hostile to edge hardware:",
    (1, [("m", "O"), ("t", "("), ("m", "N"), ("^", "2"),
         ("t", ") self-attention in the sequence length")]),
    (1, "large dense matrix multiplications in every encoder layer"),
    (1, "non-linearities (Softmax, GELU) between those matmuls"),
    "Edge SoCs are simultaneously short on DRAM bandwidth, on-chip memory "
    "and power budget – exactly the resources Transformers stress.",
    "A general-purpose CPU/GPU wastes energy on control and data movement; a "
    "dedicated datapath does not – a computer-engineering problem: "
    "co-design the arithmetic, the data movement and the silicon together.",
], 0.85, 1.65, 7.55, 5.3, size=15.5, spacing=1.24, gap=11)
box(s, 8.7, 1.7, 3.95, 4.95, fill=PANEL, line=LINE, rounded=True)
text(s, 8.98, 2.0, 3.45, 4.4, [
    [{"t": "Why an FPGA", "s": 14, "b": True, "c": INK}],
    [{"t": "▸  Custom INT8 datapath, no ISA overhead", "s": 12.5, "c": MUTED, "space_before": 8}],
    [{"t": "▸  Hard DSP + BRAM blocks map matmul directly", "s": 12.5, "c": MUTED, "space_before": 6}],
    [{"t": "▸  Reprogrammable – an academic-scale ASIC proxy", "s": 12.5, "c": MUTED, "space_before": 6}],
    [{"t": "▸  Commodity board: PYNQ-Z2, ~$199", "s": 12.5, "c": MUTED, "space_before": 6}],
    [{"t": "Builds on prior FPGA transformer accelerators "
           "(ME-ViT, FTRANS, systolic-array designs) – same design "
           "family, embedded-scale device.", "s": 12, "c": INK, "space_before": 12}],
], spacing=1.1)
notes(s, "Establish the gap. Every recent FPGA transformer accelerator "
         "converges on the same three ideas - systolic/PE matmul, fixed-point "
         "quantization, dedicated activation units - because the bottleneck is "
         "always the same. Prior art (refs [2]-[5]) targets datacenter FPGAs; "
         "we target a 220-DSP embedded Zynq. The engineering interest is the "
         "resource pressure: everything is scarce at once.")

# ============================================================================
# 4 - PRELIMINARIES
# ============================================================================
s = add_slide(); base(s, "Three ideas the rest of the talk builds on",
                       kicker="1 · Preliminaries (self-contained)")
cols = [
    ("Self-attention", BLUE, [
        "Every token attends to every other token.",
        [("m", "Q·K"), ("^", "T"), ("t", "  →  scale  →  "), ("rm", "Softmax"),
         ("t", "  →  weighted sum of "), ("m", "V"), ("t", ".")],
        "Then a position-wise MLP with a GELU.",
        [("t", "Cost is "), ("it", "O"), ("t", "("), ("m", "N"), ("^", "2"),
         ("t", ") MACs — the quadratic term.")],
    ]),
    ("INT8 quantization", ORANGE, [
        "Store each value as a signed 8-bit int + a shared "
        "power-of-two scale.",
        [("m", "x"), ("t", "  ≈  "), ("rm", "round"), ("t", "("), ("m", "x"),
         ("t", " / scale)"), ("t", ".")],
        [("m", "INT8 × INT8"), ("t", "  →  wide product  →  round-half-up "
         "& saturate to [−128, 127].")],
        "⅓ the memory bandwidth of FP32.",
    ]),
    ("Systolic array", BLUE, [
        "2-D grid of tiny multiply-accumulate PEs.",
        "Operands stream through neighbours only — no global "
        "memory, short wires.",
        "Weight-stationary: each PE holds one weight while features "
        "stream past.",
        "Matches the Transformer's weight-reuse pattern.",
    ]),
]
x = 0.7
for name, c, pts in cols:
    box(s, x, 1.68, 3.9, 4.5, fill=WHITE, line=LINE, rounded=True)
    box(s, x, 1.68, 3.9, 0.62, fill=c, rounded=True, radius=0.12)
    tfh = box(s, x, 1.68, 3.9, 0.62, fill=None).text_frame
    tfh.vertical_anchor = MSO_ANCHOR.MIDDLE
    _set(tfh, name, 15, WHITE, bold=True, align=PP_ALIGN.CENTER)
    mbullets(s, pts, x + 0.3, 2.6, 3.35, 3.5, size=12.5, spacing=1.22, gap=10)
    x += 4.07
text(s, 0.7, 6.55, 12.0, 0.5,
     [{"t": "These three primitives are the whole talk: matmul + Softmax + "
            "GELU, in INT8, on a systolic array.", "s": 11.5, "i": True,
       "c": MUTED, "align": PP_ALIGN.CENTER}])
notes(s, "This slide is the glossary so the contribution slides are "
         "self-contained. Keep it to ~45s: attention is matmul + Softmax + "
         "matmul + GELU; quantization trades precision for bandwidth and logic; "
         "a weight-stationary systolic array is how you do the matmul without "
         "long wires.")

# ============================================================================
# 5 - PROBLEM STATEMENT
# ============================================================================
s = add_slide(); base(s, "Problem statement", kicker="2 · The core issue")
box(s, 0.9, 1.7, 11.5, 1.5, fill=INK, rounded=True)
text(s, 1.25, 1.9, 10.8, 1.2, [
    [{"t": "Run the compute-dominant primitives of a Transformer block "
           "– dense matmul plus its Softmax / GELU non-linearities "
           "– as a dedicated, numerically-verified INT8 datapath on a "
           "commodity 220-DSP edge FPGA, and prove the speed-up is real.",
      "s": 15.5, "b": True, "c": WHITE}],
], spacing=1.12)
bullets(s, [
    "FP32 inference is infeasible on an embedded FPGA – every MAC costs "
    "more logic, every value costs 4× the bandwidth.",
    "A correct accelerator is not enough: it has to be verified against a "
    "ground-truth model at every layer (RTL, integration, silicon).",
    "And the reported gain must correspond to an operation the hardware can "
    "actually perform correctly – not an impressive-looking number that "
    "hides a broken computation.",
], 0.9, 3.5, 11.5, 3.2, size=16)
notes(s, "Three clauses: (1) build the datapath on a small device, (2) verify "
         "it end to end, (3) only claim a speed-up that is genuinely true. The "
         "third clause becomes a real result later (slide 18).")

# ============================================================================
# 6 - OBJECTIVES
# ============================================================================
s = add_slide(); base(s, "Objectives", kicker="3 · General & specific")
box(s, 0.9, 1.6, 11.5, 1.15, fill=PANEL, line=LINE, rounded=True)
text(s, 1.2, 1.75, 11.0, 0.95, [
    [{"t": "General  ", "s": 13, "b": True, "c": BLUE},
     {"t": "Design, implement and quantitatively evaluate a complete "
           "hardware accelerator for a Transformer block's dominant "
           "primitives on a resource-constrained edge FPGA, and demonstrate "
           "measurable latency / throughput / energy gains over a CPU baseline.",
      "s": 13, "c": INK}],
], spacing=1.1)
objs = [
    ("O1", "INT8 weight-stationary 16×16 systolic matmul core with fused "
           "fixed-point Softmax and GELU engines, formalised as exact "
           "fixed-point equations."),
    ("O2", "Tolerance-bounded verification: SystemVerilog testbenches + a "
           "bit-faithful Python/NumPy golden model carried to silicon."),
    ("O3", "Integrate the core as an AXI peripheral on a Zynq-7020 (PYNQ-Z2) "
           "SoC and bring it up on real hardware."),
    ("O4", "Close physical timing at 100 MHz and optimise post-route "
           "resource / power at signoff."),
    ("O5", "Benchmark the hardware kernel against the on-chip ARM Cortex-A9 "
           "and characterise the result honestly against real ViT workloads."),
]
y = 3.0
for tag, desc in objs:
    box(s, 0.9, y, 0.72, 0.72, fill=BLUE, rounded=True, radius=0.2)
    tfh = box(s, 0.9, y, 0.72, 0.72, fill=None).text_frame
    tfh.vertical_anchor = MSO_ANCHOR.MIDDLE
    _set(tfh, tag, 14, WHITE, bold=True, align=PP_ALIGN.CENTER)
    text(s, 1.8, y - 0.04, 10.6, 0.85,
         [[{"t": desc, "s": 13.5, "c": INK}]], spacing=1.06)
    y += 0.82
notes(s, "These five specific objectives are the spine of the whole talk and "
         "the conclusion returns to each one with a recommendation.")

# ============================================================================
# 7 - SCOPE
# ============================================================================
s = add_slide(); base(s, "Scope & boundaries", kicker="4 · What this project is and is not")
box(s, 0.8, 1.6, 5.9, 5.2, fill=WHITE, line=GREEN, line_w=1.5, rounded=True)
box(s, 0.8, 1.6, 5.9, 0.6, fill=GREEN, rounded=True, radius=0.12)
_set(box(s, 0.8, 1.6, 5.9, 0.6, fill=None).text_frame, "IN SCOPE", 14, WHITE,
     bold=True, align=PP_ALIGN.CENTER)
bullets(s, [
    "Fused matmul → Softmax → GELU streaming pipeline",
    "INT8, weight-stationary, 16×16 systolic array (256 MACs)",
    "Xilinx Zynq-7020 / PYNQ-Z2, 100 MHz",
    "RTL flow (SystemVerilog / Verilog), not HLS",
    "Kernel-level benchmark vs. the board's ARM Cortex-A9",
    "Full physical signoff + bitstream + silicon bring-up",
], 1.05, 2.4, 5.4, 4.3, size=12.5, spacing=1.12, gap=8)
box(s, 6.95, 1.6, 5.6, 5.2, fill=WHITE, line=ORANGE, line_w=1.5, rounded=True)
box(s, 6.95, 1.6, 5.6, 0.6, fill=ORANGE, rounded=True, radius=0.12)
_set(box(s, 6.95, 1.6, 5.6, 0.6, fill=None).text_frame, "OUT OF SCOPE", 14,
     WHITE, bold=True, align=PP_ALIGN.CENTER)
bullets(s, [
    "End-to-end accelerated ViT inference (fixed pipeline maps to no single "
    "ViT sub-block – slide 18)",
    "Batch processing & the full 768-wide ViT-Tiny MLP (64 KB DMA ceiling)",
    "Training / back-propagation",
    "Datacenter-class FPGAs and multi-device scaling",
    "Physically-instrumented power measurement (signoff-grade estimate used)",
], 7.2, 2.4, 5.1, 4.3, size=12.5, spacing=1.12, gap=8)
notes(s, "Being explicit about the out-of-scope column is itself a result: "
         "each exclusion has a concrete, documented reason, not hand-waving. "
         "The DMA ceiling and the ViT workload mismatch both come back later.")

# ============================================================================
# 8 - METHODOLOGY FLOW
# ============================================================================
s = add_slide(); base(s, "Methodology: a verify-every-layer flow",
                       kicker="5 · Co-design flow")
steps = [
    ("Fixed-point\nmath (Eq. 1–2)", BLUE),
    ("RTL +\nSystemVerilog\ntestbenches\n(Cadence Xcelium)", BLUE),
    ("Python / NumPy\nbit-faithful\ngolden model", ORANGE),
    ("SoC integration\n(Vivado IP\nIntegrator)", BLUE),
    ("P&R + physical\nsignoff\n(timing, power)", BLUE),
    ("Bitstream +\nhardware\nplatform (.xsa)", BLUE),
    ("PYNQ-Z2\nsilicon bring-up\n& benchmark", ORANGE),
]
n = len(steps); gap = 0.22
w = (12.0 - gap * (n - 1)) / n
x = 0.7
for i, (t, c) in enumerate(steps):
    box(s, x, 1.7, w, 2.55, fill=WHITE, line=c, line_w=1.5, rounded=True)
    tfc = box(s, x, 1.7, w, 2.55, fill=None).text_frame
    tfc.vertical_anchor = MSO_ANCHOR.MIDDLE
    tfc.word_wrap = True
    _set(tfc, t, 10.5, INK, bold=True, align=PP_ALIGN.CENTER, spacing=1.05)
    if i < n - 1:
        ar = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + w - 0.02),
                                Inches(2.78), Inches(gap + 0.04), Inches(0.4))
        ar.fill.solid(); ar.fill.fore_color.rgb = MUTED
        ar.line.fill.background(); ar.shadow.inherit = False
    x += w + gap
box(s, 0.7, 4.75, 12.0, 2.0, fill=PANEL, line=LINE, rounded=True)
text(s, 1.0, 4.95, 11.4, 1.7, [
    [{"t": "Governing discipline:  ", "s": 13, "b": True, "c": ORANGE},
     {"t": "every layer is checked against its own reference, never assumed "
           "correct because the layer below it passed. The SystemVerilog "
           "golden model is re-derived in NumPy and cross-checked against the "
           "RTL shifter's exact rounding before it is trusted to validate "
           "silicon.", "s": 13, "c": INK}],
    [{"t": "Verification is tolerance-bounded (scale-dependent LSB threshold), "
           "not exact-match – to absorb quantization-error compounding "
           "across two INT8 boundaries.", "s": 12, "c": MUTED, "space_before": 8}],
], spacing=1.1)
notes(s, "The flow is linear on the slide but was highly iterative in "
         "practice (Appendix A). The key methodological choice: a bug at layer "
         "N is not diagnosed by trusting layer N-1; each interface is "
         "re-derived from the current source of truth. This is what caught the "
         "stale driver and the six parameter mismatches.")

# ============================================================================
# 9 - ARCHITECTURE: PE
# ============================================================================
s = add_slide(); base(s, "Core architecture – the processing element",
                       kicker="6 · Systolic matmul core (MM_ultra)")
picture(s, os.path.join(FIG, "fig_pe_microarch_v2.png"), 0.7, 1.5, 7.4, 5.2)
mbullets(s, [
    [("m", "16 × 16"), ("t", " grid  →  256 INT8 MACs, one MAC / PE / cycle.")],
    [("t", "Weight-stationary: "), ("it", "reg_w"), ("t", " loaded once via "),
     ("it", "set_w"), ("t", ", held for the whole matmul; "), ("m", "x"),
     ("t", " streams west→east, "), ("it", "psum"), ("t", " north→south.")],
    [("t", "20-bit signed accumulator  ("), ("m", "2·data_width + log"),
     ("_", "2"), ("m", " m"), ("t", ",  "), ("m", "m"), ("t", " = 16).")],
    [("t", "Output "), ("rm", "round"), ("t", "-half-up on an arithmetic "
     "right shift, then "), ("rm", "clip"), ("t", " to [−128, 127]   "
     "(Eq. 1, "), ("it", "right_shifter.v"), ("t", ").")],
    "Runtime block-count registers set the contraction / output dims.",
], 8.35, 1.75, 4.35, 5.0, size=12.5, spacing=1.2, gap=10)
notes(s, "One PE: a held weight, a streamed activation with a registered "
         "pass-through, a multiplier, and a 20-bit accumulate register. That "
         "psum_out_r register is the exact object the contribution slide is "
         "about. Round-half-up-and-saturate is the only place precision is "
         "lost, and it is formalised so the golden model can match it exactly.")

# ============================================================================
# 10 - ARCHITECTURE: SOFTMAX / GELU
# ============================================================================
s = add_slide(); base(s, "Core architecture – fixed-point non-linear engines",
                       kicker="6 · Softmax & GELU")
picture(s, os.path.join(FIG, "fig_softmax_fsm.png"), 0.7, 1.45, 4.5, 5.4)
mbullets(s, [
    "Softmax — 3-pass scalar FSM, one buffered row at a time; each pass "
    "streams the full row once.",
    [("t", "Pass 2/3 use a base-2 exp approximation ("), ("m", "log"),
     ("_", "2"), ("m", " e"), ("t", "-scaled); pass 3 avoids a divider "
     "with a log-domain term ("), ("it", "Ln_module"), ("t", ").")],
    "GELU — two-segment piecewise-linear: saturate outside a threshold, "
    "linear correction (lin.v) inside.",
], 5.45, 1.65, 7.25, 2.1, size=12.5, spacing=1.2, gap=9)

box(s, 5.45, 3.75, 7.3, 3.0, fill=PANEL, line=LINE, rounded=True)
_set(box(s, 5.7, 3.9, 6.9, 0.4, fill=None).text_frame,
     "Per-pass equations  (exact base-2 restatement of softmax)", 11,
     ORANGE, bold=True)
mathbox(s, 5.8, 4.45, 6.85, 1.7, [
    [("bd", "Pass 1    "), ("it", "m"), ("rm", " = "), ("rm", "max"),
     ("_", "i"), ("rm", " "), ("it", "x"), ("_", "i")],
    [("bd", "Pass 2    "), ("it", "S"), ("rm", " = "), ("rm", "Σ"),
     ("_", "i"), ("rm", " 2"), ("^", "(xᵢ − m)·log₂ e")],
    [("bd", "Pass 3    "), ("it", "y"), ("_", "i"), ("rm", " = 2"),
     ("^", "((xᵢ − m) − ln S)·log₂ e")],
], size=15, color=INK, spacing=1.55)
text(s, 5.75, 6.18, 6.9, 0.5,
     [{"t": "3N cycles / row, strictly serial  →  the Softmax throughput "
            "bottleneck.", "s": 10.5, "i": True, "c": MUTED}])
notes(s, "Softmax is exact softmax re-expressed in the base-2, log-domain "
         "form the hardware actually computes - so 'golden' really means "
         "identical, not merely close. The 3N-cycle serial structure is a "
         "deliberate area choice and a known throughput limit we quantify "
         "later.")

# ============================================================================
# 11 - ARCHITECTURE: SoC
# ============================================================================
s = add_slide(); base(s, "SoC integration on the Zynq-7020",
                       kicker="6 · transformer_block_axi_top")
picture(s, os.path.join(FIG, "fig_soc_architecture_v2.png"), 0.7, 1.55, 12.0, 3.5)
bullets(s, [
    "AXI4-Lite control (7 config regs + 1 status bit) + dual AXI4-Stream in "
    "(feature, weight) / single AXI4-Stream out (result).",
    "Three independent AXI DMA engines; PS7 dual-core Cortex-A9 configures "
    "and drives the streams; AXI SmartConnect interconnect.",
    "Bespoke AXI-Stream width adapters bridge the parallel array ↔ serial "
    "Softmax ↔ GELU datapath widths, plus a purpose-built row-boundary signal.",
], 0.9, 5.2, 11.7, 1.9, size=12.5, spacing=1.1, gap=6)
notes(s, "Integration surfaced two things worth noting: 40+ async-reset "
         "DRC violations on BRAM control logic (fixed across 12 files), and "
         "the discovery that the *full* pipeline had never actually been "
         "AXI-wrapped - only the standalone matmul. We built the wrapper "
         "keeping the RTL's own parameter names to avoid re-introducing an "
         "earlier drift bug.")

# ============================================================================
# 12 - VERIFICATION RESULTS
# ============================================================================
s = add_slide(); base(s, "RTL verification – tolerance-bounded, end to end",
                       kicker="6 · Cadence Xcelium simulation")
wf = picture(s, os.path.join(FIG, "simvision_waveform_full.png"),
             0.7, 1.5, 8.15, 4.0)
# --- annotations on the waveform ---
annot_box(s, wf, (0.222, 0.740, 0.996, 0.870))               # 3 softmax flags
annot_label(s, wf, 0.235, 0.585, 2.55, "3-Pass Softmax Progression")
annot_arrow(s, wf, 0.34, 0.701, 0.34, 0.740)
annot_box(s, wf, (0.505, 0.872, 0.640, 0.945))              # 18,083 value
annot_label(s, wf, 0.700, 0.878, 2.15, "18,083 cycles locked")
annot_arrow(s, wf, 0.698, 0.908, 0.641, 0.908)
caption(s, "Real SimVision capture (transformer_block_tb): AXI-Stream ingest, "
           "3-pass Softmax flags, streaming output; pipe_latency_cycles locks "
           "at 18,083.", 0.7, 5.55, 8.15)
text(s, 9.15, 1.62, 3.7, 0.4,
     [{"t": "FULL-SCALE RUN · 200 × 96 × 160", "s": 10.5, "b": True,
       "c": MUTED}])
stat_card(s, 9.15, 2.05, 3.75, 1.55, "0 / 32,000",
          "output elements outside the tolerance bound", accent=GREEN,
          value_size=27, label_size=10)
stat_card(s, 9.15, 3.8, 3.75, 1.55, "18,083",
          "cycle end-to-end latency, read straight off the counter",
          accent=BLUE, value_size=28, label_size=10)
text(s, 9.15, 5.55, 3.75, 1.4,
     [{"t": "4 SystemVerilog testbenches (gelu, Softmax, MM_Ultra, "
            "integration), each with a $real golden reference.", "s": 10.5,
       "c": MUTED}], spacing=1.14)
notes(s, "Tolerance is a 6-LSB bound at the shared Softmax/GELU scale, chosen "
         "to absorb error compounding across two INT8 boundaries - not a "
         "fudge. The 18,083-cycle figure is read off the counter in the "
         "waveform, not reconstructed, and it is the same number the silicon "
         "run reproduces later.")

# ============================================================================
# 13 - CONTRIBUTION 1/3
# ============================================================================
s = add_slide(); base(s, "Technical contribution – the symptom",
                       kicker="★  A synthesis attribute that silently did nothing")
box(s, 0.9, 1.6, 11.5, 1.35, fill=INK, rounded=True)
text(s, 1.2, 1.78, 11.0, 1.1, [
    [{"t": "Post-route, the matmul-dominated accelerator was LUT-bound, not "
           "DSP-bound – the exact inverse of what a 256-MAC systolic "
           "array should look like.", "s": 15, "b": True, "c": WHITE}],
], spacing=1.1)
simple_table(s, [
    ["Resource (post-route, full SoC)", "Usage", "Reading"],
    ["DSP48E1 hard multipliers", "13 / 220   (5.9%)", "almost idle"],
    ["Slice LUTs", "30,276 / 53,200   (56.9%)", "near the limit"],
    ["CARRY4 primitives", "4,874", "MACs built from fabric"],
], 0.9, 3.2, 11.5, 1.7, col_w=[5.4, 3.6, 2.5], fs=12.5)
bullets(s, [
    "A 16×16 INT8 multiply-accumulate array is precisely the workload "
    "DSP48E1 blocks exist for – yet synthesis was building the multipliers "
    "out of general LUT / CARRY4 logic.",
    "First fix attempt: put a (* use_dsp = \"yes\" *) attribute on the "
    "multiply-accumulate always block. Re-synthesis produced byte-identical "
    "LUT / DSP / CARRY4 counts – no error, and no effect.",
], 0.9, 5.15, 11.5, 1.9, size=13, spacing=1.12, gap=7)
notes(s, "Frame it as a diagnosis story. 5.9% DSP utilisation on a systolic "
         "array is a red flag you only see if you read the utilisation report, "
         "not just 'did the build pass'. The obvious pragma did literally "
         "nothing, and crucially it did nothing *silently*.")

# ============================================================================
# 14 - CONTRIBUTION 2/3
# ============================================================================
s = add_slide(); base(s, "Technical contribution – root cause & fix",
                       kicker="★  Attribute placement + a budget-sized mapping")
text(s, 0.9, 1.45, 11.6, 0.9, [
    [{"t": "Per Xilinx UG901, ", "s": 13.5, "c": INK},
     {"t": "use_dsp must attach to the register declaration that holds the "
           "multiply result", "s": 13.5, "b": True, "c": INK},
     {"t": " – an attribute on the always statement is not a recognised "
           "attachment point and is dropped during elaboration with no warning.",
      "s": 13.5, "c": INK}],
], spacing=1.1)
# before / after code  (syntax-highlighted Verilog)
def codebox(x, title, lines, tint):
    box(s, x, 2.42, 5.75, 2.45, fill=WHITE, line=tint, line_w=1.5,
        rounded=True)
    box(s, x, 2.42, 5.75, 0.42, fill=tint, rounded=True, radius=0.18)
    _set(box(s, x, 2.42, 5.75, 0.42, fill=None).text_frame, title, 11, WHITE,
         bold=True, align=PP_ALIGN.CENTER)
    tf = s.shapes.add_textbox(Inches(x + 0.2), Inches(2.98),
                              Inches(5.4), Inches(1.85)).text_frame
    code_highlight(tf, lines, size=9.5, spacing=1.18)
codebox(0.9, "BEFORE  –  no-op", [
    '(* use_dsp = "yes" *)',
    'always @(posedge clk) begin',
    '    psum_out <= psum_in + x_in*reg_w;',
    'end',
    '// attribute on the block: silently ignored',
], ORANGE)
codebox(6.85, "AFTER  –  UG901-correct", [
    '(* use_dsp = "yes" *) reg signed',
    '  [2*data_width+log2_array_m-1:0] psum_out_r;',
    'always @(posedge clk)',
    '    psum_out_r <= psum_in + x_in*reg_w;',
    '// output reg -> wire, driven by continuous assign',
], GREEN)
# syntax legend
leg = [("keyword", C_KW), ("(* pragma *)", C_ATTR), ("// comment", C_COM),
       ("signal / var", C_ID), ("literal", C_NUM)]
lx = 0.95
lt = s.shapes.add_textbox(Inches(lx), Inches(4.95), Inches(11.6),
                          Inches(0.34)).text_frame
lt.word_wrap = True
pp = lt.paragraphs[0]
for i, (name, col) in enumerate(leg):
    if i:
        r = pp.add_run(); r.text = "    "
        r.font.size = Pt(9); r.font.name = FONT
    r = pp.add_run(); r.text = "■ "
    r.font.size = Pt(9); r.font.name = FONT; r.font.color.rgb = col
    r = pp.add_run(); r.text = name
    r.font.size = Pt(9); r.font.name = MONO; r.font.color.rgb = MUTED
bullets(s, [
    "Fix is cycle-for-cycle behaviour-identical: output reg → wire, an "
    "internal register carries the attribute, port driven by a continuous "
    "assignment.",
    "All 256 PEs on DSP would exceed the 220-slice budget, so PE_array.v "
    "parameterises the split — NUM_DSP_ROWS = 12 of 16 → 192 PEs on DSP48E1, "
    "4 rows (64 PEs) on LUT/CARRY4.",
    "Deliberate, budget-sized partial mapping – not an all-or-nothing switch.",
], 0.9, 5.35, 11.6, 1.75, size=11.5, spacing=1.1, gap=5)
notes(s, "Two parts: (1) the attribute-attachment rule - wire vs reg, "
         "declaration vs block - which is easy to miss from the UG901 text; "
         "(2) you cannot just flip every PE to DSP because the chip only has "
         "220 slices, so the mapping is parameterised and sized to the budget. "
         "True dual-8-bit DSP packing was considered and rejected as too "
         "invasive to the array timing skew.")

# ============================================================================
# 15 - CONTRIBUTION 3/3 (results)
# ============================================================================
s = add_slide(); base(s, "Technical contribution – result at signoff",
                       kicker="★  One RTL-local change, measured before / after")
simple_table(s, [
    ["Metric (post-route, full SoC)", "Before", "After", "Δ"],
    ["Slice LUTs", "30,276 (56.9%)", "15,363 (28.9%)", "−49.3%"],
    ["CARRY4 primitives", "4,874", "1,862", "−61.8%"],
    ["DSP48E1", "13 / 220 (5.9%)", "205 / 220 (93.2%)", "+192"],
    ["WNS @ 100 MHz", "+0.361 ns", "+0.293 ns", "−19% marg."],
    ["Total on-chip power", "1.741 W", "1.687 W", "−3.1%"],
], 0.55, 1.5, 7.35, 2.7, col_w=[2.55, 1.7, 1.7, 1.4], fs=10.5,
   first_bold=True)
# headline stat callouts
sc_w = 2.33
for i, (v, lab, acc) in enumerate([
    ("−49.3%", "Slice LUTs", GREEN),
    ("+192", "DSP48E1 slices", BLUE),
    ("−3.1%", "on-chip power", GREEN),
]):
    stat_card(s, 0.55 + i * (sc_w + 0.13), 4.45, sc_w, 1.05, v, lab,
              accent=acc, value_size=21, label_size=9.5)
# Vivado device placement view
vd = picture(s, os.path.join(FIG, "fig_vivado_device.png"),
             8.15, 1.5, 4.65, 3.95)
annot_box(s, vd, (0.235, 0.02, 0.90, 0.965), width=2.0)      # DSP column band
annot_label(s, vd, 0.5, 0.0, 3.78,
            "205 / 220 DSP48E1  (93.2% DSP column saturation)", size=8.5,
            anchor="c")
caption(s, "Vivado Device view — post-implementation cell placement across "
           "the Zynq-7020 fabric; yellow = DSP / BRAM columns.",
        8.15, 5.5, 4.65)
box(s, 0.55, 5.75, 7.35, 1.15, fill=INK, rounded=True)
text(s, 0.8, 5.9, 6.9, 0.95, [
    [{"t": "Lesson  ", "s": 11.5, "b": True, "c": BLUE},
     {"t": "a synthesis pragma that raises no error can still do nothing — "
           "check utilisation before / after, not just that the build passed.",
      "s": 11, "c": WHITE}],
    [{"t": "WNS +0.361 → +0.293 ns: denser DSP column, timing still met — an "
           "anticipated trade-off, not a regression.", "s": 10, "c":
      RGBColor(0xC7, 0xD0, 0xDC), "space_before": 5}],
], spacing=1.1)
notes(s, "This is the headline: a single, behaviour-preserving RTL change "
         "cut LUTs in half and dropped power 3%. It stands entirely on its "
         "own - no other slide needed to understand it. The lesson generalises "
         "to any tool pragma.")

# ============================================================================
# 16 - RESULTS: BENCHMARK
# ============================================================================
s = add_slide(); base(s, "Results – hardware kernel vs. ARM Cortex-A9",
                       kicker="7 · Kernel benchmark on PYNQ-Z2")
picture(s, os.path.join(FIG, "latency_comparison.png"), 0.7, 1.45, 6.0, 3.3, frame=True)
picture(s, os.path.join(FIG, "speedup_factor.png"), 6.85, 1.45, 6.0, 3.3, frame=True)
mathbox(s, 0.7, 4.83, 12.1, 0.4, [
    ("bd", "speedup"), ("rm", " = "), ("it", "t"), ("_", "CPU"),
    ("rm", " / "), ("it", "t"), ("_", "HW"), ("rm", "          "),
    ("bd", "throughput"), ("rm", " = 2·"), ("it", "M"), ("it", "N"),
    ("it", "K"), ("rm", " / "), ("it", "t"), ("_", "kernel"),
], size=11.5, color=MUTED, align=PP_ALIGN.CENTER)
simple_table(s, [
    ["Shape (fused matmul+Softmax+GELU)", "HW", "CPU", "Speedup"],
    ["192 × 192  (projection-sized)", "5.84 ms", "408.9 ms", "70.02×"],
    ["192 × 320  (MLP-shaped)", "6.38 ms", "623.3 ms", "97.73×"],
], 0.7, 5.28, 7.55, 1.35, col_w=[3.75, 1.3, 1.3, 1.2], fs=11)
stat_card(s, 8.5, 5.28, 4.3, 0.78, "70.02× – 97.73×",
          "measured kernel speedup vs. ARM Cortex-A9", accent=BLUE,
          value_size=18, label_size=9)
stat_card(s, 8.5, 6.14, 4.3, 0.78, "2.25 GOPS/W",
          "energy efficiency @ 3.795 GOP/s peak (2.47 dyn.)", accent=GREEN,
          value_size=18, label_size=9)
notes(s, "Same fused operation on both sides. 70x and 98x measured, live, on "
         "the board. Efficiency combines the live throughput with Vivado's "
         "post-route activity-based power estimate - a signoff-grade estimate, "
         "stated as such, not a wall-plug measurement.")

# ============================================================================
# 17 - RESULTS: SILICON VERIFICATION
# ============================================================================
s = add_slide(); base(s, "Results – simulation ≡ silicon",
                       kicker="7 · Physical verification at the verified scale")
wz = picture(s, os.path.join(FIG, "simvision_waveform_zoom.png"),
             0.7, 1.5, 7.7, 3.7)
# --- annotations on the waveform ---
annot_box(s, wz, (0.205, 0.53, 0.755, 0.675))               # streaming bursts
annot_label(s, wz, 0.14, 0.20, 2.7, "Continuous 32-bit streaming output")
annot_arrow(s, wz, 0.40, 0.325, 0.40, 0.53)
annot_box(s, wz, (0.760, 0.63, 0.796, 0.725))              # single-cycle pulse
annot_label(s, wz, 0.545, 0.20, 2.75, "Single-cycle out_last pulse")
annot_arrow(s, wz, 0.778, 0.325, 0.778, 0.628)
caption(s, "SimVision zoom: end-of-inference handshake – out_valid / "
           "out_data[31:0], single-cycle out_last, counter locking at 18,083.",
        0.7, 5.3, 7.7)
text(s, 8.7, 1.7, 4.05, 0.9,
     [{"t": "Same shape, real board", "s": 14, "b": True, "c": INK},
      ], spacing=1.1)
text(s, 8.7, 2.15, 4.05, 0.9,
     [{"t": "200 × 96 × 160, on the physical PYNQ-Z2, read back over the "
            "PYNQ Python driver:", "s": 11, "c": MUTED}], spacing=1.14)
stat_card(s, 8.7, 3.15, 4.05, 1.4, "0 / 32,000",
          "output elements outside the tolerance bound", accent=GREEN,
          value_size=25, label_size=10)
text(s, 8.7, 4.8, 4.05, 1.7,
     [{"t": "Behavioural simulation and physical silicon agree at the "
            "design's originally verified scale — not a new, more forgiving "
            "test.", "s": 11, "c": MUTED}], spacing=1.16)
notes(s, "The decisive move during bring-up: when small 'smoke-test' shapes "
         "failed, we re-ran the *exact* shape simulation had already proven, "
         "and it was perfect. That separated 'the design is broken' from 'my "
         "quick test exercised an unverified corner' - which is what it was "
         "(a single-row address-counter edge case, documented as open).")

# ============================================================================
# 18 - RESULTS: HONEST WORKLOAD ANALYSIS
# ============================================================================
s = add_slide(); base(s, "Results – an honest workload analysis",
                       kicker="7 · Workload characterisation (a methodological result)")
picture(s, os.path.join(FIG, "fig_vit_mismatch_v2.png"), 0.65, 1.45, 7.7, 3.3)
sam = picture(s, os.path.join(FIG, "fig_vit_sample_samoyed.jpg"),
              0.65, 4.95, 2.7, 2.0)
annot_box(s, sam, (0.0, 0.0, 1.0, 1.0), width=2.0)
annot_label(s, sam, 0.5, -0.02, 2.75, "Samoyed · 87.26% confidence",
            size=8.5, anchor="c")
mathbox(s, 3.6, 5.0, 5.0, 2.0, [
    [("bd", "Empirical software-baseline check")],
    [("t", "From-scratch NumPy ViT-Tiny classifies this sample as "),
     ("it", "Samoyed"), ("t", " (87.26% confidence) — identical top-1 to "
     "the PyTorch reference,")],
    [("t", "max logit "), ("rm", "Δ"), ("t", " ≤ "), ("m", "1.0 × 10"),
     ("^", "−5"), ("t", ".")],
], size=11, color=MUTED, spacing=1.2, para_gap=4)
bullets(s, [
    "The fixed matmul→Softmax→GELU pipeline maps to no single ViT "
    "operation:",
    (1, "self-attention = matmul–Softmax–matmul, no GELU"),
    (1, "MLP block = matmul–GELU–matmul, no Softmax"),
    "Substituting it into either would silently apply an extra "
    "normalisation / activation and corrupt the result.",
    "Verified against the RTL, not assumed – so we report a kernel "
    "throughput benchmark, never an end-to-end accelerated-ViT claim.",
], 8.65, 1.65, 4.1, 5.2, size=11.5, spacing=1.12, gap=7)
notes(s, "This is the 'transparency' the guidelines ask for, turned into a "
         "contribution. Asked for an end-to-end ViT speed-up, we checked "
         "first whether the comparison would even be true - it would not - and "
         "reported that instead of a fabricated number. The check before the "
         "benchmark mattered more than the benchmark.")

# ============================================================================
# 19 - COMPARISON WITH PRIOR WORK
# ============================================================================
s = add_slide(); base(s, "Comparison with prior FPGA transformer accelerators",
                       kicker="7 · Same design family, different device class")
simple_table(s, [
    ["Design", "Target FPGA (total DSPs)", "Precision", "DSP util.", "Reported efficiency"],
    ["taoFPGA (this work)", "Zynq-7020  (220)", "INT8", "205/220 (93%)",
     "2.25 GOPS/W; 70–98× vs. on-chip ARM"],
    ["ME-ViT [3]", "Alveo U200  (5,867)", "n/s", "1,024 (17%)",
     "4.0× power-eff. vs. GPU"],
    ["FTRANS [4]", "VCU118  (6,840)", "16-bit fixed + BCM", "82–96%",
     "81× / 8.8× vs. CPU / GPU"],
], 0.7, 1.7, 12.0, 2.6, col_w=[2.4, 2.7, 2.4, 1.9, 2.6], fs=11.5, first_bold=True)
bullets(s, [
    "ME-ViT and FTRANS target datacenter-class FPGAs – >25× the DSP "
    "budget – and benchmark against GPUs/CPUs.",
    "taoFPGA targets a 220-DSP embedded SoC and benchmarks against its own "
    "on-chip ARM Cortex-A9.",
    "The table situates design choices within one architectural family "
    "(fixed-point + DSP-array-dominated, device near DSP saturation) – it "
    "is not a device-independent performance ranking.",
], 0.7, 4.6, 12.0, 2.3, size=13, spacing=1.12, gap=7)
notes(s, "Same discipline as the ViT slide: a raw GOPS/W ranking across three "
         "very different devices would misrepresent the comparison, so we "
         "don't make one. All three designs run their device's DSP column "
         "near saturation - that's the shared story.")

# ============================================================================
# 20 - PLANNING VS EXECUTION  (mandatory)
# ============================================================================
s = add_slide(); base(s, "Planning vs. execution",
                       kicker="8 · Pre-project plan  →  what actually happened")
rows = [
    ["Phase (pre-project report)", "Planned", "Actual execution"],
    ["1  Literature review & theory", "Dec 25 · Eliran",
     "Done. Transformer arch, HW quantization, FPGA accel surveyed; 8 refs cited."],
    ["2  Architecture & methodology", "Jan 26 · Shay",
     "Done. Weight-stationary 16×16 INT8 array + fused fixed-point "
     "Softmax/GELU. RTL flow chosen over HLS."],
    ["3  Critical component / POC", "Feb 26 · Eliran",
     "Done. MM_ultra core built & verified in Cadence Xcelium vs. a "
     "SystemVerilog golden model."],
    ["4  Full impl. & integration", "Apr 26 · Shay",
     "Done, expanded: full pipeline AXI-wrapped from scratch; 60 async-reset "
     "blocks fixed / 12 files; 6 stale script params corrected."],
    ["5  Performance test & calibration", "May 26 · Eliran",
     "Done. PYNQ-Z2 bring-up; full-scale run 0/32,000 errors; 'calibration' "
     "became the DSP-inference fix (LUT −49%, power −3%)."],
    ["6  Results analysis & report", "Jun 26 · both",
     "Done. Kernel benchmark vs. on-chip ARM (70–98×). GPU / "
     "end-to-end-ViT comparison dropped after workload-mismatch analysis."],
    ["Schedule", "Final pres. Jun 26",
     "Final report Sep 22 2026 (~3-month slip): early environment/"
     "infrastructure debugging + added integration scope."],
]
gt = simple_table(s, rows, 0.5, 1.45, 12.35, 5.4,
                  col_w=[2.85, 1.8, 7.7], fs=10, first_bold=True)
notes(s, "Mandatory slide. Honest read: all six work phases completed, two "
         "with more scope than planned (integration, calibration-turned-"
         "optimisation). Two deliberate scope changes - RTL instead of HLS, "
         "and kernel benchmark instead of GPU/end-to-end-ViT - each for a "
         "documented engineering reason. ~3-month calendar slip, mostly from "
         "environment/infrastructure problems early on.")

# ============================================================================
# 21 - CHALLENGES
# ============================================================================
s = add_slide(); base(s, "Challenges & engineering discussion",
                       kicker="8 · What was hard, what is still open")
box(s, 0.7, 1.6, 6.05, 4.9, fill=WHITE, line=ORANGE, line_w=1.4, rounded=True)
_set(box(s, 0.7, 1.6, 6.05, 0.52, fill=ORANGE, rounded=True, radius=0.14).text_frame,
     "STANDING BOTTLENECKS", 12, WHITE, bold=True, align=PP_ALIGN.CENTER)
bullets(s, [
    "64 KB single-transfer DMA ceiling (16-bit length reg). Blocks the "
    "768-wide ViT-Tiny MLP and all batching.",
    (1, "chunking is unsafe: tlast resets the buffer write-address counter "
        "every transfer → chunk 2 overwrites chunk 1"),
    "Serial Softmax: parallel 2-D array (A_size results/cycle) feeding a "
    "1-scalar/cycle, 3N-cycle stage – a structural throughput limit.",
], 1.0, 2.35, 5.5, 4.0, size=12, spacing=1.16, gap=10)
box(s, 6.95, 1.6, 5.7, 4.9, fill=WHITE, line=BLUE, line_w=1.4, rounded=True)
_set(box(s, 6.95, 1.6, 5.7, 0.52, fill=BLUE, rounded=True, radius=0.14).text_frame,
     "REPRESENTATIVE DEBUGGING WINS", 12, WHITE, bold=True, align=PP_ALIGN.CENTER)
bullets(s, [
    "Async-reset DRC: one root cause chased through 12 files / 3 re-synth "
    "rounds → project-wide grep audit.",
    "Elaboration-time memory blow-up from a generate-unrolled test array "
    "→ on-demand packing functions (5.9 GB → 51 MB).",
    "A comprehensively stale PYNQ driver, rebuilt from the real register map.",
    "Tiny-shape HW mismatch traced to a single-row address-counter edge "
    "case – not a design flaw (re-ran the verified shape to confirm).",
], 7.2, 2.35, 5.2, 4.0, size=12, spacing=1.14, gap=9)
notes(s, "Left column = what we would fix next and why it is non-trivial. "
         "Right column = four Appendix-A stories that show method: audit the "
         "pattern not the symptom; scale test data with an on-demand function; "
         "re-derive an interface from its source of truth; and re-run a known-"
         "good condition before blaming the design.")

# ============================================================================
# 22 - ROADMAP / IMPROVEMENTS
# ============================================================================
s = add_slide(); base(s, "Improvements & architectural roadmap",
                       kicker="8 · Next iteration")
steps = [
    ("Scatter-Gather DMA", "Replace direct-register DMA (or re-synthesise "
     "with a wider transfer-length register). Per-descriptor frame-boundary "
     "control removes the 64 KB ceiling → full-width MLP + batching + a "
     "real end-to-end path."),
    ("Decouple the three stages", "Matmul / Softmax / GELU as independent "
     "streaming nodes with true backpressure; add the missing GELU skid "
     "buffer. Addresses the serial-Softmax bottleneck directly."),
    ("Parallel / pipelined Softmax", "Break the 3N-cycle serial structure "
     "– the single largest throughput lever, independent of clock or DSP."),
    ("Correct PYNQ-Z2 board files", "Install the vendor board files and "
     "re-apply the DDR3 preset (currently PYNQ-Z1-derived, flagged inline)."),
]
y = 1.7
for i, (t, d) in enumerate(steps):
    box(s, 0.9, y, 0.6, 0.6, fill=BLUE, rounded=True, radius=0.2)
    _set(box(s, 0.9, y, 0.6, 0.6, fill=None).text_frame, str(i + 1), 15, WHITE,
         bold=True, align=PP_ALIGN.CENTER)
    text(s, 1.75, y - 0.05, 10.7, 1.2, [
        [{"t": t + "  –  ", "s": 14, "b": True, "c": INK},
         {"t": d, "s": 12.5, "c": MUTED}],
    ], spacing=1.08)
    y += 1.28
notes(s, "Everything here follows directly from the bottleneck slide. Item 1 "
         "is the prerequisite fix - it is what unlocks the out-of-scope column "
         "from slide 7.")

# ============================================================================
# 23 - LOGISTICS / BUDGET
# ============================================================================
s = add_slide(); base(s, "Logistics – budget, tooling, references",
                       kicker="8 · Cost & resources")
box(s, 0.8, 1.6, 6.0, 3.3, fill=PANEL, line=LINE, rounded=True)
text(s, 1.05, 1.8, 5.5, 3.0, [
    [{"t": "Budget", "s": 14, "b": True, "c": INK}],
    [{"t": "▸  PYNQ-Z2 board (Zynq-7020)   ~ $199", "s": 12.5, "c": INK, "space_before": 8}],
    [{"t": "▸  Vivado / Vitis – university / WebPACK license   —", "s": 12.5, "c": INK, "space_before": 5}],
    [{"t": "▸  Cadence Xcelium – university license   —", "s": 12.5, "c": INK, "space_before": 5}],
    [{"t": "▸  Python / NumPy / PyTorch (timm)   free", "s": 12.5, "c": INK, "space_before": 5}],
    [{"t": "Total hardware outlay ≈ $199. No cloud / fabrication cost.",
      "s": 11.5, "i": True, "c": MUTED, "space_before": 10}],
], spacing=1.05)
box(s, 7.0, 1.6, 5.55, 3.3, fill=PANEL, line=LINE, rounded=True)
text(s, 7.25, 1.8, 5.05, 3.0, [
    [{"t": "Effort split", "s": 14, "b": True, "c": INK}],
    [{"t": "▸  Eliran – literature, matmul core & POC, verification, "
           "silicon bring-up & benchmarking", "s": 12, "c": INK, "space_before": 8}],
    [{"t": "▸  Shay – architecture selection, full-system "
           "integration, AXI wrapper, physical signoff", "s": 12, "c": INK, "space_before": 6}],
    [{"t": "▸  Both – results analysis, report & presentations",
      "s": 12, "c": INK, "space_before": 6}],
], spacing=1.05)
box(s, 0.8, 5.1, 11.75, 1.7, fill=WHITE, line=LINE, rounded=True)
text(s, 1.05, 5.28, 11.2, 1.4, [
    [{"t": "Key references   ", "s": 12.5, "b": True, "c": INK},
     {"t": "[1] Vaswani et al., Attention Is All You Need, NeurIPS 2017   ·   "
           "[3] Marino et al., ME-ViT, HiPC 2023   ·   [4] Li et al., "
           "FTRANS, ISLPED 2020   ·   [6] AMD/Xilinx UG901 (Synthesis)   "
           "·   [7] Dosovitskiy et al., ViT, ICLR 2021", "s": 10.5, "c": MUTED}],
], spacing=1.1)
notes(s, "The project is deliberately cheap: one commodity board, academic "
         "tool licenses, open-source Python. The reproducibility cost for "
         "anyone else is ~$199 plus the public repo.")

# ============================================================================
# 24 - CONCLUSION
# ============================================================================
s = add_slide(); base(s, "Conclusions – one recommendation per objective",
                       kicker="9 · Aligned with the five specific objectives")
data = [
    ["", "Delivered", "Recommendation"],
    ["O1  Core + engines", "16×16 INT8 array + fused fixed-point "
     "Softmax/GELU, formalised as Eq. 1–2.",
     "Decouple the 3 stages into streaming nodes with backpressure."],
    ["O2  Verification", "0 / 32,000 error at the verified scale, sim ≡ "
     "silicon.", "Extend the golden-model sweep to small / edge shapes "
     "(F_length = 1, 2-row)."],
    ["O3  SoC bring-up", "Runs on real PYNQ-Z2 via the PYNQ driver.",
     "Install vendor PYNQ-Z2 board files; re-apply the DDR3 preset."],
    ["O4  Physical signoff", "Timing met @ 100 MHz; LUT −49.3%, power "
     "−3.1% from one RTL-local fix.",
     "Adopt the register-level use_dsp pattern as the project standard."],
    ["O5  Evaluation", "70–98× kernel speedup, 2.25 GOPS/W; honest "
     "ViT workload analysis.",
     "Scatter-Gather DMA → full-width MLP + batched, end-to-end evaluation."],
]
simple_table(s, data, 0.55, 1.5, 12.3, 4.2, col_w=[2.3, 4.6, 5.4], fs=10.5,
             first_bold=True)
box(s, 0.55, 5.95, 12.3, 1.0, fill=INK, rounded=True)
text(s, 0.9, 6.1, 11.6, 0.8, [
    [{"t": "Governing discipline throughout:  ", "s": 12.5, "b": True, "c": BLUE},
     {"t": "verify every layer against its own ground truth, and report every "
           "limitation as precisely as the result being claimed.", "s": 12.5,
      "c": WHITE}],
], spacing=1.05)
notes(s, "Close on the through-line: the numbers matter, but the method - "
         "never inherit correctness from an adjacent layer, and never claim "
         "more than the hardware can actually do - is the transferable "
         "contribution. Thank the supervisor and mentor.")

# ============================================================================
# 25 - Q&A
# ============================================================================
s = add_slide()
_slide_no[0] += 1          # keep appendix footer numbering in sync
box(s, -0.06, -0.06, SW + 0.12, SH + 0.12, fill=INK)
box(s, 0, 3.05, SW, 0.06, fill=BLUE)
text(s, 0, 2.05, SW, 1.0, [{"t": "Thank you", "s": 46, "b": True, "c": WHITE,
                            "align": PP_ALIGN.CENTER}])
text(s, 0, 3.35, SW, 0.7, [{"t": "Questions & discussion", "s": 20,
                            "c": RGBColor(0xC7, 0xD0, 0xDC),
                            "align": PP_ALIGN.CENTER}])
text(s, 0, 4.5, SW, 0.6, [[
    {"t": "Eliran Turgeman", "s": 13, "b": True, "c": WHITE},
    {"t": "   ·   ", "s": 13, "c": MUTED},
    {"t": "Shay Rask", "s": 13, "b": True, "c": WHITE},
    {"t": "     ·     taoFPGA  ·  Project 309", "s": 13, "c": MUTED},
]], align=PP_ALIGN.CENTER)
chip = box(s, SW/2 - 1.0, 5.35, 2.0, 0.55, fill=None, line=BLUE, line_w=1.5,
           rounded=True, radius=0.5)
_set(chip.text_frame, "PROJECT 309", 12, WHITE, bold=True, align=PP_ALIGN.CENTER)
chip.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
notes(s, "Anticipated questions: why INT8 power-of-two scales; why 12/16 DSP "
         "rows exactly; what the 2-row DMA hang root cause might be; why not "
         "HLS; how the golden model handles Softmax rounding; what "
         "Scatter-Gather DMA changes in the RTL.")

# ============================================================================
# 26 - APPENDIX A: KEY DEBUGGING WINS
# ============================================================================
s = add_slide(); base(s, "Appendix A — key engineering debugging wins",
                       kicker="Backup · representative issues from Report Appendix A")
simple_table(s, [
    ["Problem", "Root cause", "Fix & result"],
    ["Xcelium session crash at full scale (200×96×160), during "
     "native-code generation  [A.1]",
     "Testbench x/y/z arrays built with a generate loop — one elaborated "
     "hardware object per scalar; memory grew worse than quadratically "
     "(59 MB → >5,900 MB at 128³).",
     "Replaced with automatic functions pack_x_word / pack_y_word / "
     "unpack_z_word (compute each word on demand).  ~51 MB / ~4 s, "
     "identical 2,894-cycle latency."],
    ["40+ post-synthesis DRC warnings: block-RAM control logic driven by "
     "asynchronously-reset registers  [A.5]",
     "Async reset on BRAM control can corrupt memory outside STA visibility. "
     "The pattern recurred one hierarchy level deeper each re-synth — 3 named "
     "files became 12.",
     "Project-wide grep for the anti-pattern, then converted 60 always "
     "blocks across 12 files to synchronous reset.  Bit-for-bit identical "
     "simulation after every round."],
    ["Softmax_control scale port (4-bit, 7–12) vs. gelu.v scale port "
     "(3-bit, max 7) — could only agree at scale = 7  [A.3]",
     "A known, code-commented limitation. gelu.v had no shift branch for "
     "scale > 7, so a plain port-width bump would silently mis-shift values "
     "8–15 as if 7 — a correctness bug.",
     "Widened the scale port through all three modules to 4 bits, added the "
     "missing shift-direction branch in gelu.v, extended the GELU testbench "
     "range 0–6 → 0–11."],
], 0.5, 1.5, 12.35, 5.2, col_w=[3.2, 4.55, 4.6], fs=9.5, first_bold=True)
notes(s, "Three Appendix-A stories that show method: (A.1) a generate loop is "
         "an elaboration-time construct — don't use it to hold data; (A.5) a "
         "DRC names the nearest offender, not the pattern — audit project-wide; "
         "(A.3) a comment saying 'known limitation' is not 'handled' — read the "
         "implementation, not just the port width.")

# ============================================================================
# 27 - APPENDIX: 3-PASS FIXED-POINT SOFTMAX MATH
# ============================================================================
s = add_slide(); base(s, "Appendix — 3-pass fixed-point Softmax math",
                       kicker="Backup · exact base-2, division-free reformulation")
mathbox(s, 0.9, 1.55, 11.5, 0.7, [
    [("rm", "Textbook:   "), ("rm", "softmax"), ("t", "("), ("it", "x"),
     ("t", ")"), ("_", "i"), ("rm", " = "),
     ("rm", "exp"), ("t", "("), ("it", "x"), ("_", "i"), ("t", " − "),
     ("it", "m"), ("t", ") / "), ("it", "S"), ("rm", "      →      "),
     ("bd", "hardware uses the base-2, log-domain form the exp / Ln units "
      "actually compute:")],
], size=13.5, color=INK)
rows_y = 2.4
for i, (tag, seg, cyc) in enumerate([
    ("Pass 1 — MAX",
     [("it", "m"), ("rm", " = "), ("rm", "max"), ("_", "i"), ("rm", " "),
      ("it", "x"), ("_", "i")],
     "N cycles — running comparator finds the row maximum."),
    ("Pass 2 — ACCUMULATE",
     [("it", "S"), ("rm", " = "), ("rm", "Σ"), ("_", "i"), ("rm", " 2"),
      ("^", "(xᵢ − m)·log₂ e")],
     "N cycles — base-2 exp: split x·log₂e into integer + fractional part, "
     "linear-interpolate the fractional 2ˣ term."),
    ("Pass 3 — NORMALIZE",
     [("it", "y"), ("_", "i"), ("rm", " = 2"),
      ("^", "((xᵢ − m) − ln S)·log₂ e")],
     "N cycles — second exp unit + Ln_module piecewise log; replaces an "
     "explicit hardware divider."),
]):
    box(s, 0.9, rows_y, 3.15, 1.12, fill=PANEL, line=LINE, rounded=True)
    _set(box(s, 1.05, rows_y + 0.1, 2.8, 0.36, fill=None).text_frame, tag, 12,
         BLUE, bold=True)
    mathbox(s, 1.05, rows_y + 0.5, 2.9, 0.55, [seg], size=13, color=INK)
    text(s, 4.25, rows_y + 0.14, 8.2, 1.0,
         [{"t": cyc, "s": 11.5, "c": MUTED}], spacing=1.2)
    rows_y += 1.26
box(s, 0.9, 6.28, 11.55, 0.74, fill=INK, rounded=True)
text(s, 1.15, 6.4, 11.1, 0.5, [
    [{"t": "Total 3N cycles / row, sequential.  ", "s": 11.5, "b": True,
      "c": BLUE},
     {"t": "The NumPy golden model uses this identical log₂e-scaled form — "
           "'golden' means bit-faithful, not merely close.", "s": 11.5,
      "c": WHITE}],
])
notes(s, "This is the exact statement from Report §II.B. The point of "
         "reformulating softmax into base-2 / log-domain is that it removes an "
         "explicit hardware divider (pass 3) and it matches the golden model "
         "exactly, so verification is bit-faithful rather than approximate.")

# ============================================================================
# 28 - APPENDIX: TOLERANCE BOUNDARY ANALYSIS
# ============================================================================
s = add_slide(); base(s, "Appendix — tolerance-boundary analysis",
                       kicker="Backup · why 6 LSB, and across which boundaries")
mbullets(s, [
    "Verification is tolerance-bounded, not exact-match — INT8 requantization "
    "and the piecewise exp / log approximations each add sub-LSB error that "
    "compounds along the pipeline.",
    [("bd", "Two INT8 quantization boundaries the error crosses:")],
    (1, [("t", "① matmul accumulator → Softmax input:  round-half-up + "
          "saturate to [−128, 127]  ("), ("it", "right_shifter.v"),
         ("t", ", Eq. 1)")]),
    (1, "② Softmax output → GELU input:  a shared fixed-point scale "
        "(softmax_scale_out = gelu_scale) so both stages read the boundary "
        "identically"),
    "Unit tests use a tighter, scale-dependent LSB threshold per module; the "
    "full-pipeline integration test uses a 6-LSB bound at the shared "
    "Softmax-output / GELU scale.",
    "6 LSB absorbs benign quantization compounding while still catching real "
    "logic errors — those produce large or structured deviations (e.g. the "
    "exact-zero outputs of Appendix A.10), not a uniform ±few-LSB spread.",
], 0.9, 1.55, 8.1, 5.3, size=12.5, spacing=1.2, gap=10)
stat_card(s, 9.3, 1.9, 3.5, 1.5, "6 LSB",
          "integration tolerance at the shared Softmax / GELU scale",
          accent=BLUE, value_size=30, label_size=10)
stat_card(s, 9.3, 3.7, 3.5, 1.5, "0 / 32,000",
          "outside tolerance at full scale (200×96×160), 18,083-cycle latency",
          accent=GREEN, value_size=23, label_size=9.5)
text(s, 9.3, 5.5, 3.5, 1.3,
     [{"t": "Same bound is met on real PYNQ-Z2 silicon (Slide 17).",
       "s": 10.5, "i": True, "c": MUTED}], spacing=1.15)
notes(s, "From Report §III.B and §II.C. The 6-LSB figure is specific to the "
         "integration test at the shared Softmax/GELU scale; unit tests are "
         "tighter. The rationale: real bugs don't look like uniform small "
         "noise, so a modest tolerance separates 'quantization compounding' "
         "from 'logic error' cleanly.")

out = os.path.join(HERE, "taoFPGA_Final_Presentation.pptx")
prs.save(out)
print("saved:", out, "slides:", len(prs.slides._sldIdLst))
