"""Тесты получения метаданных из репозитория по HTTP."""

import unittest
import urllib.error
from unittest import mock

from depviz.errors import (
    FetchError,
    HttpStatusError,
    MetadataFormatError,
    PackageNotFoundError,
)
from depviz.registry import (
    ACCEPT_HEADER,
    build_metadata_url,
    fetch_metadata,
)
from tests.fake_registry import FakeRegistry, FakeResponse, make_packument

SERVER_ERROR_STATUS = "500 Internal Server Error"
PROBLEM_NAME = "problem"


class TestBuildMetadataUrl(unittest.TestCase):
    """Проверки построения адреса метаданных."""

    def test_plain_package(self) -> None:
        """Имя обычного пакета добавляется к адресу репозитория."""
        url = build_metadata_url("https://registry.example.org", "express")
        self.assertEqual(url, "https://registry.example.org/express")

    def test_scoped_package_slash_is_encoded(self) -> None:
        """В имени пакета с областью слеш кодируется."""
        url = build_metadata_url("https://registry.example.org", "@a/b")
        self.assertEqual(url, "https://registry.example.org/@a%2Fb")


class TestFetchMetadata(unittest.TestCase):
    """Проверки загрузки метаданных через локальный сервер."""

    def test_returns_parsed_document(self) -> None:
        """Корректный ответ разбирается в словарь."""
        responses = {"demo": make_packument("demo", "1.0.0", {"dep": "^1"})}
        with FakeRegistry(responses) as registry:
            metadata = fetch_metadata(registry.url, "demo")
        self.assertEqual(metadata["dist-tags"], {"latest": "1.0.0"})

    def test_request_asks_for_npm_metadata(self) -> None:
        """Запрос содержит заголовок Accept, принятый в npm."""
        responses = {"demo": make_packument("demo", "1.0.0", {})}
        with FakeRegistry(responses) as registry:
            fetch_metadata(registry.url, "demo")
        self.assertEqual(registry.requests[0].accept, ACCEPT_HEADER)

    def test_scoped_package_is_requested_by_full_name(self) -> None:
        """Пакет с областью запрашивается по полному имени."""
        responses = {"@scope/lib": make_packument("@scope/lib", "2.0.0", {})}
        with FakeRegistry(responses) as registry:
            metadata = fetch_metadata(registry.url, "@scope/lib")
        self.assertEqual(metadata["name"], "@scope/lib")

    def test_unknown_package_is_reported(self) -> None:
        """Статус 404 превращается в PackageNotFoundError."""
        with FakeRegistry({}) as registry:
            with self.assertRaises(PackageNotFoundError) as context:
                fetch_metadata(registry.url, "absent")
        self.assertEqual(context.exception.package, "absent")

    def test_server_error_is_reported(self) -> None:
        """Прочие HTTP-ошибки превращаются в HttpStatusError."""
        responses = {PROBLEM_NAME: FakeResponse(b"{}", SERVER_ERROR_STATUS)}
        with FakeRegistry(responses) as registry:
            with self.assertRaises(HttpStatusError):
                fetch_metadata(registry.url, PROBLEM_NAME)

    def test_invalid_json_is_reported(self) -> None:
        """Ответ, не являющийся JSON, приводит к ошибке формата."""
        responses = {"broken": FakeResponse(b"<html>not json</html>")}
        with FakeRegistry(responses) as registry:
            with self.assertRaises(MetadataFormatError):
                fetch_metadata(registry.url, "broken")

    def test_non_object_json_is_reported(self) -> None:
        """JSON-массив вместо объекта приводит к ошибке формата."""
        responses = {"list": FakeResponse(b"[1, 2, 3]")}
        with FakeRegistry(responses) as registry:
            with self.assertRaises(MetadataFormatError):
                fetch_metadata(registry.url, "list")


class TestNetworkFailures(unittest.TestCase):
    """Проверки реакции на сбои сети."""

    def test_unreachable_server_is_reported(self) -> None:
        """Недоступный сервер приводит к FetchError."""
        failure = urllib.error.URLError("connection refused")
        with mock.patch("urllib.request.urlopen", side_effect=failure):
            with self.assertRaises(FetchError):
                fetch_metadata("http://registry.invalid", "demo")

    def test_timeout_is_reported(self) -> None:
        """Превышение времени ожидания приводит к FetchError."""
        with mock.patch("urllib.request.urlopen", side_effect=TimeoutError):
            with self.assertRaises(FetchError):
                fetch_metadata("http://registry.invalid", "demo")
