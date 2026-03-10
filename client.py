import logging
import marshal
import pickle
import socket
import types
from collections.abc import Sequence
from time import sleep


logger = logging.getLogger(__name__)


def my_funs() -> tuple[
    types.FunctionType,
    types.FunctionType,
]:
    def mapper(value: str) -> tuple[str, int]:
        return value, 1

    def reducer(my_args: tuple[str, list[int]]) -> tuple[str, int]:
        value, observations = my_args
        return value, sum(observations)

    return mapper, reducer


def do_request(my_funs: types.FunctionType, data: Sequence[str]) -> None:
    conn: socket.socket = socket.create_connection(("127.0.0.1", 1936))
    conn.send(b"\x00")

    my_code: bytes = marshal.dumps(my_funs.__code__)
    conn.send(len(my_code).to_bytes(4, "little", signed=False))
    conn.send(my_code)

    my_data: bytes = pickle.dumps(data)
    conn.send(len(my_data).to_bytes(4, "little"))
    conn.send(my_data)

    job_id: int = int.from_bytes(conn.recv(4), "little")
    conn.close()

    logger.info(f"Getting data from job_id {job_id}")

    result: object = None
    while result is None:
        conn = socket.create_connection(("127.0.0.1", 1936))

        conn.send(b"\x01")
        conn.send(job_id.to_bytes(4, "little"))

        result_size: int = int.from_bytes(conn.recv(4), "little")
        result = pickle.loads(conn.recv(result_size))
        conn.close()
        sleep(1)
    logger.info(f"Result is {result}")


if __name__ == "__main__":
    do_request(my_funs, "Python rocks. Python is great".split(" "))
