from enum import Enum as ReprEnum
from typing import Any, Generator


def pad_list(_list: list[int], count: int, /, padding_byte: bytes = b"\0") -> list[int]:
    """
    Pad the given list with `padding_byte` until we hit `count` items.
    If `padding_byte` is more than a single byte, then I can't be held responsible for
    what happens.
    """
    _list.extend([int(padding_byte[0]) for _ in range(count - len(_list))])
    return _list


def s_to_ns(seconds: float | int) -> int:
    """
    Convert `seconds` into NanoSeconds
    """
    return int(seconds * 1000000000)


def chunk_list(_list: list[Any], count: int) -> Generator[Any, None, None]:
    for i in range(0, len(_list), count):
        yield _list[i : i + count]


def chunk_bytes(_bytes: bytes, count: int) -> Generator[bytes, None, None]:
    for i in range(0, len(_bytes), count):
        yield _bytes[i : i + count]


class BytesEnum(bytes, ReprEnum):
    def __reduce_ex__(self, proto):
        """Note: Remove this after Python 3.11.5 Comes out"""
        return self.__class__, (self._value_,)
