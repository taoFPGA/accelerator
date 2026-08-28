"""
One-shot, targeted edit: corrects every stale page number in the Table of
Contents / List of Figures / List of Tables of the CURRENT
taoFPGA_Project_Book.docx, in place.

The real page for each entry was independently re-verified against a
fresh render of this exact file (see the session's extraction script),
searching only in text AFTER the List of Tables' last real line so no
TOC/LOF/LOT entry could false-match its own listing text instead of the
real heading later in the document. Only the trailing page-number token
is rewritten per paragraph; all other text and formatting is preserved.

Run once from the dev machine:
    python fix_toc_pages.py
"""
import docx

PATH = "taoFPGA_Project_Book.docx"

# paragraph index -> new page number (only entries whose page actually changed)
NEW_PAGES = {
    42: 4,    # Preliminaries
    49: 7,    # C. Key Contributions & Paper Outline
    50: 7,    # II. Core Hardware Architecture & Mathematical Formulation
    51: 7,    # A. Systolic Matrix Multiplication Core
    52: 8,    # B. Fixed-Point Non-Linear Arithmetic Engines
    56: 9,    # B. Simulation Results & Numerical Precision Verification
    57: 9,    # C. Pre-Silicon Logic Debugging
    58: 9,    # IV. SoC Integration & Hardware Platform Design
    59: 9,    # A. SoC Architecture
    60: 10,   # B. Physical Adaptations for Board Deployment
    65: 11,   # C. Physical Congestion vs. Timing Trade-Off
    66: 11,   # D. Bitstream & Hardware Platform Sign-Off
    67: 12,   # VI. Experimental Evaluation & Hardware Bring-Up
    68: 12,   # A. Benchmarking Methodology
    69: 12,   # B. Performance Metrics & Acceleration
    71: 13,   # D. Workload Characterization vs. ViT Networks
    72: 13,   # E. Hardware Bring-Up Observations & Edge Cases
    74: 15,   # VII. Engineering Discussion, Bottlenecks & Future Work
    75: 15,   # A. DMA Buffer Boundary Constraints
    76: 15,   # B. Serial Softmax Throughput Bottleneck
    77: 15,   # C. Architectural Roadmap
    78: 15,   # VIII. Conclusion
    79: 15,   # References
    80: 16,   # Appendix A: Engineering Problems Encountered and Their Solutions
    81: 16,   # A.1
    82: 16,   # A.2
    83: 17,   # A.3
    84: 17,   # A.4
    85: 17,   # A.5
    86: 18,   # A.6
    87: 18,   # A.7
    92: 20,   # A.12
    96: 8,    # Fig. 1
    97: 8,    # Fig. 2
    98: 9,    # Fig. 3
    100: 11,  # Fig. 5 (Vivado) -- was "#" placeholder
    101: 12,  # Fig. 6 (Latency)
    102: 12,  # Fig. 7 (Throughput)
    104: 13,  # Fig. 9 (Real ViT)
    106: 10,  # Table I
}


def set_page_number(p, new_page):
    text = p.text
    if "\t" not in text:
        raise RuntimeError(f"Expected a tab-separated page number in: {text!r}")
    label = text.rsplit("\t", 1)[0]
    new_text = f"{label}\t{new_page}"
    if not p.runs:
        raise RuntimeError(f"Paragraph has no runs: {text!r}")
    font_name = p.runs[0].font.name
    font_size = p.runs[0].font.size
    bold = p.runs[0].font.bold
    italic = p.runs[0].font.italic
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
    run = p.add_run(new_text)
    run.font.name = font_name
    if font_size is not None:
        run.font.size = font_size
    run.font.bold = bold
    run.font.italic = italic


def main():
    doc = docx.Document(PATH)
    for idx, new_page in NEW_PAGES.items():
        p = doc.paragraphs[idx]
        old_text = p.text
        set_page_number(p, new_page)
        print(f"{idx}: {old_text!r} -> {p.text!r}")
    doc.save(PATH)
    print(f"Updated {len(NEW_PAGES)} page numbers in {PATH}")


if __name__ == "__main__":
    main()
