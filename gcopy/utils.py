from sys import version_info
from inspect import currentframe
from readline import get_history_item, get_current_history_length
from dis import _unpack_opargs
from types import FrameType, GeneratorType, CodeType, FunctionType
from typing import Iterable, Any
from opcode import opmap


_opmap = dict(zip(opmap.values(), opmap.keys()))


def is_cli() -> bool:
    """Determines if using get_history_item is possible e.g. for CLIs"""
    return bool(get_current_history_length())


def cli_findsource() -> list[str]:
    """Finds the source assuming CLI"""
    return [
        get_history_item(-i) for i in range(get_current_history_length() - 1, 0, -1)
    ]


def skip(iter_val: Iterable, n: int) -> None:
    """Skips the next n iterations in a for loop"""
    for _ in range(n):
        next(iter_val)


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


def get_nonlocals(FUNC: FunctionType) -> dict:
    """Gets the nonlocals or closure variables of a function"""
    cells = getattr(FUNC, "__closure__", [])
    nonlocals = {}
    if cells:
        for key, value in zip(FUNC.__code__.co_freevars, cells, strict=True):
            try:
                nonlocals[key] = value.cell_contents
            except ValueError as e:
                ## if doing recursion, the function can get recorded as nonlocal ##
                if key == FUNC.__name__:
                    nonlocals[key] = FUNC
                    continue
                raise e
    return nonlocals


def try_set(self, key: Any, value: Any, default: Any = None) -> None:
    """
    Tries to set a value to a key on an
    object if the object is not the default
    """
    if self != default:
        self[key] = value


def get_globals() -> dict:
    """Gets the globals of the originating module that was called from"""
    frame = currentframe()
    while frame.f_code.co_name != "<module>":
        frame = frame.f_back
    return frame.f_globals


def similiar_opcode(
    code_obj1: CodeType,
    code_obj2: CodeType,
    opcode1: int,
    opcode2: int,
    item_index1: int,
    item_index2: int,
) -> bool:
    """
    Determines if the opcodes lead to pratically the same result
    (for similarity between code objects that differ by the variable type attributed to it)
    """
    ## i.e. LOAD, STORE, DELETE ##
    name1 = _opmap[opcode1].split("_")
    name2 = _opmap[opcode2].split("_")
    if name1[0] != name2[0]:
        return False
    mapping = {
        "DEREF": "co_freevars",
        "CLOSURE": "co_cellvars",
        "FAST": "co_varnames",
        "GLOBAL": "co_names",
    }

    # print(getattr(code_obj1, mapping[name1[1]])[item_index1], getattr(code_obj2, mapping[name2[1]])[item_index2])
    def get_code_attr(code_obj: CodeType, name: list[str], item_index: int) -> Any:
        attr = mapping[name[1]]
        array = getattr(code_obj, attr)
        if attr == "co_freevars":
            item_index -= getattr(code_obj, "co_nlocals")
        return array[item_index]

    try:
        return get_code_attr(code_obj1, name1, item_index1) == get_code_attr(
            code_obj2, name2, item_index2
        )
    except (IndexError, KeyError):
        return False


def code_cmp(code_obj1: CodeType, code_obj2: CodeType) -> bool:
    """compares 2 code objects to see if they are essentially the same"""

    def code_setup(code_obj: CodeType) -> bytes:
        count, RESUME = 0, opmap["RESUME"]
        for index, opcode, item_index in _unpack_opargs(code_obj.co_code):
            if opcode == RESUME:
                break
            count += 1
        return _unpack_opargs(code_obj.co_code[count * 2 :])

    try:
        for (index1, opcode1, item_index1), (index2, opcode2, item_index2) in zip(
            code_setup(code_obj1), code_setup(code_obj2), strict=True
        ):
            if opcode1 != opcode2:
                if not similiar_opcode(
                    code_obj1, code_obj2, opcode1, opcode2, item_index1, item_index2
                ):
                    return False
    ## catch the error if the code objects are not the same length ##
    except ValueError:
        return False
    return True
