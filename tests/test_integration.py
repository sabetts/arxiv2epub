import zipfile
from pathlib import Path

import pytest

from arxiv_epub import convert

pytestmark = pytest.mark.network


def test_convert_end_to_end(tmp_path):
    out = convert("https://arxiv.org/html/2610.06805v1", output=str(tmp_path / "paper.epub"), verbose=0)
    assert out.exists()

    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert names[0] == "mimetype"
        assert z.read("mimetype") == b"application/epub+zip"
        assert any(n.endswith("content.opf") for n in names)
        assert any(n.endswith("nav.xhtml") for n in names)
        chapters = [n for n in names if n.endswith(".xhtml")]
        assert len(chapters) > 5
        math = sum(z.read(n).count(b"<math") for n in chapters)
        assert math > 100
        assert any(b"www.w3.org/1998/Math/MathML" in z.read(n) for n in chapters)
