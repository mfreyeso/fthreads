from client import my_funs
from utils import map_reduce


mapper, reducer = my_funs()


def test_mapper_emits_count_one() -> None:
    assert mapper("hello") == ("hello", 1)
    assert mapper("world") == ("world", 1)


def test_reducer_sums_observations() -> None:
    assert reducer(("hello", [1, 1, 1])) == ("hello", 3)
    assert reducer(("x", [1])) == ("x", 1)
    assert reducer(("empty", [])) == ("empty", 0)


def test_map_reduce_word_count() -> None:
    words: list[str] = ["the", "cat", "sat", "on", "the", "mat", "the"]
    results: list[tuple[str, int]] = map_reduce(words, mapper, reducer, 3)
    counts: dict[str, int] = dict(results)
    assert counts["the"] == 3
    assert counts["cat"] == 1
    assert counts["mat"] == 1
    assert len(counts) == 5
