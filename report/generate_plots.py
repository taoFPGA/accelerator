"""
Generates the three defense-presentation charts for the ViT hardware
kernel benchmark (report/project_story.md Section 31): latency
comparison, throughput comparison, and speedup factor.

The numbers below are the actual measured results from the clean
benchmark run recorded in Section 31 -- not placeholders. Re-run
apps/vit/vit_benchmark.py on the board and update these constants if the
benchmark is ever repeated.

Run on the dev machine (needs matplotlib, not needed on the board):
    python generate_plots.py
Output: report/figures/*.png (300 DPI, for slides) and *.pdf (vector,
for LaTeX embedding).

Colors are the two adjacent slots (blue, orange) from this project's
data-viz reference palette -- validated to clear every CVD/contrast gate
as an adjacent pair, so the CPU/Hardware distinction reads correctly
under color-vision deficiency, not just for standard vision.
"""
import os

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT_DIR, exist_ok=True)

# --- Measured results (report/project_story.md Section 31, clean re-run) ---
SHAPES = ["Projection\n(192x192)", "MLP-shaped\n(192x320)"]
CPU_LATENCY_MS = [408.942, 623.336]
HW_LATENCY_MS = [5.840, 6.378]
CPU_THROUGHPUT_GOPS = [0.036, 0.039]
HW_THROUGHPUT_GOPS = [2.487, 3.795]
SPEEDUP = [70.02, 97.73]

# --- Palette (report/../dataviz skill reference palette; slots 1 & 2) ---
COLOR_HW = "#2a78d6"     # slot 1, blue -- the accelerator being showcased
COLOR_CPU = "#eb6834"    # slot 2, orange -- baseline
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE_AXIS = "#c3c2b7"
SURFACE = "#fcfcfb"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial"],
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "text.color": INK_PRIMARY,
    "axes.edgecolor": BASELINE_AXIS,
    "axes.labelcolor": INK_SECONDARY,
    "xtick.color": INK_SECONDARY,
    "ytick.color": INK_SECONDARY,
})


def _style_axes(ax, ylabel):
    ax.set_ylabel(ylabel, fontsize=11, color=INK_SECONDARY)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE_AXIS)
    ax.yaxis.grid(True, color=GRIDLINE, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0, labelsize=10)


def _bar_labels(ax, bars, fmt):
    for b in bars:
        h = b.get_height()
        ax.annotate(fmt.format(h), xy=(b.get_x() + b.get_width() / 2, h),
                    xytext=(0, 4), textcoords="offset points",
                    ha="center", va="bottom", fontsize=10, color=INK_PRIMARY)


def _title(fig, title, subtitle):
    fig.suptitle(title, x=0.02, ha="left", fontsize=15, fontweight="bold", color=INK_PRIMARY)
    fig.text(0.02, 0.91, subtitle, ha="left", fontsize=10, color=INK_SECONDARY)


def grouped_bar_chart(values_a, values_b, label_a, label_b, ylabel, title, subtitle, filename, value_fmt):
    x = range(len(SHAPES))
    width = 0.32
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    fig.subplots_adjust(top=0.78, bottom=0.14)

    bars_a = ax.bar([i - width / 2 for i in x], values_a, width, label=label_a, color=COLOR_CPU, zorder=3)
    bars_b = ax.bar([i + width / 2 for i in x], values_b, width, label=label_b, color=COLOR_HW, zorder=3)
    _bar_labels(ax, bars_a, value_fmt)
    _bar_labels(ax, bars_b, value_fmt)

    ax.set_xticks(list(x))
    ax.set_xticklabels(SHAPES, fontsize=10.5)
    _style_axes(ax, ylabel)
    ax.margins(y=0.15)

    legend = ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(0.0, 1.0),
                        fontsize=10, labelcolor=INK_SECONDARY)

    _title(fig, title, subtitle)

    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(OUT_DIR, f"{filename}.{ext}"), dpi=300)
    plt.close(fig)
    print(f"Wrote {filename}.png / {filename}.pdf")


def speedup_chart():
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    fig.subplots_adjust(top=0.78, bottom=0.14)

    bars = ax.bar(SHAPES, SPEEDUP, width=0.45, color=COLOR_HW, zorder=3)
    _bar_labels(ax, bars, "{:.2f}x")

    _style_axes(ax, "Speedup (CPU time / hardware time)")
    ax.margins(y=0.15)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0fx"))

    _title(fig, "Hardware Kernel Speedup",
           "Same fused matmul+softmax+GELU operation, hardware vs. CPU")

    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(OUT_DIR, f"speedup_factor.{ext}"), dpi=300)
    plt.close(fig)
    print("Wrote speedup_factor.png / speedup_factor.pdf")


def main():
    grouped_bar_chart(
        CPU_LATENCY_MS, HW_LATENCY_MS, "CPU", "Hardware",
        ylabel="Latency (ms, lower is better)",
        title="Latency: CPU vs. Hardware Accelerator",
        subtitle="ViT-Tiny-representative matmul+softmax+GELU kernel",
        filename="latency_comparison",
        value_fmt="{:.1f} ms",
    )
    grouped_bar_chart(
        CPU_THROUGHPUT_GOPS, HW_THROUGHPUT_GOPS, "CPU", "Hardware",
        ylabel="Throughput (GOP/s, higher is better)",
        title="Throughput: CPU vs. Hardware Accelerator",
        subtitle="ViT-Tiny-representative matmul+softmax+GELU kernel",
        filename="throughput_comparison",
        value_fmt="{:.3f}",
    )
    speedup_chart()


if __name__ == "__main__":
    main()
