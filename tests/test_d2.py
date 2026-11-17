"""Тесты формирования описания графа на языке D2."""

import unittest

from depviz.d2 import format_d2, quote_key
from depviz.graph import DependencyGraph


def make_graph(root: str, edges: dict[str, list[str]]) -> DependencyGraph:
    """Создать граф с заданным корнем и связями."""
    return DependencyGraph(root, edges)


class TestQuoteKey(unittest.TestCase):
    """Проверки оформления имени пакета как строки D2."""

    def test_plain_name_is_quoted(self) -> None:
        """Обычное имя берется в двойные кавычки."""
        self.assertEqual(quote_key("left-pad"), '"left-pad"')

    def test_scoped_name_keeps_special_characters(self) -> None:
        """Символы @ и / сохраняются внутри кавычек."""
        self.assertEqual(quote_key("@babel/core"), '"@babel/core"')

    def test_dots_stay_inside_quotes(self) -> None:
        """Точка в имени не превращается во вложенность D2."""
        self.assertEqual(quote_key("lodash.merge"), '"lodash.merge"')

    def test_quote_and_backslash_are_escaped(self) -> None:
        """Кавычка и обратная косая черта экранируются."""
        self.assertEqual(quote_key('a"b\\c'), '"a\\"b\\\\c"')


class TestFormatD2(unittest.TestCase):
    """Проверки функции format_d2."""

    def test_one_connection_per_dependency(self) -> None:
        """Каждая зависимость описывается отдельной связью."""
        graph = make_graph("A", {"A": ["B", "C"], "B": ["D"], "C": [], "D": []})
        expected = ['"A" -> "B"', '"A" -> "C"', '"B" -> "D"']
        self.assertEqual(format_d2(graph).splitlines(), expected)

    def test_connections_follow_traversal_order(self) -> None:
        """Связи записываются в порядке обхода графа."""
        graph = make_graph("A", {"A": ["C", "B"], "C": ["B"], "B": []})
        expected = ['"A" -> "C"', '"A" -> "B"', '"C" -> "B"']
        self.assertEqual(format_d2(graph).splitlines(), expected)

    def test_shared_dependency_has_two_incoming_connections(self) -> None:
        """Общая зависимость присутствует в двух связях."""
        graph = make_graph("A", {"A": ["B", "C"], "B": ["D"], "C": ["D"]})
        self.assertEqual(format_d2(graph).count('-> "D"'), 2)

    def test_cycle_is_described_with_back_connection(self) -> None:
        """Циклическая зависимость описывается обычной связью."""
        graph = make_graph("A", {"A": ["B"], "B": ["A"]})
        self.assertEqual(
            format_d2(graph).splitlines(), ['"A" -> "B"', '"B" -> "A"']
        )

    def test_self_dependency(self) -> None:
        """Зависимость пакета от самого себя - связь в тот же узел."""
        graph = make_graph("A", {"A": ["A"]})
        self.assertEqual(format_d2(graph), '"A" -> "A"')

    def test_single_package_is_declared_alone(self) -> None:
        """Пакет без зависимостей объявляется отдельной строкой."""
        graph = make_graph("left-pad", {"left-pad": []})
        self.assertEqual(format_d2(graph), '"left-pad"')
