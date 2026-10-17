from __future__ import annotations

from collections.abc import Iterable

from bs4 import Tag

MATHML_NS = "http://www.w3.org/1998/Math/MathML"
SVG_NS = "http://www.w3.org/2000/svg"

_BLOCK_TAGS = {"table", "div", "p", "ol", "ul", "section", "figure", "blockquote", "pre"}


def namespace_mathml(root: Tag) -> None:
    """Declare namespaces so MathML/SVG survive XHTML serialization."""
    for math in root.find_all("math"):
        if not math.has_attr("xmlns"):
            math["xmlns"] = MATHML_NS
    for svg in root.find_all("svg"):
        if not svg.has_attr("xmlns"):
            svg["xmlns"] = SVG_NS


def flatten_foreign_objects(root: Tag) -> int:
    """Replace SVG <foreignObject> boxes (which readers do not render) with HTML.

    LaTeXML wraps TikZ nodes, \\fbox output and minipages in SVG foreignObject
    elements. Most e-readers show only the empty frame, so promote the embedded
    markup back into the document flow. Returns the number of SVGs converted.
    """
    converted = 0
    for svg in root.find_all("svg"):
        foreign_objects = svg.find_all(["foreignobject", "foreignObject"])
        if not foreign_objects:
            continue

        parts: list = []
        for foreign_object in foreign_objects:
            content = foreign_object.find(class_="ltx_foreignobject_content") or foreign_object
            parts.extend(content.contents)

        is_block = any(getattr(part, "name", None) in _BLOCK_TAGS for part in parts)
        replacement = root.new_tag("div" if is_block else "span")
        replacement["class"] = "ltx_foreignobject_flatten"
        for part in parts:
            replacement.append(part.extract())
        svg.replace_with(replacement)
        converted += 1
    return converted


def build_id_map(sources: Iterable[tuple[str, Tag]]) -> dict[str, str]:
    """Map every element id (including container ids) to its chapter filename."""
    mapping: dict[str, str] = {}
    for filename, root in sources:
        container_id = root.get("id")
        if container_id:
            mapping.setdefault(container_id, filename)
        for element in root.find_all(attrs={"id": True}):
            element_id = element.get("id")
            if element_id:
                mapping.setdefault(element_id, filename)
    return mapping


def rewrite_links(root: Tag, id_map: dict[str, str], current_file: str) -> None:
    for anchor in root.find_all("a", href=True):
        href = anchor["href"]
        if not href.startswith("#"):
            continue
        target = href[1:]
        target_file = id_map.get(target)
        if target_file and target_file != current_file:
            anchor["href"] = f"{target_file}#{target}"
