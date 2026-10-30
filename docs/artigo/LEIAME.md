# Artigo do TCC (modelo LaTeX da UNIJUÍ)

Projeto LaTeX do trabalho em formato de artigo, a partir do modelo do curso
([dornelles/tcc-artigo-template-latex](https://github.com/dornelles/tcc-artigo-template-latex),
*commit* `b4f7dce`, de 17/08/2026). Os arquivos `unijui.sty`, `abntex2cite.sty` e
`figuras/00-capa/logo_unijui.png` são do modelo, sem alterações de conteúdo (o repositório guarda
os `.sty` com fim de linha LF, e o original usa CRLF). O conteúdo é o mesmo da monografia (`docs/monografia/`), condensado.

## Compilar

- **No Overleaf:** em *New Project > Upload Project*, envie `data/artigo/SACLA-artigo-overleaf.zip`
  (gerado por `python tasks.py artigo`) ou um .zip desta pasta. O compilador é o padrão
  (pdfLaTeX), com `main.tex` como documento principal.
- **Localmente:** `python tasks.py artigo` compila numa cópia temporária, no contêiner `latex`
  (pdflatex, bibtex, pdflatex duas vezes), e gera em `data/artigo/` o `SACLA-artigo.pdf` e o
  `SACLA-artigo-overleaf.zip`. O único aviso esperado é uma caixa 12 pt larga demais na capa,
  que também aparece no modelo original.
- **Avisos esperados no Overleaf**, todos do modelo ou da classe: babel `brazil` obsoleto (vem
  do `abntex2.cls`), `\settocpreprocessor` obsoleto (abnTeX2/memoir) e `subfig` antigo
  (carregado pelo `main.tex` do modelo).

## Estrutura

| Arquivo | Conteúdo |
|---|---|
| `main.tex` | dados do trabalho, resumo, abstract, siglas e a ordem dos capítulos |
| `capitulos/01-introducao.tex` a `05-consideracoes-finais.tex` | texto, na estrutura do modelo |
| `apendices/apendice-a.tex`, `apendice-b.tex` | configuração de log e reprodução do experimento |
| `declaracoes/declaracao-uso-ia.tex` | declaração sobre o uso de IA generativa |
| `referencias.bib` | 27 referências, conferidas na fonte |
| `figuras/04-desenvolvimento/` | figuras do Desenvolvimento, copiadas de `results/` e de `docs/monografia/figuras/` |

Os números do texto vêm de `results/` (os mesmos da monografia).

## O que falta preencher

Os campos entre colchetes são do autor e não estão no repositório:

- `main.tex`:
  - `\orientador`, o segundo nome em `\autoresartigo` e a titulação do(a) orientador(a);
  - os e-mails institucionais;
  - `\professordabanca` e `\datadabanca`.
- `main.tex`, texto de apresentação: conferir com o(a) orientador(a).
- `declaracoes/declaracao-uso-ia.tex`: conferir se a descrição corresponde ao uso feito e
  acrescentar a versão do modelo, se o curso exigir.

## Convenções

- Seções e subseções não são numeradas no modelo; as remissões no texto são pelo nome da seção.
- Figuras, tabelas e quadros seguem os exemplos do modelo: minipage, `\legend{Fonte: ...}` e
  `\legend{Nota: ...}`.
- Tabelas de dados numéricos usam booktabs, sem bordas laterais; quadros, de conteúdo textual,
  têm todas as bordas. As colunas de texto dos quadros usam o tipo `L{largura}`, alinhado à
  esquerda, definido em `main.tex`.
- Figuras em PNG **RGB, sem transparência**. Com canal alfa (RGBA, o padrão do matplotlib), o
  pdfTeX recomprime cada imagem em toda passada: as figuras RGBA quase dobravam o tempo de
  compilação e faziam o Overleaf gratuito estourar o tempo. Para converter uma figura nova:
  `Image.alpha_composite(Image.new("RGBA", im.size, "white"), im).convert("RGB")` (Pillow).
- `\iforest` escreve *Isolation Forest* em itálico.
- Autores institucionais no `.bib` usam `{\relax Nome}`, que deixa a referência em maiúsculas e
  a citação em caixa mista (NBR 6023 e NBR 10520).
