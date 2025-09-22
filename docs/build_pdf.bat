@echo off
setlocal
echo Building LaTeX PDF (requires MiKTeX/TeX Live and Inkscape on PATH)
cd /d %~dp0
pdflatex -shell-escape -interaction=nonstopmode report.tex
pdflatex -shell-escape -interaction=nonstopmode report.tex
endlocal
