"""Интерфейс командной строки: запуск приложения и вывод результата."""

import sys
from typing import Optional, Sequence

from depviz.ascii_tree import format_ascii_tree
from depviz.collector import (
    collect_direct_dependencies,
    collect_graph,
    collect_reverse_dependencies,
)
from depviz.config import (
    SHOW_CONFIG,
    SHOW_D2,
    SHOW_DIRECT,
    SHOW_REVERSE,
    Config,
    parse_config,
)
from depviz.d2 import format_d2
from depviz.errors import ConfigError, FetchError
from depviz.report import (
    format_config,
    format_direct_dependencies,
    format_graph,
    format_reverse,
)

EXIT_OK = 0
EXIT_CONFIG_ERROR = 2
EXIT_FETCH_ERROR = 3


def build_graph_output(config: Config) -> str:
    """Построить граф и вывести его в выбранном виде и, если нужно, деревом."""
    graph = collect_graph(config)
    if config.show == SHOW_D2:
        text = format_d2(graph)
    else:
        text = format_graph(graph)
    if config.ascii_tree:
        return f"{text}\n\n{format_ascii_tree(graph)}"
    return text


def build_output(config: Config) -> str:
    """Выполнить выбранное действие и вернуть текст для вывода."""
    if config.show == SHOW_CONFIG:
        return format_config(config)
    if config.show == SHOW_DIRECT:
        return format_direct_dependencies(collect_direct_dependencies(config))
    if config.show == SHOW_REVERSE:
        return format_reverse(collect_reverse_dependencies(config))
    return build_graph_output(config)


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
