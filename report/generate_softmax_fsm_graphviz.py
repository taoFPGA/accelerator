"""
Alternative rendering of Fig. X (Section II.B, the 3-pass Softmax_control
FSM) using Graphviz instead of hand-placed matplotlib shapes -- same
content/equations as generate_architecture_figures.py's version (states,
per-pass formulas, cycle counts, the "row done" return edge), same
project palette, just laid out by Graphviz's own engine.

NOTE (see report/project_story.md and this session's own investigation):
Softmax_control.v is NOT implemented as a literal case-statement FSM in
the RTL -- its 3-pass control is counters + threshold comparisons
(cnt_stage vs length/lengthX2/lengthX3). This diagram is therefore a
conceptual illustration of that control flow, same as the matplotlib
version it's an alternative to -- not a claim that Vivado extracted or
can show a synthesized state machine for this logic (confirmed directly:
no state_reg exists for this module, and even a genuine state_reg found
elsewhere in the design came back with no FSM_ENCODING tag).

Requires: pip install --user graphviz, plus a `dot` binary on PATH.
Renders directly to SVG (this environment's bundled `dot`, from the
Xcelium install, doesn't support PNG output directly -- but SVG is
natively supported, no separate rasterization step needed).

Run:
    python3 generate_softmax_fsm_graphviz.py
"""
import os

import graphviz

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT_DIR, exist_ok=True)

# Palette -- identical slots to generate_architecture_figures.py / generate_plots.py
COLOR_HW = "#2a78d6"      # blue -- the three active PASS states
COLOR_IDLE = "#898781"    # muted grey -- IDLE
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
SURFACE = "#fcfcfb"

STATE_FONT = "Helvetica"


def state_label(title, equation=None):
    """Plain multi-line label (title, optional equation below).

    This environment's `dot` build lacks libexpat and cannot parse
    HTML-like labels at all -- confirmed empirically: an HTML-like
    label attempt here silently fell back to just the node's internal
    name, with only a terse "Not built with libexpat" warning as the
    clue. Plain text + literal '\\n' line breaks works reliably instead,
    using the same literal Unicode subscript/math glyphs the
    matplotlib version (generate_architecture_figures.py) already uses
    successfully -- SVG text rendering handles those via normal font
    fallback, unlike the EPS/Ghostscript path this script no longer uses."""
    if equation:
        return f"{title}\n{equation}"
    return title


g = graphviz.Digraph(
    "softmax_fsm",
    graph_attr={
        "rankdir": "TB",
        "bgcolor": SURFACE,
        "splines": "ortho",
        "nodesep": "0.45",
        "ranksep": "0.55",
    },
    node_attr={
        "shape": "box",
        "style": "rounded,filled",
        "fontname": STATE_FONT,
        "fontcolor": "white",
        "color": INK,
        "penwidth": "1.1",
        "margin": "0.22,0.16",
    },
    edge_attr={
        "fontname": STATE_FONT,
        "fontsize": "10",
        "fontcolor": INK_SECONDARY,
        "color": INK,
        "penwidth": "1.2",
        "arrowsize": "0.8",
    },
)

g.node("IDLE", label=state_label("IDLE"), fillcolor=COLOR_IDLE)
g.node(
    "PASS1",
    label=state_label("PASS 1: MAX", "m = maxᵢ(xᵢ)"),
    fillcolor=COLOR_HW,
)
g.node(
    "PASS2",
    label=state_label(
        "PASS 2: ACCUMULATE",
        "S = Σᵢ 2^((xᵢ−m)·log₂e)",
    ),
    fillcolor=COLOR_HW,
)
g.node(
    "PASS3",
    label=state_label(
        "PASS 3: NORMALIZE",
        "yᵢ = 2^(((xᵢ−m)−ln S)·log₂e)",
    ),
    fillcolor=COLOR_HW,
)

g.edge("IDLE", "PASS1", label="new row")
g.edge("PASS1", "PASS2", label="N cycles")
g.edge("PASS2", "PASS3", label="N cycles")
g.edge(
    "PASS3", "IDLE", label="row done",
    color=INK_SECONDARY, constraint="false",
)

svg_path = os.path.join(OUT_DIR, "fig_softmax_fsm_graphviz")
g.render(svg_path, format="svg", cleanup=True)
print(f"Wrote {svg_path}.svg")
