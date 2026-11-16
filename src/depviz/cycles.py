"""Поиск циклических зависимостей в графе."""

from depviz.graph import DependencyGraph


def advance_search(
    path: list[str],
    iterators: list,
    edges: dict[str, list[str]],
    finished: set[str],
) -> list[str]:
    """Сделать один шаг обхода в глубину; вернуть найденный цикл или []."""
    following = next(iterators[-1], None)
    if following is None:
        finished.add(path.pop())
        iterators.pop()
    elif following in path:
        return path[path.index(following):] + [following]
    elif following not in finished:
        path.append(following)
        iterators.append(iter(edges.get(following, [])))
    return []


def search_from(
    start: str, edges: dict[str, list[str]], finished: set[str]
) -> list[list[str]]:
    """Найти циклы в части графа, достижимой из стартового пакета."""
    path = [start]
    iterators = [iter(edges.get(start, []))]
    cycles: list[list[str]] = []
    while iterators:
        cycle = advance_search(path, iterators, edges, finished)
        if cycle:
            cycles.append(cycle)
    return cycles


def find_cycles(graph: DependencyGraph) -> list[list[str]]:
    """Найти циклы: по одному на каждое обратное ребро обхода в глубину.

    Цикл представлен списком пакетов, первый и последний совпадают.
    """
    finished: set[str] = set()
    cycles: list[list[str]] = []
    for start in graph.edges:
        if start not in finished:
            cycles.extend(search_from(start, graph.edges, finished))
    return cycles
