// Gera a monografia em .docx no padrão ABNT (NBR 14724) a partir de monografia.json e dos
// capítulos em texto/*.md (um Markdown simples, descrito em LEIAME.md).
// Uso (serviço docs): node docs/monografia/gerar.js
"use strict";

const fs = require("fs");
const path = require("path");
const d = require("docx");

const MONO = __dirname;
const ROOT = path.resolve(MONO, "..", "..");
const OUT = path.join(MONO, "SACLA-monografia.docx");
// Pastas onde as figuras são procuradas, em ordem (as da avaliação ficam em results/).
const FIGURE_DIRS = [
  path.join(MONO, "figuras"),
  ...["experimentos", "confirmatorio", "ablacao", "deriva"].flatMap((kind) => {
    const base = path.join(ROOT, "results", kind);
    return fs.existsSync(base)
      ? fs.readdirSync(base).map((exp) => path.join(base, exp, "figuras"))
      : [];
  }),
];

// --- Medidas ABNT (twips: 1 cm = 567) ---------------------------------------------------
const CM = 567;
const PAGE = { width: 11906, height: 16838 }; // A4
const MARGIN = { top: 3 * CM, left: 3 * CM, bottom: 2 * CM, right: 2 * CM };
const TEXT_WIDTH = PAGE.width - MARGIN.left - MARGIN.right; // 16 cm
const FONT = "Times New Roman";
const MONOFONT = "Courier New";
const SIZE = 24; // 12 pt (meios-pontos)
const SMALL = 20; // 10 pt: legendas, fontes, notas, tabelas, citações longas
const LINE_15 = 360;
const LINE_1 = 240;
const INDENT = Math.round(1.25 * CM); // recuo da primeira linha do parágrafo
const PX_PER_CM = 96 / 2.54;
// Regra de espaçamento explícita: sem ela, o LibreOffice lê a altura da linha como exata.
const AUTO = d.LineRuleType.AUTO;
const LIST_LEVEL = 4; // nível das listas de figuras e de tabelas nos campos de sumário

const meta = JSON.parse(fs.readFileSync(path.join(MONO, "monografia.json"), "utf8"));
const chapterFiles = fs
  .readdirSync(path.join(MONO, "texto"))
  .filter((f) => f.endsWith(".md"))
  .sort();
const chapters = chapterFiles.map((f) => fs.readFileSync(path.join(MONO, "texto", f), "utf8"));

// --- Numeração de figuras, tabelas e equações (na ordem em que aparecem) --------------------
const LABELS = { fig: "Figura", tab: "Tabela", eq: "Equação" };
const numbers = {};
const counters = { fig: 0, tab: 0, eq: 0 };
for (const text of chapters) {
  for (const match of text.matchAll(/\{#(fig|tab|eq):([\w-]+)/g)) {
    const key = `${match[1]}:${match[2]}`;
    if (numbers[key]) throw new Error(`identificador repetido: ${key}`);
    numbers[key] = ++counters[match[1]];
  }
}
function crossRefs(text) {
  return text.replace(/@(fig|tab|eq):([\w-]+)/g, (_, kind, id) => {
    const n = numbers[`${kind}:${id}`];
    if (!n) throw new Error(`referência sem alvo: @${kind}:${id}`);
    return `${LABELS[kind]} ${n}`;
  });
}

// --- Texto em linha: **negrito**, *itálico*, `código` -----------------------------------------
function runs(text, base = {}) {
  const out = [];
  let bold = false;
  let italics = false;
  let buffer = "";
  const flush = () => {
    // Só marca negrito/itálico quando ativos: "false" explícito anularia o estilo (títulos).
    if (buffer) {
      out.push(new d.TextRun({ text: buffer, bold: bold || undefined, italics: italics || undefined, ...base }));
    }
    buffer = "";
  };
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === "`") {
      const end = text.indexOf("`", i + 1);
      flush();
      out.push(
        new d.TextRun({
          text: text.slice(i + 1, end),
          font: MONOFONT,
          bold: bold || undefined,
          italics: italics || undefined,
          ...base,
          size: (base.size || SIZE) - 2,
        }),
      );
      i = end;
    } else if (ch === "*" && text[i + 1] === "*") {
      flush();
      bold = !bold;
      i++;
    } else if (ch === "*") {
      flush();
      italics = !italics;
    } else {
      buffer += ch;
    }
  }
  flush();
  return out;
}

// --- Parágrafos-padrão -----------------------------------------------------------------------
const body = (text) =>
  new d.Paragraph({
    children: runs(crossRefs(text)),
    alignment: d.AlignmentType.JUSTIFIED,
    indent: { firstLine: INDENT },
    spacing: { line: LINE_15, lineRule: AUTO, after: 0 },
  });

const small = (text, options = {}) =>
  new d.Paragraph({
    children: runs(crossRefs(text), { size: SMALL }),
    alignment: options.alignment || d.AlignmentType.LEFT,
    spacing: { line: LINE_1, lineRule: AUTO, before: options.before || 0, after: options.after ?? 0 },
    keepNext: options.keepNext || false,
  });

const centered = (text, options = {}) =>
  new d.Paragraph({
    children: runs(text, { size: options.size || SIZE, bold: options.bold || false }),
    alignment: d.AlignmentType.CENTER,
    spacing: { line: options.line || LINE_15, lineRule: AUTO, before: options.before || 0, after: options.after || 0 },
  });

const pageBreak = () => new d.Paragraph({ children: [new d.PageBreak()] });

const preTitle = (text) =>
  new d.Paragraph({
    style: "TituloPre",
    children: [new d.TextRun({ text })],
    pageBreakBefore: true,
  });

// --- Figuras --------------------------------------------------------------------------------
function findFigure(relative) {
  const name = path.basename(relative);
  for (const dir of FIGURE_DIRS) {
    const candidate = path.join(dir, name);
    if (fs.existsSync(candidate)) return candidate;
  }
  throw new Error(`figura não encontrada: ${relative}`);
}

function pngSize(file) {
  const data = fs.readFileSync(file);
  return { width: data.readUInt32BE(16), height: data.readUInt32BE(20), data };
}

function figure(line) {
  const match = line.match(/^!\[(.+)\]\((.+?)\)\{#fig:([\w-]+)(?:\s+width=([\d.]+))?\}$/);
  if (!match) throw new Error(`figura malformada: ${line}`);
  const [, title, relative, id, width] = match;
  const file = findFigure(relative);
  const png = pngSize(file);
  const widthPx = Math.round(parseFloat(width || "15") * PX_PER_CM);
  const heightPx = Math.round((widthPx * png.height) / png.width);
  return [
    new d.Paragraph({
      style: "LegendaFigura",
      children: runs(`Figura ${numbers[`fig:${id}`]} – ${title}`, { size: SMALL }),
    }),
    new d.Paragraph({
      alignment: d.AlignmentType.CENTER,
      keepNext: true,
      spacing: { line: LINE_1, lineRule: AUTO, after: 60 },
      children: [
        new d.ImageRun({
          type: "png",
          data: png.data,
          transformation: { width: widthPx, height: heightPx },
          altText: { title, description: title, name: path.basename(file) },
        }),
      ],
    }),
  ];
}

// --- Tabelas --------------------------------------------------------------------------------
const BORDER = { style: d.BorderStyle.SINGLE, size: 6, color: "000000" };
const NO_BORDER = { style: d.BorderStyle.NONE, size: 0, color: "FFFFFF" };

function splitRow(line) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

// Larguras: cada coluna precisa da sua palavra mais longa (no cabeçalho, em negrito) e, se
// couber, do texto inteiro numa linha. Colunas curtas ficam com a largura natural; as de texto
// longo dividem o resto da largura útil.
const CHAR_TWIPS = 105; // largura média de um caractere a 10 pt
const CELL_PADDING = 220; // margens internas da célula
const SHORT_COLUMN = 16; // até tantos caracteres, a coluna não quebra linha
function columnWidths(header, rows) {
  const plain = (text) => (text || "").replace(/[*`]/g, "");
  const longest = header.map((_, c) => Math.max(...[header, ...rows].map((r) => plain(r[c]).length)));
  const longestWord = header.map((_, c) =>
    Math.max(...[header, ...rows].flatMap((r) => plain(r[c]).split(/\s+/).map((w) => w.length))),
  );
  const minimum = longestWord.map((w) => (w + 1.5) * CHAR_TWIPS + CELL_PADDING);
  const natural = longest.map((n, c) => Math.max(n * CHAR_TWIPS + CELL_PADDING, minimum[c]));
  const short = longest.map((n) => n <= SHORT_COLUMN);
  let widths;
  if (natural.reduce((a, b) => a + b, 0) <= TEXT_WIDTH) {
    const scale = TEXT_WIDTH / natural.reduce((a, b) => a + b, 0);
    widths = natural.map((w) => w * scale);
  } else {
    const fixed = natural.reduce((sum, w, c) => sum + (short[c] ? w : 0), 0);
    const flexible = natural.reduce((sum, w, c) => sum + (short[c] ? 0 : w), 0);
    const room = Math.max(TEXT_WIDTH - fixed, 0);
    widths = natural.map((w, c) => (short[c] ? w : Math.max(minimum[c], (room * w) / flexible)));
    const scale = TEXT_WIDTH / widths.reduce((a, b) => a + b, 0);
    widths = widths.map((w) => w * scale);
  }
  const rounded = widths.map((w) => Math.floor(w));
  rounded[rounded.length - 1] += TEXT_WIDTH - rounded.reduce((a, b) => a + b, 0);
  return rounded;
}

function table(caption, lines) {
  const match = caption.match(/^Tabela:\s*(.+?)\s*\{#tab:([\w-]+)\}$/);
  if (!match) throw new Error(`legenda de tabela malformada: ${caption}`);
  const [, title, id] = match;
  const header = splitRow(lines[0]);
  const aligns = splitRow(lines[1]).map((cell) =>
    cell.endsWith(":") && cell.startsWith(":")
      ? d.AlignmentType.CENTER
      : cell.endsWith(":")
        ? d.AlignmentType.RIGHT
        : d.AlignmentType.LEFT,
  );
  const rows = lines.slice(2).map(splitRow);
  const widths = columnWidths(header, rows);

  const cell = (text, c, isHeader, isLast) =>
    new d.TableCell({
      width: { size: widths[c], type: d.WidthType.DXA },
      margins: { top: 40, bottom: 40, left: 80, right: 80 },
      borders: {
        top: isHeader ? BORDER : NO_BORDER,
        bottom: isHeader || isLast ? BORDER : NO_BORDER,
        left: NO_BORDER,
        right: NO_BORDER,
      },
      children: [
        new d.Paragraph({
          alignment: isHeader ? d.AlignmentType.CENTER : aligns[c],
          spacing: { line: LINE_1, lineRule: AUTO, before: 0, after: 0 },
          children: runs(text, { size: SMALL, bold: isHeader || undefined }),
        }),
      ],
    });

  const tableRows = [
    new d.TableRow({
      tableHeader: true,
      cantSplit: true,
      children: header.map((text, c) => cell(text, c, true, false)),
    }),
    ...rows.map(
      (row, r) =>
        new d.TableRow({
          cantSplit: true,
          children: header.map((_, c) => cell(row[c] || "", c, false, r === rows.length - 1)),
        }),
    ),
  ];
  return [
    new d.Paragraph({
      style: "LegendaTabela",
      children: runs(`Tabela ${numbers[`tab:${id}`]} – ${title}`, { size: SMALL }),
    }),
    new d.Table({
      width: { size: TEXT_WIDTH, type: d.WidthType.DXA },
      columnWidths: widths,
      alignment: d.AlignmentType.CENTER,
      rows: tableRows,
    }),
  ];
}

// --- Equações -------------------------------------------------------------------------------
function equation(line) {
  const match = line.match(/^\$\$\s*(.+?)\s*\{#eq:([\w-]+)\}$/);
  if (!match) throw new Error(`equação malformada: ${line}`);
  const [, expression, id] = match;
  const parts = [];
  // Expoentes: 2^{...}; o resto em itálico, com sinal de menos tipográfico.
  const pieces = expression.replace(/-/g, "−").split(/(\^\{[^}]*\})/);
  for (const piece of pieces) {
    if (!piece) continue;
    const superscript = piece.startsWith("^{");
    const text = superscript ? piece.slice(2, -1) : piece;
    parts.push(new d.TextRun({ text, italics: true, superScript: superscript }));
  }
  return new d.Paragraph({
    tabStops: [
      { type: d.TabStopType.CENTER, position: Math.round(TEXT_WIDTH / 2) },
      { type: d.TabStopType.RIGHT, position: TEXT_WIDTH },
    ],
    spacing: { line: LINE_15, lineRule: AUTO, before: 120, after: 120 },
    children: [
      new d.TextRun({ text: "\t" }),
      ...parts,
      new d.TextRun({ text: `\t(${numbers[`eq:${id}`]})` }),
    ],
  });
}

// --- Capítulos (Markdown simples) ------------------------------------------------------------
const heading = { h1: 0, h2: 0, h3: 0 };
let listInstance = 0;

function headingParagraph(level, rawTitle) {
  const unnumbered = rawTitle.endsWith("{-}");
  const title = rawTitle.replace(/\s*\{-\}$/, "");
  let label = title;
  if (!unnumbered) {
    if (level === 1) {
      heading.h1++;
      heading.h2 = 0;
      heading.h3 = 0;
      label = `${heading.h1} ${title}`;
    } else if (level === 2) {
      heading.h2++;
      heading.h3 = 0;
      label = `${heading.h1}.${heading.h2} ${title}`;
    } else {
      heading.h3++;
      label = `${heading.h1}.${heading.h2}.${heading.h3} ${title}`;
    }
  }
  const levels = [d.HeadingLevel.HEADING_1, d.HeadingLevel.HEADING_2, d.HeadingLevel.HEADING_3];
  return new d.Paragraph({
    heading: levels[level - 1],
    alignment: unnumbered ? d.AlignmentType.CENTER : d.AlignmentType.LEFT,
    children: runs(label),
  });
}

function chapterBlocks(text) {
  const blocks = [];
  const lines = text.replace(/\r/g, "").split("\n");
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i++;
      continue;
    }
    const h = line.match(/^(#{1,3})\s+(.+)$/);
    if (h) {
      blocks.push(headingParagraph(h[1].length, h[2].trim()));
      i++;
      continue;
    }
    if (line.startsWith("```")) {
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) {
        blocks.push(
          new d.Paragraph({
            spacing: { line: LINE_1, lineRule: AUTO, before: 0, after: 0 },
            children: [new d.TextRun({ text: lines[i] || " ", font: MONOFONT, size: 18 })],
          }),
        );
        i++;
      }
      blocks.push(new d.Paragraph({ spacing: { line: LINE_1, lineRule: AUTO, after: 120 }, children: [] }));
      i++;
      continue;
    }
    if (line.startsWith("![")) {
      blocks.push(...figure(line.trim()));
      i++;
      continue;
    }
    if (line.startsWith("Tabela:")) {
      const caption = line.trim();
      i++;
      while (!lines[i].trim()) i++;
      const tableLines = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) tableLines.push(lines[i++]);
      blocks.push(...table(caption, tableLines));
      continue;
    }
    if (line.startsWith("$$")) {
      blocks.push(equation(line.trim()));
      i++;
      continue;
    }
    if (/^(Fonte|Nota):/.test(line)) {
      blocks.push(small(line.trim(), { after: 240 }));
      i++;
      continue;
    }
    if (/^- /.test(line) || /^\d+\. /.test(line)) {
      const numbered = /^\d+\. /.test(line);
      listInstance++;
      while (i < lines.length && (numbered ? /^\d+\. /.test(lines[i]) : /^- /.test(lines[i]))) {
        const itemText = lines[i].replace(/^(- |\d+\. )/, "");
        blocks.push(
          new d.Paragraph({
            numbering: { reference: numbered ? "numerada" : "marcadores", level: 0, instance: listInstance },
            alignment: d.AlignmentType.JUSTIFIED,
            spacing: { line: LINE_15, lineRule: AUTO, after: 0 },
            children: runs(crossRefs(itemText)),
          }),
        );
        i++;
      }
      continue;
    }
    // Parágrafo: linhas seguidas até uma linha em branco ou outro bloco.
    const paragraph = [line.trim()];
    i++;
    while (i < lines.length && lines[i].trim() && !/^(#|!\[|Tabela:|\$\$|```|- |\d+\. |Fonte:|Nota:)/.test(lines[i])) {
      paragraph.push(lines[i].trim());
      i++;
    }
    blocks.push(body(paragraph.join(" ")));
  }
  return blocks;
}

const isReferences = (text) => text.startsWith("# REFERÊNCIAS");
function referenceBlocks(text) {
  const [title, ...rest] = text.replace(/\r/g, "").split("\n");
  const blocks = [headingParagraph(1, title.replace(/^#\s+/, "").trim())];
  for (const entry of rest.join("\n").split(/\n\s*\n/)) {
    if (!entry.trim()) continue;
    blocks.push(
      new d.Paragraph({
        alignment: d.AlignmentType.LEFT,
        spacing: { line: LINE_1, lineRule: AUTO, after: LINE_1 },
        children: runs(entry.replace(/\n/g, " ").trim()),
      }),
    );
  }
  return blocks;
}

// --- Elementos pré-textuais -----------------------------------------------------------------
const titleLine = `${meta.titulo}: ${meta.subtitulo}`.toUpperCase();

function cover() {
  return [
    ...meta.instituicao.map((line) => centered(line, { bold: true, line: LINE_15, lineRule: AUTO })),
    centered(meta.autor.toUpperCase(), { before: 2600 }),
    new d.Paragraph({
      alignment: d.AlignmentType.CENTER,
      spacing: { before: 3000, line: LINE_15, lineRule: AUTO },
      children: [
        new d.TextRun({ text: `${meta.titulo.toUpperCase()}:`, bold: true }),
        new d.TextRun({ text: ` ${meta.subtitulo.toUpperCase()}` }),
      ],
    }),
    centered(meta.local, { before: 4600 }),
    centered(meta.ano),
  ];
}

function nature(before) {
  return [
    new d.Paragraph({
      alignment: d.AlignmentType.JUSTIFIED,
      indent: { left: 8 * CM }, // natureza: do meio da mancha para a direita
      spacing: { line: LINE_1, lineRule: AUTO, before },
      children: runs(meta.natureza, { size: SMALL }),
    }),
    new d.Paragraph({
      alignment: d.AlignmentType.JUSTIFIED,
      indent: { left: 8 * CM }, // natureza: do meio da mancha para a direita
      spacing: { line: LINE_1, lineRule: AUTO, before: 240 },
      children: runs(meta.orientador, { size: SMALL }),
    }),
  ];
}

function titleBlock(before) {
  return new d.Paragraph({
    alignment: d.AlignmentType.CENTER,
    spacing: { before, line: LINE_15, lineRule: AUTO },
    children: [
      new d.TextRun({ text: `${meta.titulo.toUpperCase()}:`, bold: true }),
      new d.TextRun({ text: ` ${meta.subtitulo.toUpperCase()}` }),
    ],
  });
}

function titlePage() {
  return [
    centered(meta.autor.toUpperCase()),
    titleBlock(3600),
    ...nature(1400),
    centered(meta.local, { before: 4300 }),
    centered(meta.ano),
  ];
}

function approvalPage() {
  const signature = (text) => {
    const [name, institution] = text.split("\n");
    return [
      centered("_________________________________________", { before: 600, line: LINE_1, lineRule: AUTO }),
      centered(name, { line: LINE_1, lineRule: AUTO }),
      centered(institution, { line: LINE_1, lineRule: AUTO }),
    ];
  };
  return [
    new d.Paragraph({ children: [new d.TextRun({ text: meta.autor.toUpperCase() })], alignment: d.AlignmentType.CENTER, pageBreakBefore: true, spacing: { line: LINE_15, lineRule: AUTO } }),
    titleBlock(1200),
    ...nature(800),
    centered("Aprovado em: ____ de ______________ de ______.", { before: 600 }),
    centered("BANCA EXAMINADORA", { before: 400, bold: true }),
    ...meta.banca.flatMap(signature),
  ];
}

function abstractPage(title, text, keywordLabel, keywords) {
  return [
    preTitle(title),
    new d.Paragraph({
      alignment: d.AlignmentType.JUSTIFIED,
      spacing: { line: LINE_15, lineRule: AUTO },
      children: runs(text),
    }),
    new d.Paragraph({
      spacing: { line: LINE_15, lineRule: AUTO, before: LINE_15 },
      children: [
        new d.TextRun({ text: `${keywordLabel}: `, bold: true }),
        new d.TextRun({ text: `${keywords.join(". ")}.` }),
      ],
    }),
  ];
}

function acronyms() {
  return [
    preTitle("LISTA DE ABREVIATURAS E SIGLAS"),
    ...meta.siglas.map(
      ([acronym, meaning]) =>
        new d.Paragraph({
          tabStops: [{ type: d.TabStopType.LEFT, position: Math.round(2.5 * CM) }],
          indent: { left: Math.round(2.5 * CM), hanging: Math.round(2.5 * CM) },
          spacing: { line: LINE_15, lineRule: AUTO },
          children: [new d.TextRun({ text: `${acronym}\t${meaning}` })],
        }),
    ),
  ];
}

function tocBlock(title, options) {
  return [preTitle(title), new d.TableOfContents(title, { hyperlink: true, ...options })];
}

// --- Documento ------------------------------------------------------------------------------
const pageProperties = (extra = {}) => ({
  page: { size: PAGE, margin: { ...MARGIN, header: 2 * CM, footer: CM }, ...extra },
});

const pageNumberHeader = new d.Header({
  children: [
    new d.Paragraph({
      alignment: d.AlignmentType.RIGHT,
      children: [new d.TextRun({ children: [d.PageNumber.CURRENT], size: SMALL })],
    }),
  ],
});
const emptyHeader = new d.Header({ children: [new d.Paragraph({ children: [] })] });

const textual = chapters.flatMap((text) => (isReferences(text) ? referenceBlocks(text) : chapterBlocks(text)));

const doc = new d.Document({
  creator: meta.autor,
  title: `${meta.titulo}: ${meta.subtitulo}`,
  description: "Trabalho de Conclusão de Curso (padrão ABNT, NBR 14724)",
  features: { updateFields: true }, // o Word atualiza sumário e listas ao abrir
  styles: {
    default: {
      document: { run: { font: FONT, size: SIZE }, paragraph: { spacing: { line: LINE_15, lineRule: AUTO } } },
    },
    paragraphStyles: [
      {
        id: "Heading1",
        name: "Heading 1",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { font: FONT, size: SIZE, bold: true, color: "000000" },
        paragraph: { spacing: { before: 0, after: LINE_15, line: LINE_15, lineRule: AUTO }, pageBreakBefore: true, keepNext: true, outlineLevel: 0 },
      },
      {
        id: "Heading2",
        name: "Heading 2",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { font: FONT, size: SIZE, bold: false, color: "000000" },
        paragraph: { spacing: { before: LINE_15, after: LINE_15, line: LINE_15, lineRule: AUTO }, keepNext: true, outlineLevel: 1 },
      },
      {
        id: "Heading3",
        name: "Heading 3",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { font: FONT, size: SIZE, bold: true, color: "000000" },
        paragraph: { spacing: { before: LINE_15, after: LINE_15, line: LINE_15, lineRule: AUTO }, keepNext: true, outlineLevel: 2 },
      },
      // Sumário com a mesma aparência dos títulos (NBR 6027): capítulos e terciárias em negrito.
      ...[1, 2, 3, 4].map((level) => ({
        id: `TOC${level}`,
        name: `toc ${level}`,
        basedOn: "Normal",
        next: "Normal",
        run: { font: FONT, size: SIZE, bold: level === 1 || level === 3 ? true : undefined },
        paragraph: {
          indent: { left: level <= 3 ? (level - 1) * 284 : 0 },
          spacing: { before: 0, after: 0, line: LINE_15, lineRule: AUTO },
        },
      })),
      {
        id: "TituloPre",
        name: "TituloPre",
        basedOn: "Normal",
        next: "Normal",
        run: { font: FONT, size: SIZE, bold: true },
        paragraph: { alignment: d.AlignmentType.CENTER, spacing: { before: 0, after: LINE_15, line: LINE_15, lineRule: AUTO } },
      },
      {
        id: "LegendaFigura",
        name: "LegendaFigura",
        basedOn: "Normal",
        next: "Normal",
        run: { font: FONT, size: SMALL },
        paragraph: { alignment: d.AlignmentType.CENTER, keepNext: true, spacing: { before: 240, after: 60, line: LINE_1, lineRule: AUTO } },
      },
      {
        id: "LegendaTabela",
        name: "LegendaTabela",
        basedOn: "Normal",
        next: "Normal",
        run: { font: FONT, size: SMALL },
        paragraph: { alignment: d.AlignmentType.CENTER, keepNext: true, spacing: { before: 240, after: 60, line: LINE_1, lineRule: AUTO } },
      },
    ],
  },
  numbering: {
    config: [
      {
        reference: "marcadores",
        levels: [
          {
            level: 0,
            format: d.LevelFormat.BULLET,
            text: "–",
            alignment: d.AlignmentType.LEFT,
            style: { paragraph: { indent: { left: INDENT + 360, hanging: 360 } } },
          },
        ],
      },
      {
        reference: "numerada",
        levels: [
          {
            level: 0,
            format: d.LevelFormat.DECIMAL,
            text: "%1.",
            alignment: d.AlignmentType.LEFT,
            style: { paragraph: { indent: { left: INDENT + 360, hanging: 360 } } },
          },
        ],
      },
    ],
  },
  sections: [
    // Capa: não conta na paginação.
    { properties: pageProperties(), headers: { default: emptyHeader }, children: cover() },
    // Pré-textuais: contadas a partir da folha de rosto, sem número impresso.
    {
      properties: { ...pageProperties({ pageNumbers: { start: 1 } }) },
      headers: { default: emptyHeader },
      children: [
        ...titlePage(),
        ...approvalPage(),
        ...abstractPage("RESUMO", meta.resumo, "Palavras-chave", meta.palavras_chave),
        ...abstractPage("ABSTRACT", meta.abstract, "Keywords", meta.keywords),
        // Nível 4 (estilo "toc 4", sem negrito nem recuo): o sumário usa os níveis 1 a 3.
        ...tocBlock("LISTA DE FIGURAS", { stylesWithLevels: [new d.StyleLevel("LegendaFigura", LIST_LEVEL)] }),
        ...tocBlock("LISTA DE TABELAS", { stylesWithLevels: [new d.StyleLevel("LegendaTabela", LIST_LEVEL)] }),
        ...acronyms(),
        ...tocBlock("SUMÁRIO", { headingStyleRange: "1-3" }),
      ],
    },
    // Textuais e pós-textuais: número no canto superior direito, continuando a contagem.
    { properties: pageProperties(), headers: { default: pageNumberHeader }, children: textual },
  ],
});

d.Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(OUT, buffer);
  const stats = `figuras: ${counters.fig}, tabelas: ${counters.tab}, equações: ${counters.eq}`;
  console.log(`ok ${path.relative(ROOT, OUT)} (${(buffer.length / 1024).toFixed(0)} KB; ${stats})`);
});
