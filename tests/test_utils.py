from gcopy.utils import *


def test_cli_findsource() -> None:
    if is_cli():
        pass


def test_skip() -> None:
    i = iter(range(3))
    skip(i, 2)
    assert next(i) == 2


def test_is_cli() -> None:
    is_cli()  ## run it to make sure no errors ##


def test_get_col_offset() -> None:
    from inspect import currentframe

    frame = currentframe()
    ## it's essentially the col_offset in this line up to the get_col_offset function ##
    assert get_col_offset(frame) == 11


def test_empty_generator() -> None:
    count = 0
    for i in empty_generator():
        count += 1
    assert count == 0


def test_code_attrs() -> None:
    code_attrs()


def test_attr_cmp() -> None:
    attrs = (
        "co_freevars",
        "co_cellvars",
        "co_firstlineno",
        "co_nlocals",
        "co_stacksize",
        "co_flags",
        "co_code",
        "co_consts",
        "co_names",
        "co_varnames",
        "co_name",
    )
    if (3, 3) <= version_info:
        attrs += ("co_qualname",)
    code_obj_1 = compile("1+1", "", "eval")
    code_obj_2 = compile("1+1", "<string>", "eval")
    assert attr_cmp(code_obj_1, code_obj_2, attrs)
    assert attr_cmp(code_obj_1, code_obj_2, attrs + ("co_filename",)) == False


def test_getcode() -> None:
    ## generator ##
    assert type(getcode((i for i in (None,)))) == CodeType

    ## coroutine ##
    async def t():
        pass

    assert type(getcode(t())) == CodeType

    ## async generator ##
    async def t():
        yield 1

    assert type(getcode(t())) == CodeType


def test_getframe() -> None:
    ## generator ##
    assert type(getframe((i for i in (None,)))) == FrameType

    ## coroutine ##
    async def t():
        pass

    assert type(getframe(t())) == FrameType

    ## async generator ##
    async def t():
        yield 1

    assert type(getframe(t())) == FrameType


def test_hasattrs() -> None:
    assert hasattrs(compile("1+1", "", "eval"), code_attrs())


def test_chain() -> None:
    ls = list(range(1, 5))
    for i in chain([1, 2], [3, 4]):
        assert i == ls.pop(0)


# test_is_cli()
test_cli_findsource()
test_skip()
test_get_col_offset()
test_empty_generator()
test_code_attrs()
test_attr_cmp()
import warnings

with warnings.catch_warnings():
    ## raises a runtime warning because we didn't use the coroutine i.e. in an event loop ##
    warnings.simplefilter("ignore")
    test_getcode()
    test_getframe()
test_hasattrs()
test_chain()
