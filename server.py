import asyncio
from collections.abc import Iterable
from functools import partial
import logging
import marshal
import multiprocessing as mp
import pickle
from queue import Empty, Queue
import signal
import threading
from time import sleep as sync_sleep
import types
from typing import cast

from utils import map_reduce, reporter


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handle_interrupt_signal(server: asyncio.Server) -> None:
    server.close()
    while server.is_serving():
        sync_sleep(0.1)


work_queue: Queue[tuple[int, types.CodeType | None, object]] = Queue()
results_queue: Queue[tuple[int, list[tuple[object, object]]]] = Queue()
results: dict[int, list[tuple[object, object]]] = {}


async def submit_job(
    job_id: int, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    writer.write(job_id.to_bytes(4, "little"))
    writer.close()

    code_size: int = int.from_bytes(await reader.read(4), "little")
    my_code: types.CodeType = marshal.loads(await reader.read(code_size))

    data_size: int = int.from_bytes(await reader.read(4), "little")
    data: object = pickle.loads(await reader.read(data_size))

    work_queue.put_nowait((job_id, my_code, data))


def get_results_queue() -> None:
    while results_queue.qsize() > 0:
        try:
            job_id, data = results_queue.get_nowait()
            results[job_id] = data
        except Empty:
            logger.info("No results in queue")
            return


async def get_results(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    get_results_queue()

    job_id: int = int.from_bytes(await reader.read(4), "little")
    data: bytes = pickle.dumps(None)

    if job_id in results:
        data = pickle.dumps(results[job_id])
        del results[job_id]

    writer.write(len(data).to_bytes(4, "little"))
    writer.write(data)


async def accept_requests(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    job_id: list[int] = [0],
) -> None:
    op: bytes = await reader.read(1)
    if op[0] == 0:
        await submit_job(job_id[0], reader, writer)
        job_id[0] += 1
    elif op[0] == 1:
        await get_results(reader, writer)


def worker() -> None:
    while True:
        job_id, code, data = work_queue.get()
        logger.info(f"Processing job id: {job_id} data: {data} and code: {code}")
        if job_id == -1:
            break
        assert code is not None
        func: types.FunctionType = types.FunctionType(
            code, globals(), "mapper_and_reducer"
        )
        mapper, reducer = cast(tuple[types.FunctionType, types.FunctionType], func())

        counts: list[tuple[object, object]] = map_reduce(
            cast(Iterable[object], data), mapper, reducer, 100, reporter
        )
        counts.sort(key=lambda x: x[1], reverse=True)
        results_queue.put((job_id, counts))

    logger.info("Worker thread terminating")


def init_worker() -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)


async def main() -> None:
    server: asyncio.Server = await asyncio.start_server(
        accept_requests, "127.0.0.1", 1936
    )

    loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
    loop.add_signal_handler(
        signal.SIGINT, partial(handle_interrupt_signal, server=server)
    )

    worker_thread: threading.Thread = threading.Thread(target=partial(worker))
    worker_thread.start()

    async with server:
        try:
            await server.serve_forever()
        except asyncio.exceptions.CancelledError:
            logger.warning("Server cancelled")

    work_queue.put((-1, None, None))
    worker_thread.join()

    logger.info("graceful exit")


asyncio.run(main())
