from arxiv_epub import build, parse
from arxiv_epub.arxiv import PaperMeta
from arxiv_epub.images import ImageResult


def _html(title: str) -> str:
    return f"""
<html><body><article class="ltx_document">
<h1 class="ltx_title ltx_title_document">{title}</h1>
<div class="ltx_authors">
  <span class="ltx_creator"><span class="ltx_personname">Jane Doe</span></span>
</div>
<div id="abstract1" class="ltx_abstract">
  <h6 class="ltx_title ltx_title_abstract">Abstract</h6>
  <p class="ltx_p">An abstract.</p>
</div>
<section id="S1" class="ltx_section">
  <h2 class="ltx_title ltx_title_section"><span class="ltx_tag ltx_tag_section">1 </span>Intro</h2>
  <p>See <cite class="ltx_cite"><a href="#bib.bib1">[1]</a></cite>.</p>
</section>
<section id="bib" class="ltx_bibliography">
  <h2 class="ltx_title ltx_title_bibliography">References</h2>
  <ol class="ltx_biblist"><li id="bib.bib1" class="ltx_bibitem">
    <span class="ltx_tag ltx_tag_bibitem">[1]</span> Ref.
  </li></ol>
</section>
</article></body></html>
"""


def _paper(title: str, arxiv_id: str) -> parse.ParsedPaper:
    return parse.parse_document(_html(title), PaperMeta(arxiv_id=arxiv_id))


def _filenames(book) -> list[str]:
    return [item.file_name for item in book.get_items() if getattr(item, "file_name", "")]


def test_multi_paper_filenames_are_unique_and_prefixed():
    first = _paper("First Paper", "1111.1111")
    second = _paper("Second Paper", "2222.2222")
    book = build.build_book(
        [first, second],
        [ImageResult(assets={}, warnings=[]), ImageResult(assets={}, warnings=[])],
        title="My Collection",
    )

    files = _filenames(book)
    assert len(files) == len(set(files)), files
    for expected in (
        "cover.xhtml",
        "p1-cover.xhtml",
        "p2-cover.xhtml",
        "p1-ch01.xhtml",
        "p2-ch01.xhtml",
        "p1-references.xhtml",
        "p2-references.xhtml",
    ):
        assert expected in files, expected


def test_multi_paper_links_stay_within_their_paper():
    first = _paper("First Paper", "1111.1111")
    second = _paper("Second Paper", "2222.2222")
    build.build_book(
        [first, second],
        [ImageResult(assets={}, warnings=[]), ImageResult(assets={}, warnings=[])],
    )
    assert 'href="p1-references.xhtml#bib.bib1"' in str(first.chapters[0].element)
    assert 'href="p2-references.xhtml#bib.bib1"' in str(second.chapters[0].element)


def test_multi_paper_toc_and_spine():
    first = _paper("First Paper", "1111.1111")
    second = _paper("Second Paper", "2222.2222")
    book = build.build_book(
        [first, second],
        [ImageResult(assets={}, warnings=[]), ImageResult(assets={}, warnings=[])],
        title="My Collection",
    )
    assert book.title == "My Collection"
    assert book.toc[0].href == "cover.xhtml"
    grouped = [entry for entry in book.toc if isinstance(entry, tuple)]
    assert len(grouped) == 2
    cover_item = next(item for item in book.get_items() if item.file_name == "cover.xhtml")
    assert book.spine[0] is cover_item


def test_single_paper_toc_unchanged():
    paper = _paper("Only Paper", "3333.3333")
    book = build.build_book([paper], [ImageResult(assets={}, warnings=[])])
    assert not any(isinstance(entry, tuple) for entry in book.toc)
    assert book.toc[0].href == "cover.xhtml"
    assert _filenames(book).count("ch01.xhtml") == 1
