import pytest

from arxiv_epub.arxiv import ArxivError, parse_reference


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2402.08954", ("2402.08954", None)),
        ("2402.08954v2", ("2402.08954", "v2")),
        ("https://arxiv.org/abs/2402.08954", ("2402.08954", None)),
        ("https://arxiv.org/abs/2402.08954v3", ("2402.08954", "v3")),
        ("https://arxiv.org/pdf/2402.08954v1", ("2402.08954", "v1")),
        ("https://arxiv.org/html/2610.06805v1", ("2610.06805", "v1")),
        ("http://arxiv.org/pdf/2402.08954v1.pdf", ("2402.08954", "v1")),
        ("hep-th/9901001", ("hep-th/9901001", None)),
        ("https://arxiv.org/abs/hep-th/9901001v2", ("hep-th/9901001", "v2")),
    ],
)
def test_parse_reference(value, expected):
    assert parse_reference(value) == expected


def test_parse_reference_invalid():
    with pytest.raises(ArxivError):
        parse_reference("not-a-paper")
