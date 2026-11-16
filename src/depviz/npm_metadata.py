"""Разбор метаданных npm-пакета: версия и прямые зависимости."""

from dataclasses import dataclass
from typing import Any, Optional

from depviz.errors import MetadataFormatError

DIST_TAGS_FIELD = "dist-tags"
VERSIONS_FIELD = "versions"
DEPENDENCIES_FIELD = "dependencies"
LATEST_TAG = "latest"
NPM_ALIAS_PREFIX = "npm:"
NON_REGISTRY_MARKERS = ("/", ":")


@dataclass(frozen=True)
class DirectDependencies:
    """Прямые зависимости конкретной версии пакета."""

    package: str
    version: str
    dependencies: dict[str, str]


def require_mapping(value: Any, field: str, package: str) -> dict[str, Any]:
    """Убедиться, что значение поля является JSON-объектом."""
    if not isinstance(value, dict):
        raise MetadataFormatError(
            f"в метаданных пакета '{package}' поле '{field}' "
            "отсутствует или не является объектом"
        )
    return value


def resolve_latest_version(metadata: dict[str, Any], package: str) -> str:
    """Определить версию пакета, на которую указывает тег latest."""
    tags = require_mapping(
        metadata.get(DIST_TAGS_FIELD), DIST_TAGS_FIELD, package
    )
    version = tags.get(LATEST_TAG)
    if not isinstance(version, str):
        raise MetadataFormatError(
            f"у пакета '{package}' не задан тег '{LATEST_TAG}'"
        )
    return version


def find_version_manifest(
    metadata: dict[str, Any], package: str, version: str
) -> dict[str, Any]:
    """Найти описание указанной версии в метаданных пакета."""
    versions = require_mapping(
        metadata.get(VERSIONS_FIELD), VERSIONS_FIELD, package
    )
    return require_mapping(
        versions.get(version), f"{VERSIONS_FIELD}.{version}", package
    )


def read_dependencies(
    manifest: dict[str, Any], package: str
) -> dict[str, str]:
    """Извлечь зависимости версии в словарь, отсортированный по имени."""
    raw = manifest.get(DEPENDENCIES_FIELD, {})
    mapping = require_mapping(raw, DEPENDENCIES_FIELD, package)
    for name, requirement in mapping.items():
        if not isinstance(requirement, str):
            raise MetadataFormatError(
                f"у зависимости '{name}' пакета '{package}' "
                "версия задана не строкой"
            )
    return dict(sorted(mapping.items()))


def get_direct_dependencies(
    metadata: dict[str, Any], package: str
) -> DirectDependencies:
    """Получить прямые зависимости последней версии пакета."""
    version = resolve_latest_version(metadata, package)
    manifest = find_version_manifest(metadata, package, version)
    dependencies = read_dependencies(manifest, package)
    return DirectDependencies(package, version, dependencies)


def parse_alias_target(alias: str) -> Optional[str]:
    """Выделить имя пакета из значения вида имя@диапазон."""
    head, separator, _range = alias.rpartition("@")
    target = head if separator and head else alias
    return target or None


def resolve_registry_name(name: str, requirement: str) -> Optional[str]:
    """Определить имя пакета в реестре npm.

    Для алиаса вида npm:имя@диапазон возвращается настоящее имя пакета,
    для зависимостей из git, URL или файла - None.
    """
    if requirement.startswith(NPM_ALIAS_PREFIX):
        return parse_alias_target(requirement[len(NPM_ALIAS_PREFIX):])
    if any(marker in requirement for marker in NON_REGISTRY_MARKERS):
        return None
    return name


def registry_dependency_names(dependencies: dict[str, str]) -> list[str]:
    """Получить уникальные имена реестровых зависимостей по порядку."""
    resolved = (
        resolve_registry_name(name, requirement)
        for name, requirement in dependencies.items()
    )
    return list(dict.fromkeys(name for name in resolved if name))
