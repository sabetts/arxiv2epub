from __future__ import annotations

import html
from importlib.resources import files

from bs4 import Tag
from ebooklib import epub

from .arxiv import PaperMeta
from .htmlutil import build_id_map, namespace_mathml, rewrite_links
from .images import ImageResult
from .parse import Chapter, ParsedPaper

COLLECTION_COVER = "cover.xhtml"
NAV_FILE = "nav.xhtml"
CSS_FILE = "style.css"
DEFAULT_COLLECTION_TITLE = "arXiv collection"


def _style_css() -> str:
    return files("arxiv_epub").joinpath("assets").joinpath("style.css").read_text(encoding="utf-8")


def _chapter_filename(index: int, chapter: Chapter, prefix: str) -> str:
    classes = chapter.element.get("class") or []
    if "ltx_bibliography" in classes:
        name = "references.xhtml"
    elif "ltx_appendix" in classes:
        name = f"appendix{index:02d}.xhtml"
    else:
        name = f"ch{index:02d}.xhtml"
    return prefix + name


def assign_filenames(paper: ParsedPaper, prefix: str = "") -> None:
    for index, chapter in enumerate(paper.chapters, start=1):
        chapter.filename = _chapter_filename(index, chapter, prefix)


def prepare(paper: ParsedPaper, cover_file: str) -> None:
    """Apply namespaces and rewrite internal links to target chapter files."""
    for element in paper.front_matter:
        namespace_mathml(element)
    for chapter in paper.chapters:
        namespace_mathml(chapter.element)

    sources = [(cover_file, element) for element in paper.front_matter]
    sources += [(chapter.filename, chapter.element) for chapter in paper.chapters]
    id_map = build_id_map(sources)

    for element in paper.front_matter:
        rewrite_links(element, id_map, cover_file)
    for chapter in paper.chapters:
        rewrite_links(chapter.element, id_map, chapter.filename)


def _paper_cover_content(meta: PaperMeta, front_matter: list[Tag]) -> str:
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


def _collection_cover_content(title: str, papers: list[ParsedPaper], cover_files: list[str]) -> str:
    parts = ['<section class="titlepage collection">']
    parts.append(f"<h1>{html.escape(title)}</h1>")
    parts.append('<ol class="papers">')
    for paper, cover_file in zip(papers, cover_files):
        meta = paper.meta
        authors = ", ".join(meta.authors)
        parts.append(
            f'<li><a href="{html.escape(cover_file, quote=True)}">'
            f"{html.escape(meta.title or meta.ref)}</a>"
        )
        if authors:
            parts.append(f'<p class="authors">{html.escape(authors)}</p>')
        parts.append("</li>")
    parts.append("</ol></section>")
    return "".join(parts)


def _set_metadata(book: epub.EpubBook, papers: list[ParsedPaper], title: str | None) -> None:
    metas = [paper.meta for paper in papers]
    book.set_language("en")
    book.add_metadata("DC", "publisher", "arXiv")

    if len(metas) == 1:
        meta = metas[0]
        book.set_identifier(f"arxiv:{meta.ref}")
        book.set_title(title or meta.title or meta.ref)
        if meta.abstract:
            book.add_metadata("DC", "description", meta.abstract)
        if meta.published:
            book.add_metadata("DC", "date", meta.published[:10])
    else:
        book.set_identifier("urn:arxiv:collection:" + "-".join(meta.arxiv_id for meta in metas))
        book.set_title(title or DEFAULT_COLLECTION_TITLE)
        summary = "; ".join(f"{meta.title or meta.ref} (arXiv:{meta.ref})" for meta in metas)
        book.add_metadata("DC", "description", summary)

    seen: list[str] = []
    for meta in metas:
        for author in meta.authors:
            if author not in seen:
                seen.append(author)
                book.add_author(author)
        book.add_metadata("DC", "source", meta.html_url)
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


def _chapter_entries(paper: ParsedPaper) -> list:
    entries: list = []
    for chapter in paper.chapters:
        link = epub.Link(chapter.filename, chapter.title or chapter.uid, chapter.filename)
        children = _nav_children(chapter.nav, chapter.filename)
        entries.append((link, children) if children else link)
    return entries


def _build_toc(
    papers: list[ParsedPaper],
    cover_files: list[str],
    title: str,
    multi: bool,
) -> list:
    if not multi:
        toc: list = [epub.Link(COLLECTION_COVER, "Title Page", "cover")]
        toc.extend(_chapter_entries(papers[0]))
        return toc

    toc = [epub.Link(COLLECTION_COVER, title, "collection")]
    for paper, cover_file in zip(papers, cover_files):
        link = epub.Link(cover_file, paper.meta.title or paper.meta.ref, cover_file)
        toc.append((link, _chapter_entries(paper)))
    return toc


def build_book(
    papers: list[ParsedPaper],
    image_results: list[ImageResult],
    title: str | None = None,
) -> epub.EpubBook:
    multi = len(papers) > 1
    cover_files = []
    for index, paper in enumerate(papers, start=1):
        prefix = f"p{index}-" if multi else ""
        assign_filenames(paper, prefix)
        cover_files.append(prefix + COLLECTION_COVER)
    for paper, cover_file in zip(papers, cover_files):
        prepare(paper, cover_file)

    book = epub.EpubBook()
    _set_metadata(book, papers, title)

    css = epub.EpubItem(
        uid="style",
        file_name=CSS_FILE,
        media_type="text/css",
        content=_style_css().encode("utf-8"),
    )
    book.add_item(css)

    collection_title = title or DEFAULT_COLLECTION_TITLE
    collection_cover = None
    if multi:
        collection_cover = epub.EpubHtml(
            uid="collection",
            file_name=COLLECTION_COVER,
            title=collection_title,
            lang="en",
            content=_collection_cover_content(collection_title, papers, cover_files),
        )
        collection_cover.add_item(css)
        book.add_item(collection_cover)

    paper_parts: list[tuple[epub.EpubHtml, list[epub.EpubHtml]]] = []
    for index, (paper, cover_file) in enumerate(zip(papers, cover_files), start=1):
        cover = epub.EpubHtml(
            uid=f"cover{index}",
            file_name=cover_file,
            title=paper.meta.title or "Title Page",
            lang="en",
            content=_paper_cover_content(paper.meta, paper.front_matter),
        )
        cover.add_item(css)
        book.add_item(cover)

        chapter_items: list[epub.EpubHtml] = []
        for position, chapter in enumerate(paper.chapters, start=1):
            item = epub.EpubHtml(
                uid=f"p{index}c{position:02d}",
                file_name=chapter.filename,
                title=chapter.title or chapter.uid,
                lang="en",
                content=str(chapter.element),
            )
            item.add_item(css)
            book.add_item(item)
            chapter_items.append(item)
        paper_parts.append((cover, chapter_items))

    seen_images: set[str] = set()
    for image_result in image_results:
        for asset in image_result.assets.values():
            if asset.name in seen_images:
                continue
            seen_images.add(asset.name)
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

    book.toc = _build_toc(papers, cover_files, collection_title, multi)

    spine: list = []
    if collection_cover is not None:
        spine.append(collection_cover)
    spine.append(nav)
    for cover, chapter_items in paper_parts:
        spine.append(cover)
        spine.extend(chapter_items)
    book.spine = spine

    first_chapter = papers[0].chapters[0].filename
    book.guide = [
        {"type": "cover", "title": "Title Page", "href": COLLECTION_COVER},
        {"type": "toc", "title": "Contents", "href": NAV_FILE},
        {"type": "text", "title": "Beginning", "href": first_chapter},
    ]
    return book


def write_epub(
    papers: list[ParsedPaper],
    image_results: list[ImageResult],
    output_path: str,
    title: str | None = None,
) -> None:
    book = build_book(papers, image_results, title=title)
    epub.write_epub(output_path, book, {"epub3_landmark": True})
