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
    reference: str,
    output: str | None = None,
    raw_dir: str | None = None,
    force: bool = False,
    verbose: int = 0,
) -> Path:
    arxiv_id, version = arxiv.parse_reference(reference)
    session = arxiv.new_session()

    _log(verbose, 1, f"Fetching HTML for arXiv:{arxiv_id}{version or ''}")
    html_text, base_url = arxiv.fetch_html(arxiv_id, version, session)

    meta = PaperMeta(arxiv_id=arxiv_id, version=version)
    try:
        meta = arxiv.fetch_metadata(arxiv_id, session)
        meta.version = version
    except Exception as exc:
        _log(verbose, 1, f"Metadata API unavailable ({exc}); using HTML only")

    paper = parse.parse_document(html_text, meta)
    build.assign_filenames(paper)

    _log(verbose, 1, f"Paper: {paper.meta.title}")
    _log(verbose, 1, f"Sections: {len(paper.chapters)}")

    roots = list(paper.front_matter) + [chapter.element for chapter in paper.chapters]
    _log(verbose, 1, "Downloading images ...")
    image_result = images.fetch_images(roots, base_url, session)
    for warning in image_result.warnings:
        _log(verbose, 0, f"Warning: {warning}")
    _log(verbose, 1, f"Embedded {len(image_result.assets)} image(s)")

    out_path = Path(output) if output else Path(f"{sanitize_filename(paper.meta.title, arxiv_id)}.epub")
    if out_path.exists() and not force and output is None:
        out_path = out_path.with_name(f"{out_path.stem} ({paper.meta.ref}){out_path.suffix}")

    if raw_dir:
        raw_path = Path(raw_dir)
        raw_path.mkdir(parents=True, exist_ok=True)
        (raw_path / f"{paper.meta.ref}.html").write_text(html_text, encoding="utf-8")

    _log(verbose, 1, f"Writing {out_path}")
    build.write_epub(paper, image_result, str(out_path))
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="arxiv-epub",
        description="Convert an arXiv experimental HTML paper into an EPUB.",
    )
    parser.add_argument("reference", help="arXiv id (2402.08954) or URL (abs/pdf/html)")
    parser.add_argument("-o", "--output", help="Output .epub path")
    parser.add_argument("--raw-dir", help="Save the fetched HTML for debugging")
    parser.add_argument("-f", "--force", action="store_true", help="Overwrite the output file")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Verbose output")
    args = parser.parse_args(argv)

    try:
        out_path = convert(
            args.reference,
            output=args.output,
            raw_dir=args.raw_dir,
            force=args.force,
            verbose=args.verbose,
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
