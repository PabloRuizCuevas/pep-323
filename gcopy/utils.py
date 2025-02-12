from sys import version_info
from inspect import getframeinfo
from readline import get_history_item
from dis import get_instructions
from types import FrameType, GeneratorType, CodeType
from typing import Iterable, Any


def is_cli() -> bool:
    """Determines if using get_history_item is possible e.g. for CLIs"""
    try:
        get_history_item(0)
        return True
    except IndexError:
        return False


def get_col_offset(frame: FrameType) -> int:
    """Gets the col offset from a frame"""
    if version_info < (3, 11):
        raise NotImplementedError(
            "get_instructions does not provide positions, you have to rewrite the get_instructions function to allow so"
        )
        lasti = frame.f_lasti
        for instruction in get_instructions(frame.f_code):
            if instruction.offset == lasti:
                return instruction.positions.col_offset
        raise ValueError("f_lasti not encountered")
    return getframeinfo(frame).positions.col_offset


def empty_generator() -> GeneratorType:
    """Creates a simple empty generator"""
    return
    yield


def code_attrs() -> tuple[str, ...]:
    """
    all the attrs used by a CodeType object in
    order of types.CodeType function signature
    ideally and correct to the current version
    """
    attrs = ("co_argcount",)
    if (3, 8) <= version_info:
        attrs += ("co_posonlyargcount",)
    attrs += (
        "co_kwonlyargcount",
        "co_nlocals",
        "co_stacksize",
        "co_flags",
        "co_code",
        "co_consts",
        "co_names",
        "co_varnames",
        "co_filename",
        "co_name",
    )
    if (3, 3) <= version_info:
        attrs += ("co_qualname",)
    attrs += ("co_firstlineno",)
    if (3, 10) <= version_info:
        attrs += ("co_linetable",)
    else:
        attrs += ("co_lnotab",)
    if (3, 11) <= version_info:
        attrs += ("co_exceptiontable",)
    attrs += ("co_freevars", "co_cellvars")
    return attrs


def attr_cmp(obj1: Any, obj2: Any, attrs: Iterable[str]) -> bool:
    """Compares two objects by a collection of their attrs"""
    for attr in attrs:
        if getattr(obj1, attr) != getattr(obj2, attr):
            return False
    return True


def getcode(obj: Any) -> CodeType:
    """Gets the code object from an object via commonly used attrs"""
    for attr in ["__code__", "gi_code", "ag_code", "cr_code"]:
        if hasattr(obj, attr):
            return getattr(obj, attr)
    raise AttributeError("code object not found")


def getframe(obj: Any) -> FrameType:
    """Gets the frame object from an object via commonly used attrs"""
    for attr in ["gi_frame", "ag_frame", "cr_frame"]:
        if hasattr(obj, attr):
            return getattr(obj, attr)
    raise AttributeError("frame object not found")


def hasattrs(self: Any, attrs: Iterable[str]) -> bool:
    """hasattr check over a collection of attrs"""
    for attr in attrs:
        if not hasattr(self, attr):
            return False
    return True


def chain(*iterators: tuple[Iterable]) -> GeneratorType:
    """appends iterators together to yield from one after the other"""
    for iterator in iterators:
        for value in iterator:
            yield value
