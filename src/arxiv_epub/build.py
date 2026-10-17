from __future__ import annotations

import html
from importlib.resources import files

from bs4 import Tag
from ebooklib import epub

from .arxiv import PaperMeta
from .htmlutil import build_id_map, namespace_mathml, rewrite_links
from .images import ImageResult
from .parse import Chapter, ParsedPaper

COVER_FILE = "cover.xhtml"
NAV_FILE = "nav.xhtml"
CSS_FILE = "style.css"


def _style_css() -> str:
    return files("arxiv_epub").joinpath("assets").joinpath("style.css").read_text(encoding="utf-8")


def assign_filenames(paper: ParsedPaper) -> None:
    for index, chapter in enumerate(paper.chapters, start=1):
        classes = chapter.element.get("class") or []
        if "ltx_bibliography" in classes:
            chapter.filename = "references.xhtml"
        elif "ltx_appendix" in classes:
            chapter.filename = f"appendix{index:02d}.xhtml"
        else:
            chapter.filename = f"ch{index:02d}.xhtml"


def prepare(paper: ParsedPaper) -> None:
    """Apply namespaces and rewrite internal links to target chapter files."""
    for element in paper.front_matter:
        namespace_mathml(element)
    for chapter in paper.chapters:
        namespace_mathml(chapter.element)

    sources = [(COVER_FILE, element) for element in paper.front_matter]
    sources += [(chapter.filename, chapter.element) for chapter in paper.chapters]
    id_map = build_id_map(sources)

    for element in paper.front_matter:
        rewrite_links(element, id_map, COVER_FILE)
    for chapter in paper.chapters:
        rewrite_links(chapter.element, id_map, chapter.filename)


def _cover_content(meta: PaperMeta, front_matter: list[Tag]) -> str:
    parts = ['<section class="titlepage">']
    parts.append(f"<h1>{html.escape(meta.title or meta.ref)}</h1>")
    if meta.authors:
        parts.append(f'<p class="authors">{html.escape(", ".join(meta.authors))}</p>')
    parts.append(
        f'<p class="source"><a href="{html.escape(meta.abs_url, quote=True)}">{html.escape(meta.ref)}</a></p>'
    )
    parts.extend(str(element) for element in front_matter)
    parts.append("</section>")
    return "".join(parts)


def _set_metadata(book: epub.EpubBook, meta: PaperMeta) -> None:
    book.set_identifier(f"arxiv:{meta.ref}")
    book.set_title(meta.title or meta.ref)
    book.set_language("en")
    for author in meta.authors:
        book.add_author(author)
    if meta.abstract:
        book.add_metadata("DC", "description", meta.abstract)
    book.add_metadata("DC", "publisher", "arXiv")
    book.add_metadata("DC", "source", meta.html_url)
    if meta.published:
        book.add_metadata("DC", "date", meta.published[:10])
    if meta.doi:
        book.add_metadata("DC", "identifier", meta.doi)
    if meta.journal_ref:
        book.add_metadata("DC", "source", meta.journal_ref)
    for category in meta.categories:
        book.add_metadata("DC", "subject", category)


def _nav_children(entries: list, filename: str) -> list:
    result: list = []
    for entry in entries:
        if entry.anchor:
            href = f"{filename}#{entry.anchor}"
            link = epub.Link(href, entry.title, href)
            if entry.children:
                result.append((link, _nav_children(entry.children, filename)))
            else:
                result.append(link)
        elif entry.children:
            result.append((epub.Section(entry.title), _nav_children(entry.children, filename)))
    return result


def _build_toc(paper: ParsedPaper) -> list:
    toc: list = [epub.Link(COVER_FILE, "Title Page", "cover")]
    for chapter in paper.chapters:
        link = epub.Link(chapter.filename, chapter.title or chapter.uid, chapter.filename)
        children = _nav_children(chapter.nav, chapter.filename)
        toc.append((link, children) if children else link)
    return toc


def build_book(paper: ParsedPaper, image_result: ImageResult) -> epub.EpubBook:
    assign_filenames(paper)
    prepare(paper)

    book = epub.EpubBook()
    _set_metadata(book, paper.meta)

    css = epub.EpubItem(
        uid="style",
        file_name=CSS_FILE,
        media_type="text/css",
        content=_style_css().encode("utf-8"),
    )
    book.add_item(css)

    cover = epub.EpubHtml(
        uid="cover",
        file_name=COVER_FILE,
        title="Title Page",
        lang="en",
        content=_cover_content(paper.meta, paper.front_matter),
    )
    cover.add_item(css)
    book.add_item(cover)

    chapter_items = []
    for index, chapter in enumerate(paper.chapters, start=1):
        item = epub.EpubHtml(
            uid=f"chapter{index:02d}",
            file_name=chapter.filename,
            title=chapter.title or chapter.uid,
            lang="en",
            content=str(chapter.element),
        )
        item.add_item(css)
        book.add_item(item)
        chapter_items.append(item)

    for asset in image_result.assets.values():
        book.add_item(
            epub.EpubImage(
                uid=f"img-{asset.name}",
                file_name=f"images/{asset.name}",
                media_type=asset.media_type,
                content=asset.content,
            )
        )

    nav = epub.EpubNav()
    nav.add_item(css)
    book.add_item(nav)

    book.toc = _build_toc(paper)
    book.spine = [cover, nav, *chapter_items]
    book.guide = [
        {"type": "cover", "title": "Title Page", "href": COVER_FILE},
        {"type": "toc", "title": "Contents", "href": NAV_FILE},
        {"type": "text", "title": "Beginning", "href": paper.chapters[0].filename},
    ]
    return book


def write_epub(paper: ParsedPaper, image_result: ImageResult, output_path: str) -> None:
    book = build_book(paper, image_result)
    epub.write_epub(output_path, book, {"epub3_landmark": True})
