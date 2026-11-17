"""Тесты чтения тестового репозитория из файла."""

import os
import tempfile
import unittest

from depviz.errors import (
    FetchError,
    MetadataFormatError,
    PackageNotFoundError,
)
from depviz.file_repository import load_file_repository, parse_repository


def load_text(text: str, encoding: str = "utf-8"):
    """Записать текст во временный файл и загрузить репозиторий."""
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "graph.txt")
        with open(path, "w", encoding=encoding, newline="") as handle:
            handle.write(text)
        return load_file_repository(path)


class TestParseRepository(unittest.TestCase):
    """Проверки разбора текста описания графа."""

    def test_packages_and_dependencies(self) -> None:
        """Строки разбираются в пакеты и списки зависимостей."""
        packages = parse_repository("A: B C\nB:\nC: B\n")
        self.assertEqual(packages, {"A": ["B", "C"], "B": [], "C": ["B"]})

    def test_commas_spaces_and_blank_lines(self) -> None:
        """Разделители: запятые и пробелы; пустые строки пропускаются."""
        packages = parse_repository("\nA : B,C ,  D\n\n")
        self.assertEqual(packages["A"], ["B", "C", "D"])

    def test_mentioned_package_gets_no_dependencies(self) -> None:
        """Пакет, упомянутый только как зависимость, считается листом."""
        packages = parse_repository("A: B\n")
        self.assertEqual(packages["B"], [])

    def test_repeated_dependency_is_merged(self) -> None:
        """Повтор зависимости в строке учитывается один раз."""
        self.assertEqual(parse_repository("A: B B\n")["A"], ["B"])

    def test_invalid_lines_are_rejected(self) -> None:
        """Строки неверного формата и с неверными именами отклоняются."""
        invalid_texts = ["A B\n", ": B\n", "a: B\n", "A: b\n", "A1: B\n"]
        for text in invalid_texts:
            with self.subTest(text=text):
                with self.assertRaises(MetadataFormatError):
                    parse_repository(text)

    def test_duplicate_definition_is_rejected(self) -> None:
        """Повторное описание пакета отклоняется."""
        with self.assertRaises(MetadataFormatError):
            parse_repository("A: B\nA: C\n")


class TestLoadFileRepository(unittest.TestCase):
    """Проверки загрузки репозитория из файла."""

    def test_dependencies_are_returned(self) -> None:
        """Зависимости пакета читаются из файла."""
        repository = load_text("A: B C\nB:\nC:\n")
        self.assertEqual(repository.get_dependencies("A"), ["B", "C"])

    def test_windows_line_endings_and_bom(self) -> None:
        """Файл с CRLF и BOM читается так же, как обычный."""
        repository = load_text("A: B\r\nB:\r\n", encoding="utf-8-sig")
        self.assertEqual(repository.get_dependencies("A"), ["B"])

    def test_unknown_package_is_reported(self) -> None:
        """Запрос неизвестного пакета дает PackageNotFoundError."""
        repository = load_text("A: B\n")
        with self.assertRaises(PackageNotFoundError):
            repository.get_dependencies("Z")

    def test_returned_list_is_a_copy(self) -> None:
        """Изменение результата не портит данные репозитория."""
        repository = load_text("A: B\n")
        repository.get_dependencies("A").append("Z")
        self.assertEqual(repository.get_dependencies("A"), ["B"])

    def test_missing_file_is_reported(self) -> None:
        """Отсутствующий файл дает FetchError."""
        with self.assertRaises(FetchError):
            load_file_repository(os.path.join("no", "such", "graph.txt"))

    def test_format_error_mentions_file(self) -> None:
        """Сообщение об ошибке формата содержит имя файла и строку."""
        with self.assertRaises(MetadataFormatError) as context:
            load_text("A: B\nbroken line\n")
        self.assertIn("graph.txt", str(context.exception))
        self.assertIn("строка 2", str(context.exception))


class TestGetDependents(unittest.TestCase):
    """Проверки поиска пакетов, зависящих от заданного."""

    def test_dependents_follow_file_order(self) -> None:
        """Зависимые пакеты возвращаются в порядке описания в файле."""
        repository = load_text("A: C\nB: C\nC:\n")
        self.assertEqual(repository.get_dependents("C"), ["A", "B"])

    def test_only_direct_dependents_are_returned(self) -> None:
        """Косвенно зависящие пакеты не возвращаются."""
        repository = load_text("A: B\nB: C\nC:\n")
        self.assertEqual(repository.get_dependents("C"), ["B"])

    def test_package_nobody_depends_on(self) -> None:
        """У пакета, от которого никто не зависит, список пуст."""
        repository = load_text("A: B\nB:\n")
        self.assertEqual(repository.get_dependents("A"), [])

    def test_self_dependency_counts(self) -> None:
        """Пакет, зависящий от самого себя, является своим зависимым."""
        repository = load_text("A: A\n")
        self.assertEqual(repository.get_dependents("A"), ["A"])

    def test_package_mentioned_only_as_dependency(self) -> None:
        """Пакет без собственной строки тоже имеет зависимых."""
        repository = load_text("A: Z\n")
        self.assertEqual(repository.get_dependents("Z"), ["A"])

    def test_unknown_package_is_reported(self) -> None:
        """Запрос зависимых неизвестного пакета дает ошибку."""
        repository = load_text("A: B\n")
        with self.assertRaises(PackageNotFoundError):
            repository.get_dependents("Q")
