from arxiv_epub.cli import sanitize_filename
from arxiv_epub.images import _is_downloadable, _safe_name, _sniff_media_type


def test_sanitize_filename():
    assert sanitize_filename("H-JEPA: End-to-End Learning") == "H-JEPA End-to-End Learning"
    assert sanitize_filename("a/b\\c:d*e?f") == "a b c d e f"
    assert sanitize_filename("") == "paper"


def test_safe_name_is_stable_and_sanitized():
    name = _safe_name("https://arxiv.org/html/2402.08954v1/My Figure (1).png", "image/png")
    assert name.endswith("My_Figure_1_.png")
    assert name == _safe_name("https://arxiv.org/html/2402.08954v1/My Figure (1).png", "image/png")
    assert name != _safe_name("https://arxiv.org/html/2402.08954v1/other.png", "image/png")


def test_sniff_media_type():
    assert _sniff_media_type(b"\x89PNG\r\n\x1a\n", None, "x") == "image/png"
    assert _sniff_media_type(b"\xff\xd8\xff\xe0", None, "x") == "image/jpeg"
    assert _sniff_media_type(b"%PDF-1.7", "application/octet-stream", "x") == "application/pdf"
    assert _sniff_media_type(b"abc", "image/webp; charset=binary", "x") == "image/webp"


def test_is_downloadable():
    assert _is_downloadable("https://arxiv.org/html/2402.08954v1/a.png", "arxiv.org")
    assert _is_downloadable("https://export.arxiv.org/a.png", "arxiv.org")
    assert not _is_downloadable("https://example.com/a.png", "arxiv.org")
    assert not _is_downloadable("data:image/png;base64,AAAA", "arxiv.org")
