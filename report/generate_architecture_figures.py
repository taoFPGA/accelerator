"""
Generates two original architectural figures for the IEEE paper, drawn
from scratch from taoFPGA's own RTL structure and module/signal names --
not reproduced or adapted from any third-party publication (see
report/project_story.md and the paper's own References for the prior
work this project builds on; no figure from that prior work is used or
traced here).

  fig_soc_architecture.png/pdf   -- Fig. Y (Section IV.A): top-level SoC
                                     datapath, PS7 -> 3x AXI DMA ->
                                     transformer_block_axi_top's internal
                                     pipeline -> back to Result DMA.
  fig_softmax_fsm.png/pdf        -- Fig. X (Section II.B): the 3-pass
                                     Softmax_control FSM and its per-pass
                                     equations (Eq. 2), visualizing why
                                     it is a serial, 3N-cycle bottleneck.

Run on the dev machine (needs matplotlib):
    python generate_architecture_figures.py
"""
import os

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
from matplotlib.path import Path
import matplotlib.patches as mpatches

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT_DIR, exist_ok=True)

# Palette (project's data-viz reference palette; same slots used in the benchmark charts)
COLOR_HW = "#2a78d6"      # blue -- accelerator/compute blocks
COLOR_CTRL = "#eb6834"    # orange -- PS7 / control / DMA
COLOR_ADAPT = "#898781"   # muted grey -- width-adapter glue logic
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


def box(ax, xy, w, h, text, color, fontsize=8.5, textcolor="white", style="round,pad=0.06"):
    x, y = xy
    p = FancyBboxPatch((x, y), w, h, boxstyle=style, linewidth=1.1,
                        edgecolor=INK, facecolor=color, zorder=3)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, color=textcolor, zorder=4, linespacing=1.25)
    return p


def arrow(ax, p0, p1, color=INK, style="-|>", lw=1.3, connectionstyle="arc3,rad=0.0"):
    a = FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=10,
                         linewidth=lw, color=color, zorder=2,
                         connectionstyle=connectionstyle, shrinkA=2, shrinkB=2)
    ax.add_patch(a)
    return a


# ============================================================================
# Fig. Y -- Top-level SoC architecture (Section IV.A)
# ============================================================================
fig, ax = plt.subplots(figsize=(12.6, 4.4))
ax.set_xlim(0, 130)
ax.set_ylim(0, 39)
ax.axis("off")

# --- PS7 ---
box(ax, (2, 30), 14, 8, "ARM Cortex-A9\n(Zynq-7020 PS7)", COLOR_CTRL, fontsize=9.5)

# --- 3x AXI DMA ---
dma_y = 18
box(ax, (2, dma_y), 14, 6, "AXI DMA\nFeature (MM2S)", COLOR_CTRL)
box(ax, (2, dma_y - 8), 14, 6, "AXI DMA\nWeight (MM2S)", COLOR_CTRL)
box(ax, (2, dma_y - 16), 14, 6, "AXI DMA\nResult (S2MM)", COLOR_CTRL)

arrow(ax, (9, 30), (9, 24), color=INK_SECONDARY)
arrow(ax, (16, 34), (24, 21), color=INK_SECONDARY, connectionstyle="arc3,rad=-0.15")
arrow(ax, (16, 21), (24, 21), color=INK_SECONDARY)
arrow(ax, (16, 13), (24, 15.5), color=INK_SECONDARY, connectionstyle="arc3,rad=0.15")
ax.text(19, 25.5, "AXI-Lite\n(ctrl regs)", fontsize=6.5, color=INK_SECONDARY, ha="center")

# --- transformer_block_axi_top dashed boundary ---
# Sized to hug the single pipeline row (y=12..21) plus enough headroom for
# the label and enough footroom for the S2MM exit arrow's dip to y=5 --
# not stretched to match the unrelated PS7/DMA column's height.
boundary = Rectangle((23, 2), 104, 23, fill=False, linestyle="--",
                      edgecolor=INK_SECONDARY, linewidth=1.0, zorder=1)
ax.add_patch(boundary)
ax.text(24, 26.3, "transformer_block_axi_top", fontsize=8.5, style="italic",
        color=INK_SECONDARY, ha="left")

# --- Internal pipeline (single row, left to right) ---
py = 12
pw, ph = 11.5, 9
gap = 1.3
x = 26
stages = [
    ("Width\nAdapters", COLOR_ADAPT, 8),
    ("MM_in_buffer /\nMM_buffer", COLOR_HW, 8),
    ("16×16 Systolic\nArray (MM_ultra)", COLOR_HW, 8.5),
    ("Shifter /\nQuantizer\n(Eq. 1)", COLOR_HW, 8),
    ("Width\nAdapter", COLOR_ADAPT, 8),
    ("3-Pass\nSoftmax\n(Eq. 2)", COLOR_HW, 8),
    ("Width\nAdapter", COLOR_ADAPT, 8),
    ("GELU\n(EightGelus)", COLOR_HW, 8),
]
centers = []
for label, color, fs in stages:
    box(ax, (x, py), pw, ph, label, color, fontsize=fs)
    centers.append(x + pw / 2)
    x += pw + gap
for i in range(len(stages) - 1):
    arrow(ax, (centers[i] + pw / 2, py + ph / 2), (centers[i + 1] - pw / 2, py + ph / 2))

# Feature/Weight DMA feed into first width-adapter stage
arrow(ax, (16, 21), (26, py + ph * 0.65), color=INK_SECONDARY, connectionstyle="arc3,rad=-0.2")
arrow(ax, (16, 13), (26, py + ph * 0.35), color=INK_SECONDARY, connectionstyle="arc3,rad=0.2")

# GELU output back to Result DMA (S2MM)
last_cx = centers[-1]
arrow(ax, (last_cx, py), (last_cx, 5), color=INK_SECONDARY, connectionstyle="arc3,rad=0")
arrow(ax, (last_cx, 5), (16, dma_y - 16 + 3), color=INK_SECONDARY, connectionstyle="arc3,rad=-0.15")

fig.tight_layout()
for ext in ("png", "pdf"):
    fig.savefig(os.path.join(OUT_DIR, f"fig_soc_architecture.{ext}"), dpi=300)
plt.close(fig)
print("Wrote fig_soc_architecture.png/pdf")


# ============================================================================
# Fig. X -- 3-pass Softmax FSM (Section II.B)
# ============================================================================
fig, ax = plt.subplots(figsize=(3.5, 4.6))
ax.set_xlim(0, 10)
ax.set_ylim(0, 18.3)
ax.axis("off")

state_w, state_h = 7.6, 2.5
xs = 1.2
states = [
    ("IDLE", COLOR_ADAPT, ""),
    ("PASS 1: MAX\nm = maxᵢ(xᵢ)", COLOR_HW, "N cycles"),
    ("PASS 2: ACCUMULATE\nS = Σᵢ 2^((xᵢ−m)·log₂e)", COLOR_HW, "N cycles"),
    ("PASS 3: NORMALIZE\nyᵢ = 2^(((xᵢ−m)−ln S)·log₂e)", COLOR_HW, "N cycles"),
]
ys = [15.0, 11.6, 8.2, 4.8]
for (label, color, cyc), y in zip(states, ys):
    box(ax, (xs, y), state_w, state_h, label, color, fontsize=7.6)
    if cyc:
        ax.text(xs + state_w + 0.35, y + state_h / 2, cyc, fontsize=7,
                color=INK_SECONDARY, va="center", ha="left", rotation=0)

for i in range(len(states) - 1):
    arrow(ax, (xs + state_w / 2, ys[i]), (xs + state_w / 2, ys[i + 1] + state_h))

# return arrow PASS3 -> IDLE (row done)
arrow(ax, (xs, ys[-1] + state_h / 2), (xs - 0.9, ys[-1] + state_h / 2), color=INK_SECONDARY)
arrow(ax, (xs - 0.9, ys[-1] + state_h / 2), (xs - 0.9, ys[0] + state_h / 2), color=INK_SECONDARY)
arrow(ax, (xs - 0.9, ys[0] + state_h / 2), (xs, ys[0] + state_h / 2), color=INK_SECONDARY)
ax.text(xs - 1.3, (ys[0] + ys[-1]) / 2 + 1, "row done", fontsize=6.5,
        color=INK_SECONDARY, rotation=90, ha="center", va="center")

fig.tight_layout()
for ext in ("png", "pdf"):
    fig.savefig(os.path.join(OUT_DIR, f"fig_softmax_fsm.{ext}"), dpi=300)
plt.close(fig)
print("Wrote fig_softmax_fsm.png/pdf")
