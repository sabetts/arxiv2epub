from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

from . import arxiv, build, images, parse
from .arxiv import ArxivError, PaperMeta

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(title: str, fallback: str = "paper") -> str:
    text = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    text = _INVALID.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip().strip(".")
    if not text:
        text = fallback
    return text[:120].rstrip()


def _log(verbose: int, level: int, message: str) -> None:
    if verbose >= level:
        print(message, file=sys.stderr)


def convert(
    references: str | list[str],
    output: str | None = None,
    raw_dir: str | None = None,
    force: bool = False,
    verbose: int = 0,
    title: str | None = None,
) -> Path:
    if isinstance(references, str):
        references = [references]
    if not references:
        raise ArxivError("No arXiv references given")

    session = arxiv.new_session()
    papers: list[parse.ParsedPaper] = []
    image_results: list[images.ImageResult] = []
    raw_path = Path(raw_dir) if raw_dir else None
    if raw_path:
        raw_path.mkdir(parents=True, exist_ok=True)

    for reference in references:
        arxiv_id, version = arxiv.parse_reference(reference)
        _log(verbose, 1, f"Fetching HTML for arXiv:{arxiv_id}{version or ''}")
        html_text, base_url = arxiv.fetch_html(arxiv_id, version, session)

        meta = PaperMeta(arxiv_id=arxiv_id, version=version)
        try:
            meta = arxiv.fetch_metadata(arxiv_id, session)
            meta.version = version
        except Exception as exc:
            _log(verbose, 1, f"Metadata API unavailable ({exc}); using HTML only")

        paper = parse.parse_document(html_text, meta)
        _log(verbose, 1, f"Paper: {paper.meta.title} ({len(paper.chapters)} sections)")

        roots = list(paper.front_matter) + [chapter.element for chapter in paper.chapters]
        _log(verbose, 1, "Downloading images ...")
        image_result = images.fetch_images(roots, base_url, session)
        for warning in image_result.warnings:
            _log(verbose, 0, f"Warning: {warning}")
        _log(verbose, 1, f"Embedded {len(image_result.assets)} image(s)")

        papers.append(paper)
        image_results.append(image_result)

        if raw_path:
            (raw_path / f"{paper.meta.ref}.html").write_text(html_text, encoding="utf-8")

    multi = len(papers) > 1
    if title:
        default_name = title
    elif multi:
        default_name = build.DEFAULT_COLLECTION_TITLE
    else:
        default_name = papers[0].meta.title or papers[0].meta.ref

    out_path = Path(output) if output else Path(f"{sanitize_filename(default_name, 'arXiv collection')}.epub")
    if out_path.exists() and not force and output is None:
        suffix = str(len(papers)) if multi else papers[0].meta.ref
        out_path = out_path.with_name(f"{out_path.stem} ({suffix}){out_path.suffix}")

    _log(verbose, 1, f"Writing {out_path}")
    build.write_epub(papers, image_results, str(out_path), title=title)
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="arxiv-epub",
        description="Convert one or more arXiv experimental HTML papers into an EPUB.",
    )
    parser.add_argument(
        "references",
        nargs="+",
        metavar="REFERENCE",
        help="arXiv ids (2402.08954) or URLs (abs/pdf/html); multiple become one book",
    )
    parser.add_argument("-o", "--output", help="Output .epub path")
    parser.add_argument("-t", "--title", help="Title for a multi-paper collection")
    parser.add_argument("--raw-dir", help="Save the fetched HTML for debugging")
    parser.add_argument("-f", "--force", action="store_true", help="Overwrite the output file")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Verbose output")
    args = parser.parse_args(argv)

    try:
        out_path = convert(
            args.references,
            output=args.output,
            raw_dir=args.raw_dir,
            force=args.force,
            verbose=args.verbose,
            title=args.title,
        )
    except ArxivError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except parse.ParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
