################
### tracking ###
################
from .source_processing import get_indent  # , is_definition, lineno_adjust
from .utils import is_cli, get_history_item, getcode
from inspect import currentframe, getframeinfo, getsourcelines

## for the monkey patching ##
from fishhook import hook, orig  ## pip install fishhook
from typing import Iterator, Iterable, Any
from types import FrameType, FunctionType


def track_iter(obj: Iterator | Iterable, frame: FrameType) -> Iterator | Iterable:
    """
    Tracks an iterator in the local scope initiated by a for loop

    This function has a specific use case where the initialization
    of an iterator via a for loop implictely does not allow for
    reliable extraction from the garbage collector and thus manually
    assigning the iterator for tracking is used

    Note: variables are signified as '.%s' % number_of_indents
    i.e.
        for i in range(3) is 4 indents and thus is assigned '.4'

    This way makes it more effective to retrieve the iterator
    rather than appending iterators. This means only numbers
    that are divisble by 4 should not be used in general usage
    by users.

    When tracking generator expressions it uses the current
    bytecode instruction index instead
    """
    f_locals = frame.f_locals
    ## in case we're checking if it's the same code object in source_processing.extract_source_from_comparison ##
    try:
        code = frame.f_back.f_code
        if (
            code.co_name == "extract_source_from_comparison"
            and code.co_filename.split("\\")[-1] == "source_processing.py"
        ):
            return obj
    except:
        pass
    if frame.f_code.co_name == "<genexpr>":
        if ".internals" not in frame.f_locals:
            frame.f_locals[".internals"] = {}
        if ".0" not in frame.f_locals[".internals"]:
            frame.f_locals[".internals"] |= {
                ".mapping": [0],
                ".0": frame.f_locals[".0"],
            }
            del frame.f_locals[".0"]
        key = frame.f_lasti
        if key not in frame.f_locals[".internals"][".mapping"]:
            frame.f_locals[".internals"][".mapping"] += [key]
    else:
        if is_cli():
            code_context = get_history_item(-frame.f_lineno)
        else:
            ## specific to the Generator class ##
            if frame.f_code.co_filename == "<Generator>":
                source = frame.f_back.f_locals["self"].__source__
                code_context = source[frame.f_lineno - 1]
                ## we have to do it this way since '.internals' is not initiailized in the current f_locals ##
                f_locals = frame.f_locals[".internals"][".self"]._locals()
            else:
                code_context = getframeinfo(frame).code_context[0]
        key = get_indent(code_context)
        ## won't work for compound statements that are in block statements ##
        ## therefore, we check for a block statement and add 4 if so ##
        ## e.g. if iter(k): iter(j); iter(f) e.g. how to get j and f set correctly ##
        # temp = code_context[key:]
        ## needs fixing e.g. lineno_adjust somewhere ##
        ## also why does it not have other block conditions?? e.g. except, elif,case,default etc. ##
        # if (
        #     temp.startswith("if ")
        #     or temp.startswith("for ")
        #     or temp.startswith("while ")
        #     or is_definition(temp)
        # ) and lineno_adjust(frame) == 0:
        #     key += 4
    if ".internals" not in f_locals:
        f_locals[".internals"] = {}
    f_locals[".internals"][".%s" % key] = obj
    return obj


def track_adjust(f_locals: dict) -> bool:
    """
    Adjusts the track_iter created variables
    used in generator expressions from offset
    based to indentation based

    We have to do this because generator expressions
    can only have offset based trackers whereas
    when we format the source lines it requires
    indentation based

    Note: only needed on the current variables
    in the frame that use offset based trackers
    """
    index = 0
    for index, key in enumerate(f_locals.pop(".mapping", []), start=1):
        f_locals[".%s" % (index * 4)] = f_locals.pop(".%s" % key)
    return bool(index)


def track_shift(FUNC: FunctionType, internals: dict) -> None:
    ## adjust the indentation based trackers to a minimum of 4 ##
    indent = get_indent(getsourcelines(getcode(FUNC))[0][0])
    for key in tuple(internals.keys()):
        if isinstance(key, str) and key[0] == "." and key[1:].isdigit():
            new_key = int(key[1:])
            if new_key % 4 == 0:
                internals[".%s" % (new_key - indent)] = internals.pop(key)


####################
## monkey patches ##
####################


def track(obj: Any) -> Any:
    """tracks iterators"""
    frame = currentframe().f_back
    return track_iter(iter(obj), frame)


def atrack(obj: Any) -> Any:
    """tracks async iterators (not needed for internal use but as an option left for the user)"""
    frame = currentframe().f_back
    return track_iter(aiter(obj), frame)


def hook_iter(iterator: Iterator | Iterable, _globals: dict) -> None:
    """
    Replaces the iter of an iterator with track_iter wrapper

    Note: requires _globals e.g. your frames globals dictionary
    in order to make sure it's setup in the correct scope
    """
    try:
        name = iterator.__name__
        orig = iterator.__iter__
        exec("class %s(%s):pass" % (name, name), _globals)
        _globals[name].orig = orig

        def __iter__(self) -> Iterator:
            frame = currentframe().f_back
            return track_iter(self.orig(), frame)

        _globals[name].__iter__ = __iter__
    except:

        @hook(iterator)
        def __iter__(self) -> Iterator:
            iterator = iter(orig(self))
            frame = currentframe().f_back
            return track_iter(iterator, frame)


def patch_iterators(_globals: dict = None) -> None:
    """Sets all builtin iterators in the current scope to their tracked versions"""
    if _globals is None:
        _globals = currentframe().f_back.f_globals
    ## Note: Can't change syntactical initiations e.g. (,), [], {}, and {...:...} ##
    if isinstance(__builtins__, dict):
        objs = __builtins__.items()
    else:
        objs = vars(__builtins__).items()
    for name, obj in objs:
        if isinstance(obj, type) and issubclass(obj, Iterator | Iterable):
            hook_iter(obj, _globals)
