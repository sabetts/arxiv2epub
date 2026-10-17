from __future__ import annotations

import hashlib
import mimetypes
import posixpath
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import Tag

IMAGE_DIR = "images"
ALLOWED_HOST_SUFFIX = "arxiv.org"

EXT_BY_TYPE = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
    "image/webp": ".webp",
    "image/avif": ".avif",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
    "application/pdf": ".pdf",
}

_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"%PDF-", "application/pdf"),
)

_SANITIZE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass
class ImageAsset:
    name: str
    media_type: str
    content: bytes


@dataclass
class ImageResult:
    assets: dict[str, ImageAsset]
    warnings: list[str]


def _safe_name(url: str, media_type: str) -> str:
    base = posixpath.basename(urlsplit(url).path) or "image"
    base = _SANITIZE.sub("_", base).strip("._") or "image"
    if "." not in base:
        base += EXT_BY_TYPE.get(media_type, ".bin")
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    return f"{digest}-{base}"


def _sniff_media_type(content: bytes, content_type: str | None, url: str) -> str:
    if content_type:
        cleaned = content_type.split(";", 1)[0].strip().lower()
        if cleaned.startswith("image/") or cleaned == "application/pdf":
            return cleaned
    for signature, media_type in _SIGNATURES:
        if content.startswith(signature):
            return media_type
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    guessed, _ = mimetypes.guess_type(urlsplit(url).path)
    return guessed or "application/octet-stream"


def _is_downloadable(url: str, base_host: str) -> bool:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return False
    host = parts.hostname or ""
    if host == base_host or host == ALLOWED_HOST_SUFFIX:
        return True
    return host.endswith("." + ALLOWED_HOST_SUFFIX)


def fetch_images(
    roots: list[Tag],
    base_url: str,
    session: requests.Session,
    timeout: float = 60.0,
) -> ImageResult:
    assets: dict[str, ImageAsset] = {}
    warnings: list[str] = []
    by_url: dict[str, str] = {}
    base_host = urlsplit(base_url).hostname or "arxiv.org"

    for root in roots:
        for img in root.find_all("img"):
            src = (img.get("src") or "").strip()
            if not src or src.startswith("data:"):
                continue
            absolute = urljoin(base_url, src)
            if absolute in by_url:
                img["src"] = f"{IMAGE_DIR}/{by_url[absolute]}"
                continue
            if not _is_downloadable(absolute, base_host):
                continue
            try:
                response = session.get(absolute, timeout=timeout)
                response.raise_for_status()
            except requests.RequestException as exc:
                warnings.append(f"Could not download image {absolute}: {exc}")
                continue

            media_type = _sniff_media_type(response.content, response.headers.get("Content-Type"), absolute)
            name = _safe_name(absolute, media_type)
            assets[name] = ImageAsset(name=name, media_type=media_type, content=response.content)
            by_url[absolute] = name
            img["src"] = f"{IMAGE_DIR}/{name}"

    return ImageResult(assets=assets, warnings=warnings)
