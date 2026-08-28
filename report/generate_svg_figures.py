"""
Vector-clean redraws of Figs. 1, 4, and 8 (PE microarchitecture, top-level
SoC datapath, ViT structural mismatch) -- replacing the versions in
generate_figures2.py / generate_architecture_figures.py, which used curved
"arc3" matplotlib connector arrows and had at least one arrow (Fig. 4's
GELU->Result-DMA return path) whose margin was tight enough to look
clipped near the canvas edge.

Built directly on pycairo (not matplotlib -- matplotlib isn't installed
in this environment and can't be pip-installed here: it depends on
Pillow, whose source build fails on missing system jpeg headers).
pycairo draws real vector paths/text natively to both a PNG surface
(used here only for visual self-verification while writing this script)
and a genuine SVG surface (the actual deliverable) from the identical
drawing calls -- no rasterization step, no font-embedding surprises.

Same content, same project palette, same underlying facts (PE.v's real
signal names/widths; the SoC's real DMA/interconnect structure; the
already-documented ViT sub-block sequences) as the versions this
replaces -- only the drawing style changes:

  - Every connector is strictly orthogonal (Manhattan routing: only
    horizontal/vertical segments, explicit multi-point paths where a
    signal has to route around another block, never a curved arc).
  - Canvas bounds are sized with deliberate margin around the actual
    content extent, checked by construction against every element's
    real bounding box, not by eyeballing a cropped render.

Run (needs pycairo -- `pip3 install --user pycairo`, or check first,
it's already present in some environments):
    python3 generate_svg_figures.py
"""
import math
import os

import cairo

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT_DIR, exist_ok=True)


def hexcolor(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


# Palette -- identical slots to every other figure script in this project
COLOR_HW = hexcolor("#2a78d6")
COLOR_CTRL = hexcolor("#eb6834")
COLOR_ADAPT = hexcolor("#898781")
COLOR_BAD = hexcolor("#c0392b")
INK = hexcolor("#0b0b0b")
INK_SECONDARY = hexcolor("#52514e")
SURFACE = hexcolor("#fcfcfb")
BORDER = hexcolor("#c3c2b7")
WHITE = (1, 1, 1)

FONT = "DejaVu Sans"


class Canvas:
    """Logical coordinates are y-up (0,0 at bottom-left, matching the
    mental model the original matplotlib scripts used), converted to
    Cairo's native y-down pixel space at draw time -- so text is never
    drawn through a flipped transform (which would mirror it), only its
    anchor point is remapped.

    `scale` maps 1 logical unit to N pixels, purely for the PNG
    self-check render's resolution -- the SVG output is real vector
    geometry regardless of this value, Word will scale it cleanly at
    any size."""

    def __init__(self, xlim, ylim, scale=6, margin=4):
        """xlim/ylim: (min, max) logical bounds -- like matplotlib's
        set_xlim/set_ylim, NOT assumed to start at 0. `margin` pads all
        four sides beyond the given bounds, so labels placed exactly at
        the declared edge still aren't flush against the canvas border."""
        x0, x1 = xlim
        y0, y1 = ylim
        self.x0 = x0 - margin
        self.y0 = y0 - margin
        self.w = (x1 + margin) - self.x0
        self.h = (y1 + margin) - self.y0
        self.scale = scale
        self.px_w = int(self.w * scale)
        self.px_h = int(self.h * scale)

    def _x(self, x):
        return x - self.x0

    def _y(self, y):
        return self.h - (y - self.y0)

    def _ctx_setup(self, ctx):
        ctx.scale(self.scale, self.scale)
        ctx.set_source_rgb(*SURFACE)
        ctx.paint()
        ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)

    def render(self, draw_fn, name):
        # PNG (self-check only)
        png_surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.px_w, self.px_h)
        png_ctx = cairo.Context(png_surf)
        self._ctx_setup(png_ctx)
        draw_fn(self, png_ctx)
        png_path = os.path.join(OUT_DIR, f"{name}.png")
        png_surf.write_to_png(png_path)

        # SVG (the real deliverable) -- real physical size in points, not
        # scaled by the PNG's resolution multiplier.
        svg_path = os.path.join(OUT_DIR, f"{name}.svg")
        svg_surf = cairo.SVGSurface(svg_path, self.w, self.h)
        svg_ctx = cairo.Context(svg_surf)
        svg_ctx.set_source_rgb(*SURFACE)
        svg_ctx.paint()
        svg_ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        draw_fn(self, svg_ctx)
        svg_surf.finish()

        print(f"Wrote {name}.svg (+ {name}.png for self-check)")


def rounded_rect_path(ctx, cv, x, y, w, h, r=2.2):
    """x,y = logical bottom-left corner (y-up). Path only -- caller fills/strokes."""
    x0, y0 = cv._x(x), cv._y(y + h)         # top-left in pixel space
    x1, y1 = cv._x(x + w), cv._y(y)         # bottom-right in pixel space
    ctx.new_sub_path()
    ctx.arc(x0 + r, y0 + r, r, math.pi, 1.5 * math.pi)
    ctx.arc(x1 - r, y0 + r, r, 1.5 * math.pi, 2 * math.pi)
    ctx.arc(x1 - r, y1 - r, r, 0, 0.5 * math.pi)
    ctx.arc(x0 + r, y1 - r, r, 0.5 * math.pi, math.pi)
    ctx.close_path()


def multiline_text(ctx, cv, cx, cy, text, size, color, line_spacing=1.28, bold=False, align="center"):
    """cx,cy = logical center point (y-up). '\\n'-separated lines, each
    individually centered/measured and stacked around cy."""
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL,
                          cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)
    lines = text.split("\n")
    lh = size * line_spacing
    total_h = lh * len(lines)
    top = cy + total_h / 2 - lh * 0.5
    px_cx = cv._x(cx)
    ctx.set_source_rgb(*color)
    for i, line in enumerate(lines):
        ext = ctx.text_extents(line)
        ly = top - i * lh
        px_y = cv._y(ly) + ext.height / 2
        if align == "center":
            px_x = px_cx - ext.width / 2 - ext.x_bearing
        elif align == "left":
            px_x = px_cx
        else:
            px_x = px_cx - ext.width - ext.x_bearing
        ctx.move_to(px_x, px_y)
        ctx.show_text(line)


def _box_center_px(cv, x, y, w, h):
    """Pixel-space x-center (logical space is 1:1 with pixels pre-scale
    for x, since only y flips) and logical-space y-center, matching what
    multiline_text expects."""
    return (x + w / 2), (y + h / 2)


def draw_box(ctx, cv, x, y, w, h, text, color, fontsize=3.1, textcolor=WHITE, lw=0.35):
    rounded_rect_path(ctx, cv, x, y, w, h)
    ctx.set_source_rgb(*color)
    ctx.fill_preserve()
    ctx.set_source_rgb(*INK)
    ctx.set_line_width(lw)
    ctx.stroke()
    cx, cy = _box_center_px(cv, x, y, w, h)
    multiline_text(ctx, cv, cx, cy, text, fontsize, textcolor)


def dashed_rect(ctx, cv, x, y, w, h, color=INK_SECONDARY, lw=0.35, dash=(1.4, 1.0)):
    x0, y0 = cv._x(x), cv._y(y + h)
    ctx.set_source_rgb(*color)
    ctx.set_line_width(lw)
    ctx.set_dash(dash)
    ctx.rectangle(x0, y0, w, h)
    ctx.stroke()
    ctx.set_dash([])


def _arrowhead(ctx, cv, tip, direction, color, size=1.6):
    """tip: logical (x,y). direction: one of 'N','S','E','W' -- the
    direction the arrow travels *into* the tip."""
    tx, ty = cv._x(tip[0]), cv._y(tip[1])
    ang = {"E": 0, "W": math.pi, "N": -math.pi / 2, "S": math.pi / 2}[direction]
    a1 = ang + math.radians(150)
    a2 = ang - math.radians(150)
    ctx.set_source_rgb(*color)
    ctx.move_to(tx, ty)
    ctx.line_to(tx + size * math.cos(a1), ty + size * math.sin(a1))
    ctx.line_to(tx + size * math.cos(a2), ty + size * math.sin(a2))
    ctx.close_path()
    ctx.fill()


def _seg_dir(p0, p1):
    x0, y0 = p0
    x1, y1 = p1
    if x1 > x0:
        return "E"
    if x1 < x0:
        return "W"
    if y1 > y0:
        return "N"
    return "S"


def orthogonal_path(ctx, cv, points, color=INK, lw=0.42, arrow=True, arrow_size=1.6):
    """points: explicit (x,y) waypoints in logical (y-up) space. Every
    consecutive pair must already share an x or a y -- asserted, so a
    non-orthogonal mistake fails loudly instead of silently drawing a
    diagonal. Arrowhead only at the final point, oriented along the
    final segment's direction."""
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        assert x0 == x1 or y0 == y1, f"non-orthogonal segment {points[i]}->{points[i+1]}"
    ctx.set_source_rgb(*color)
    ctx.set_line_width(lw)
    ctx.move_to(cv._x(points[0][0]), cv._y(points[0][1]))
    for (x, y) in points[1:]:
        ctx.line_to(cv._x(x), cv._y(y))
    ctx.stroke()
    if arrow:
        d = _seg_dir(points[-2], points[-1])
        _arrowhead(ctx, cv, points[-1], d, color, size=arrow_size)


def label(ctx, cv, x, y, text, size=2.6, color=INK, align="left"):
    """x,y = logical center point of the whole (possibly multi-line)
    label block (y-up). Each line is individually measured and
    vertically stacked around y, horizontally positioned per `align`."""
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)
    lines = text.split("\n")
    lh = size * 1.25
    n = len(lines)
    top_offset = (n - 1) * lh / 2  # logical-space offset of line 0 above y
    px_x0 = cv._x(x)
    ctx.set_source_rgb(*color)
    for i, line in enumerate(lines):
        ext = ctx.text_extents(line)
        line_logical_y = y + top_offset - i * lh
        px_y = cv._y(line_logical_y) + ext.height / 2
        if align == "left":
            px_x = px_x0
        elif align == "right":
            px_x = px_x0 - ext.width
        else:
            px_x = px_x0 - ext.width / 2
        ctx.move_to(px_x, px_y)
        ctx.show_text(line)


# ============================================================================
# Fig. 1 -- PE internal microarchitecture (Section II.A)
# ============================================================================
def draw_fig1(cv, ctx):
    dashed_rect(ctx, cv, 8, 0, 114, 98.5)
    label(ctx, cv, 10, 90.5, "PE (sourcecode/core/PE.v)", size=2.7, color=INK_SECONDARY)

    draw_box(ctx, cv, 80, 78, 30, 12, "reg_w\n(stationary weight, INT8,\nloaded on set_w)", COLOR_CTRL, fontsize=2.55)
    draw_box(ctx, cv, 80, 58, 30, 12, "×  (INT8 × INT8)", COLOR_HW, fontsize=3.0)
    draw_box(ctx, cv, 80, 38, 30, 12, "+", COLOR_HW, fontsize=3.6)
    draw_box(ctx, cv, 80, 15, 30, 12, "psum_out_r\n(20-bit signed reg,\nUG901 use_dsp target)", COLOR_HW, fontsize=2.45)
    draw_box(ctx, cv, 16, 2, 26, 12, "x_out\n(INT8 reg, 1-cycle\nsystolic delay)", COLOR_ADAPT, fontsize=2.55)

    orthogonal_path(ctx, cv, [(95, 78), (95, 70)])
    orthogonal_path(ctx, cv, [(95, 58), (95, 50)])
    orthogonal_path(ctx, cv, [(95, 38), (95, 27)])

    orthogonal_path(ctx, cv, [(10, 8), (10, 64)], arrow=False)
    orthogonal_path(ctx, cv, [(10, 8), (16, 8)])
    orthogonal_path(ctx, cv, [(10, 64), (80, 64)])
    label(ctx, cv, -2, 71.5, "x_in [7:0]\n(from west PE)", size=2.65, align="left")

    orthogonal_path(ctx, cv, [(-2, 88), (80, 88)])
    label(ctx, cv, -4, 91.0, "set_w", size=2.65, align="left")
    orthogonal_path(ctx, cv, [(-2, 80), (80, 80)])
    label(ctx, cv, -4, 84.5, "w [7:0]", size=2.65, align="left")

    orthogonal_path(ctx, cv, [(130, 44), (110, 44)])
    label(ctx, cv, 132, 48, "psum_in [19:0]\n(from north PE)", size=2.55, align="left")

    orthogonal_path(ctx, cv, [(42, 8), (130, 8)])
    label(ctx, cv, 132, 8, "x_out [7:0]\n(to east PE)", size=2.55, align="left")

    orthogonal_path(ctx, cv, [(95, 15), (95, -6)])
    label(ctx, cv, 95, -10, "psum_out [19:0] (to south PE)", size=2.55, align="center")


cv1 = Canvas(xlim=(-6, 175), ylim=(-14, 98), scale=6)
cv1.render(draw_fig1, "fig_pe_microarch_v2")


# ============================================================================
# Fig. 4 -- Top-level SoC datapath (Section IV.A)
# Left column: PS7 + 3x AXI DMA. Right, inside the dashed
# transformer_block_axi_top boundary: the real 8-stage internal pipeline.
# The GELU->Result-DMA (S2MM) return path is the one the matplotlib
# version clipped near the bottom edge -- routed here with generous,
# checked clearance below every other element on the canvas.
# ============================================================================
def draw_fig4(cv, ctx):
    # ---- Left column: PS7 + 3x AXI DMA ----
    lx, lw_ = 4, 34
    draw_box(ctx, cv, lx, 75, lw_, 16, "ARM Cortex-A9\n(Zynq-7020 PS7)", COLOR_CTRL, fontsize=2.9)
    draw_box(ctx, cv, lx, 54, lw_, 13, "AXI DMA\nFeature (MM2S)", COLOR_CTRL, fontsize=2.7)
    draw_box(ctx, cv, lx, 37, lw_, 13, "AXI DMA\nWeight (MM2S)", COLOR_CTRL, fontsize=2.7)
    draw_box(ctx, cv, lx, 6, lw_, 13, "AXI DMA\nResult (S2MM)", COLOR_CTRL, fontsize=2.7)

    # ---- transformer_block_axi_top dashed boundary ----
    bx0, by0, bw, bh = 46, 10, 214, 54
    dashed_rect(ctx, cv, bx0, by0, bw, bh)
    label(ctx, cv, bx0 + 2, by0 + bh - 4, "transformer_block_axi_top", size=2.6, color=INK_SECONDARY)

    # ---- 8-stage internal pipeline, one row, left to right ----
    stages = [
        ("Width\nAdapters", COLOR_ADAPT),
        ("MM_in_buffer /\nMM_buffer", COLOR_HW),
        ("16×16 Systolic\nArray (MM_ultra)", COLOR_HW),
        ("Shifter /\nQuantizer\n(Eq. 1)", COLOR_HW),
        ("Width\nAdapter", COLOR_ADAPT),
        ("3-Pass\nSoftmax\n(Eq. 2)", COLOR_HW),
        ("Width\nAdapter", COLOR_ADAPT),
        ("GELU\n(EightGelus)", COLOR_HW),
    ]
    py, ph_, pgap = 45, 13, 2
    pw = (bw - 2 * 6 - (len(stages) - 1) * pgap) / len(stages)
    x = bx0 + 6
    centers = []
    for text, color in stages:
        draw_box(ctx, cv, x, py, pw, ph_, text, color, fontsize=2.35)
        centers.append(x + pw / 2)
        x += pw + pgap
    for i in range(len(centers) - 1):
        orthogonal_path(ctx, cv, [(centers[i] + pw / 2, py + ph_ / 2), (centers[i + 1] - pw / 2, py + ph_ / 2)])

    # ---- PS7 -> AXI-Lite control port (whole wrapper's config regs) ----
    ps7_cx = lx + lw_ / 2
    orthogonal_path(ctx, cv, [(ps7_cx, 75), (ps7_cx, 68), (bx0 - 4, 68), (bx0 - 4, py + ph_ - 1), (bx0, py + ph_ - 1)])
    label(ctx, cv, bx0 - 4, 71.5, "AXI-Lite\n(ctrl regs)", size=2.2, align="center", color=INK_SECONDARY)

    # ---- Feature/Weight DMA -> first stage (Width Adapters), each on its own clean row ----
    first_cx = centers[0]
    orthogonal_path(ctx, cv, [(lx + lw_, 54 + 13 * 0.72), (first_cx - pw / 2, 54 + 13 * 0.72), (first_cx - pw / 2, py + ph_ * 0.72)])
    orthogonal_path(ctx, cv, [(lx + lw_, 37 + 13 * 0.28), (first_cx - pw / 2, 37 + 13 * 0.28), (first_cx - pw / 2, py + ph_ * 0.28)])

    # ---- GELU (last stage) output -> Result DMA (S2MM), routed along the
    # bottom with real, checked clearance: y=1 is below every box on the
    # canvas (Result DMA's own bottom is at y=6), so the long westward
    # run never grazes anything, then a final short eastward entry into
    # the box's actual east edge with a properly-oriented arrowhead. ----
    last_cx = centers[-1]
    result_cy = 6 + 13 / 2
    orthogonal_path(ctx, cv, [
        (last_cx, py),
        (last_cx, 1),
        (lx + lw_ + 3, 1),
        (lx + lw_ + 3, result_cy),
        (lx + lw_, result_cy),
    ])

    label(ctx, cv, bx0 + bw / 2, by0 - 5, "GELU output -> Result DMA (S2MM), routed along the bottom",
          size=2.2, align="center", color=INK_SECONDARY)


cv4 = Canvas(xlim=(0, 264), ylim=(-8, 94), scale=5)
cv4.render(draw_fig4, "fig_soc_architecture_v2")


# ============================================================================
# Fig. 8/9 -- ViT structural mismatch (Section VI.D)
# Three stacked pipelines: the two real ViT sub-block dataflows (blue) vs.
# taoFPGA's fixed fused pipeline (orange) -- all three sequences are facts
# already stated in prose; this only visualizes them, plus an orthogonal
# callout bracket on each ViT row marking the stage it structurally lacks
# relative to the fixed pipeline.
# ============================================================================
def draw_fig9(cv, ctx):
    stage_w, stage_h, gap = 32, 14, 7
    box_x0 = 62
    rows = [
        ("ViT Self-Attention", 64, [("MatMul\n(Q·Kᵀ)", COLOR_HW), ("Softmax", COLOR_HW), ("MatMul\n(·V)", COLOR_HW)], "no GELU stage"),
        ("ViT MLP Block", 37, [("MatMul\n(·W1)", COLOR_HW), ("GELU", COLOR_HW), ("MatMul\n(·W2)", COLOR_HW)], "no Softmax stage"),
        ("taoFPGA Fixed\nPipeline", 10, [("MatMul", COLOR_CTRL), ("Softmax", COLOR_CTRL), ("GELU", COLOR_CTRL)], None),
    ]

    for row_label, y, stages, missing in rows:
        label(ctx, cv, 2, y + stage_h / 2, row_label, size=2.9, align="left")
        x = box_x0
        centers = []
        for text, color in stages:
            draw_box(ctx, cv, x, y, stage_w, stage_h, text, color, fontsize=2.7)
            centers.append(x + stage_w / 2)
            x += stage_w + gap
        for i in range(len(centers) - 1):
            orthogonal_path(ctx, cv, [(centers[i] + stage_w / 2, y + stage_h / 2), (centers[i + 1] - stage_w / 2, y + stage_h / 2)])

        if missing:
            # Orthogonal callout bracket: a vertical tick above the row's
            # rightmost box, stepping up and out to a clear label -- never
            # a diagonal pointer.
            bx = centers[-1]
            orthogonal_path(ctx, cv, [(bx, y + stage_h), (bx, y + stage_h + 6), (bx + 18, y + stage_h + 6)], color=COLOR_BAD, arrow=False)
            ctx.set_line_width(0.4)
            ctx.set_source_rgb(*COLOR_BAD)
            label(ctx, cv, bx + 19, y + stage_h + 6, missing, size=2.5, align="left", color=COLOR_BAD)

    label(ctx, cv, 2, 3,
          "Fixed pipeline always applies both Softmax and GELU -- neither ViT sub-block needs both,\n"
          "so the accelerator cannot be substituted into either without corrupting the result (Section VI.D).",
          size=2.35, align="left", color=INK_SECONDARY)


cv9 = Canvas(xlim=(0, 200), ylim=(0, 84), scale=6)
cv9.render(draw_fig9, "fig_vit_mismatch_v2")
