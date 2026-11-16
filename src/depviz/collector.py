"""Сбор данных о зависимостях в соответствии с конфигурацией."""

from depviz.config import Config
from depviz.errors import ConfigError
from depviz.file_repository import load_file_repository
from depviz.graph import DependencyGraph, build_graph
from depviz.npm_metadata import DirectDependencies, get_direct_dependencies
from depviz.registry import fetch_metadata
from depviz.sources import DependencySource, RegistrySource


def create_source(config: Config) -> DependencySource:
    """Создать источник данных: файл тестового репозитория или URL."""
    if config.test_mode:
        return load_file_repository(config.repo)
    return RegistrySource(config.repo)


def collect_graph(config: Config) -> DependencyGraph:
    """Построить граф зависимостей пакета с учетом фильтра."""
    source = create_source(config)
    return build_graph(config.package, source, config.filter_substring)


def collect_direct_dependencies(config: Config) -> DirectDependencies:
    """Получить прямые зависимости пакета из репозитория по URL."""
    if config.test_mode:
        raise ConfigError(
            "режим direct работает только с репозиторием по URL; "
            "для тестового репозитория используйте --show graph"
        )
    metadata = fetch_metadata(config.repo, config.package)
    return get_direct_dependencies(metadata, config.package)
