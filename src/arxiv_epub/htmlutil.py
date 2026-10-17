from __future__ import annotations

from collections.abc import Iterable

from bs4 import Tag

MATHML_NS = "http://www.w3.org/1998/Math/MathML"
SVG_NS = "http://www.w3.org/2000/svg"


def namespace_mathml(root: Tag) -> None:
    """Declare namespaces so MathML/SVG survive XHTML serialization."""
    for math in root.find_all("math"):
        if not math.has_attr("xmlns"):
            math["xmlns"] = MATHML_NS
    for svg in root.find_all("svg"):
        if not svg.has_attr("xmlns"):
            svg["xmlns"] = SVG_NS


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
