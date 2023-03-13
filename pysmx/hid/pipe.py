from os import mkfifo
from pathlib import Path


# FIFO Pipe Locations and Settings
PIPE_DIR = Path(__file__).parent / "pipes"
IN_PIPE = PIPE_DIR / "input"
OUT_PIPE = PIPE_DIR / "output"

PIPE_READ_BUFFER_SIZE = 8192


def ensure_pipes_exist() -> None:
    if not IN_PIPE.is_fifo():
        mkfifo(str(IN_PIPE))

    if not OUT_PIPE.is_fifo():
        mkfifo(str(OUT_PIPE))


# TODO: Figure out a better name for these?
def write_cmd_event(msg: bytes) -> None:
    with IN_PIPE.open("wb") as f:
        f.write(msg)


def read_cmd_event() -> bytes:
    data = b""
    with OUT_PIPE.open("rb") as f:
        data = f.read(PIPE_READ_BUFFER_SIZE)

    return data


def is_sentinel(data: bytes) -> bool:
    """
    We have defined a sentinel response of `[0]`. Check if we have detected the sentinel
    """
    return len(data) == 1 and data[0] == 0


def send_command(pad: int, cmd: bytes, /, has_output: bool = False) -> bytes:
    ensure_pipes_exist()

    # Write command event
    write_cmd_event(str(pad).encode("UTF-8") + b":" + cmd)

    # Wait for the result
    while True:
        data = read_cmd_event()

        # If we expect a non empty response, keep checking the pipe until we get one
        if not has_output:
            break
        else:
            if not is_sentinel(data):
                break

    return data
