#!/usr/bin/env python3
"""
Build docs/report.pdf using Python.

This script wraps latexmk/pdflatex so you can generate the same PDF
as docs/report.tex without leaving Python.

Usage (from repo root or any dir):
  python docs/build_pdf.py [--engine auto|latexmk|pdflatex] [--tex report.tex]

Defaults:
  - engine: auto (prefer latexmk if available, else pdflatex x2)
  - tex: report.tex (relative to this docs/ folder)
  - shell-escape enabled (needed for \\includesvg)
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
from pathlib import Path
import sys
import glob


def which(cmd: str) -> str | None:
    return shutil.which(cmd)


def _unique_existing_paths(paths: list[Path]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for p in paths:
        try:
            s = str(p)
        except Exception:
            continue
        if not s or s in seen:
            continue
        if Path(s).exists():
            seen.add(s)
            result.append(s)
    return result


def _prepend_to_env_path(paths: list[str]) -> None:
    if not paths:
        return
    sep = os.pathsep
    current = os.environ.get("PATH", "")
    # Avoid duplicates while preserving order
    current_parts = current.split(sep) if current else []
    new_parts: list[str] = []
    for p in paths:
        if p and p not in new_parts and p not in current_parts:
            new_parts.append(p)
    if new_parts:
        os.environ["PATH"] = sep.join(new_parts + current_parts)


def _common_tex_bins_windows() -> list[Path]:
    candidates: list[Path] = []
    # MiKTeX (per-user)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "Programs" / "MiKTeX" / "miktex" / "bin" / "x64")
    # MiKTeX (system)
    candidates.append(Path(r"C:\Program Files\MiKTeX\miktex\bin\x64"))
    candidates.append(Path(r"C:\Program Files (x86)\MiKTeX 2.9\miktex\bin\x64"))
    # TeX Live (common years)
    for year in range(2017, 2031):
        candidates.append(Path(fr"C:\texlive\{year}\bin\windows"))
    # TeX Live default old layout
    candidates.append(Path(r"C:\texlive\bin\win32"))
    # Also allow any C:\texlive\*\bin\windows discovered via glob
    for p in glob.glob(r"C:\\texlive\\*\\bin\\windows"):
        candidates.append(Path(p))
    return candidates


def _common_inkscape_bins_windows() -> list[Path]:
    candidates: list[Path] = []
    candidates.append(Path(r"C:\Program Files\Inkscape\bin"))
    candidates.append(Path(r"C:\Program Files\Inkscape"))
    for p in glob.glob(r"C:\\Program Files\\Inkscape-*\\bin"):
        candidates.append(Path(p))
    return candidates


def ensure_tools_on_path(user_texbins: list[str], user_inkbins: list[str]) -> None:
    """Prepend likely TeX/InkScape bins to PATH so which() can find them.

    - Always prepend explicit user-provided bins first.
    - If still not found on Windows, try common install paths.
    """
    prepend: list[Path] = []
    prepend += [Path(p) for p in user_texbins if p]
    prepend += [Path(p) for p in user_inkbins if p]

    if platform.system().lower().startswith("win"):
        # Try common paths if tools are missing
        need_tex = which("pdflatex") is None and which("latexmk") is None
        need_ink = which("inkscape") is None
        if need_tex:
            prepend += _common_tex_bins_windows()
        if need_ink:
            prepend += _common_inkscape_bins_windows()

    to_add = _unique_existing_paths(prepend)
    _prepend_to_env_path(to_add)


def run(cmd: list[str], cwd: Path) -> int:
    proc = subprocess.run(cmd, cwd=str(cwd))
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Build LaTeX PDF (docs/report.tex)")
    parser.add_argument("--engine", choices=["auto", "latexmk", "pdflatex"], default="auto")
    parser.add_argument("--tex", default="report.tex", help="TeX filename relative to docs/")
    parser.add_argument("--passes", type=int, default=2, help="pdflatex passes when not using latexmk")
    parser.add_argument("--no-shell-escape", action="store_true", help="Disable -shell-escape")
    parser.add_argument("--texbin", action="append", default=[], help="Directory with TeX binaries (pdflatex/latexmk). Can be passed multiple times; prepended to PATH for this run.")
    parser.add_argument("--inkscape-bin", action="append", default=[], help="Directory with Inkscape binary; prepended to PATH for this run.")
    args = parser.parse_args()

    docs_dir = Path(__file__).resolve().parent
    tex_path = docs_dir / args.tex

    if not tex_path.exists():
        print(f"[ERROR] TeX file not found: {tex_path}")
        return 1

    # Ensure tools are reachable on PATH for this process
    ensure_tools_on_path(args.texbin, args.inkscape_bin)

    # Detect inkscape if SVGs are included
    includesvg = False
    try:
        content = tex_path.read_text(encoding="utf-8", errors="ignore")
        includesvg = "\\includesvg" in content
    except Exception:
        pass

    if includesvg and which("inkscape") is None and not args.no_shell_escape:
        print("[WARN] Inkscape not found on PATH, but \\includesvg is used.")
        print("       Install Inkscape or rerun with --no-shell-escape and replace \\includesvg with \\includegraphics.")

    # Choose engine
    engine = args.engine
    if engine == "auto":
        engine = "latexmk" if which("latexmk") else "pdflatex"

    shell_escape_flag = [] if args.no_shell_escape else ["-shell-escape"]

    if engine == "latexmk":
        if which("latexmk") is None:
            print("[ERROR] latexmk not found on PATH; choose --engine pdflatex or install latexmk.")
            return 2
        cmd = [
            "latexmk",
            "-pdf",
            "-interaction=nonstopmode",
            *shell_escape_flag,
            tex_path.name,
        ]
        print("[INFO] Running:", " ".join(cmd))
        code = run(cmd, cwd=docs_dir)
        if code != 0:
            print(f"[ERROR] latexmk returned {code}")
            return code
    else:  # pdflatex
        if which("pdflatex") is None:
            print("[ERROR] pdflatex not found on PATH. Install MiKTeX/TeX Live or use --texbin to point to it.")
            return 3
        passes = max(1, int(args.passes))
        cmd = [
            "pdflatex",
            "-interaction=nonstopmode",
            *shell_escape_flag,
            tex_path.name,
        ]
        print("[INFO] Running pdflatex passes:", passes)
        for i in range(passes):
            print(f"[INFO] Pass {i+1}/{passes}:", " ".join(cmd))
            code = run(cmd, cwd=docs_dir)
            if code != 0:
                print(f"[ERROR] pdflatex returned {code} on pass {i+1}")
                return code

    pdf_path = docs_dir / (tex_path.with_suffix(".pdf").name)
    if pdf_path.exists():
        print(f"[OK] Built: {pdf_path}")
        return 0
    else:
        print("[ERROR] Build completed but PDF not found:", pdf_path)
        return 4


if __name__ == "__main__":
    sys.exit(main())
