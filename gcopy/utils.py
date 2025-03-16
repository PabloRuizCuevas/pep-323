from sys import version_info
from inspect import getframeinfo, signature, Signature, BoundArguments, getsource
from readline import get_history_item, get_current_history_length
from dis import get_instructions
from types import FrameType, GeneratorType, CodeType, FunctionType
from typing import Iterable, Any
from collections import OrderedDict


def is_cli() -> bool:
    """Determines if using get_history_item is possible e.g. for CLIs"""
    return bool(get_current_history_length())


def cli_findsource() -> list[str]:
    """Finds the source assuming CLI"""
    length = get_current_history_length()
    return [get_history_item(-i) for i in range(length - 1, 0, -1)]


def skip(iter_val: Iterable, n: int) -> None:
    """Skips the next n iterations in a for loop"""
    for _ in range(n):
        next(iter_val)


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
        flag1, flag2 = hasattr(obj1, attr), hasattr(obj2, attr)
        ## both must have the attr or not to preceed ##
        if flag1 == flag2:
            if flag1 and flag2 and getattr(obj1, attr) != getattr(obj2, attr):
                return False
        else:
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


class binding:
    """
    To make Signature types pickleable (this class is only needed for binding)

    Note: ensure default args are pickleable if wanting to pickle
    """

    _bound_arguments_cls = BoundArguments

    def __init__(self, FUNC: FunctionType) -> None:
        self.parameters = signature(FUNC).parameters

    def __getstate__(self) -> dict:
        return {
            "keys": tuple(self.parameters.keys()),
            "values": tuple(self.parameters.values()),
        }

    def __setstate__(self, state: dict) -> None:
        self.parameters = OrderedDict(zip(state["keys"], state["values"]))

    def bind(self, *args, **kwargs) -> BoundArguments:
        """Convenience method to get the signature"""
        return Signature._bind(self, args, kwargs)

    @property
    def signature(self) -> Signature:
        """Convenience method to get the signature if desired"""
        return Signature(self.parameters.values())

    def __repr__(self) -> str:
        return repr(self.signature)

    def __eq__(self, obj: Any) -> bool:
        if hasattr(obj, "parameters") and isinstance(obj, binding):
            return obj.parameters == self.parameters
        return False


def get_nonlocals(FUNC: FunctionType) -> dict:
    """Gets the nonlocals or closure variables of a function"""
    cells = getattr(FUNC, "__closure__", [])
    nonlocals = {}
    if cells:
        for key, value in zip(FUNC.__code__.co_freevars, cells):
            nonlocals[key] = value.cell_contents
    return nonlocals


def try_set(self, key: Any, value: Any, default: Any = None) -> None:
    """
    Tries to set a value to a key on an
    object if the object is not the default
    """
    if self != default:
        self[key] = value
