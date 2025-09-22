#!/usr/bin/env python3
"""
Generate a PDF similar to docs/report.pdf using pure Python (no LaTeX).

Approach
- Uses matplotlib.backends.backend_pdf.PdfPages to assemble pages.
- Renders text and simple lists onto A4-sized figures.
- Attempts to include docs/flowchart.svg by converting it to PNG via Inkscape
  if available (subprocess). If Inkscape is unavailable, the figure is skipped
  with a visible note.

Output
- docs/report_python.pdf

Usage
  python docs/report_from_python.py
"""

from __future__ import annotations

import subprocess
from pathlib import Path
import sys
import textwrap
from datetime import date

import matplotlib
matplotlib.use("Agg")  # headless, file-only backend
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


DOCS = Path(__file__).resolve().parent
SVG_PATH = DOCS / "flowchart.svg"
TMP_PNG = DOCS / "flowchart_tmp.png"
OUTPUT_PDF = DOCS / "report_python.pdf"


def which(prog: str) -> bool:
    try:
        subprocess.run([prog, "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return True
    except FileNotFoundError:
        return False


def try_convert_svg_to_png(svg: Path, png: Path) -> bool:
    """Convert SVG to PNG using Inkscape if available.
    Supports Inkscape 1.x and legacy 0.9x CLI flags.
    """
    if not svg.exists():
        return False
    if not which("inkscape"):
        return False
    # Prefer new CLI first
    cmds = [
        [
            "inkscape",
            str(svg),
            "--export-type=png",
            f"--export-filename={png}",
        ],
        [
            "inkscape",
            str(svg),
            "--export-png",
            str(png),
        ],
    ]
    for cmd in cmds:
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode == 0 and png.exists():
                return True
        except Exception:
            pass
    return False


def draw_wrapped_text(ax, text: str, x: float, y: float, width_chars: int, line_height: float, fontsize: int = 11, weight: str = "normal") -> float:
    """Draw text wrapped to width_chars at (x,y) top-down, returns next y."""
    wrapper = textwrap.TextWrapper(width=width_chars, replace_whitespace=False, drop_whitespace=False)
    for paragraph in text.splitlines():
        if paragraph.strip() == "":
            y -= line_height
            continue
        for line in wrapper.wrap(paragraph):
            ax.text(x, y, line, ha='left', va='top', fontsize=fontsize, weight=weight)
            y -= line_height
    return y


def new_page():
    # A4 in inches
    fig = plt.figure(figsize=(8.27, 11.69), dpi=150)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    return fig, ax


def main() -> int:
    with PdfPages(OUTPUT_PDF) as pdf:
        # Cover page
        fig, ax = new_page()
        ax.text(0.5, 0.80, "Opis in arhitektura:\nvizualizacija toka vode", ha='center', va='center', fontsize=24, weight='bold')
        ax.text(0.5, 0.72, "Projekt: water_flow_visualization", ha='center', va='center', fontsize=12)
        ax.text(0.5, 0.69, date.today().isoformat(), ha='center', va='center', fontsize=11)
        pdf.savefig(fig)
        plt.close(fig)

        # Summary
        fig, ax = new_page()
        y = 0.95
        y = draw_wrapped_text(ax, "Povzetek", 0.10, y, width_chars=90, line_height=0.035, fontsize=16, weight='bold')
        y -= 0.01
        summary = (
            "Ta dokument opisuje implementacijo vizualizacije toka vode v dveh izvedbah: "
            "Python (water_flow_visualization.py) in C++ (water_flow_visualization.cpp). "
            "Algoritem temelji na divergencno prostem hitrostnem polju, polju barvila, "
            "pol-lagrangevem prenašanju (advekciji) in blagem dušenju, kar daje vodnat, turbulenten videz. "
            "Program omogoča živ prikaz in izvoz animiranega GIF-a."
        )
        y = draw_wrapped_text(ax, summary, 0.10, y, width_chars=95, line_height=0.030, fontsize=11)
        pdf.savefig(fig)
        plt.close(fig)

        # Algorithm overview + flowchart
        fig, ax = new_page()
        y = 0.95
        y = draw_wrapped_text(ax, "Pregled algoritma", 0.10, y, width_chars=90, line_height=0.035, fontsize=16, weight='bold')
        y -= 0.01
        bullets = [
            "Tokovna funkcija ψ(x,y,t): časovno spreminjajoči sinusni/cosinusni vzorci.",
            "Hitrostno polje v=(u,v): u=∂ψ/∂y, v=−∂ψ/∂x; glajenje (Gauss).",
            "Polje barvila: modri odtenki, šum, vinjetiranje.",
            "Advekcija: pol-lagrangevsko s bilinearno interpolacijo.",
            "Dušenje in barvno ravnotežje: mešanje z osnovnim barvilom.",
            "Izhod: okno (neobvezno) in GIF zapis.",
        ]
        for b in bullets:
            y = draw_wrapped_text(ax, f"• {b}", 0.12, y, width_chars=92, line_height=0.030, fontsize=11)
        y -= 0.02

        # Flowchart image (if we can convert)
        img_drawn = False
        if SVG_PATH.exists():
            if try_convert_svg_to_png(SVG_PATH, TMP_PNG) and TMP_PNG.exists():
                import matplotlib.image as mpimg
                img = mpimg.imread(TMP_PNG)
                # Place image centered
                ax.imshow(img, extent=(0.10, 0.90, 0.15, 0.55), aspect='auto')
                img_drawn = True
        if not img_drawn:
            note = (
                "Flowchart (SVG) ni bil vključen. Za vključen prikaz namestite Inkscape "
                "(na PATH) ali pretvorite docs/flowchart.svg v PNG in zamenjajte pot."
            )
            y = draw_wrapped_text(ax, note, 0.10, 0.60, width_chars=90, line_height=0.030, fontsize=10, weight='bold')

        pdf.savefig(fig)
        plt.close(fig)

        # Python/C++ sections (condensed)
        fig, ax = new_page()
        y = 0.95
        y = draw_wrapped_text(ax, "Python: water_flow_visualization.py", 0.10, y, width_chars=90, line_height=0.035, fontsize=16, weight='bold')
        y -= 0.01
        py_bullets = [
            "SimulationConfig: resolution, steps, dt, strength, fps, live_view, gif_name, output_dir.",
            "Tok in hitrost: stream_function, velocity_field, gaussian_blur.",
            "Vzorčenje in advekcija: bilinear_sample, advect.",
            "Inicializacija barvila: create_initial_dye (modri toni + šum + vinjeta).",
            "Zanka: v, advekcija, dušenje, zbiranje slik; imageio.mimsave za GIF.",
        ]
        for b in py_bullets:
            y = draw_wrapped_text(ax, f"• {b}", 0.12, y, width_chars=92, line_height=0.030, fontsize=11)
        y -= 0.02
        y = draw_wrapped_text(ax, "C++: water_flow_visualization.cpp", 0.10, y, width_chars=90, line_height=0.035, fontsize=16, weight='bold')
        y -= 0.01
        cpp_bullets = [
            "Config: podobne nastavitve kot v Pythonu.",
            "Tok in hitrost: streamFunction, buildVelocityField, gaussianBlur (ločljivi 1D filtri).",
            "Advekcija: bilinearno vzorčenje.",
            "Živ prikaz (neobvezno): OpenCV okno.",
            "GIF izvoz: Magick++ (ImageMagick).",
        ]
        for b in cpp_bullets:
            y = draw_wrapped_text(ax, f"• {b}", 0.12, y, width_chars=92, line_height=0.030, fontsize=11)
        pdf.savefig(fig)
        plt.close(fig)

        # Parameters and differences (short)
        fig, ax = new_page()
        y = 0.95
        y = draw_wrapped_text(ax, "Parametri in priporočila", 0.10, y, width_chars=90, line_height=0.035, fontsize=16, weight='bold')
        y -= 0.01
        params = [
            "resolution: velikost slike (višje počasneje).",
            "steps: število sličic (trajanje GIF-a).",
            "dt: časovni korak advekcije.",
            "strength: skala hitrosti (vrtinci).",
            "fps: hitrost predvajanja.",
            "live_view: omogoči/izključi okno za predogled.",
        ]
        for b in params:
            y = draw_wrapped_text(ax, f"• {b}", 0.12, y, width_chars=92, line_height=0.030, fontsize=11)
        y -= 0.03
        y = draw_wrapped_text(ax, "Razlike med izvedbama", 0.10, y, width_chars=90, line_height=0.035, fontsize=16, weight='bold')
        y -= 0.01
        diffs = [
            "Odvisnosti: Python (numpy/matplotlib/imageio), C++ (Magick++, opcijsko OpenCV).",
            "Hitrost: C++ običajno hitrejši; Python lažji za prilagoditve.",
            "Vizualno: algoritmi usklajeni, možne manjše razlike.",
        ]
        for b in diffs:
            y = draw_wrapped_text(ax, f"• {b}", 0.12, y, width_chars=92, line_height=0.030, fontsize=11)
        pdf.savefig(fig)
        plt.close(fig)

    # Cleanup temporary PNG if created
    try:
        if TMP_PNG.exists():
            TMP_PNG.unlink()
    except Exception:
        pass

    print(f"[OK] Wrote: {OUTPUT_PDF}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

