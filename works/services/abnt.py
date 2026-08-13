"""Formatação bibliográfica em estilo ABNT NBR 6023:2025."""

from __future__ import annotations

from datetime import date
import re
import unicodedata
from urllib.parse import urlparse


MONTHS_PT = {
    1: "jan.", 2: "fev.", 3: "mar.", 4: "abr.", 5: "maio", 6: "jun.",
    7: "jul.", 8: "ago.", 9: "set.", 10: "out.", 11: "nov.", 12: "dez.",
}


def clean_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def sentence_title(value: str) -> str:
    value = clean_text(value).rstrip(". ")
    return value


def author_reference(name: str) -> str:
    """Converte um nome pessoal em SOBRENOME, Prenomes sem destruir nomes institucionais."""
    name = clean_text(name)
    if not name:
        return ""
    if "," in name:
        surname, given = (part.strip() for part in name.split(",", 1))
        return f"{surname.upper()}, {given}" if given else surname.upper()
    parts = name.split()
    if len(parts) == 1:
        return parts[0].upper()
    suffixes = {"filho", "neto", "júnior", "junior", "sobrinho"}
    if parts[-1].lower() in suffixes and len(parts) >= 3:
        surname_parts = parts[-2:]
        given = " ".join(parts[:-2])
    else:
        surname_parts = [parts[-1]]
        given = " ".join(parts[:-1])
    surname = " ".join(surname_parts).upper()
    return f"{surname}, {given}" if given else surname


def author_list(authors: list[str]) -> str:
    authors = [author_reference(item) for item in (authors or []) if clean_text(item)]
    if not authors:
        return "AUTORIA NÃO IDENTIFICADA"
    if len(authors) <= 3:
        return "; ".join(authors)
    return f"{authors[0]} et al."


def access_date_pt(value: date | None) -> str:
    value = value or date.today()
    return f"{value.day} {MONTHS_PT[value.month]} {value.year}"


def trusted_publication_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    allowed_domains = (
        "doi.org", "openalex.org", "crossref.org", "google.com",
        "googleapis.com", "openlibrary.org", "worldcat.org", "archive.org",
        "jstor.org", "cambridge.org", "oup.com", "sagepub.com",
        "springer.com", "wiley.com", "tandfonline.com", "degruyter.com",
    )
    if any(host == domain or host.endswith("." + domain) for domain in allowed_domains):
        return True
    # O SciELO usa domínios nacionais diferentes (scielo.br, scielo.cl etc.).
    return bool(re.fullmatch(r"(?:[a-z0-9-]+\.)*scielo\.[a-z]{2,}(?:\.[a-z]{2})?", host))


def format_reference(publication) -> str:
    authors = author_list(publication.authors)
    title = sentence_title(publication.title) or "Título não identificado"
    subtitle = sentence_title(publication.subtitle)
    full_title = f"{title}: {subtitle}" if subtitle else title
    year = str(publication.year or "[s.d.]")
    url = clean_text(publication.url)
    accessed = access_date_pt(getattr(publication, "access_date", None))
    source_type = publication.source_type

    if source_type in {"article", "chapter"} and publication.container_title:
        container = sentence_title(publication.container_title)
        details = []
        if publication.volume:
            details.append(f"v. {clean_text(publication.volume)}")
        if publication.issue:
            details.append(f"n. {clean_text(publication.issue)}")
        if publication.pages:
            details.append(f"p. {clean_text(publication.pages)}")
        details_text = ", ".join(details)
        base = f"{authors}. {full_title}. {container}"
        if details_text:
            base += f", {details_text}"
        base += f", {year}."
    else:
        edition = f" {clean_text(publication.edition)} ed." if publication.edition else ""
        city = clean_text(publication.city) or "[S. l.]"
        publisher = clean_text(publication.publisher) or "[s. n.]"
        base = f"{authors}. {full_title}.{edition} {city}: {publisher}, {year}."

    if publication.doi:
        doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", clean_text(publication.doi), flags=re.I)
        base += f" DOI: https://doi.org/{doi}."
    if url:
        base += f" Disponível em: {url}. Acesso em: {accessed}."
    return re.sub(r"\s+", " ", base).strip()


def citation_label(publication) -> str:
    """Forma autor-data conforme NBR 10520:2023 (sem caixa-alta integral)."""
    authors = publication.authors or []
    if not authors:
        lead = sentence_title(publication.title).split(":", 1)[0][:40]
    else:
        formatted = author_reference(authors[0]).split(",", 1)[0].title()
        lead = f"{formatted} et al." if len(authors) > 3 else formatted
    return f"({lead}, {publication.year or 's.d.'})"


def sort_key(publication) -> str:
    author = publication.authors[0] if publication.authors else publication.title
    normalized = unicodedata.normalize("NFKD", clean_text(author))
    return "".join(char for char in normalized if not unicodedata.combining(char)).casefold()
