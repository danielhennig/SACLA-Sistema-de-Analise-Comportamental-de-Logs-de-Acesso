#!/bin/sh
# Artigo do TCC (Fase 9): compila docs/artigo como o Overleaf (pdflatex, bibtex, pdflatex 2x)
# numa cópia temporária, para não deixar arquivos auxiliares no projeto, e gera em data/artigo/
# o PDF de conferência e o .zip para enviar ao Overleaf (New Project > Upload Project).
# Uso, no contêiner `latex`: sh docker/latex/compilar.sh
set -eu

SRC=/app/docs/artigo
OUT=/app/data/artigo
WORK=$(mktemp -d)
mkdir -p "$OUT"
cp -r "$SRC"/. "$WORK"
cd "$WORK"

passo() {
    if ! pdflatex -interaction=nonstopmode -halt-on-error main.tex > /dev/null; then
        grep -n -A5 '^!' main.log || tail -40 main.log
        exit 1
    fi
}

passo
bibtex main > bibtex.out || { cat bibtex.out; exit 1; }
passo
passo

cp main.pdf "$OUT/SACLA-artigo.pdf"
rm -f "$OUT/SACLA-artigo-overleaf.zip"
(cd "$SRC" && zip -q -r -X "$OUT/SACLA-artigo-overleaf.zip" . \
    -x '*.aux' '*.bbl' '*.blg' '*.brf' '*.log' '*.lof' '*.lot' '*.out' '*.toc' '*.pdf')

echo "== avisos =="
grep -c 'Overfull' main.log | sed 's/^/caixas cheias demais (Overfull): /' || true
grep 'Overfull' main.log || true
grep -E 'undefined|Citation .* undefined|Reference .* undefined|There were' main.log || true
grep -i 'warning' bibtex.out || true
echo "== saída =="
pdfinfo "$OUT/SACLA-artigo.pdf" | grep -E '^Pages'
ls -l "$OUT"
