$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
pdflatex -shell-escape -interaction=nonstopmode report.tex
pdflatex -shell-escape -interaction=nonstopmode report.tex
