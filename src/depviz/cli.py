"""Интерфейс командной строки: запуск приложения и вывод результата."""

import sys
from typing import Optional, Sequence

from depviz.collector import collect_direct_dependencies
from depviz.config import SHOW_CONFIG, Config, parse_config
from depviz.errors import ConfigError, FetchError
from depviz.npm_metadata import DirectDependencies

EXIT_OK = 0
EXIT_CONFIG_ERROR = 2
EXIT_FETCH_ERROR = 3
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
        ("show", config.show),
    ]


def format_config(config: Config) -> str:
    """Сформировать текст с параметрами в формате ключ-значение."""
    pairs = config_to_pairs(config)
    return "\n".join(f"{key}: {value}" for key, value in pairs)


def format_direct_dependencies(result: DirectDependencies) -> str:
    """Сформировать текст со списком прямых зависимостей пакета."""
    title = f"Прямые зависимости {result.package}@{result.version}"
    if not result.dependencies:
        return f"{title}: отсутствуют"
    lines = [f"{title} ({len(result.dependencies)}):"]
    for name, requirement in result.dependencies.items():
        lines.append(f"  {name} ({requirement})")
    return "\n".join(lines)


def build_output(config: Config) -> str:
    """Выполнить выбранное действие и вернуть текст для вывода."""
    if config.show == SHOW_CONFIG:
        return format_config(config)
    return format_direct_dependencies(collect_direct_dependencies(config))


def report_error(error: Exception, exit_code: int) -> int:
    """Вывести сообщение об ошибке в stderr и вернуть код завершения."""
    print(f"Ошибка: {error}", file=sys.stderr)
    return exit_code


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Выполнить приложение и вернуть код завершения процесса."""
    try:
        output = build_output(parse_config(argv))
    except ConfigError as error:
        return report_error(error, EXIT_CONFIG_ERROR)
    except FetchError as error:
        return report_error(error, EXIT_FETCH_ERROR)
    print(output)
    return EXIT_OK
