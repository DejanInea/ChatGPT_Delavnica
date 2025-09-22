# LaTeX report build instructions

Prerequisites
- Install a LaTeX distribution (MiKTeX or TeX Live)
- Install Inkscape and ensure `inkscape` is on PATH (for SVG conversion)

Build
- PowerShell: `./build_pdf.ps1`
- CMD: `build_pdf.bat`
- Manual: `pdflatex -shell-escape docs/report.tex` (run twice)

Outputs
- `docs/report.pdf`
- Auxiliary files in `docs/`
