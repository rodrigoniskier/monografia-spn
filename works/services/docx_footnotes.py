"""Insere notas de rodapé verdadeiras em um DOCX gerado pelo aplicativo."""

from __future__ import annotations

from copy import deepcopy
from io import BytesIO
import re
import zipfile

from lxml import etree


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKGREL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NS = {"w": W_NS, "rel": PKGREL_NS, "ct": CT_NS}

REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes"
CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"
TOKEN_RE = re.compile(
    r"\[\[FN:([0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})\]\]",
    re.I,
)


def _qname(namespace: str, tag: str) -> str:
    return f"{{{namespace}}}{tag}"


def _xml_bytes(root) -> bytes:
    return etree.tostring(
        root, xml_declaration=True, encoding="UTF-8", standalone="yes"
    )


def _next_rid(rels_root) -> str:
    highest = 0
    for relationship in rels_root.findall(_qname(PKGREL_NS, "Relationship")):
        match = re.fullmatch(r"rId(\d+)", relationship.get("Id") or "")
        if match:
            highest = max(highest, int(match.group(1)))
    return f"rId{highest + 1}"


def _ensure_relationship(rels_root) -> None:
    for relationship in rels_root.findall(_qname(PKGREL_NS, "Relationship")):
        if relationship.get("Type") == REL_TYPE:
            relationship.set("Target", "footnotes.xml")
            return
    relationship = etree.SubElement(
        rels_root, _qname(PKGREL_NS, "Relationship")
    )
    relationship.set("Id", _next_rid(rels_root))
    relationship.set("Type", REL_TYPE)
    relationship.set("Target", "footnotes.xml")


def _ensure_content_type(content_types_root) -> None:
    part_name = "/word/footnotes.xml"
    for override in content_types_root.findall(_qname(CT_NS, "Override")):
        if override.get("PartName") == part_name:
            override.set("ContentType", CONTENT_TYPE)
            return
    override = etree.SubElement(content_types_root, _qname(CT_NS, "Override"))
    override.set("PartName", part_name)
    override.set("ContentType", CONTENT_TYPE)


def _ensure_settings(settings_root) -> None:
    footnote_properties = settings_root.find("w:footnotePr", namespaces=NS)
    if footnote_properties is None:
        footnote_properties = etree.SubElement(
            settings_root, _qname(W_NS, "footnotePr")
        )
    desired = (("numFmt", "decimal"), ("numStart", "1"), ("numRestart", "continuous"))
    for tag, value in desired:
        element = footnote_properties.find(f"w:{tag}", namespaces=NS)
        if element is None:
            element = etree.SubElement(footnote_properties, _qname(W_NS, tag))
        element.set(_qname(W_NS, "val"), value)


def _font_properties(parent, *, reference_style=False):
    properties = etree.SubElement(parent, _qname(W_NS, "rPr"))
    if reference_style:
        style = etree.SubElement(properties, _qname(W_NS, "rStyle"))
        style.set(_qname(W_NS, "val"), "FootnoteReference")
    fonts = etree.SubElement(properties, _qname(W_NS, "rFonts"))
    for attribute in ("ascii", "hAnsi", "eastAsia"):
        fonts.set(_qname(W_NS, attribute), "Times New Roman")
    size = etree.SubElement(properties, _qname(W_NS, "sz"))
    size.set(_qname(W_NS, "val"), "20")
    size_complex = etree.SubElement(properties, _qname(W_NS, "szCs"))
    size_complex.set(_qname(W_NS, "val"), "20")
    return properties


def _separator(notes_root, note_id: str, tag: str) -> None:
    note = etree.SubElement(notes_root, _qname(W_NS, "footnote"))
    note.set(_qname(W_NS, "id"), note_id)
    note.set(
        _qname(W_NS, "type"),
        "separator" if tag == "separator" else "continuationSeparator",
    )
    paragraph = etree.SubElement(note, _qname(W_NS, "p"))
    run = etree.SubElement(paragraph, _qname(W_NS, "r"))
    etree.SubElement(run, _qname(W_NS, tag))


def _append_note(notes_root, note_id: int, text: str) -> None:
    note = etree.SubElement(notes_root, _qname(W_NS, "footnote"))
    note.set(_qname(W_NS, "id"), str(note_id))
    paragraph = etree.SubElement(note, _qname(W_NS, "p"))
    properties = etree.SubElement(paragraph, _qname(W_NS, "pPr"))
    style = etree.SubElement(properties, _qname(W_NS, "pStyle"))
    style.set(_qname(W_NS, "val"), "FootnoteText")
    spacing = etree.SubElement(properties, _qname(W_NS, "spacing"))
    spacing.set(_qname(W_NS, "before"), "0")
    spacing.set(_qname(W_NS, "after"), "0")
    spacing.set(_qname(W_NS, "line"), "240")
    spacing.set(_qname(W_NS, "lineRule"), "auto")
    alignment = etree.SubElement(properties, _qname(W_NS, "jc"))
    alignment.set(_qname(W_NS, "val"), "both")

    reference_run = etree.SubElement(paragraph, _qname(W_NS, "r"))
    _font_properties(reference_run, reference_style=True)
    etree.SubElement(reference_run, _qname(W_NS, "footnoteRef"))

    text_run = etree.SubElement(paragraph, _qname(W_NS, "r"))
    _font_properties(text_run)
    text_node = etree.SubElement(text_run, _qname(W_NS, "t"))
    text_node.set(_qname(XML_NS, "space"), "preserve")
    text_node.text = " " + str(text or "").strip()


def _reference_run(note_id: int):
    run = etree.Element(_qname(W_NS, "r"))
    properties = etree.SubElement(run, _qname(W_NS, "rPr"))
    style = etree.SubElement(properties, _qname(W_NS, "rStyle"))
    style.set(_qname(W_NS, "val"), "FootnoteReference")
    reference = etree.SubElement(run, _qname(W_NS, "footnoteReference"))
    reference.set(_qname(W_NS, "id"), str(note_id))
    return run


def _text_run(text: str, original_run):
    run = etree.Element(_qname(W_NS, "r"))
    original_properties = original_run.find("w:rPr", namespaces=NS)
    if original_properties is not None:
        run.append(deepcopy(original_properties))
    text_node = etree.SubElement(run, _qname(W_NS, "t"))
    if text[:1].isspace() or text[-1:].isspace():
        text_node.set(_qname(XML_NS, "space"), "preserve")
    text_node.text = text
    return run


def _replace_markers(document_root, notes_by_marker: dict[str, str]):
    ordered_notes: list[str] = []
    used_markers: set[str] = set()
    for text_node in list(document_root.xpath(".//w:t", namespaces=NS)):
        raw_text = text_node.text or ""
        matches = list(TOKEN_RE.finditer(raw_text))
        if not matches:
            continue
        original_run = text_node.getparent()
        while original_run is not None and original_run.tag != _qname(W_NS, "r"):
            original_run = original_run.getparent()
        if original_run is None:
            raise ValueError("Um marcador de nota está fora de uma execução de texto válida.")
        parent = original_run.getparent()
        insertion_index = parent.index(original_run) + 1
        text_node.text = raw_text[: matches[0].start()]
        cursor = matches[0].start()
        for match in matches:
            marker = match.group(1).lower()
            if marker in used_markers:
                raise ValueError("Uma mesma nota foi usada mais de uma vez no documento.")
            if marker not in notes_by_marker:
                raise ValueError("O documento contém uma nota sem referência correspondente.")
            if match.start() > cursor:
                run = _text_run(raw_text[cursor:match.start()], original_run)
                parent.insert(insertion_index, run)
                insertion_index += 1
            note_id = len(ordered_notes) + 1
            parent.insert(insertion_index, _reference_run(note_id))
            insertion_index += 1
            ordered_notes.append(notes_by_marker[marker])
            used_markers.add(marker)
            cursor = match.end()
        if cursor < len(raw_text):
            parent.insert(insertion_index, _text_run(raw_text[cursor:], original_run))
    remaining = "".join(
        text or "" for text in document_root.xpath(".//w:t/text()", namespaces=NS)
    )
    if TOKEN_RE.search(remaining):
        raise ValueError("Nem todos os marcadores de nota puderam ser convertidos.")
    return ordered_notes


def inject_footnotes(docx_data: bytes, notes_by_marker: dict[str, str]) -> BytesIO:
    """Converte marcadores [[FN:uuid]] em notas nativas e retorna novo DOCX."""
    normalized_notes = {
        str(marker).lower(): str(text or "").strip()
        for marker, text in notes_by_marker.items()
    }
    with zipfile.ZipFile(BytesIO(docx_data), "r") as source:
        document_root = etree.fromstring(source.read("word/document.xml"))
        ordered_notes = _replace_markers(document_root, normalized_notes)
        if not ordered_notes:
            output = BytesIO(docx_data)
            output.seek(0)
            return output

        notes_root = etree.Element(
            _qname(W_NS, "footnotes"), nsmap={"w": W_NS, "r": R_NS}
        )
        _separator(notes_root, "-1", "separator")
        _separator(notes_root, "0", "continuationSeparator")
        for note_id, text in enumerate(ordered_notes, start=1):
            _append_note(notes_root, note_id, text)

        relationships_root = etree.fromstring(
            source.read("word/_rels/document.xml.rels")
        )
        _ensure_relationship(relationships_root)
        content_types_root = etree.fromstring(source.read("[Content_Types].xml"))
        _ensure_content_type(content_types_root)
        settings_root = etree.fromstring(source.read("word/settings.xml"))
        _ensure_settings(settings_root)

        replacements = {
            "word/document.xml": _xml_bytes(document_root),
            "word/footnotes.xml": _xml_bytes(notes_root),
            "word/_rels/document.xml.rels": _xml_bytes(relationships_root),
            "[Content_Types].xml": _xml_bytes(content_types_root),
            "word/settings.xml": _xml_bytes(settings_root),
        }
        if "word/_rels/footnotes.xml.rels" not in source.namelist():
            footnote_rels = etree.Element(
                _qname(PKGREL_NS, "Relationships"),
                nsmap={None: PKGREL_NS},
            )
            replacements["word/_rels/footnotes.xml.rels"] = _xml_bytes(
                footnote_rels
            )
        existing = set(source.namelist())
        output = BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as destination:
            for info in source.infolist():
                destination.writestr(info, replacements.get(info.filename, source.read(info.filename)))
            for name, data in replacements.items():
                if name not in existing:
                    destination.writestr(name, data)
    output.seek(0)
    return output
