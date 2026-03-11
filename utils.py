from itertools import islice
import asyncio
from collections import defaultdict
from collections.abc import Callable, Generator, Iterable, Sequence
import marshal
import types
from typing import cast


def chunk[T](my_iter: Iterable[T], chunk_size: int) -> Generator[list[T]]:
    it = iter(my_iter)
    while batch := list(islice(it, chunk_size)):
        yield batch


def chunk_runner(fun_marshal: bytes, data: Sequence[object]) -> list[object]:
    fun: types.FunctionType = types.FunctionType(
        marshal.loads(fun_marshal), globals(), "fun"
    )
    ret: list[object] = []
    for datum in data:
        print(fun(datum))
        ret.append(fun(datum))
    return ret


async def chunked_async_map(
    mapper: types.FunctionType, data: Iterable[object], chunk_size: int
) -> list[list[object]]:
    async_returns = [
        asyncio.to_thread(chunk_runner, marshal.dumps(mapper.__code__), data_part)
        for data_part in chunk(data, chunk_size)
    ]
    return await asyncio.gather(*async_returns)


def reporter(results: Sequence[object]) -> None:
    for result in results:
        print(result)


def map_reduce[K, V, In, Out](
    my_input: Iterable[In],
    mapper: Callable[[In], tuple[K, V]],
    reducer: Callable[[tuple[K, list[V]]], tuple[K, Out]],
    chunk_size: int,
    callback: Callable[[Sequence[tuple[K, Out]]], None] | None = None,
) -> list[tuple[K, Out]]:
    map_returns: list[list[object]] = asyncio.run(
        chunked_async_map(cast(types.FunctionType, mapper), my_input, chunk_size)
    )

    map_results: list[tuple[K, V]] = []
    for ret in map_returns:
        map_results.extend(cast(list[tuple[K, V]], ret))
    distributor: defaultdict[K, list[V]] = defaultdict(list)

    for key, value in map_results:
        distributor[key].append(value)

    returns: list[list[object]] = asyncio.run(
        chunked_async_map(
            cast(types.FunctionType, reducer), distributor.items(), chunk_size
        )
    )

    results: list[tuple[K, Out]] = []
    for ret in returns:
        results.extend(cast(list[tuple[K, Out]], ret))

    return results
