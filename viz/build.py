#!/usr/bin/env python3
"""
Package viz/src/ into the single self-contained viz/taofpga_dataflow.html.

    python viz/build.py            # (re)build the bundle
    python viz/build.py --check    # exit 1 if the bundle is stale (for CI)

No dependencies beyond the Python standard library. Inlines src/style.css,
src/lib/*.js (vendored three.js r128), and src/{data,content,app}.js into
index.html. The Google Fonts <link> is left external on purpose -- it
enhances online, and the page falls back to system fonts offline.
"""
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "src"
OUT = ROOT / "taofpga_dataflow.html"

LIBS = [
    "three.min.js",
    "CopyShader.js",
    "LuminosityHighPassShader.js",
    "SMAAShader.js",
    "OrbitControls.js",
    "RoomEnvironment.js",
    "EffectComposer.js",
    "RenderPass.js",
    "ShaderPass.js",
    "UnrealBloomPass.js",
    "SMAAPass.js",
]
APP_SCRIPTS = ["data.js", "content.js", "app.js"]


def read(p):
    return (SRC / p).read_text(encoding="utf-8")


def script_block(label, js):
    # a lone "</script>" inside string/comment content would close the tag early
    safe = js.replace("</script", "<\\/script")
    return "<script>/* %s */\n%s\n</script>" % (label, safe)


def build():
    html = read("index.html")

    # 1. inline the stylesheet
    css = read("style.css")
    html = html.replace(
        '<link rel="stylesheet" href="style.css" />',
        "<style>\n%s\n</style>" % css.strip("\n"),
        1,
    )

    # 2. inline the vendored libraries (order preserved)
    for name in LIBS:
        tag = '<script src="lib/%s"></script>' % name
        if tag not in html:
            raise SystemExit("index.html is missing: " + tag)
        html = html.replace(
            tag,
            script_block(name + "  (bundled offline, three.js r128 / 0.128.0)",
                         (SRC / "lib" / name).read_text(encoding="utf-8")),
            1,
        )

    # 3. inline the app scripts
    for name in APP_SCRIPTS:
        tag = '<script src="%s"></script>' % name
        if tag not in html:
            raise SystemExit("index.html is missing: " + tag)
        html = html.replace(tag, script_block(name, read(name)), 1)

    return html


def main():
    check = "--check" in sys.argv[1:]
    built = build()
    if check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != built:
            print("STALE: viz/taofpga_dataflow.html is out of date -- run `python viz/build.py`",
                  file=sys.stderr)
            sys.exit(1)
        print("OK: bundle matches viz/src/")
        return
    OUT.write_text(built, encoding="utf-8")
    kb = len(built.encode("utf-8")) / 1024
    print("built %s  (%.0f KB)" % (OUT.relative_to(ROOT.parent), kb))


if __name__ == "__main__":
    main()
