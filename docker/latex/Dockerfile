# syntax=docker/dockerfile:1
# Artigo do TCC (Fase 9): compila o projeto LaTeX do modelo da UNIJUÍ (classe abnTeX2), do mesmo
# jeito que o Overleaf: pdflatex + bibtex. TeX Live do Debian bookworm (abnTeX2 em
# texlive-publishers; Times via mathptmx em texlive-fonts-recommended). O unijui.sty carrega o
# fontawesome5, que no Debian está em texlive-fonts-extra; cm-super dá fontes vetoriais
# ao \texttt em T1 (sem ele, o TeX gera fontes em bitmap, o que o Overleaf não faz).
FROM debian:bookworm-20251020-slim@sha256:78d2f66e0fec9e5a39fb2c72ea5e052b548df75602b5215ed01a17171529f706

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      texlive-latex-base texlive-latex-recommended texlive-latex-extra \
      texlive-fonts-recommended texlive-fonts-extra texlive-lang-portuguese texlive-publishers \
      texlive-bibtex-extra cm-super latexmk poppler-utils zip \
 && rm -rf /var/lib/apt/lists/*

# O projeto é montado em /app em tempo de execução (bind mount).
WORKDIR /app
