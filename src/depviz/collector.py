"""Сбор данных о зависимостях в соответствии с конфигурацией."""

from depviz.config import Config
from depviz.errors import ConfigError
from depviz.npm_metadata import DirectDependencies, get_direct_dependencies
from depviz.registry import fetch_metadata


def collect_direct_dependencies(config: Config) -> DirectDependencies:
    """Получить прямые зависимости пакета из репозитория по URL."""
    if config.test_mode:
        raise ConfigError(
            "тестовый режим пока не поддерживается для вывода зависимостей"
        )
    metadata = fetch_metadata(config.repo, config.package)
    return get_direct_dependencies(metadata, config.package)
