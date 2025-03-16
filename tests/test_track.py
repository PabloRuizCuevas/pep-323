from gcopy.track import *
from inspect import currentframe


def test_track_iter() -> None:
    patch_iterators()
    for i in range(1):
        for j in range(1):
            pass
    assert (
        type(locals()[".internals"][".4"]).__name__
        == type(locals()[".internals"][".8"]).__name__
        == "range_iterator"
    )


def test_offset_adjust() -> None:
    assert list(offset_adjust({".1": None, ".2": None, ".3": None}).keys()) == [
        ".4",
        ".8",
        ".12",
    ]


def test_track_iter_inside_exec() -> None:
    FUNC_code = compile(
        """def test():
    for i in range(3):
         return locals()[".internals"][".0"]
""",
        currentframe().f_code.co_filename,
        "exec",
    )
    exec(FUNC_code, globals(), locals())
    range_iterator = locals()["test"]()
    assert [i for i in range_iterator] == [1, 2]


def test_track_iter_inside_Generator() -> None:
    from gcopy.custom_generator import Generator

    @Generator
    def test2():
        for i in range(3):
            yield i

    gen = test2()
    next(gen)
    gen2 = gen.copy()
    assert next(gen._locals()[".internals"][".4"]) == 1
    assert next(gen2._locals()[".internals"][".4"]) == 1


## Note: instance checks will fail because of the monkey patching i.e.    ##
## isinstance("hi",str) will fail because of the fishhook monkey patching ##
## therefore I've ran the tests backwards so that it works
test_offset_adjust()
test_track_iter()
test_track_iter_inside_exec()
test_track_iter_inside_Generator()
