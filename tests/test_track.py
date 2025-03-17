from gcopy.track import *


def test_offset_adjust() -> None:
    assert list(offset_adjust({".1": None, ".2": None, ".3": None}).keys()) == [
        ".4",
        ".8",
        ".12",
    ]


def test_patch_iters() -> None:
    if isinstance(__builtins__, dict):
        objs = __builtins__.items()
    else:
        objs = vars(__builtins__).items()
    patch_iterators(globals())
    for name, obj in objs:
        if isinstance(obj, type) and issubclass(obj, Iterator | Iterable):
            if obj.__name__ in ("memoryview",):
                iter(obj(b"abcedfg"))
            elif obj.__name__ in ("enumerate", "reversed"):
                iter(obj([]))
            elif obj.__name__ == "range":
                iter(obj(2))
            elif obj.__name__ in ("zip", "filter", "map"):
                iter(obj([], []))
            else:
                iter(obj())


def test_track_iter() -> None:
    patch_iterators(globals())
    ## range iterators (uses hook) ##
    for i in range(3):
        for j in range(3):
            for k in range(3):
                pass
    test = (
        lambda key, value: currentframe()
        .f_back.f_locals[".internals"][".%s" % key]
        .__class__.__name__
        == value
    )
    assert test(4, "range_iterator")
    assert test(8, "range_iterator")
    ## other iterators (doesn't use hook) ##
    for i in list([1, 2, 3]):
        for j in track([1, 2, 3]):
            pass
    assert test(4, "list_iterator")
    assert test(8, "list_iterator")


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


test_patch_iters()
test_track_iter()
test_track_iter_inside_exec()
test_track_iter_inside_Generator()
test_offset_adjust()
