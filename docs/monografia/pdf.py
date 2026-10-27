"""PDF de conferência da monografia, com sumário e listas atualizados (LibreOffice via UNO).

O .docx traz sumário e listas como campos do Word (blocos w:sdt), que o Word atualiza ao abrir.
O LibreOffice 7.4 importa esses blocos como texto, com páginas estimadas. Para o PDF ficar
exato, este script troca cada bloco por um índice nativo do LibreOffice (sumário pelos títulos;
listas pelos estilos de legenda), atualiza os índices duas vezes, para estabilizar a paginação,
e exporta o PDF. O .docx não é alterado. Uso (serviço docs):
    python3 docs/monografia/pdf.py docs/monografia/SACLA-monografia.docx data/monografia/
"""

import subprocess
import sys
import time
from pathlib import Path

import uno
from com.sun.star.beans import PropertyValue

PORT = 2002
CONNECT = f"uno:socket,host=localhost,port={PORT};urp;StarOffice.ComponentContext"
STARTUP_ATTEMPTS = 120  # meio segundo cada
INDEX_PASSES = 2
# Título do elemento pré-textual -> estilo de parágrafo de que o índice é feito (None = títulos).
INDEXES = {"LISTA DE FIGURAS": "LegendaFigura", "LISTA DE TABELAS": "LegendaTabela", "SUMÁRIO": None}
SUMMARY_LEVELS = 3
LIST_LEVEL = 4  # o mesmo nível de gerar.js: estilo "toc 4", sem negrito nem recuo


def prop(name, value):
    item = PropertyValue()
    item.Name, item.Value = name, value
    return item


def paragraphs(doc):
    enumeration = doc.Text.createEnumeration()
    while enumeration.hasMoreElements():
        element = enumeration.nextElement()
        if element.supportsService("com.sun.star.text.Paragraph"):
            yield element


def replace_indexes(doc):
    """Troca as entradas importadas de cada bloco por um índice do LibreOffice.

    O documento é percorrido de novo a cada bloco: apagar parágrafos invalida os anteriores.
    """
    for title, style in INDEXES.items():
        items = list(paragraphs(doc))
        position = next(
            i for i, item in enumerate(items)
            if item.ParaStyleName == "TituloPre" and item.getString().strip() == title
        )
        entries = []
        for following in items[position + 1:]:
            if not following.ParaStyleName.startswith("Contents"):
                break
            entries.append(following)
        if not entries:
            raise RuntimeError(f"bloco de índice não encontrado depois de {title}")
        cursor = doc.Text.createTextCursorByRange(entries[0].getStart())
        cursor.gotoRange(entries[-1].getEnd(), True)
        cursor.setString("")
        index = doc.createInstance("com.sun.star.text.ContentIndex")
        index.Title = ""
        if style is None:
            index.CreateFromOutline = True
            index.Level = SUMMARY_LEVELS
        else:
            index.CreateFromOutline = False
            index.CreateFromLevelParagraphStyles = True
            # Posição n-1 = nível n; o UNO exige a sequência de nomes tipada explicitamente.
            uno.invoke(index.LevelParagraphStyles, "replaceByIndex",
                       (LIST_LEVEL - 1, uno.Any("[]string", (style,))))
            index.Level = LIST_LEVEL
        doc.Text.insertTextContent(cursor, index, True)


def main(docx, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    # Trava deixada por uma execução interrompida: com ela, o LibreOffice não abre o arquivo.
    (docx.parent / f".~lock.{docx.name}#").unlink(missing_ok=True)
    office = subprocess.Popen(
        ["soffice", "--headless", "--invisible", "--nologo", "--norestore",
         f"--accept=socket,host=localhost,port={PORT};urp;"]
    )
    try:
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver", local)
        for _ in range(STARTUP_ATTEMPTS):
            try:
                context = resolver.resolve(CONNECT)
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("o LibreOffice não respondeu")
        desktop = context.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", context)
        doc = desktop.loadComponentFromURL(
            uno.systemPathToFileUrl(str(docx.resolve())), "_blank", 0, (prop("Hidden", True),))
        if doc is None:
            raise RuntimeError(f"o LibreOffice não abriu {docx}")
        replace_indexes(doc)
        indexes = doc.getDocumentIndexes()
        for _ in range(INDEX_PASSES):
            for i in range(indexes.getCount()):
                indexes.getByIndex(i).update()
        pdf = out_dir / (docx.stem + ".pdf")
        doc.storeToURL(uno.systemPathToFileUrl(str(pdf.resolve())),
                       (prop("FilterName", "writer_pdf_Export"),))
        pages, count = doc.getCurrentController().PageCount, indexes.getCount()
        doc.close(True)
        print(f"ok {pdf} ({pages} páginas, {count} índices atualizados)")
    finally:
        office.terminate()
        office.wait(timeout=30)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
