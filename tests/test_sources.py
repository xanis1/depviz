"""Тесты источников данных о зависимостях."""

import unittest

from depviz.graph import build_graph
from depviz.sources import ReverseSource


class FakeProvider:
    """Хранилище с заранее заданными списками зависимых пакетов."""

    def __init__(self, dependents: dict[str, list[str]]) -> None:
        """Сохранить словарь зависимых пакетов."""
        self.dependents = dependents
        self.requested: list[str] = []

    def get_dependents(self, package: str) -> list[str]:
        """Вернуть зависимых пакета и записать обращение."""
        self.requested.append(package)
        return list(self.dependents.get(package, []))


class TestReverseSource(unittest.TestCase):
    """Проверки источника обратных связей."""

    def test_dependencies_are_the_dependents(self) -> None:
        """Источник отдает зависимых в роли зависимостей."""
        provider = FakeProvider({"D": ["B", "C"]})
        source = ReverseSource(provider)
        self.assertEqual(source.get_dependencies("D"), ["B", "C"])
        self.assertEqual(provider.requested, ["D"])

    def test_builder_walks_dependents_level_by_level(self) -> None:
        """Построитель графа обходит зависимых теми же уровнями."""
        provider = FakeProvider({"D": ["B", "C"], "B": ["A"], "C": ["A"]})
        graph = build_graph("D", ReverseSource(provider))
        self.assertEqual(graph.levels, [["D"], ["B", "C"], ["A"]])
        self.assertEqual(provider.requested, ["D", "B", "C", "A"])
