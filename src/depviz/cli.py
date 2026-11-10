"""Интерфейс командной строки: запуск приложения и вывод результата."""

import sys
from typing import Optional, Sequence

from depviz.config import Config, parse_config
from depviz.errors import ConfigError

EXIT_OK = 0
EXIT_CONFIG_ERROR = 2
NOT_SET_LABEL = "<не задано>"


def format_flag(value: bool) -> str:
    """Представить логический флаг строкой для вывода."""
    return "true" if value else "false"


def config_to_pairs(config: Config) -> list[tuple[str, str]]:
    """Преобразовать конфигурацию в список пар ключ-значение."""
    return [
        ("package", config.package),
        ("repo", config.repo),
        ("test_mode", format_flag(config.test_mode)),
        ("ascii_tree", format_flag(config.ascii_tree)),
        ("filter", config.filter_substring or NOT_SET_LABEL),
    ]


def format_config(config: Config) -> str:
    """Сформировать текст с параметрами в формате ключ-значение."""
    pairs = config_to_pairs(config)
    return "\n".join(f"{key}: {value}" for key, value in pairs)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Выполнить приложение и вернуть код завершения процесса."""
    try:
        config = parse_config(argv)
    except ConfigError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    print(format_config(config))
    return EXIT_OK
