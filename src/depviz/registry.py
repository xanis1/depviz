"""Получение метаданных пакетов из npm-репозитория по HTTP."""

import http.client
import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import quote

from depviz.errors import (
    FetchError,
    HttpStatusError,
    MetadataFormatError,
    PackageNotFoundError,
)

HTTP_NOT_FOUND = 404
REQUEST_TIMEOUT_SECONDS = 15
ACCEPT_HEADER = (
    "application/vnd.npm.install-v1+json; q=1.0, "
    "application/json; q=0.8, */*"
)
USER_AGENT = "depviz (educational dependency graph tool)"


def build_metadata_url(repo_url: str, package: str) -> str:
    """Сформировать адрес документа с метаданными пакета."""
    return f"{repo_url}/{quote(package, safe='@')}"


def read_response(url: str, timeout: float) -> bytes:
    """Выполнить GET-запрос и вернуть тело ответа."""
    headers = {"Accept": ACCEPT_HEADER, "User-Agent": USER_AGENT}
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        status = error.code
        error.close()
        raise HttpStatusError(status, url) from error
    except (OSError, http.client.HTTPException) as error:
        raise FetchError(
            f"не удалось получить данные с '{url}': {error}"
        ) from error


def parse_json_document(body: bytes, url: str) -> dict[str, Any]:
    """Разобрать тело ответа как JSON-объект."""
    try:
        document = json.loads(body.decode("utf-8"))
    except ValueError as error:
        raise MetadataFormatError(
            f"ответ на запрос '{url}' не является корректным JSON"
        ) from error
    if not isinstance(document, dict):
        raise MetadataFormatError(
            f"ответ на запрос '{url}' должен быть JSON-объектом"
        )
    return document


def fetch_metadata(repo_url: str, package: str) -> dict[str, Any]:
    """Загрузить метаданные пакета из репозитория по его URL."""
    url = build_metadata_url(repo_url, package)
    try:
        body = read_response(url, REQUEST_TIMEOUT_SECONDS)
    except HttpStatusError as error:
        if error.status == HTTP_NOT_FOUND:
            raise PackageNotFoundError(package, repo_url) from error
        raise
    return parse_json_document(body, url)
