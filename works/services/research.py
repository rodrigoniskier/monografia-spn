"""Metabuscador de publicações reais em catálogos acadêmicos públicos."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import date
import logging
import re
import unicodedata
from urllib.parse import quote

from django.conf import settings
import requests

from .abnt import trusted_publication_url


logger = logging.getLogger("works.research")
TIMEOUT = (4, 10)
MAX_RESULTS_PER_PROVIDER = 7
USER_AGENT = "MonografiaSPN/1.0 (pesquisa academica; mailto:{})"


@dataclass
class ResearchResult:
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    source_type: str = "other"
    url: str = ""
    provider: str = ""
    subtitle: str = ""
    city: str = ""
    publisher: str = ""
    edition: str = ""
    container_title: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    doi: str = ""
    isbn: str = ""
    language: str = ""
    relevance: float = 0.0

    def serializable(self):
        return asdict(self)


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT.format(settings.RESEARCH_CONTACT_EMAIL),
        "Accept": "application/json",
    })
    return session


def _year(value) -> int | None:
    try:
        result = int(value)
        return result if 1400 <= result <= 2200 else None
    except (TypeError, ValueError):
        return None


def _tokenize(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", str(value or "").casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    stop = {"a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "na", "no", "para", "por", "um", "uma", "the", "of", "and", "in", "to"}
    return {token for token in re.findall(r"[a-z0-9]{3,}", normalized) if token not in stop}


def _score(query: str, result: ResearchResult) -> float:
    query_tokens = _tokenize(query)
    result_tokens = _tokenize(" ".join([result.title, result.subtitle, result.container_title, " ".join(result.authors)]))
    if not query_tokens:
        return 0
    overlap = len(query_tokens & result_tokens) / len(query_tokens)
    authority = 0.12 if result.doi or result.isbn else 0.04
    metadata = 0.06 if result.authors and result.year else 0
    return round(min(1, overlap + authority + metadata), 3)


def _crossref(query: str) -> list[ResearchResult]:
    params = {
        "query.bibliographic": query,
        "rows": MAX_RESULTS_PER_PROVIDER,
        "select": "DOI,title,subtitle,author,published-print,published-online,issued,container-title,publisher,type,volume,issue,page,language,URL",
        "mailto": settings.RESEARCH_CONTACT_EMAIL,
    }
    response = _session().get("https://api.crossref.org/works", params=params, timeout=TIMEOUT)
    response.raise_for_status()
    results = []
    type_map = {"journal-article": "article", "book": "book", "book-chapter": "chapter", "dissertation": "thesis"}
    for item in response.json().get("message", {}).get("items", []):
        title = " ".join(item.get("title") or []).strip()
        if not title:
            continue
        authors = []
        for author in item.get("author") or []:
            name = " ".join(filter(None, [author.get("given"), author.get("family")])).strip()
            if name:
                authors.append(name)
        parts = ((item.get("published-print") or item.get("published-online") or item.get("issued") or {}).get("date-parts") or [[]])
        doi = str(item.get("DOI") or "").strip()
        url = f"https://doi.org/{doi}" if doi else str(item.get("URL") or "").replace("http://", "https://")
        if not trusted_publication_url(url):
            continue
        results.append(ResearchResult(
            title=title,
            subtitle=" ".join(item.get("subtitle") or []).strip(),
            authors=authors,
            year=_year(parts[0][0] if parts and parts[0] else None),
            source_type=type_map.get(item.get("type"), "other"),
            url=url,
            provider="Crossref",
            publisher=str(item.get("publisher") or ""),
            container_title=" ".join(item.get("container-title") or []).strip(),
            volume=str(item.get("volume") or ""), issue=str(item.get("issue") or ""),
            pages=str(item.get("page") or ""), doi=doi,
            language=str(item.get("language") or ""),
        ))
    return results


def _openalex(query: str) -> list[ResearchResult]:
    params = {"search": query, "per-page": MAX_RESULTS_PER_PROVIDER, "mailto": settings.RESEARCH_CONTACT_EMAIL}
    response = _session().get("https://api.openalex.org/works", params=params, timeout=TIMEOUT)
    response.raise_for_status()
    results = []
    type_map = {"article": "article", "book": "book", "book-chapter": "chapter", "dissertation": "thesis"}
    for item in response.json().get("results", []):
        title = str(item.get("display_name") or "").strip()
        primary = item.get("primary_location") or {}
        source = primary.get("source") or {}
        doi = str(item.get("doi") or "").replace("https://doi.org/", "")
        url = str(item.get("doi") or item.get("id") or "").replace("http://", "https://")
        if not title or not trusted_publication_url(url):
            continue
        authors = [
            str((entry.get("author") or {}).get("display_name") or "").strip()
            for entry in item.get("authorships") or []
        ]
        results.append(ResearchResult(
            title=title, authors=[name for name in authors if name],
            year=_year(item.get("publication_year")),
            source_type=type_map.get(item.get("type"), "other"),
            url=url, provider="OpenAlex", doi=doi,
            container_title=str(source.get("display_name") or ""),
            volume=str((item.get("biblio") or {}).get("volume") or ""),
            issue=str((item.get("biblio") or {}).get("issue") or ""),
            pages="-".join(filter(None, [str((item.get("biblio") or {}).get("first_page") or ""), str((item.get("biblio") or {}).get("last_page") or "")])),
            language=str(item.get("language") or ""),
        ))
    return results


def _google_books(query: str) -> list[ResearchResult]:
    params = {"q": query, "maxResults": MAX_RESULTS_PER_PROVIDER, "printType": "books"}
    response = _session().get("https://www.googleapis.com/books/v1/volumes", params=params, timeout=TIMEOUT)
    response.raise_for_status()
    results = []
    for item in response.json().get("items", []):
        info = item.get("volumeInfo") or {}
        title = str(info.get("title") or "").strip()
        identifiers = info.get("industryIdentifiers") or []
        isbn = next((entry.get("identifier") for entry in identifiers if entry.get("type") in {"ISBN_13", "ISBN_10"}), "")
        url = str(info.get("infoLink") or item.get("selfLink") or "").replace("http://", "https://")
        if not title or not trusted_publication_url(url):
            continue
        published = str(info.get("publishedDate") or "")
        results.append(ResearchResult(
            title=title, subtitle=str(info.get("subtitle") or ""),
            authors=[str(name) for name in info.get("authors") or []],
            year=_year(published[:4]), source_type="book", url=url,
            provider="Google Books", publisher=str(info.get("publisher") or ""),
            isbn=str(isbn or ""), language=str(info.get("language") or ""),
        ))
    return results


def _open_library(query: str) -> list[ResearchResult]:
    params = {"q": query, "limit": MAX_RESULTS_PER_PROVIDER, "fields": "key,title,author_name,first_publish_year,publisher,isbn,language"}
    response = _session().get("https://openlibrary.org/search.json", params=params, timeout=TIMEOUT)
    response.raise_for_status()
    results = []
    for item in response.json().get("docs", []):
        title = str(item.get("title") or "").strip()
        key = str(item.get("key") or "")
        url = f"https://openlibrary.org{key}" if key.startswith("/") else ""
        if not title or not trusted_publication_url(url):
            continue
        results.append(ResearchResult(
            title=title, authors=[str(name) for name in item.get("author_name") or []],
            year=_year(item.get("first_publish_year")), source_type="book",
            url=url, provider="Open Library",
            publisher=str((item.get("publisher") or [""])[0]),
            isbn=str((item.get("isbn") or [""])[0]),
            language=str((item.get("language") or [""])[0]),
        ))
    return results


def search_publications(query: str, mode: str = "all") -> tuple[list[dict], list[str]]:
    query = re.sub(r"\s+", " ", str(query or "")).strip()[:300]
    if len(query) < 3:
        return [], ["Informe pelo menos três caracteres para pesquisar."]
    providers = {
        "Crossref": _crossref,
        "OpenAlex": _openalex,
        "Google Books": _google_books,
        "Open Library": _open_library,
    }
    if mode == "modern":
        providers = {key: value for key, value in providers.items() if key in {"Crossref", "OpenAlex"}}
    elif mode == "classic":
        providers = {key: value for key, value in providers.items() if key in {"Google Books", "Open Library"}}

    gathered: list[ResearchResult] = []
    warnings = []
    with ThreadPoolExecutor(max_workers=len(providers)) as executor:
        futures = {executor.submit(searcher, query): name for name, searcher in providers.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                gathered.extend(future.result())
            except requests.RequestException as exc:
                logger.warning("Catálogo %s indisponível: %s", name, exc)
                warnings.append(f"{name} não respondeu nesta pesquisa.")
            except Exception as exc:
                logger.exception("Erro no catálogo %s", name)
                warnings.append(f"{name} não pôde ser consultado.")

    deduplicated: dict[str, ResearchResult] = {}
    for item in gathered:
        if mode == "modern" and (not item.year or item.year < date.today().year - 10):
            continue
        item.relevance = _score(query, item)
        if item.relevance < 0.08:
            continue
        identity = (item.doi.casefold() if item.doi else re.sub(r"\W+", "", item.title.casefold()) + str(item.year or ""))
        previous = deduplicated.get(identity)
        if previous is None or item.relevance > previous.relevance:
            deduplicated[identity] = item
    if mode == "classic":
        sort_key = lambda item: (-item.relevance, item.year or 9999, item.title.casefold())
    else:
        sort_key = lambda item: (-item.relevance, -(item.year or 0), item.title.casefold())
    ordered = sorted(deduplicated.values(), key=sort_key)[:24]
    return [item.serializable() for item in ordered], warnings
