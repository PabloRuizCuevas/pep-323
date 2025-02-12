################
### tracking ###
################
from source_processing import is_definition, lineno_adjust, get_indent
from utils import is_cli, get_history_item, get_col_offset
from inspect import currentframe, getframeinfo

## for the monkey patching ##
from fishhook import hook, orig  ## pip install fishhook
from typing import Iterator, Iterable


def track_iter(obj: Iterator | Iterable) -> Iterator | Iterable:
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

    Using in generator expressions uses the col_offset instead
    """
    obj = iter(obj)
    frame = currentframe().f_back
    if frame.f_code.co_name == "<genexpr>":
        ## we don't need to concern about interference with indent adjusts since the frames ##
        ## are separate  e.g. we don't need to include the line and the offset just the offset ##
        key = get_col_offset(frame)
    else:
        if is_cli():
            code_context = get_history_item(-frame.f_lineno)
        else:
            code_context = getframeinfo(frame).code_context[0]
        key = get_indent(code_context)
        ## won't work for compound statements that are in block statements ##
        ## therefore, we check for a block statement and add 4 if so ##
        temp = code_context[key:]
        if (
            temp.startswith("if ")
            or temp.startswith("for ")
            or temp.startswith("while ")
            or is_definition(temp)
        ) and lineno_adjust(frame.f_code, frame) == 0:
            key += 4
    frame.f_locals[".%s" % key] = obj
    return obj


def offset_adjust(f_locals: dict) -> dict:
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
    ## the first offset will probably get in the way ##
    lineno = 0  ## every line will increase the indentation by 4 ##
    for key, value in f_locals.items():
        if isinstance(key, str) and key[0] == "." and key[1:].isdigit():
            del f_locals[key]
            lineno += 1
            f_locals[4 * lineno] = value
    return f_locals


####################
## monkey patches ##
####################
def hook_iter(iterator: Iterator | Iterable) -> None:
    try:
        name = iterator.__name__
        exec("class %s(%s):pass" % (name, name), globals())

        def __iter__(self) -> Iterator:
            f_locals = currentframe().f_back.f_locals
            return track_iter(iterator, f_locals)

        globals()[name].__iter__ = __iter__
    except:

        @hook(iterator)
        def __iter__(self) -> Iterator:
            iterator = orig(self)
            f_locals = currentframe().f_back.f_locals
            return track_iter(iterator, f_locals)


#############################
#### patch all iterators ####
#############################
## Note: Can't change syntactical initiations e.g. (,), [], {}, and {...:...} ##
for name, obj in vars(__builtins__).items():
    if isinstance(obj, type) and issubclass(obj, Iterator | Iterable):
        hook_iter(obj)
