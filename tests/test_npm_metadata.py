"""Тесты разбора метаданных npm-пакета."""

import unittest
from typing import Any

from depviz.errors import MetadataFormatError
from depviz.npm_metadata import (
    get_direct_dependencies,
    registry_dependency_names,
    resolve_registry_name,
)

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


class TestResolveRegistryName(unittest.TestCase):
    """Проверки определения имени пакета в реестре npm."""

    def test_plain_ranges_keep_dependency_name(self) -> None:
        """Обычные версии и диапазоны не меняют имя зависимости."""
        ranges = ["^1.2.3", "~2.0", "1.0.0", "*", "latest", ">=1 <3", "1 || 2"]
        for requirement in ranges:
            with self.subTest(requirement=requirement):
                resolved = resolve_registry_name("dep", requirement)
                self.assertEqual(resolved, "dep")

    def test_alias_gives_real_package_name(self) -> None:
        """Алиас npm: заменяется настоящим именем пакета."""
        aliases = {
            "npm:real@^1.0.0": "real",
            "npm:real": "real",
            "npm:@scope/real@2.0.0": "@scope/real",
            "npm:@scope/real": "@scope/real",
        }
        for requirement, expected in aliases.items():
            with self.subTest(requirement=requirement):
                resolved = resolve_registry_name("dep", requirement)
                self.assertEqual(resolved, expected)

    def test_non_registry_requirements_are_skipped(self) -> None:
        """Git, URL, файловые и GitHub-зависимости пропускаются."""
        sources = [
            "github:user/repo", "user/repo", "git+https://host/repo.git",
            "https://host/pkg.tgz", "file:../pkg", "workspace:*", "npm:",
        ]
        for requirement in sources:
            with self.subTest(requirement=requirement):
                self.assertIsNone(resolve_registry_name("dep", requirement))

    def test_names_are_unique_and_ordered(self) -> None:
        """Совпавшие после замены алиасов имена объединяются."""
        dependencies = {
            "a-dep": "1.0.0",
            "a-dep-cjs": "npm:a-dep@^1.0.0",
            "z-dep": "2.0.0",
            "git-dep": "github:user/repo",
        }
        self.assertEqual(
            registry_dependency_names(dependencies), ["a-dep", "z-dep"]
        )
