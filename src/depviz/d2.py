"""Формирование описания графа зависимостей на языке диаграмм D2."""

from depviz.graph import DependencyGraph

CONNECTION = " -> "


def quote_key(name: str) -> str:
    """Оформить имя пакета как строку D2 в двойных кавычках."""
    escaped = name.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def format_connections(package: str, dependencies: list[str]) -> list[str]:
    """Сформировать связи D2 от пакета к его зависимостям."""
    source = quote_key(package)
    return [f"{source}{CONNECTION}{quote_key(name)}" for name in dependencies]


def format_d2(graph: DependencyGraph) -> str:
    """Сформировать описание графа зависимостей на языке D2.

    Каждая зависимость записывается связью вида "A" -> "B" в порядке
    обхода графа. Пакет без связей, то есть единственный корень,
    объявляется отдельной строкой.
    """
    lines: list[str] = []
    for package, dependencies in graph.edges.items():
        lines.extend(format_connections(package, dependencies))
    if not lines:
        lines.append(quote_key(graph.root))
    return "\n".join(lines)
