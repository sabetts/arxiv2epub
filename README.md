# arxiv-epub

Convert an arXiv **experimental HTML** paper ([arxiv.org/html/](https://info.arxiv.org/about/accessible_HTML.html))
into a reflowable EPUB 3, with figures, MathML equations, footnotes and the
bibliography bundled for offline reading.

## Install / run

The project is managed with [uv](https://docs.astral.sh/uv/).

```bash
uv run arxiv-epub 2402.08954
uv run arxiv-epub https://arxiv.org/abs/2402.08954 -o paper.epub
uv run arxiv-epub https://arxiv.org/html/2610.06805v1 -v
```

Or as a library:

```python
from arxiv_epub import convert

path = convert("2610.06805", output="paper.epub")
```

## What it does

1. **Fetch** — resolves an id or `abs`/`pdf`/`html` URL to the HTML rendering.
2. **Metadata** — merges the arXiv Atom API (title, authors, abstract, categories,
   DOI, date) with the HTML content.
3. **Parse** — drops the arXiv page chrome and turns each top-level `section`
   (including the bibliography and appendices) into a chapter.
4. **Images** — downloads every figure from arXiv and embeds it locally.
5. **Math** — keeps the native MathML and its embedded LaTeX annotation.
6. **Links** — rewrites citations and cross-references so they resolve inside
   the book.
7. **Assemble** — builds the EPUB (nested table of contents, text title page,
   metadata, stylesheet) with [EbookLib](https://github.com/aerkalov/ebooklib).

## CLI

```
arxiv-epub REFERENCE [-o OUTPUT] [--raw-dir DIR] [-f] [-v]
```

- `REFERENCE` — id (`2402.08954`, `2402.08954v2`, `hep-th/9901001`) or URL.
- `-o, --output` — output path (defaults to the sanitized paper title).
- `--raw-dir` — save the fetched HTML for debugging.
- `-f, --force` — overwrite the output file.
- `-v, --verbose` — progress output.

## Limitations

- Requires an HTML edition. arXiv generates HTML from LaTeX submitted
  December 2023 onward (and is backfilling the older corpus); conversion can
  still fail for some papers. When there is no HTML, the tool reports it rather
  than falling back to the PDF.
- Equations use MathML. This renders in Apple Books, Kobo, Calibre and most
  EPUB 3 readers, but **Kindle/Aldiko do not render MathML**.
- Very unusual LaTeXML tables or algorithm SVGs may need small styling tweaks.

## Development

```bash
uv run pytest -m "not network"   # unit tests
uv run pytest -m network         # end-to-end test against arxiv.org
```
