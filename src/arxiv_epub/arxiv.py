from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import requests

HTML_URL = "https://arxiv.org/html/{ref}"
API_URL = "https://export.arxiv.org/api/query"
USER_AGENT = "arxiv-epub/0.1 (+https://github.com/; mailto:arxiv-epub@example.com)"
ATOM = "{http://www.w3.org/2005/Atom}"

NEW_ID = re.compile(r"^(?P<id>\d{4}\.\d{4,5})(?P<ver>v\d+)?$")
OLD_ID = re.compile(r"^(?P<id>[a-zA-Z-]+(?:\.[A-Z]{2})?/\d{7})(?P<ver>v\d+)?$")
_URL_MARKERS = ("/abs/", "/pdf/", "/html/")


class ArxivError(RuntimeError):
    pass


class NoHTMLError(ArxivError):
    pass


@dataclass
class PaperMeta:
    arxiv_id: str
    version: str | None = None
    title: str = ""
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    categories: list[str] = field(default_factory=list)
    primary_category: str | None = None
    published: str | None = None
    doi: str | None = None
    journal_ref: str | None = None
    license: str | None = None

    @property
    def ref(self) -> str:
        return f"{self.arxiv_id}{self.version or ''}"

    @property
    def abs_url(self) -> str:
        return f"https://arxiv.org/abs/{self.ref}"

    @property
    def html_url(self) -> str:
        return HTML_URL.format(ref=self.ref)


def parse_reference(value: str) -> tuple[str, str | None]:
    """Return (arxiv_id, version) from an id, abs/pdf/html URL, or DOI-ish string."""
    text = value.strip()
    if not text:
        raise ArxivError("Empty arXiv reference")

    if "//" in text or text.startswith("arxiv.org"):
        for marker in _URL_MARKERS:
            if marker in text:
                text = text.split(marker, 1)[1]
                break
        else:
            text = urlsplit(text).path if "//" in text else text
            text = text.rstrip("/").rsplit("/", 1)[-1]
        text = text.split("?", 1)[0].split("#", 1)[0]
        if text.lower().endswith(".pdf"):
            text = text[:-4]

    for pattern in (NEW_ID, OLD_ID):
        match = pattern.match(text)
        if match:
            return match.group("id"), match.group("ver")

    raise ArxivError(f"Could not parse arXiv reference: {value!r}")


def new_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def fetch_html(
    arxiv_id: str,
    version: str | None = None,
    session: requests.Session | None = None,
    timeout: float = 60.0,
) -> tuple[str, str]:
    """Download the experimental HTML rendering. Returns (html_text, base_url)."""
    session = session or new_session()
    ref = f"{arxiv_id}{version or ''}"
    url = HTML_URL.format(ref=ref)
    response = session.get(url, timeout=timeout, allow_redirects=True)
    if response.status_code == 404:
        raise NoHTMLError(
            f"No HTML edition for arXiv:{ref}. arXiv generates HTML only for LaTeX "
            "submissions from December 2023 onward, and some conversions fail."
        )
    response.raise_for_status()
    html = response.text
    if "ltx_document" not in html:
        raise NoHTMLError(f"Unexpected HTML response for arXiv:{ref} (no LaTeXML article found)")
    return html, response.url


def fetch_metadata(
    arxiv_id: str,
    session: requests.Session | None = None,
    timeout: float = 30.0,
) -> PaperMeta:
    """Best-effort metadata from the arXiv Atom API (used to enrich the HTML content)."""
    session = session or new_session()
    response = session.get(API_URL, params={"id_list": arxiv_id}, timeout=timeout)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    entry = root.find(f"{ATOM}entry")
    meta = PaperMeta(arxiv_id=arxiv_id)
    if entry is None:
        return meta

    def _text(tag: str) -> str | None:
        node = entry.find(f"{ATOM}{tag}")
        return " ".join(node.text.split()) if node is not None and node.text else None

    meta.title = _text("title") or ""
    meta.abstract = _text("summary") or ""
    meta.published = _text("published")
    meta.journal_ref = _text("journal_ref")
    meta.doi = entry.findtext("{http://arxiv.org/schemas/atom}doi")
    meta.license = entry.findtext("{http://arxiv.org/schemas/atom}license")

    meta.authors = [
        name.text.strip()
        for author in entry.findall(f"{ATOM}author")
        if (name := author.find(f"{ATOM}name")) is not None and name.text
    ]
    meta.categories = [
        cat.get("term") for cat in entry.findall(f"{ATOM}category") if cat.get("term")
    ]
    primary = entry.find("{http://arxiv.org/schemas/atom}primary_category")
    if primary is not None:
        meta.primary_category = primary.get("term")
    return meta
