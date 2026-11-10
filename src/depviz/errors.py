"""Исключения инструмента визуализации графа зависимостей."""


class ConfigError(Exception):
    """Ошибка в параметрах, заданных пользователем."""


class FetchError(Exception):
    """Ошибка получения или разбора метаданных пакета."""


class HttpStatusError(FetchError):
    """Сервер ответил HTTP-статусом, означающим ошибку."""

    def __init__(self, status: int, url: str) -> None:
        """Запомнить статус ответа и адрес запроса."""
        super().__init__(
            f"сервер ответил статусом HTTP {status} на запрос '{url}'"
        )
        self.status = status
        self.url = url


class PackageNotFoundError(FetchError):
    """Запрошенный пакет отсутствует в репозитории."""

    def __init__(self, package: str, repo_url: str) -> None:
        """Запомнить имя пакета и адрес репозитория."""
        super().__init__(
            f"пакет '{package}' не найден в репозитории '{repo_url}'"
        )
        self.package = package
        self.repo_url = repo_url


class MetadataFormatError(FetchError):
    """Метаданные пакета имеют неожиданный формат."""
