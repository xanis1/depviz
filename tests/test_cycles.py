"""Тесты поиска циклических зависимостей."""

import unittest

from depviz.cycles import find_cycles
from depviz.graph import DependencyGraph


def make_graph(edges: dict[str, list[str]]) -> DependencyGraph:
    """Создать граф с корнем A из словаря связей."""
    return DependencyGraph("A", edges)


class TestFindCycles(unittest.TestCase):
    """Проверки функции find_cycles."""

    def test_acyclic_graph_has_no_cycles(self) -> None:
        """В графе без циклов ничего не находится."""
        graph = make_graph({"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []})
        self.assertEqual(find_cycles(graph), [])

    def test_cycle_through_root(self) -> None:
        """Цикл через корень записывается с повтором первого пакета."""
        graph = make_graph({"A": ["B"], "B": ["C"], "C": ["A"]})
        self.assertEqual(find_cycles(graph), [["A", "B", "C", "A"]])

    def test_cycle_inside_graph(self) -> None:
        """Цикл в глубине графа не включает лишние пакеты."""
        graph = make_graph(
            {"A": ["B"], "B": ["C"], "C": ["D", "B"], "D": []}
        )
        self.assertEqual(find_cycles(graph), [["B", "C", "B"]])

    def test_self_loop(self) -> None:
        """Зависимость от самого себя считается циклом."""
        graph = make_graph({"A": ["A", "B"], "B": []})
        self.assertEqual(find_cycles(graph), [["A", "A"]])

    def test_several_cycles(self) -> None:
        """Несколько обратных ребер дают несколько циклов."""
        graph = make_graph({"A": ["B", "C"], "B": ["A"], "C": ["A"]})
        self.assertEqual(
            find_cycles(graph), [["A", "B", "A"], ["A", "C", "A"]]
        )
