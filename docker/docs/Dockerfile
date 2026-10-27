# syntax=docker/dockerfile:1
# Monografia (Fase 9): gera o .docx com a biblioteca docx (versão fixada em package.json e
# package-lock.json) e o PDF de conferência com o LibreOffice (+ páginas em imagem, poppler).
# python3-uno: o PDF é exportado por um script que atualiza sumário e listas antes (campos que
# o Word atualiza sozinho ao abrir). Times New Roman não existe no Linux: o PDF de conferência
# usa a Liberation Serif, que tem as mesmas métricas; no Word, vale a fonte original.
FROM node:24.11.1-bookworm-slim@sha256:48abc13a19400ca3985071e287bd405a1d99306770eb81d61202fb6b65cf0b57

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libreoffice-writer-nogui python3-uno poppler-utils fonts-liberation fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/monografia
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund
ENV NODE_PATH=/opt/monografia/node_modules

# O projeto é montado em /app em tempo de execução (bind mount).
WORKDIR /app
