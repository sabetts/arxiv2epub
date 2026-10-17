from arxiv_epub.arxiv import PaperMeta

SAMPLE = """
<html><body><article class="ltx_document">
<h1 class="ltx_title ltx_title_document">A Title</h1>
<div class="ltx_authors">
  <span class="ltx_creator"><span class="ltx_personname">Jane Doe</span></span>
  <span class="ltx_creator"><span class="ltx_personname">John Roe</span></span>
</div>
<div id="abstract1" class="ltx_abstract">
  <h6 class="ltx_title ltx_title_abstract">Abstract</h6>
  <p class="ltx_p">An abstract.</p>
</div>
<div class="ltx_para" id="p1"><p>Intro text.</p></div>
<section id="S1" class="ltx_section">
  <h2 class="ltx_title ltx_title_section"><span class="ltx_tag ltx_tag_section">1 </span>Intro</h2>
  <p>See <cite class="ltx_cite"><a href="#bib.bib1">[1]</a></cite>.</p>
  <section id="S1.SS1" class="ltx_subsection">
    <h3 class="ltx_title ltx_title_subsection">1.1 Sub</h3><p>x</p>
  </section>
</section>
<section id="bib" class="ltx_bibliography">
  <h2 class="ltx_title ltx_title_bibliography">References</h2>
  <ol class="ltx_biblist"><li id="bib.bib1" class="ltx_bibitem">
    <span class="ltx_tag ltx_tag_bibitem">[1]</span> Ref.
  </li></ol>
</section>
</article></body></html>
"""


def _parse():
    from arxiv_epub import build, parse

    paper = parse.parse_document(SAMPLE, PaperMeta(arxiv_id="2402.08954"))
    build.assign_filenames(paper)
    return paper


def test_metadata_from_html():
    paper = _parse()
    assert paper.meta.title == "A Title"
    assert paper.meta.authors == ["Jane Doe", "John Roe"]
    assert paper.meta.abstract == "Abstract An abstract."


def test_front_matter_and_chapters():
    paper = _parse()
    assert any("ltx_abstract" in (el.get("class") or []) for el in paper.front_matter)
    assert paper.front_matter[-1].get("id") == "p1"
    assert [c.uid for c in paper.chapters] == ["S1", "bib"]
    assert [c.filename for c in paper.chapters] == ["ch01.xhtml", "references.xhtml"]
    assert paper.chapters[0].title == "1 Intro"
    assert paper.chapters[0].nav[0].anchor == "S1.SS1"


def test_links_rewritten_across_files():
    from arxiv_epub import build

    paper = _parse()
    build.prepare(paper, "cover.xhtml")
    intro = str(paper.chapters[0].element)
    assert 'href="references.xhtml#bib.bib1"' in intro
