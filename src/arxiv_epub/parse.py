from __future__ import annotations

from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Tag

from .arxiv import PaperMeta
from .htmlutil import flatten_foreign_objects

STRIP_CLASSES = ("ltx_pagination", "ltx_role_newpage", "ltx_page_navbar", "ltx_TOC")
_HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")


class ParseError(RuntimeError):
    pass


@dataclass
class NavEntry:
    title: str
    anchor: str | None
    children: list["NavEntry"] = field(default_factory=list)


@dataclass
class Chapter:
    uid: str
    title: str
    element: Tag
    filename: str = ""
    nav: list[NavEntry] = field(default_factory=list)


@dataclass
class ParsedPaper:
    meta: PaperMeta
    front_matter: list[Tag]
    chapters: list[Chapter]


def clean_text(element: Tag) -> str:
    return " ".join(element.get_text(" ", strip=True).split())


def _strip_noise(root: Tag) -> None:
    for tag in root.find_all(["script", "style"]):
        tag.decompose()
    for cls in STRIP_CLASSES:
        for el in root.find_all(class_=cls):
            el.decompose()


def _heading(section: Tag) -> Tag | None:
    for heading in section.find_all(_HEADINGS, recursive=False):
        return heading
    return None


def _extract_authors(authors_el: Tag) -> list[str]:
    names: list[str] = []
    for span in authors_el.select("span.ltx_personname"):
        name = clean_text(span)
        if name and name not in names:
            names.append(name)
    return names


def _subnav(section: Tag) -> list[NavEntry]:
    entries: list[NavEntry] = []
    for sub in section.find_all("section", recursive=False):
        heading = _heading(sub)
        title = clean_text(heading) if heading else (sub.get("id") or "Section")
        entries.append(
            NavEntry(title=title, anchor=sub.get("id"), children=_subnav(sub))
        )
    return entries


def _make_chapter(section: Tag, index: int) -> Chapter:
    uid = section.get("id") or f"section-{index}"
    heading = _heading(section)
    title = clean_text(heading) if heading else uid
    return Chapter(uid=uid, title=title, element=section, nav=_subnav(section))


def parse_document(html: str, meta: PaperMeta) -> ParsedPaper:
    soup = BeautifulSoup(html, "lxml")
    article = soup.select_one("article.ltx_document")
    if article is None:
        raise ParseError("No LaTeXML article (article.ltx_document) found in the HTML")

    _strip_noise(article)
    flatten_foreign_objects(article)

    title_el = article.select_one("h1.ltx_title_document")
    authors_el = article.select_one(".ltx_authors")
    abstract_el = article.select_one(".ltx_abstract")

    if title_el is not None and not meta.title:
        meta.title = clean_text(title_el)
    if authors_el is not None and not meta.authors:
        meta.authors = _extract_authors(authors_el)
    if abstract_el is not None and not meta.abstract:
        meta.abstract = clean_text(abstract_el)

    front_matter: list[Tag] = []
    if abstract_el is not None and not _is_empty(abstract_el):
        front_matter.append(abstract_el.extract())

    chapters: list[Chapter] = []
    current: Chapter | None = None
    for child in list(article.children):
        if not isinstance(child, Tag):
            continue
        if child is title_el or child is authors_el or child is abstract_el:
            continue
        if child.name == "section":
            current = _make_chapter(child, len(chapters) + 1)
            chapters.append(current)
        elif current is None:
            front_matter.append(child.extract())
        else:
            current.element.append(child.extract())

    if not chapters:
        raise ParseError("No sections found in the article")

    return ParsedPaper(meta=meta, front_matter=front_matter, chapters=chapters)


def _is_empty(element: Tag) -> bool:
    return not element.get_text(strip=True) and element.find("img") is None
