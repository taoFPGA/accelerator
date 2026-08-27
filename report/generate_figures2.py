"""
Generates three more original figures for the project book, drawn from the
project's own RTL and documented facts -- not reproduced from any third
party. Distinguishes real structural diagrams (grounded in actual RTL
signal names/widths, or in already-established architectural facts) from
anything that would require a real captured measurement this session
doesn't have (an actual Xcelium/SimVision waveform dump or a real Vivado
floorplan screenshot) -- neither of the latter is fabricated here; see
generate_ieee_paper.py for how each is actually handled in the manuscript.

  fig_pe_microarch.png/pdf     -- Fig. 1 (Section II.A): one PE's internal
                                   datapath (INT8 multiply, stationary
                                   weight register, accumulate register,
                                   systolic x/psum propagation), grounded
                                   directly in PE.v's real port/signal
                                   names and bit widths.
  fig_axi_timing.png/pdf       -- Fig. 3 (Section III.B): an ILLUSTRATIVE
                                   AXI4-Stream handshake + 3-pass Softmax
                                   timing structure -- protocol shape and
                                   the already-documented 3N-cycle-per-row
                                   structure, explicitly NOT presented as a
                                   captured EDA simulation trace (no real
                                   waveform dump exists to plot honestly).
  fig_vit_mismatch.png/pdf     -- Fig. 8 (Section VI.D): real ViT
                                   sub-block dataflows (self-attention,
                                   MLP) contrasted with the accelerator's
                                   fixed fused pipeline, visualizing the
                                   structural mismatch already described in
                                   prose.

Run on the dev machine (needs matplotlib):
    python generate_figures2.py
"""
import os

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, ConnectionPatch
import matplotlib.lines as mlines

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT_DIR, exist_ok=True)

COLOR_HW = "#2a78d6"
COLOR_CTRL = "#eb6834"
COLOR_ADAPT = "#898781"
COLOR_BAD = "#c0392b"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
SURFACE = "#fcfcfb"
BORDER = "#c3c2b7"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial"],
    "figure.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
})


def box(ax, xy, w, h, text, color, fontsize=8.5, textcolor="white", style="round,pad=0.06", lw=1.1, ls="-"):
    x, y = xy
    p = FancyBboxPatch((x, y), w, h, boxstyle=style, linewidth=lw, linestyle=ls,
                        edgecolor=INK, facecolor=color, zorder=3)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, color=textcolor, zorder=4, linespacing=1.3)
    return p


def arrow(ax, p0, p1, color=INK, style="-|>", lw=1.3, connectionstyle="arc3,rad=0.0"):
    a = FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=10,
                         linewidth=lw, color=color, zorder=2,
                         connectionstyle=connectionstyle, shrinkA=2, shrinkB=2)
    ax.add_patch(a)
    return a


# ============================================================================
# Fig. 1 -- PE internal microarchitecture (Section II.A)
# Grounded directly in sourcecode/core/PE.v: ports clk/set_w/rst_n/x_in/w/
# psum_in/x_out/psum_out; x_in and w are INT8 (data_width=8); psum_in/
# psum_out are 2*data_width+log2_array_m = 20 bits wide for this project's
# 16-row array (log2_array_m=4) -- NOT 32 bits, which would misstate the
# real RTL. reg_w is the stationary weight register (loaded when set_w is
# asserted); x_out and psum_out are both registered once per cycle, which
# is the one-cycle systolic skew the rest of the design (and Appendix
# A.7's DSP-mapping discussion) depends on.
# ============================================================================
fig, ax = plt.subplots(figsize=(7.6, 6.4))
ax.set_xlim(0, 115)
ax.set_ylim(0, 100)
ax.axis("off")

# Outer PE boundary
pe_box = Rectangle((14, 8), 88, 80, fill=False, linestyle="--",
                    edgecolor=INK_SECONDARY, linewidth=1.2, zorder=1)
ax.add_patch(pe_box)
ax.text(16, 90, "PE (sourcecode/core/PE.v)", fontsize=8.5, style="italic",
        color=INK_SECONDARY, ha="left")

# Right-hand compute chain: reg_w feeds the multiplier, which feeds the
# adder (with psum_in), which feeds the psum_out register -- one clean
# top-to-bottom column, each stage directly below the one that feeds it.
box(ax, (58, 74), 26, 12, "reg_w\n(stationary weight, INT8,\nloaded on set_w)", COLOR_CTRL, fontsize=7.0)
box(ax, (58, 56), 26, 11, "×  (INT8 × INT8)", COLOR_HW, fontsize=8.3)
box(ax, (58, 38), 26, 11, "+", COLOR_HW, fontsize=10)
box(ax, (58, 20), 26, 12, "psum_out_r\n(20-bit signed reg,\nUG901 use_dsp target)", COLOR_HW, fontsize=6.8)

# Left-hand x pass-through chain
box(ax, (20, 20), 24, 12, "x_out\n(INT8 reg, 1-cycle\nsystolic delay)", COLOR_ADAPT, fontsize=7.0)

# Internal connections (each a single, unambiguous straight arrow)
arrow(ax, (71, 74), (71, 67))                 # reg_w -> multiplier
arrow(ax, (71, 56), (71, 49))                 # multiplier -> adder
arrow(ax, (71, 38), (71, 32))                 # adder -> psum_out_r

# x_in branches to both the multiplier (as the second operand) and the
# x_out register (pass-through); drawn as two separate arrows from the
# same left-margin label so neither one crosses through an unrelated box.
ax.annotate("x_in [7:0]\n(from west PE)", xy=(0, 50), fontsize=7.3, va="center", ha="left")
arrow(ax, (16, 50), (58, 61), connectionstyle="arc3,rad=0.15")   # x_in -> multiplier
arrow(ax, (16, 48), (20, 30), connectionstyle="arc3,rad=-0.15")  # x_in -> x_out reg

# set_w / w inputs into reg_w
ax.annotate("set_w", xy=(40, 84), xytext=(16, 88), fontsize=7.3, va="center", ha="left",
            arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.1))
ax.annotate("w [7:0]", xy=(58, 80), xytext=(16, 80), fontsize=7.3, va="center", ha="left",
            arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.1))

# psum_in enters the adder from the right, offset above the box's own
# centered "+" label so the two never overlap.
ax.text(112, 47, "psum_in [19:0]\n(from north PE)", fontsize=7.0, va="center", ha="right")
arrow(ax, (108, 44), (84, 41))

# Outputs, each drawn straight out from its own box edge -- no diagonal
# crossing another box. x_out exits toward the east (right), matching
# PE_line.v's real x_array[i] -> x_array[i+1] chaining direction.
arrow(ax, (44, 24), (54, 14), connectionstyle="arc3,rad=-0.15")
ax.text(56, 12, "x_out [7:0]\n(to east PE)", fontsize=7.0, va="center", ha="left")
ax.text(71, 4, "psum_out [19:0]\n(to south PE)", fontsize=7.0, va="center", ha="center")
arrow(ax, (71, 20), (71, 10))

fig.tight_layout()
for ext in ("png", "pdf"):
    fig.savefig(os.path.join(OUT_DIR, f"fig_pe_microarch.{ext}"), dpi=300)
plt.close(fig)
print("Wrote fig_pe_microarch.png/pdf")


# ============================================================================
# Fig. 3 -- Illustrative AXI4-Stream handshake + 3-pass timing structure
# (Section III.B). Deliberately NOT presented as a captured simulation
# waveform -- no real Xcelium/SimVision VCD/trace was captured for this
# specific slice in this session, and drawing one with invented signal
# values would misrepresent unverified data as a real measurement. This
# diagram instead shows the real, already-documented protocol structure:
# the AXI4-Stream tvalid/tready handshake shape, and the three sequential,
# equal-length N-cycle passes (MAX -> ACCUMULATE -> NORMALIZE) that Eq. 2
# and Section II.B already establish as the real per-row timing structure.
# ============================================================================
fig, ax = plt.subplots(figsize=(7.0, 3.6))
ax.set_xlim(0, 100)
ax.set_ylim(0, 46)
ax.axis("off")
ax.text(2, 44, "Illustrative protocol structure -- not a captured EDA simulation trace",
        fontsize=8, style="italic", color=COLOR_BAD, ha="left")

signal_rows = [("clk", 36), ("tvalid", 29), ("tready", 22), ("tdata", 15)]
for label, y in signal_rows:
    ax.text(2, y + 1.5, label, fontsize=8.5, ha="left", va="center", color=INK, family="monospace")

# clk pulses
import numpy as np
t = np.arange(0, 96, 4)
for i, x0 in enumerate(t):
    y0 = 36
    ax.plot([x0, x0, x0 + 2, x0 + 2, x0 + 4], [y0, y0 + 2, y0 + 2, y0, y0],
            color=INK_SECONDARY, lw=1.0)

# tvalid: high across a burst window, illustrating backpressure gaps
def level_signal(ax, y0, segments, color=INK):
    """segments: list of (x_start, x_end, level) with level in {0,1}"""
    for x0, x1, lvl in segments:
        yy = y0 + (2 if lvl else 0)
        ax.plot([x0, x1], [yy, yy], color=color, lw=1.6)
    for i in range(len(segments) - 1):
        x_edge = segments[i][1]
        y_a = y0 + (2 if segments[i][2] else 0)
        y_b = y0 + (2 if segments[i + 1][2] else 0)
        ax.plot([x_edge, x_edge], [y_a, y_b], color=color, lw=1.6)

level_signal(ax, 29, [(8, 24, 1), (24, 32, 0), (32, 92, 1)], color=COLOR_HW)
level_signal(ax, 22, [(8, 20, 1), (20, 24, 0), (24, 92, 1)], color=COLOR_HW)
level_signal(ax, 15, [(8, 92, 1)], color=INK_SECONDARY)
ax.text(50, 12.5, "feature words streaming into MM_in_buffer", fontsize=7, color=INK_SECONDARY,
        ha="center", style="italic")

# Shade the "transfer accepted" windows (tvalid & tready both high)
for x0, x1 in [(8, 20), (32, 92)]:
    ax.add_patch(Rectangle((x0, 14), x1 - x0, 19, color=COLOR_HW, alpha=0.06, zorder=0))
ax.add_patch(Rectangle((20, 14), 4, 19, color=COLOR_BAD, alpha=0.10, zorder=0))
ax.text(22, 40, "tready\nde-asserted\n(backpressure)", fontsize=6.3, ha="center", color=COLOR_BAD)
ax.annotate("", xy=(22, 33.5), xytext=(22, 37.5),
            arrowprops=dict(arrowstyle="-|>", color=COLOR_BAD, lw=1.0))

# 3-pass structure timeline beneath
pass_y = 4
pass_defs = [("PASS 1: MAX", 8, 34, COLOR_ADAPT), ("PASS 2: ACCUMULATE", 34, 60, COLOR_HW),
             ("PASS 3: NORMALIZE", 60, 92, COLOR_HW)]
for label, x0, x1, color in pass_defs:
    box(ax, (x0, pass_y), x1 - x0, 6, label, color, fontsize=6.8)
ax.annotate("", xy=(92, pass_y - 2), xytext=(8, pass_y - 2),
            arrowprops=dict(arrowstyle="-", color=INK_SECONDARY, lw=0.8))
ax.text(50, pass_y - 4.2, "3N cycles per row (Eq. 2, Section II.B)", fontsize=7,
        ha="center", color=INK_SECONDARY)

fig.tight_layout()
for ext in ("png", "pdf"):
    fig.savefig(os.path.join(OUT_DIR, f"fig_axi_timing.{ext}"), dpi=300)
plt.close(fig)
print("Wrote fig_axi_timing.png/pdf")


# ============================================================================
# Fig. 8 -- ViT structural mismatch (Section VI.D). Contrasts the two real
# ViT sub-block dataflows against taoFPGA's fixed fused pipeline -- all
# three sequences are facts already stated in prose (Section VI.D); this
# only visualizes them.
# ============================================================================
fig, ax = plt.subplots(figsize=(7.0, 4.0))
ax.set_xlim(0, 100)
ax.set_ylim(0, 40)
ax.axis("off")

stage_w, stage_h, gap = 22, 7, 4
rows = [
    ("ViT Self-Attention", 30, [("MatMul\n(Q·Kᵀ)", COLOR_HW), ("Softmax", COLOR_HW), ("MatMul\n(·V)", COLOR_HW)]),
    ("ViT MLP Block", 17, [("MatMul\n(·W1)", COLOR_HW), ("GELU", COLOR_HW), ("MatMul\n(·W2)", COLOR_HW)]),
    ("taoFPGA Fixed Pipeline", 4, [("MatMul", COLOR_CTRL), ("Softmax", COLOR_CTRL), ("GELU", COLOR_CTRL)]),
]
for label, y, stages in rows:
    ax.text(2, y + stage_h / 2, label, fontsize=8.3, ha="left", va="center", fontweight="bold")
    x = 34
    centers = []
    for stage_label, color in stages:
        box(ax, (x, y), stage_w, stage_h, stage_label, color, fontsize=7.5)
        centers.append(x + stage_w / 2)
        x += stage_w + gap
    for i in range(len(centers) - 1):
        arrow(ax, (centers[i] + stage_w / 2, y + stage_h / 2), (centers[i + 1] - stage_w / 2, y + stage_h / 2))

# Mismatch annotations
ax.annotate("no GELU stage", xy=(34 + 2 * (stage_w + gap) + stage_w / 2, 30), xytext=(34 + 2 * (stage_w + gap) + stage_w / 2, 38),
            fontsize=7, ha="center", color=COLOR_BAD,
            arrowprops=dict(arrowstyle="-|>", color=COLOR_BAD, lw=1.0))
ax.annotate("no Softmax stage", xy=(34 + 1 * (stage_w + gap) + stage_w / 2, 17), xytext=(34 - 20, 24),
            fontsize=7, ha="center", color=COLOR_BAD,
            arrowprops=dict(arrowstyle="-|>", color=COLOR_BAD, lw=1.0))
ax.text(50, 0.5, "Fixed pipeline always applies both Softmax and GELU -- neither ViT sub-block needs both,\n"
                 "so the accelerator cannot be substituted into either without corrupting the result (Section VI.D).",
        fontsize=7.2, ha="center", color=INK_SECONDARY, style="italic")

fig.tight_layout()
for ext in ("png", "pdf"):
    fig.savefig(os.path.join(OUT_DIR, f"fig_vit_mismatch.{ext}"), dpi=300)
plt.close(fig)
print("Wrote fig_vit_mismatch.png/pdf")
