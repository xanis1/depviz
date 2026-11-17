"""Форматирование результатов для вывода на экран."""

from depviz.config import Config
from depviz.cycles import find_cycles
from depviz.graph import DependencyGraph
from depviz.npm_metadata import DirectDependencies

NOT_SET_LABEL = "<не задано>"
NO_DEPENDENCIES_LABEL = "(нет зависимостей)"
FORWARD_ARROW = " -> "
REVERSE_ARROW = " <- "
FIRST_DEPENDENT_LEVEL = 1


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


def format_node(package: str, dependencies: list[str]) -> str:
    """Сформировать строку графа: пакет и его зависимости."""
    if not dependencies:
        return f"{package} -> {NO_DEPENDENCIES_LABEL}"
    return f"{package} -> {', '.join(dependencies)}"


def format_cycles(
    cycles: list[list[str]], arrow: str = FORWARD_ARROW
) -> list[str]:
    """Сформировать строки со списком циклических зависимостей."""
    if not cycles:
        return ["Циклические зависимости: не обнаружены"]
    lines = [f"Циклические зависимости ({len(cycles)}):"]
    lines.extend(f"  {arrow.join(cycle)}" for cycle in cycles)
    return lines


def format_graph(graph: DependencyGraph) -> str:
    """Сформировать текст с графом зависимостей и найденными циклами."""
    title = (
        f"Граф зависимостей пакета {graph.root}: "
        f"узлов {graph.node_count}, ребер {graph.edge_count}"
    )
    lines = [title]
    for package, dependencies in graph.edges.items():
        lines.append(format_node(package, dependencies))
    lines.extend(format_cycles(find_cycles(graph)))
    return "\n".join(lines)


def format_reverse(graph: DependencyGraph) -> str:
    """Сформировать текст с обратными зависимостями пакета по уровням."""
    levels = graph.levels[FIRST_DEPENDENT_LEVEL:]
    total = sum(len(level) for level in levels)
    title = f"Обратные зависимости пакета {graph.root}"
    if not total:
        lines = [f"{title}: отсутствуют"]
    else:
        lines = [f"{title} (всего {total}):"]
        for number, level in enumerate(levels, start=FIRST_DEPENDENT_LEVEL):
            lines.append(f"  уровень {number}: {', '.join(level)}")
    lines.extend(format_cycles(find_cycles(graph), REVERSE_ARROW))
    return "\n".join(lines)
