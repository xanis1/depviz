"""Источники сведений о прямых зависимостях пакетов."""

from typing import Protocol

from depviz.npm_metadata import get_direct_dependencies
from depviz.npm_metadata import registry_dependency_names
from depviz.registry import fetch_metadata


class DependencySource(Protocol):
    """Источник сведений о прямых зависимостях пакетов."""

    def get_dependencies(self, package: str) -> list[str]:
        """Вернуть имена прямых зависимостей пакета."""
        raise NotImplementedError


class RegistrySource:
    """Источник данных: npm-репозиторий, доступный по URL."""

    def __init__(self, repo_url: str) -> None:
        """Запомнить адрес репозитория."""
        self.repo_url = repo_url

    def get_dependencies(self, package: str) -> list[str]:
        """Загрузить метаданные пакета и вернуть его зависимости."""
        metadata = fetch_metadata(self.repo_url, package)
        direct = get_direct_dependencies(metadata, package)
        return registry_dependency_names(direct.dependencies)
