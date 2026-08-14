import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import requests
from django.conf import settings


class UnsafeURL(ValueError):
    pass


class RemoteFetchError(ValueError):
    pass


def normalize_url(value: str) -> str:
    value = (value or "").strip()
    if value.lower().startswith("doi:"):
        value = "https://doi.org/" + value[4:].strip()
    elif value.startswith("10.") and "/" in value:
        value = "https://doi.org/" + value
    return value


def validate_public_url(value: str) -> str:
    value = normalize_url(value)
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeURL("Informe uma URL HTTP ou HTTPS válida.")
    if parsed.username or parsed.password:
        raise UnsafeURL("URLs com credenciais incorporadas não são permitidas.")
    hostname = parsed.hostname.rstrip(".").casefold()
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(
        ".local"
    ):
        raise UnsafeURL("Endereços locais não são permitidos.")
    try:
        addresses = {
            item[4][0] for item in socket.getaddrinfo(hostname, parsed.port or 443)
        }
    except socket.gaierror as exc:
        raise UnsafeURL("Não foi possível localizar o endereço informado.") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise UnsafeURL(
                "Endereços de rede privada ou reservada não são permitidos."
            )
    return value


def safe_fetch(value: str, max_redirects: int = 4):
    current = validate_public_url(value)
    session = requests.Session()
    headers = {
        "User-Agent": "CitaRN/1.0 (reference metadata importer)",
        "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.2",
    }
    for _ in range(max_redirects + 1):
        try:
            response = session.get(
                current,
                headers=headers,
                timeout=(4, 10),
                stream=True,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise RemoteFetchError("Não foi possível acessar essa URL agora.") from exc
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise RemoteFetchError(
                    "O endereço retornou um redirecionamento inválido."
                )
            current = validate_public_url(urljoin(current, location))
            continue
        if response.status_code != 200:
            response.close()
            raise RemoteFetchError(
                f"A URL retornou o status HTTP {response.status_code}."
            )
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > settings.URL_FETCH_MAX_BYTES:
            response.close()
            raise RemoteFetchError("O conteúdo remoto excede o limite permitido.")
        chunks = []
        size = 0
        for chunk in response.iter_content(64 * 1024):
            size += len(chunk)
            if size > settings.URL_FETCH_MAX_BYTES:
                response.close()
                raise RemoteFetchError("O conteúdo remoto excede o limite permitido.")
            chunks.append(chunk)
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
        final_url = response.url
        response.close()
        return b"".join(chunks), content_type, final_url
    raise RemoteFetchError("A URL realizou redirecionamentos demais.")
