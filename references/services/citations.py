import re
import unicodedata
from dataclasses import dataclass

from ..models import Reference
from .people import initials


@dataclass
class CitationItem:
    reference: Reference
    text: str
    number: int | None = None


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().rstrip(". ")


def full_title(reference) -> str:
    title = clean(reference.title)
    subtitle = clean(reference.subtitle)
    return f"{title}: {subtitle}" if subtitle else title


def _person_abnt(person: dict) -> str:
    if person.get("literal"):
        return clean(person["literal"]).upper()
    family = clean(person.get("family")).upper()
    given = clean(person.get("given"))
    return ", ".join(filter(None, [family, given]))


def authors_abnt(people: list[dict]) -> str:
    if not people:
        return ""
    rendered = [_person_abnt(person) for person in people[:3]]
    if len(people) > 3:
        return f"{rendered[0]} et al."
    return "; ".join(rendered)


def _person_apa(person: dict) -> str:
    if person.get("literal"):
        return clean(person["literal"])
    family = clean(person.get("family"))
    given_initials = initials(person.get("given", ""), spaced=True)
    return ", ".join(filter(None, [family, given_initials]))


def authors_apa(people: list[dict]) -> str:
    if not people:
        return ""
    rendered = [_person_apa(person) for person in people[:20]]
    if len(people) > 20:
        return ", ".join(rendered[:19]) + ", … " + rendered[-1]
    if len(rendered) == 1:
        return rendered[0]
    return ", ".join(rendered[:-1]) + ", & " + rendered[-1]


def _person_vancouver(person: dict) -> str:
    if person.get("literal"):
        return clean(person["literal"])
    raw_initials = initials(person.get("given", "")).replace(".", "")
    return " ".join(filter(None, [clean(person.get("family")), raw_initials]))


def authors_vancouver(people: list[dict]) -> str:
    if not people:
        return ""
    rendered = [_person_vancouver(person) for person in people[:6]]
    suffix = ", et al" if len(people) > 6 else ""
    return ", ".join(rendered) + suffix


def _person_given_family(person: dict) -> str:
    if person.get("literal"):
        return clean(person["literal"])
    return " ".join(
        filter(None, [clean(person.get("given")), clean(person.get("family"))])
    )


def authors_chicago(people: list[dict]) -> str:
    if not people:
        return ""
    first = people[0]
    if first.get("literal"):
        rendered = clean(first["literal"])
    else:
        rendered = ", ".join(
            filter(None, [clean(first.get("family")), clean(first.get("given"))])
        )
    if len(people) == 2:
        rendered += ", and " + _person_given_family(people[1])
    elif len(people) > 2:
        rendered += ", et al."
    return rendered


def authors_ieee(people: list[dict]) -> str:
    if not people:
        return ""
    rendered = []
    for person in people[:6]:
        if person.get("literal"):
            rendered.append(clean(person["literal"]))
        else:
            rendered.append(
                " ".join(
                    filter(
                        None,
                        [
                            initials(person.get("given", ""), spaced=True),
                            clean(person.get("family")),
                        ],
                    )
                )
            )
    if len(people) > 6:
        return rendered[0] + " et al."
    if len(rendered) == 1:
        return rendered[0]
    return ", ".join(rendered[:-1]) + " and " + rendered[-1]


def date_abnt(value) -> str:
    if not value:
        return ""
    months = [
        "jan.",
        "fev.",
        "mar.",
        "abr.",
        "maio",
        "jun.",
        "jul.",
        "ago.",
        "set.",
        "out.",
        "nov.",
        "dez.",
    ]
    return f"{value.day} {months[value.month - 1]} {value.year}"


def doi_url(doi: str) -> str:
    return f"https://doi.org/{clean(doi)}" if doi else ""


def join_sentences(parts: list[str]) -> str:
    return " ".join(f"{clean(part)}." for part in parts if clean(part))


def format_abnt(ref: Reference) -> str:
    author = authors_abnt(ref.authors)
    title = full_title(ref)
    year = clean(ref.year) or "[s. d.]"
    lead = f"{author}. {title}." if author else f"{title.upper()}."

    if ref.reference_type == Reference.Type.JOURNAL_ARTICLE:
        details = []
        if ref.container_title:
            details.append(clean(ref.container_title))
        if ref.volume:
            details.append(f"v. {clean(ref.volume)}")
        if ref.issue:
            details.append(f"n. {clean(ref.issue)}")
        if ref.pages:
            details.append(f"p. {clean(ref.pages)}")
        details.append(year)
        result = f"{lead} {', '.join(details)}."
    elif ref.reference_type == Reference.Type.BOOK:
        edition = f" {clean(ref.edition)}. ed." if ref.edition else ""
        publication = ": ".join(
            filter(None, [clean(ref.publisher_place), clean(ref.publisher)])
        )
        result = f"{lead}{edition} {publication + ', ' if publication else ''}{year}."
    elif ref.reference_type == Reference.Type.BOOK_CHAPTER:
        editors = authors_abnt(ref.editors)
        in_part = (
            "In: "
            + (f"{editors} (org.). " if editors else "")
            + clean(ref.container_title)
        )
        publication = ": ".join(
            filter(None, [clean(ref.publisher_place), clean(ref.publisher)])
        )
        page_part = f", p. {clean(ref.pages)}" if ref.pages else ""
        result = f"{lead} {in_part}. {publication + ', ' if publication else ''}{year}{page_part}."
    elif ref.reference_type == Reference.Type.THESIS:
        institution = ", ".join(
            filter(None, [clean(ref.publisher), clean(ref.publisher_place)])
        )
        result = f"{lead} {year}. {clean(ref.notes) + '. ' if ref.notes else ''}{institution}."
    elif ref.reference_type == Reference.Type.CONFERENCE:
        event = clean(ref.container_title)
        publication = ": ".join(
            filter(None, [clean(ref.publisher_place), clean(ref.publisher)])
        )
        result = (
            f"{lead} In: {event}. {publication + ', ' if publication else ''}{year}."
        )
    elif ref.reference_type == Reference.Type.WEBSITE:
        site = clean(ref.publisher or ref.container_title)
        result = f"{lead} {site + ', ' if site else ''}{year}."
    else:
        publication = ": ".join(
            filter(None, [clean(ref.publisher_place), clean(ref.publisher)])
        )
        result = f"{lead} {publication + ', ' if publication else ''}{year}."

    if ref.doi:
        result += f" DOI: {doi_url(ref.doi)}."
    url = clean(ref.url or ref.source_url)
    if url and (not ref.doi or "doi.org" not in url):
        result += f" Disponível em: {url}."
    if url and ref.access_date:
        result += f" Acesso em: {date_abnt(ref.access_date)}."
    return re.sub(r"\s+", " ", result).strip()


def format_apa(ref: Reference) -> str:
    author = authors_apa(ref.authors) or full_title(ref)
    year = clean(ref.year) or "n.d."
    title = full_title(ref)
    if ref.reference_type == Reference.Type.JOURNAL_ARTICLE:
        details = clean(ref.container_title)
        if ref.volume:
            details += f", {clean(ref.volume)}"
        if ref.issue:
            details += f"({clean(ref.issue)})"
        if ref.pages:
            details += f", {clean(ref.pages)}"
        core = f"{author} ({year}). {title}. {details}."
    elif ref.reference_type == Reference.Type.BOOK:
        edition = f" ({clean(ref.edition)} ed.)" if ref.edition else ""
        core = f"{author} ({year}). {title}{edition}. {clean(ref.publisher)}."
    elif ref.reference_type == Reference.Type.BOOK_CHAPTER:
        editors = authors_apa(ref.editors)
        in_part = (
            f"In {editors + ' (Eds.), ' if editors else ''}{clean(ref.container_title)}"
        )
        pages = f" (pp. {clean(ref.pages)})" if ref.pages else ""
        core = f"{author} ({year}). {title}. {in_part}{pages}. {clean(ref.publisher)}."
    elif ref.reference_type == Reference.Type.THESIS:
        core = f"{author} ({year}). {title} [{clean(ref.notes) or 'Thesis'}, {clean(ref.publisher)}]."
    else:
        site = clean(ref.publisher or ref.container_title)
        core = f"{author} ({year}). {title}. {site}."
    link = doi_url(ref.doi) or clean(ref.url or ref.source_url)
    return re.sub(r"\s+", " ", f"{core} {link}".strip())


def format_vancouver(ref: Reference) -> str:
    author = authors_vancouver(ref.authors)
    title = full_title(ref)
    lead = f"{author}. {title}." if author else f"{title}."
    year = clean(ref.year)
    if ref.reference_type == Reference.Type.JOURNAL_ARTICLE:
        journal = clean(ref.container_title)
        publication = year
        if ref.volume:
            publication += f";{clean(ref.volume)}"
        if ref.issue:
            publication += f"({clean(ref.issue)})"
        if ref.pages:
            publication += f":{clean(ref.pages)}"
        result = f"{lead} {journal}. {publication}."
    elif ref.reference_type == Reference.Type.BOOK:
        edition = f" {clean(ref.edition)} ed." if ref.edition else ""
        place_publisher = ": ".join(
            filter(None, [clean(ref.publisher_place), clean(ref.publisher)])
        )
        result = f"{lead}{edition} {place_publisher}; {year}."
    elif ref.reference_type == Reference.Type.BOOK_CHAPTER:
        editors = authors_vancouver(ref.editors)
        result = f"{lead} In: {editors + ', editors. ' if editors else ''}{clean(ref.container_title)}. {clean(ref.publisher_place)}: {clean(ref.publisher)}; {year}. p. {clean(ref.pages)}."
    else:
        result = f"{lead} {clean(ref.publisher or ref.container_title)}; {year}."
    if ref.doi:
        result += f" doi: {clean(ref.doi)}."
    url = clean(ref.url or ref.source_url)
    if url and not ref.doi:
        result += f" Available from: {url}."
    if url and ref.access_date:
        result += f" [cited {ref.access_date:%Y %b %d}]."
    return re.sub(r"\s+", " ", result).strip()


def format_chicago(ref: Reference) -> str:
    author = authors_chicago(ref.authors) or full_title(ref)
    year = clean(ref.year) or "n.d."
    title = full_title(ref)
    if ref.reference_type == Reference.Type.JOURNAL_ARTICLE:
        details = clean(ref.container_title)
        if ref.volume:
            details += f" {clean(ref.volume)}"
        if ref.issue:
            details += f", no. {clean(ref.issue)}"
        if ref.pages:
            details += f": {clean(ref.pages)}"
        core = f"{author}. {year}. “{title}.” {details}."
    elif ref.reference_type == Reference.Type.BOOK:
        place = f"{clean(ref.publisher_place)}: " if ref.publisher_place else ""
        core = f"{author}. {year}. {title}. {place}{clean(ref.publisher)}."
    else:
        core = f"{author}. {year}. “{title}.” {clean(ref.publisher or ref.container_title)}."
    link = doi_url(ref.doi) or clean(ref.url or ref.source_url)
    return re.sub(r"\s+", " ", f"{core} {link}." if link else core).strip()


def format_harvard(ref: Reference) -> str:
    author = authors_apa(ref.authors).replace(", & ", " & ") or full_title(ref)
    year = clean(ref.year) or "no date"
    title = full_title(ref)
    if ref.reference_type == Reference.Type.JOURNAL_ARTICLE:
        details = f"'{title}', {clean(ref.container_title)}"
        if ref.volume:
            details += f", vol. {clean(ref.volume)}"
        if ref.issue:
            details += f", no. {clean(ref.issue)}"
        if ref.pages:
            details += f", pp. {clean(ref.pages)}"
        core = f"{author} ({year}) {details}."
    elif ref.reference_type == Reference.Type.BOOK:
        publication = ", ".join(
            filter(None, [clean(ref.publisher), clean(ref.publisher_place)])
        )
        core = f"{author} ({year}) {title}, {publication}."
    else:
        core = f"{author} ({year}) '{title}', {clean(ref.publisher or ref.container_title)}."
    link = doi_url(ref.doi) or clean(ref.url or ref.source_url)
    return re.sub(
        r"\s+", " ", f"{core} Available at: {link}." if link else core
    ).strip()


def format_ieee(ref: Reference) -> str:
    author = authors_ieee(ref.authors)
    title = full_title(ref)
    lead = f'{author}, “{title},"' if author else f'“{title},"'
    if ref.reference_type == Reference.Type.JOURNAL_ARTICLE:
        parts = [clean(ref.container_title)]
        if ref.volume:
            parts.append(f"vol. {clean(ref.volume)}")
        if ref.issue:
            parts.append(f"no. {clean(ref.issue)}")
        if ref.pages:
            parts.append(f"pp. {clean(ref.pages)}")
        if ref.year:
            parts.append(clean(ref.year))
        core = f"{lead} {', '.join(filter(None, parts))}."
    elif ref.reference_type == Reference.Type.BOOK:
        core = f"{author}, {title}. {clean(ref.publisher_place)}: {clean(ref.publisher)}, {clean(ref.year)}."
    else:
        core = (
            f"{lead} {clean(ref.publisher or ref.container_title)}, {clean(ref.year)}."
        )
    if ref.doi:
        core += f" doi: {clean(ref.doi)}."
    elif ref.url or ref.source_url:
        core += f" [Online]. Available: {clean(ref.url or ref.source_url)}."
    return re.sub(r"\s+", " ", core).strip()


FORMATTERS = {
    "abnt": format_abnt,
    "apa": format_apa,
    "vancouver": format_vancouver,
    "chicago": format_chicago,
    "harvard": format_harvard,
    "ieee": format_ieee,
}
NUMERIC_STYLES = {"vancouver", "ieee"}


def sort_key(ref: Reference):
    people = ref.authors or []
    if people:
        value = people[0].get("family") or people[0].get("literal") or ref.title
    else:
        value = ref.title
    normalized = (
        unicodedata.normalize("NFKD", clean(value))
        .encode("ascii", "ignore")
        .decode()
        .casefold()
    )
    return normalized, clean(ref.year), clean(ref.title).casefold()


def generate_citations(references, style: str) -> list[CitationItem]:
    formatter = FORMATTERS.get(style, format_abnt)
    refs = list(references)
    if style not in NUMERIC_STYLES:
        refs.sort(key=sort_key)
    items = []
    for index, reference in enumerate(refs, start=1):
        number = index if style in NUMERIC_STYLES else None
        text = formatter(reference)
        if number:
            prefix = f"{number}." if style == "vancouver" else f"[{number}]"
            text = f"{prefix} {text}"
        items.append(CitationItem(reference=reference, text=text, number=number))
    return items


def emphasis_terms(reference: Reference) -> list[str]:
    if reference.reference_type in {Reference.Type.BOOK, Reference.Type.THESIS}:
        terms = [full_title(reference)]
    elif reference.reference_type in {
        Reference.Type.JOURNAL_ARTICLE,
        Reference.Type.BOOK_CHAPTER,
        Reference.Type.CONFERENCE,
    }:
        terms = [clean(reference.container_title)]
    elif reference.reference_type == Reference.Type.WEBSITE:
        terms = [full_title(reference)]
    else:
        terms = []
    return sorted({term for term in terms if term}, key=len, reverse=True)


def split_emphasis(text: str, reference: Reference) -> list[tuple[str, bool]]:
    segments = [(text, False)]
    for term in emphasis_terms(reference):
        updated = []
        for value, emphasized in segments:
            if emphasized or term not in value:
                updated.append((value, emphasized))
                continue
            pieces = value.split(term)
            for index, piece in enumerate(pieces):
                if piece:
                    updated.append((piece, False))
                if index < len(pieces) - 1:
                    updated.append((term, True))
        segments = updated
    return segments
