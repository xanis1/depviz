"""Локальный HTTP-сервер, имитирующий ответы npm-репозитория."""

import json
import os
import threading
from typing import Any, Callable, Iterable, NamedTuple
from unittest import mock
from wsgiref.simple_server import WSGIRequestHandler, make_server

LOCAL_HOST = "127.0.0.1"
ANY_FREE_PORT = 0
POLL_INTERVAL_SECONDS = 0.05
STATUS_OK = "200 OK"
STATUS_NOT_FOUND = "404 Not Found"
NO_PROXY_VALUE = "127.0.0.1,localhost"


class FakeResponse(NamedTuple):
    """Заготовленный ответ сервера: статус и тело."""

    body: bytes
    status: str = STATUS_OK


class RecordedRequest(NamedTuple):
    """Запрос, полученный сервером: путь и заголовок Accept."""

    path: str
    accept: str


class QuietRequestHandler(WSGIRequestHandler):
    """Обработчик запросов, который не пишет журнал в stderr."""

    def log_message(self, *args: object) -> None:
        """Подавить вывод журнала запросов."""


def make_packument(
    name: str, version: str, dependencies: dict[str, str]
) -> FakeResponse:
    """Создать ответ с метаданными пакета из одной версии."""
    manifest = {
        "name": name,
        "version": version,
        "dependencies": dependencies,
    }
    document = {
        "name": name,
        "dist-tags": {"latest": version},
        "versions": {version: manifest},
    }
    return FakeResponse(json.dumps(document).encode("utf-8"))


def make_application(
    responses: dict[str, FakeResponse], journal: list[RecordedRequest]
) -> Callable[[dict[str, Any], Callable[..., Any]], Iterable[bytes]]:
    """Создать WSGI-приложение, отдающее заготовленные ответы."""

    def application(
        environ: dict[str, Any], start_response: Callable[..., Any]
    ) -> Iterable[bytes]:
        """Обработать один запрос к имитации репозитория."""
        path = environ["PATH_INFO"].lstrip("/")
        journal.append(RecordedRequest(path, environ.get("HTTP_ACCEPT", "")))
        default = FakeResponse(b'{"error": "Not found"}', STATUS_NOT_FOUND)
        response = responses.get(path, default)
        start_response(response.status, [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(response.body))),
        ])
        return [response.body]

    return application


class FakeRegistry:
    """Менеджер контекста: запускает сервер и сообщает его URL."""

    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        """Подготовить сервер с заданными ответами по именам пакетов."""
        self.requests: list[RecordedRequest] = []
        application = make_application(responses, self.requests)
        self.server = make_server(
            LOCAL_HOST,
            ANY_FREE_PORT,
            application,
            handler_class=QuietRequestHandler,
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            kwargs={"poll_interval": POLL_INTERVAL_SECONDS},
            daemon=True,
        )
        self.environment = mock.patch.dict(
            os.environ, {"NO_PROXY": NO_PROXY_VALUE, "no_proxy": NO_PROXY_VALUE}
        )

    @property
    def url(self) -> str:
        """Адрес запущенного сервера."""
        return f"http://{LOCAL_HOST}:{self.server.server_port}"

    def __enter__(self) -> "FakeRegistry":
        """Запустить сервер в отдельном потоке."""
        self.environment.start()
        self.thread.start()
        return self

    def __exit__(self, *exception_info: object) -> None:
        """Остановить сервер и освободить порт."""
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.environment.stop()
