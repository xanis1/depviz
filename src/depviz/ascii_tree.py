"""Вывод графа зависимостей в виде ASCII-дерева."""

from depviz.errors import GraphError
from depviz.graph import DependencyGraph

BRANCH = "|-- "
LAST_BRANCH = "`-- "
VERTICAL = "|   "
BLANK = "    "
REPEAT_MARK = " (*)"
CYCLE_MARK = " (цикл)"
REPEAT_LEGEND = "(*) - зависимости этого пакета показаны выше"
CYCLE_LEGEND = "(цикл) - пакет уже встречается выше по цепочке зависимостей"
FIRST_POSITION = 1


class TreeRenderer:
    """Строит строки ASCII-дерева по графу зависимостей.

    Зависимости пакета раскрываются только при первой встрече. Повторная
    встреча пакета с зависимостями помечается (*), пакет, который уже
    находится выше по цепочке, помечается (цикл).
    """

    def __init__(self, graph: DependencyGraph) -> None:
        """Подготовить построитель для заданного графа."""
        self.graph = graph
        self.lines: list[str] = []
        self.expanded: set[str] = set()
        self.has_repeats = False
        self.has_cycles = False

    def render(self) -> list[str]:
        """Построить строки дерева с пояснениями к пометкам."""
        root = self.graph.root
        self.lines = [root]
        self.expanded = {root}
        self.has_repeats = False
        self.has_cycles = False
        try:
            self.add_children(root, "", [root])
        except RecursionError as error:
            raise GraphError(
                "дерево слишком глубокое: превышен предел рекурсии Python"
            ) from error
        return self.lines + self.legend()

    def add_children(
        self, package: str, prefix: str, path: list[str]
    ) -> None:
        """Добавить строки зависимостей пакета и раскрыть новые пакеты."""
        children = self.graph.edges.get(package, [])
        total = len(children)
        for position, child in enumerate(children, start=FIRST_POSITION):
            is_last = position == total
            connector = LAST_BRANCH if is_last else BRANCH
            self.lines.append(prefix + connector + self.label(child, path))
            if child in path or child in self.expanded:
                continue
            self.expanded.add(child)
            path.append(child)
            indent = BLANK if is_last else VERTICAL
            self.add_children(child, prefix + indent, path)
            path.pop()

    def label(self, child: str, path: list[str]) -> str:
        """Сформировать подпись пакета с пометкой повтора или цикла."""
        if child in path:
            self.has_cycles = True
            return child + CYCLE_MARK
        if child in self.expanded and self.graph.edges.get(child):
            self.has_repeats = True
            return child + REPEAT_MARK
        return child

    def legend(self) -> list[str]:
        """Сформировать пояснения к использованным пометкам."""
        notes = []
        if self.has_repeats:
            notes.append(REPEAT_LEGEND)
        if self.has_cycles:
            notes.append(CYCLE_LEGEND)
        return [""] + notes if notes else []


def format_ascii_tree(graph: DependencyGraph) -> str:
    """Сформировать ASCII-дерево зависимостей от корневого пакета."""
    return "\n".join(TreeRenderer(graph).render())
