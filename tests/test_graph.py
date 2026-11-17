"""Тесты построения графа зависимостей обходом BFS с рекурсией."""

import unittest

from depviz.errors import GraphError
from depviz.graph import GraphBuilder, build_graph

OK_CHAIN_LENGTH = 300
TOO_DEEP_CHAIN_LENGTH = 5000


class MemorySource:
    """Источник данных из словаря, запоминающий обращения к пакетам."""

    def __init__(self, packages: dict[str, list[str]]) -> None:
        """Сохранить описание пакетов."""
        self.packages = packages
        self.calls: list[str] = []

    def get_dependencies(self, package: str) -> list[str]:
        """Вернуть зависимости пакета и записать обращение."""
        self.calls.append(package)
        return list(self.packages.get(package, []))


def make_chain(length: int) -> dict[str, list[str]]:
    """Создать цепочку пакетов P0 -> P1 -> ... -> P(length-1)."""
    return {f"P{index}": [f"P{index + 1}"] for index in range(length)}


class TestBreadthFirstOrder(unittest.TestCase):
    """Проверки порядка и полноты обхода."""

    def test_nodes_are_discovered_level_by_level(self) -> None:
        """Пакеты обходятся по уровням, а не в глубину."""
        source = MemorySource(
            {"A": ["B", "C"], "B": ["D"], "C": ["E"], "D": [], "E": []}
        )
        graph = build_graph("A", source)
        self.assertEqual(list(graph.edges), ["A", "B", "C", "D", "E"])
        self.assertEqual(source.calls, ["A", "B", "C", "D", "E"])

    def test_shared_dependency_is_visited_once(self) -> None:
        """Общая зависимость обрабатывается один раз."""
        source = MemorySource({"A": ["B", "C"], "B": ["D"], "C": ["D"]})
        graph = build_graph("A", source)
        self.assertEqual(source.calls.count("D"), 1)
        self.assertEqual(graph.node_count, 4)
        self.assertEqual(graph.edge_count, 4)

    def test_unreachable_packages_are_not_included(self) -> None:
        """Пакеты, недостижимые из корня, в граф не попадают."""
        source = MemorySource({"A": ["B"], "X": ["Y"]})
        graph = build_graph("A", source)
        self.assertEqual(list(graph.edges), ["A", "B"])

    def test_package_without_dependencies(self) -> None:
        """Корень без зависимостей дает граф из одного узла."""
        graph = build_graph("A", MemorySource({"A": []}))
        self.assertEqual(graph.edges, {"A": []})
        self.assertEqual(graph.edge_count, 0)

    def test_duplicate_dependencies_are_merged(self) -> None:
        """Повторы в списке зависимостей учитываются один раз."""
        graph = build_graph("A", MemorySource({"A": ["B", "B"]}))
        self.assertEqual(graph.edges["A"], ["B"])


class TestCycles(unittest.TestCase):
    """Проверки обработки циклических зависимостей."""

    def test_cycle_through_root_terminates(self) -> None:
        """Цикл через корневой пакет не приводит к зацикливанию."""
        source = MemorySource({"A": ["B"], "B": ["C"], "C": ["A"]})
        graph = build_graph("A", source)
        self.assertEqual(graph.edges, {"A": ["B"], "B": ["C"], "C": ["A"]})
        self.assertEqual(source.calls, ["A", "B", "C"])

    def test_cycle_inside_graph_terminates(self) -> None:
        """Цикл в глубине графа обрабатывается корректно."""
        source = MemorySource({"A": ["B"], "B": ["C"], "C": ["B", "D"]})
        graph = build_graph("A", source)
        self.assertEqual(list(graph.edges), ["A", "B", "C", "D"])

    def test_self_dependency_terminates(self) -> None:
        """Зависимость пакета от самого себя сохраняется в графе."""
        graph = build_graph("A", MemorySource({"A": ["A", "B"]}))
        self.assertEqual(graph.edges["A"], ["A", "B"])


class TestFilter(unittest.TestCase):
    """Проверки исключения пакетов по подстроке."""

    def test_excluded_package_is_not_analyzed(self) -> None:
        """Исключенный пакет не запрашивается и не попадает в граф."""
        source = MemorySource({"A": ["BX", "C"], "BX": ["D"], "C": []})
        graph = build_graph("A", source, "X")
        self.assertEqual(list(graph.edges), ["A", "C"])
        self.assertNotIn("BX", source.calls)
        self.assertNotIn("D", source.calls)

    def test_substring_matches_inside_name(self) -> None:
        """Подстрока ищется в любом месте имени пакета."""
        source = MemorySource({"app": ["left-pad", "util"], "util": []})
        graph = build_graph("app", source, "pad")
        self.assertEqual(graph.edges["app"], ["util"])

    def test_dependency_reachable_other_way_is_kept(self) -> None:
        """Пакет, достижимый в обход исключенного, остается в графе."""
        source = MemorySource({"A": ["BX", "C"], "BX": ["D"], "C": ["D"]})
        graph = build_graph("A", source, "X")
        self.assertEqual(list(graph.edges), ["A", "C", "D"])

    def test_empty_substring_excludes_nothing(self) -> None:
        """Пустая подстрока означает отсутствие фильтра."""
        graph = build_graph("A", MemorySource({"A": ["B"]}), "")
        self.assertEqual(list(graph.edges), ["A", "B"])


class TestDepth(unittest.TestCase):
    """Проверки глубины рекурсии."""

    def test_long_chain_is_supported(self) -> None:
        """Длинная цепочка в сотни уровней строится без ошибок."""
        graph = build_graph("P0", MemorySource(make_chain(OK_CHAIN_LENGTH)))
        self.assertEqual(graph.node_count, OK_CHAIN_LENGTH + 1)

    def test_too_deep_graph_is_reported(self) -> None:
        """Чрезмерно глубокий граф дает понятную ошибку."""
        source = MemorySource(make_chain(TOO_DEEP_CHAIN_LENGTH))
        with self.assertRaises(GraphError):
            build_graph("P0", source)


class TestLevels(unittest.TestCase):
    """Проверки разбиения пакетов по уровням обхода."""

    def test_levels_follow_breadth_first_order(self) -> None:
        """Пакеты распределяются по расстоянию от корня."""
        source = MemorySource(
            {"A": ["B", "C"], "B": ["D"], "C": ["D", "E"], "D": [], "E": []}
        )
        graph = build_graph("A", source)
        self.assertEqual(graph.levels, [["A"], ["B", "C"], ["D", "E"]])

    def test_package_appears_on_its_shortest_level_only(self) -> None:
        """Пакет, достижимый разными путями, указан на ближайшем уровне."""
        source = MemorySource({"A": ["B", "C"], "B": ["C"], "C": []})
        graph = build_graph("A", source)
        self.assertEqual(graph.levels, [["A"], ["B", "C"]])

    def test_cycle_does_not_add_levels(self) -> None:
        """Возврат к уже обнаруженному пакету не создает новый уровень."""
        source = MemorySource({"A": ["B"], "B": ["A"]})
        graph = build_graph("A", source)
        self.assertEqual(graph.levels, [["A"], ["B"]])

    def test_builder_can_be_reused(self) -> None:
        """Повторный запуск построителя не накапливает старые уровни."""
        builder = GraphBuilder(MemorySource({"A": ["B"], "B": []}))
        builder.build("A")
        graph = builder.build("B")
        self.assertEqual(graph.levels, [["B"]])
        self.assertEqual(list(graph.edges), ["B"])
