"""Построение графа зависимостей обходом в ширину (BFS) с рекурсией."""

from dataclasses import dataclass, field

from depviz.errors import GraphError
from depviz.sources import DependencySource


@dataclass(frozen=True)
class DependencyGraph:
    """Граф зависимостей: для каждого пакета список прямых зависимостей.

    Поле levels хранит пакеты по уровням обхода: levels[0] - корень,
    levels[1] - его прямые зависимости и так далее.
    """

    root: str
    edges: dict[str, list[str]]
    levels: list[list[str]] = field(default_factory=list)

    @property
    def node_count(self) -> int:
        """Количество пакетов в графе."""
        return len(self.edges)

    @property
    def edge_count(self) -> int:
        """Количество зависимостей (ребер) в графе."""
        return sum(len(targets) for targets in self.edges.values())


class GraphBuilder:
    """Строит граф зависимостей рекурсивным обходом в ширину.

    Каждый вызов обрабатывает один уровень графа и рекурсивно вызывает
    себя для следующего. Множество обнаруженных пакетов гарантирует,
    что пакет обрабатывается один раз, поэтому циклы не зацикливают обход.
    """

    def __init__(
        self, source: DependencySource, excluded_substring: str = ""
    ) -> None:
        """Задать источник данных и подстроку исключаемых пакетов."""
        self.source = source
        self.excluded_substring = excluded_substring
        self.edges: dict[str, list[str]] = {}
        self.levels: list[list[str]] = []
        self.discovered: set[str] = set()

    def build(self, root: str) -> DependencyGraph:
        """Построить граф зависимостей, достижимых из корневого пакета."""
        self.edges = {}
        self.levels = []
        self.discovered = {root}
        try:
            self.visit_level([root])
        except RecursionError as error:
            raise GraphError(
                "граф слишком глубокий: превышен предел рекурсии Python"
            ) from error
        return DependencyGraph(root, self.edges, self.levels)

    def visit_level(self, level: list[str]) -> None:
        """Обработать уровень графа и рекурсивно перейти к следующему."""
        if not level:
            return
        self.levels.append(list(level))
        next_level: list[str] = []
        for package in level:
            dependencies = self.read_dependencies(package)
            self.edges[package] = dependencies
            next_level.extend(self.discover(dependencies))
        self.visit_level(next_level)

    def read_dependencies(self, package: str) -> list[str]:
        """Получить зависимости пакета без исключенных фильтром."""
        names = dict.fromkeys(self.source.get_dependencies(package))
        return [name for name in names if not self.is_excluded(name)]

    def is_excluded(self, package: str) -> bool:
        """Проверить, что имя пакета содержит исключаемую подстроку."""
        return bool(self.excluded_substring) and (
            self.excluded_substring in package
        )

    def discover(self, dependencies: list[str]) -> list[str]:
        """Выбрать еще не обнаруженные пакеты и пометить их найденными."""
        fresh = [name for name in dependencies if name not in self.discovered]
        self.discovered.update(fresh)
        return fresh


def build_graph(
    root: str, source: DependencySource, excluded_substring: str = ""
) -> DependencyGraph:
    """Построить граф зависимостей корневого пакета."""
    return GraphBuilder(source, excluded_substring).build(root)
