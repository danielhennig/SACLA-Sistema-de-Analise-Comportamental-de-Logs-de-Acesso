# Monografia (Fase 9)

Texto do TCC no padrão ABNT (NBR 14724, citações pela NBR 10520:2023, referências pela
NBR 6023:2018), gerado a partir de arquivos de texto versionados.

```bash
python tasks.py monografia   # gera SACLA-monografia.docx e o PDF de conferência
```

- `SACLA-monografia.docx`: o documento para editar no Word. Ao abrir, o Word pergunta se deve
  atualizar os campos: responda **sim**, para o sumário e as listas de figuras e de tabelas
  ficarem com as páginas certas.
- `data/monografia/SACLA-monografia.pdf` (não versionado): conferência gerada pelo
  LibreOffice, com sumário e listas atualizados. Usa a fonte Liberation Serif, de mesmas métricas
  da Times New Roman, então a paginação é praticamente a do Word.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `monografia.json` | capa, folha de rosto, folha de aprovação, resumo, abstract e siglas |
| `texto/*.md` | capítulos, referências e apêndices, na ordem do nome do arquivo |
| `figuras/` | figuras próprias da monografia; as da avaliação são lidas de `results/*/<exp>/figuras/` |
| `gerar.js` | monta o .docx (biblioteca docx, versão fixada em `docker/docs/`) |
| `pdf.py` | exporta o PDF de conferência pelo LibreOffice |
| `diagramas.py` | gera `figuras/fluxo.png` (serviço `analise`) |

Os campos entre colchetes (instituição, orientador, cidade, banca) devem ser preenchidos; a
ideia é transferir o texto para o modelo da faculdade.

## Marcação usada nos capítulos

- `# Título`, `## Título`, `### Título`: seções primária, secundária e terciária, numeradas
  automaticamente. `# Título {-}`: sem número (referências, apêndices).
- `**negrito**`, `*itálico*`, `` `código` ``.
- Listas com `- ` ou `1. `.
- Tabela: uma linha `Tabela: Título {#tab:id}`, a tabela em Markdown e, abaixo, `Fonte: ...`
  e, se houver, `Nota: ...`.
- Figura: `![Título](figuras/arquivo.png){#fig:id width=15}` (largura em cm), seguida de
  `Fonte: ...`.
- Equação: `$$ expressão {#eq:id}`, com expoentes como `2^{...}`.
- Referência cruzada: `@fig:id`, `@tab:id`, `@eq:id` viram "Figura N", "Tabela N" e
  "Equação N".
- Bloco de código entre três crases.
