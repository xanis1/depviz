"""Тесты вывода графа зависимостей в виде ASCII-дерева."""

import unittest

from depviz.ascii_tree import (
    CYCLE_LEGEND,
    REPEAT_LEGEND,
    format_ascii_tree,
)
from depviz.errors import GraphError
from depviz.graph import DependencyGraph

DEEP_CHAIN_LENGTH = 5000


def make_tree(root: str, edges: dict[str, list[str]]) -> list[str]:
    """Построить строки дерева для графа с заданным корнем."""
    return format_ascii_tree(DependencyGraph(root, edges)).splitlines()


class TestShape(unittest.TestCase):
    """Проверки формы дерева."""

    def test_single_package(self) -> None:
        """Пакет без зависимостей - одна строка."""
        self.assertEqual(make_tree("A", {"A": []}), ["A"])

    def test_branches_and_last_branch(self) -> None:
        """Последняя ветвь отличается от остальных."""
        edges = {"A": ["B", "C"], "B": [], "C": []}
        self.assertEqual(make_tree("A", edges), ["A", "|-- B", "`-- C"])

    def test_nested_dependencies_are_indented(self) -> None:
        """Вложенные зависимости сдвигаются, вертикальная черта сохраняется."""
        edges = {"A": ["B", "C"], "B": ["D"], "C": ["E"], "D": [], "E": []}
        expected = [
            "A",
            "|-- B",
            "|   `-- D",
            "`-- C",
            "    `-- E",
        ]
        self.assertEqual(make_tree("A", edges), expected)

    def test_output_is_ascii_except_marks(self) -> None:
        """Линии дерева состоят только из ASCII-символов."""
        edges = {"A": ["B"], "B": ["C"], "C": []}
        text = "\n".join(make_tree("A", edges))
        self.assertTrue(text.isascii())


class TestRepeatsAndCycles(unittest.TestCase):
    """Проверки пометок повторов и циклов."""

    def test_shared_leaf_is_repeated_without_mark(self) -> None:
        """Повтор пакета без зависимостей не помечается."""
        edges = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
        expected = ["A", "|-- B", "|   `-- D", "`-- C", "    `-- D"]
        self.assertEqual(make_tree("A", edges), expected)

    def test_shared_package_with_dependencies_is_marked(self) -> None:
        """Повтор пакета с зависимостями помечается и не раскрывается."""
        edges = {
            "A": ["B", "C"], "B": ["D"], "C": ["D"], "D": ["E"], "E": [],
        }
        expected = [
            "A",
            "|-- B",
            "|   `-- D",
            "|       `-- E",
            "`-- C",
            "    `-- D (*)",
            "",
            REPEAT_LEGEND,
        ]
        self.assertEqual(make_tree("A", edges), expected)

    def test_cycle_is_marked(self) -> None:
        """Пакет, уже стоящий выше по цепочке, помечается как цикл."""
        edges = {"A": ["B"], "B": ["C"], "C": ["A"]}
        expected = [
            "A",
            "`-- B",
            "    `-- C",
            "        `-- A (цикл)",
            "",
            CYCLE_LEGEND,
        ]
        self.assertEqual(make_tree("A", edges), expected)

    def test_self_dependency_is_marked_as_cycle(self) -> None:
        """Зависимость от самого себя помечается как цикл."""
        lines = make_tree("A", {"A": ["A"]})
        self.assertEqual(lines[:2], ["A", "`-- A (цикл)"])

    def test_no_legend_without_marks(self) -> None:
        """Пояснения выводятся только при наличии пометок."""
        lines = make_tree("A", {"A": ["B"], "B": []})
        self.assertNotIn(REPEAT_LEGEND, lines)
        self.assertNotIn(CYCLE_LEGEND, lines)

    def test_mixed_graph(self) -> None:
        """Смешанный граф с общими зависимостями и циклом."""
        edges = {
            "A": ["B", "C", "D"], "B": ["E", "F"], "C": ["F", "G"],
            "D": ["G", "H"], "E": ["I"], "F": ["I", "J"], "G": ["J"],
            "H": ["A"], "I": [], "J": ["K"], "K": [],
        }
        expected = [
            "A",
            "|-- B",
            "|   |-- E",
            "|   |   `-- I",
            "|   `-- F",
            "|       |-- I",
            "|       `-- J",
            "|           `-- K",
            "|-- C",
            "|   |-- F (*)",
            "|   `-- G",
            "|       `-- J (*)",
            "`-- D",
            "    |-- G (*)",
            "    `-- H",
            "        `-- A (цикл)",
            "",
            REPEAT_LEGEND,
            CYCLE_LEGEND,
        ]
        self.assertEqual(make_tree("A", edges), expected)


class TestDepth(unittest.TestCase):
    """Проверки глубины дерева."""

    def test_too_deep_tree_is_reported(self) -> None:
        """Чрезмерно глубокое дерево дает понятную ошибку."""
        edges = {
            f"P{index}": [f"P{index + 1}"]
            for index in range(DEEP_CHAIN_LENGTH)
        }
        graph = DependencyGraph("P0", edges)
        with self.assertRaises(GraphError):
            format_ascii_tree(graph)
