"""Тесты разбора метаданных npm-пакета."""

import unittest
from typing import Any

from depviz.errors import MetadataFormatError
from depviz.npm_metadata import get_direct_dependencies

PACKAGE = "demo"
VERSION = "1.2.3"


def make_metadata(manifest: Any) -> dict[str, Any]:
    """Собрать метаданные пакета с заданным описанием версии."""
    return {
        "dist-tags": {"latest": VERSION},
        "versions": {VERSION: manifest},
    }


class TestGetDirectDependencies(unittest.TestCase):
    """Проверки извлечения прямых зависимостей."""

    def test_dependencies_are_sorted_by_name(self) -> None:
        """Зависимости возвращаются в порядке имен."""
        manifest = {"dependencies": {"zeta": "^1.0.0", "alpha": "~2.1.0"}}
        result = get_direct_dependencies(make_metadata(manifest), PACKAGE)
        self.assertEqual(result.package, PACKAGE)
        self.assertEqual(result.version, VERSION)
        self.assertEqual(
            list(result.dependencies.items()),
            [("alpha", "~2.1.0"), ("zeta", "^1.0.0")],
        )

    def test_missing_dependencies_field_means_no_dependencies(self) -> None:
        """Отсутствие поля dependencies означает пустой список."""
        result = get_direct_dependencies(make_metadata({}), PACKAGE)
        self.assertEqual(result.dependencies, {})

    def test_only_runtime_dependencies_are_used(self) -> None:
        """Зависимости для разработки и peer-зависимости не учитываются."""
        manifest = {
            "dependencies": {"runtime": "1.0.0"},
            "devDependencies": {"tester": "2.0.0"},
            "peerDependencies": {"host": "3.0.0"},
        }
        result = get_direct_dependencies(make_metadata(manifest), PACKAGE)
        self.assertEqual(list(result.dependencies), ["runtime"])

    def test_missing_dist_tags_is_rejected(self) -> None:
        """Метаданные без dist-tags отклоняются."""
        with self.assertRaises(MetadataFormatError):
            get_direct_dependencies({"versions": {}}, PACKAGE)

    def test_missing_latest_tag_is_rejected(self) -> None:
        """Метаданные без тега latest отклоняются."""
        metadata = {"dist-tags": {"next": VERSION}, "versions": {}}
        with self.assertRaises(MetadataFormatError):
            get_direct_dependencies(metadata, PACKAGE)

    def test_missing_version_description_is_rejected(self) -> None:
        """Отсутствие описания версии latest приводит к ошибке."""
        metadata = {"dist-tags": {"latest": VERSION}, "versions": {}}
        with self.assertRaises(MetadataFormatError):
            get_direct_dependencies(metadata, PACKAGE)

    def test_malformed_dependencies_are_rejected(self) -> None:
        """Некорректные типы в dependencies отклоняются."""
        malformed = [{"dependencies": ["a"]}, {"dependencies": {"a": 1}}]
        for manifest in malformed:
            with self.subTest(manifest=manifest):
                with self.assertRaises(MetadataFormatError):
                    get_direct_dependencies(make_metadata(manifest), PACKAGE)
