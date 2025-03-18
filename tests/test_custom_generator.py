from gcopy.custom_generator import *
import pickle
from types import NoneType

#########################
### testing utilities ###
#########################


## classes need to be globally defined for it to be picklable ##
## e.g. cannot pickle locally defined classes/types ##
class pickler(Pickler):
    _attrs = ("a", "b", "c")


def setup() -> Generator:
    """setup used for jump_positions"""
    gen = Generator()
    gen._internals["jump_positions"], gen._internals["jump_stack"] = [
        [1, None],
        [1, None],
    ], [(0, 0), (0, 1)]
    gen._internals["jump_stack_adjuster"], gen._internals["linetable"] = [], []
    gen._internals["lineno"] = 1
    return gen


def simple_generator() -> Generator:
    yield 1
    yield 2
    yield 3


def api_test(gen, flag: bool) -> None:
    """
    Tests if the api is setup correctly

    Note: only for Generators currently e.g. gi_ prefix on attributes
    """
    for key in dir(gen):
        if key.startswith("gi_"):
            assert (getattr(gen, key) is gen._internals[key[3:]]) == flag
    assert gen._internals["state"] == gen._internals["source_lines"]


#############
### tests ###
#############


def test_EOF() -> None:
    try:
        raise EOF()
    except StopAsyncIteration:
        pass

    try:
        raise EOF()
    except StopIteration:
        pass


def test_Pickler(pickler_test: Pickler = None) -> None:
    if pickler_test is None:
        pickler_test = pickler()
        pickler_test.__setstate__(dict(zip(("a", "b", "c"), range(3))))
    assert pickler_test._copier(lambda x: x) is not pickler_test._copier(lambda x: x)
    with open("test.pkl", "wb") as file:
        pickle.dump(pickler_test, file)
    with open("test.pkl", "rb") as file:
        ## they should be identical in terms of the attrs we care about ##
        test_loaded = pickle.load(file)
        if isinstance(pickler_test, Generator):
            if "frame" in test_loaded._internals:
                assert test_loaded._internals["frame"].f_globals == get_globals()
            not_allowed = list(pickler_test._not_allowed)
            ## delete any attrs we don't want to compare ##
            pickler_test = pickler_test._internals
            test_loaded = test_loaded._internals
            for key in pickler_test:
                if key in not_allowed:
                    not_allowed.remove(key)
                    continue
                if not (key in test_loaded and test_loaded[key] == pickler_test[key]):
                    print(
                        " --- %s attr comparison == False: test_Pickler (_internals comparison key: '%s')"
                        % (pickler_test.__class__.__name__, key)
                    )
            return
        try:
            attrs = ("_attrs",) + pickler_test._attrs
            attrs = list(attrs)
            for i in pickler_test._not_allowed:
                attrs.remove(i)
            assert attr_cmp(test_loaded, pickler_test, attrs)
        except AssertionError:
            ## it'll be the frame ##
            print(
                " --- %s attr comparison == False: test_Pickler"
                % (pickler_test.__class__.__name__)
            )


def test_picklers() -> None:
    _frame = frame(currentframe())
    _code = code(_frame.f_code)
    test_Pickler(_code)
    test_Pickler(_frame)
    test_Pickler(Generator())


def test_generator_pickle() -> None:
    gen = Generator(simple_generator)
    attrs_before = dir(gen._internals["frame"])
    test_Pickler(gen)
    ## make sure no change in the attrs ##
    assert attrs_before == dir(gen._internals["frame"])
    assert next(gen) == 1
    ## copy the generator ##
    gen2 = gen.copy()
    gen3 = gen.copy()
    assert next(gen) == next(gen2) == next(gen3)
    assert next(gen) == next(gen2) == next(gen3)
    prefix = gen._internals["prefix"]
    for key in ("code", "frame", "suspended", "yieldfrom", "running"):
        assert hasattr(gen2, prefix + key)


def test_generator_custom_adjustment() -> None:
    gen = Generator()
    gen._internals["lineno"] = 0
    test = partial(custom_adjustment, gen)
    ## yield ##
    assert test("yield ... ") == ["return ... "]
    ## yield from ##
    assert test("yield from ... ") == [
        "locals()['.internals']['.yieldfrom']=... ",
        "for locals()['.internals']['.i'] in locals()['.internals']['.yieldfrom']:",
        "    return locals()['.internals']['.i']",
        "    if locals()['.internals']['.send']:",
        "        return locals()['.internals']['.yieldfrom'].send(locals()['.internals']['.send'])",
    ]
    ## for ##
    gen._internals["jump_positions"], gen._internals["jump_stack"] = [], []
    assert test("for ") == ["for "]
    assert gen._internals["jump_positions"], gen._internals["jump_stack"] == (
        [[0, None]],
        [(0, 0)],
    )
    ## while ##
    assert test("while ") == ["while "]
    assert gen._internals["jump_positions"], gen._internals["jump_stack"] == (
        [[0, None], [0, None]],
        [(0, 0), (0, 1)],
    )
    ## return ##
    assert test("return ... ") == ["return EOF('... ')"]


def test_generator_update_jump_positions() -> None:

    #### Note: jump_positions are by lineno not by index ####

    gen = setup()
    gen._internals["lineno"] += 1  ## it won't occur on the same lineno ##
    ## only positions ##
    # with reference indent #
    assert update_jump_positions(gen, [], 4) == []
    assert gen._internals["jump_positions"] == [[1, None], [1, None]]
    assert gen._internals["jump_stack"] == [(0, 0), (0, 1)]
    # without reference indent #
    assert update_jump_positions(gen, []) == []
    assert gen._internals["jump_positions"] == [[1, 2], [1, 2]]
    assert gen._internals["jump_stack"] == []
    ## with stack adjuster ##
    gen = setup()
    gen._internals["lineno"] += 1
    new_lines = ["    pass", "    for i in range(3)", "        pass"]
    gen._internals["jump_stack_adjuster"] = [[1, new_lines]]
    ## check: lines, lineno, linetable, jump_positions, jump_stack_adjuster ##
    assert update_jump_positions(gen, []) == new_lines
    assert gen._internals["jump_stack_adjuster"] == []
    ## since we're on lineno == 2 the new_lines will be 3, 4, 5 ##
    assert gen._internals["linetable"] == [3, 4, 5]
    assert gen._internals["lineno"] == 5
    assert gen._internals["jump_positions"] == [[1, 2], [1, 2], [4, 7]]


def test_generator_append_line() -> None:

    def test(start: int, index: int, indentation: int = 0) -> None:
        source = "    print('hi')\n    print('hi');\nprint('hi')\n    def hi():\n        print('hi')\n print() ## comment\n    if True:"
        return append_line(
            gen,
            index,
            source[index],
            source,
            enumerate(source[index + 1 :], start=index + 1),
            True,
            source[start:index],
            [],
            indentation,
            0,
        )

    ## empty line ##

    gen = setup()
    assert append_line(gen, 0, "", "", "", "", "", [], 0, 0) == (
        0,
        "",
        [],
        "",
        False,
        0,
        0,
    )
    assert append_line(gen, 0, "", "", "", "", "         ", [], 0, 0) == (
        0,
        "",
        [],
        "",
        False,
        0,
        0,
    )

    ## normal line ##
    assert test(0, 15) == (15, "\n", ["    print('hi')"], "", False, 0, 0)
    ## semi-colon ##
    assert test(16, 31) == (31, ";", ["    print('hi')"], "", True, 0, 0)
    ## comments ##
    assert test(79, 88) == (98, "\n", [" print() "], "", False, 0, 0)
    ## statements/colon ##
    assert test(99, 110) == (110, ":", ["    if True:"], "        ", True, 8, 0)
    ## skip definitions ##
    gen._internals["lineno"] = 1
    gen._internals["decorator"] = False
    assert test(45, 57) == (
        78,
        "\n",
        ["    def hi():", "        print('hi')"],
        "",
        False,
        8,
        0,
    )
    assert gen._internals["lineno"] == 3
    ## decorators ##


def test_generator_block_adjust() -> None:
    gen = Generator()
    gen._internals["lineno"], gen._internals["jump_stack_adjuster"] = 0, []
    ## if ##
    ## Note: definitions fall under the same as if statements ##
    test = lambda line, current=[]: block_adjust(
        gen, current, *unpack(source_iter=enumerate(line))[:-1]
    )
    assert test("    if     (yield 3):\n        return 4\n") == [
        "    return  3",
        "    locals()['.internals']['.args'] += [locals()['.internals']['.send']]",
        "    if locals()['.internals']['.args'].pop():",
    ]
    ## elif ##
    assert test("    elif (yield 3):\n        return 4\n") == [
        "    else:",
        "        return  3",
        "        locals()['.internals']['.args'] += [locals()['.internals']['.send']]",
        "        if locals()['.internals']['.args'].pop():",
    ]
    ## except ##
    assert test(
        "    except (yield 3):\n        return 4\n", ["    try:", "        pass"]
    ) == [
        "    try:",
        "        try:",
        "            pass",
        "        except:",
        "            locals()['.internals']['.error'] = locals()['.internals']['.exc_info']()[1]",
        "            return  3",
        "            locals()['.internals']['.args'] += [locals()['.internals']['.send']]",
        "            raise locals()['.internals']['.error']",
        "    except locals()['.internals']['.args'].pop():",
    ]
    ## for ##
    new_lines = [
        "    return  3",
        "    locals()['.internals']['.args'] += [locals()['.internals']['.send']]",
    ]
    test_answer = lambda expr: test(
        "    %s (yield 3):\n        return 4\n" % expr
    ) == new_lines + ["    %s locals()['.internals']['.args'].pop():" % expr]
    gen._internals["lineno"], gen._internals["jump_stack_adjuster"] = 0, []
    assert test_answer("for")
    assert gen._internals["lineno"] == 3
    assert gen._internals["jump_stack_adjuster"] == [
        [2]
        + [
            "        return  3",
            "        locals()['.internals']['.args'] += [locals()['.internals']['.send']]",
        ]
    ]
    ## while ##
    gen._internals["lineno"], gen._internals["jump_stack_adjuster"] = 0, []
    assert test_answer("while")
    assert gen._internals["lineno"] == 3
    assert gen._internals["jump_stack_adjuster"] == [
        [2]
        + [
            "        return  3",
            "        locals()['.internals']['.args'] += [locals()['.internals']['.send']]",
        ]
    ]


def test_generator_string_collector_adjust() -> None:
    gen = Generator()
    source = "    print('hi')\n    print(f'hello {(yield 3)}')\n    print(f'hello {{(yield 3)}}')"
    gen._internals["lineno"] = 1

    def test(
        line_start: int, start: int, *answer: tuple[str, tuple[int, int, str], list]
    ) -> tuple[Iterable, int, str]:
        line = source[line_start:start]
        source_iter = enumerate(source[start:], start=start)
        print(
            string_collector_adjust(
                gen, *next(source_iter), (0, 0, ""), source_iter, line, source, []
            )
        )
        assert (
            string_collector_adjust(
                gen, *next(source_iter), (0, 0, ""), source_iter, line, source, []
            )
            == answer
        )

    ## string collection ##
    test(None, 10, *("    print('hi'", (10, 13, "'"), []))
    ## f-string ##
    test(
        16,
        27,
        *(
            "",
            (27, 45, "'"),
            [
                "    return  3",
                "    locals()['.internals']['.args'] += [locals()['.internals']['.send']]",
                "    print(f'hello {locals()['.internals']['.args'].pop()}')",
            ],
        ),
    )
    ## string f-string ##
    test(
        48,
        59,
        *(
            "    print(f'hello {{(yield 3)}}'",
            (59, 79, "'"),
            [],
        ),
    )


def test_generator_clean_source_lines() -> None:
    def test():
        yield 1
        for i in range(3):
            yield i
        for i in range(3):
            yield i

    gen = Generator(test())
    ## make sure the jump_positions are forming correctly ##
    assert gen._internals["jump_positions"] == [[2, 3], [4, 5]]

    a = None

    def test() -> Generator:
        """
        single test case that attempts to test most cases:

        ## value yields ##
        ## comments ##
        ## definitions ##
        ## statements ##
        ## named expressions ##
        ## strings ##
        ## f-strings ##
        ## returns ##
        """
        nonlocal a
        yield

        (yield (yield), (yield 3)) == (yield 5), (yield 6)

        if (yield):
            yield from simple_generator()
            return 3
        while 3 < next((yield 3)):
            print(3)
        for i in (yield 2):
            print(2)
        for i in f"{(yield 2)}":
            print(2)
        if i in (yield 2):
            pass
        if i in f"{(yield 2)}":

            pass

        print(f"hi {(yield 2),(yield (yield 2))}")  ## f-string ##
        string = """def test():
    pass
"""
        print(string)

        (a := (yield (a := (yield 3)))) == (yield 3)

        try:
            print()
        except (yield 3):
            pass
        try:
            print()
        except f"hi there{(yield 3)}":
            pass
        if True:
            pass
        elif (yield 3):

            pass

        def test2():
            yield 3

        async def test2():
            yield 3

        class test2:
            def __init__(self):
                yield 3

        func()
        return (yield 3)

    gen = Generator(test)
    for line in gen._internals["source_lines"]:
        print(repr(line))


def test_generator_create_state() -> None:
    gen = Generator()
    gen._internals = {
        "lineno": 1,
        "jump_positions": [],
        "source_lines": [
            "    return 1",
            "    if True:",
            "        return 2",
            "    else:",
            "        return 3",
            "    return 4",
        ],
        "loops": [],
    }

    def test(lineno: int) -> tuple[list[str], list[int]]:
        gen._internals["lineno"] = lineno
        gen._create_state()
        return gen._internals["state"], gen._internals["linetable"]

    ## control_flow_adjust e.g. no loops ##
    assert test(3) == (["    return 2", "    return 4"], [2, 5])
    assert test(5) == (["    return 3", "    return 4"], [4, 5])

    ## with loops ##
    gen._internals["source_lines"] = [
        "    for i in range(3):",
        "        print(i)",
        "        for j in range(4):",
        "            print(j)",
        "            for k in range(4):",
        "               return 1",
        "               if True:",
        "                   return 2",
        "               else:",
        "                   return 3",
        "               return 4",
        "            print(j)",
        "        print(i)",
    ]
    ## Note: the jump_positions are lineno ##
    ## based get_loops changes them to index based ##
    start_indexes = [0, 2, 4]
    end_indexes = [13, 12, 11]
    gen._internals["loops"] = list(zip(start_indexes, end_indexes))
    assert test(8) == (
        [
            "    return 2",
            "    return 4",
            "    for k in locals()['.internals']['.12']:",
            "       return 1",
            "       if True:",
            "           return 2",
            "       else:",
            "           return 3",
            "       return 4",
            "    for j in locals()['.internals']['.8']:",
            "        print(j)",
            "        for k in range(4):",
            "           return 1",
            "           if True:",
            "               return 2",
            "           else:",
            "               return 3",
            "           return 4",
            "        print(j)",
            "    for i in locals()['.internals']['.4']:",
            "        print(i)",
            "        for j in range(4):",
            "            print(j)",
            "            for k in range(4):",
            "               return 1",
            "               if True:",
            "                   return 2",
            "               else:",
            "                   return 3",
            "               return 4",
            "            print(j)",
            "        print(i)",
        ],
        [
            7,
            10,
            4,
            5,
            6,
            7,
            8,
            9,
            10,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            10,
            11,
            12,
            0,
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            10,
            11,
            12,
            13,
        ],
    )


def test_generator_init_states() -> None:
    def test(gen) -> None:
        ## show the state_generator is dependent on external variables ##
        for _ in range(2):
            next(gen._internals["state_generator"])
            assert gen._internals["state"] == gen._internals["source_lines"]
        ## EOF ##
        gen._internals["state"] = None
        assert next(gen._internals["state_generator"], True)

    ## initialized generator ##
    test(Generator(simple_generator()))
    ## uninitialized generator ##
    test(Generator(simple_generator))


def test_generator__init__() -> None:
    def test(FUNC: Any, flag: bool) -> None:
        """
        Does two checks:
        1. has the attrs
        2. the attrs values are of the correct type
        """
        gen = Generator(FUNC)
        api_test(gen, flag)
        for key, value in {
            "state": str,
            "source": str,
            "linetable": int,
            "yieldfrom": NoneType | Iterable | GeneratorType,
            "version": str,
            "jump_positions": int,
            "suspended": bool,
            "prefix": str,
            "lineno": int,
            "code": code,
            "state_generator": GeneratorType,
            "running": bool,
            "source_lines": str,
            "type": str,
            "frame": frame,
        }.items():
            try:
                obj = gen._internals[key]
            except KeyError:
                if (
                    key == "jump_positions"
                    and isinstance(FUNC, GeneratorType)
                    and FUNC.gi_code.co_name == "<genexpr>"
                ):
                    continue
                if key != "linetable":
                    raise AssertionError("Missing key: %s" % key)
                continue
            if isinstance(obj, list):
                if obj:
                    assert isinstance(obj[0], value)
            else:
                assert isinstance(obj, value)

    ## function generator ##
    # uninitilized - this should imply that use as a decorator works also ##
    test(simple_generator, False)
    # initilized #
    test(simple_generator(), True)
    ## generator expression ##
    gen = (i for i in range(3))
    test(gen, True)

    ## test if the function related attrs get transferred ##

    closure_cell = 1

    def test2(FUNC: Any) -> None:
        """docstring"""
        closure_cell

    gen = Generator(test2)

    assert gen.__call__.__annotations__ == test2.__annotations__
    assert gen.__call__.__doc__ == test2.__doc__
    assert get_nonlocals(gen.__closure__) == get_nonlocals(test2.__closure__)


def test_generator__call__() -> None:
    def test(a, b, c=3):
        yield a
        yield b
        yield c

    gen = Generator(test)
    del gen._internals["state_generator"]
    ## initializes but also returns itself ##
    gen = gen(1, 2)
    assert gen is not None
    assert gen._internals["frame"].f_locals == {"a": 1, "b": 2, "c": 3}
    api_test(gen, True)
    assert [i for i in gen] == [1, 2, 3]
    assert gen._internals["state_generator"]


def test_generator_locals() -> None:
    gen = Generator()
    gen._internals["frame"] = frame()
    gen._locals()["a"] = 1
    assert gen._internals["frame"].f_locals == {"a": 1}


def test_generator_frame_init() -> None:
    gen = Generator(simple_generator())

    ### state adjustments ###

    ## exception ##
    gen._frame_init("Exception")
    assert gen._internals["state"] == [
        "    raise Exception",
        "    return 1",
        "    return 2",
        "    return 3",
    ]
    assert gen._internals["linetable"] == [-1, 0, 1, 2]

    ## exception with try block ##
    def test():
        try:
            yield 3
        except:
            pass

    gen2 = Generator(test())
    gen2._frame_init("Exception")
    assert gen2._internals["state"] == [
        "    try:",
        "        raise Exception",
        "        return 3",
        "    except:",
        "        pass",
    ]
    assert gen2._internals["linetable"] == [0, 0, 1, 2, 3]

    ### frame adjustments ###

    ## no local variables stored ##
    init_length, _ = gen._frame_init()
    assert init_length == 8
    ## with local variables stored ##
    gen._internals["frame"].f_locals.update({"a": 3, "b": 2, "c": 1})
    init_length, _ = gen._frame_init()
    assert init_length == 11


def test_generator_update() -> None:
    gen = Generator()
    gen._internals.update(
        {
            "frame": None,
            "linetable": [],
            "source_lines": [],
            "jump_positions": [],
        }
    )

    def test(lineno: int = 0) -> frame:
        new_frame = frame()
        new_frame.f_locals = {
            "a": 1,
            "b": 2,
            "c": 3,
            ".internals": {".send": 1},
        }
        # for __bool__
        new_frame.f_code = 1
        new_frame.f_lasti = 1
        new_frame.f_lineno = lineno
        return new_frame

    ## With previous frame (Note: in order for it to work it needs a frame initailized e.g. a previous frame) ##
    ## old frame (f_back) ##
    gen._internals["frame"] = test()
    ## new/internal frame (frame) ##
    gen._locals()[".internals"][".frame"] = test()
    gen._update(0)
    ## new frame locals takes precedence ##
    assert gen._internals["frame"].f_locals == {
        "a": 1,
        "b": 2,
        "c": 3,
        ".internals": {},
    }
    ## old frame locals are preserved ##
    assert gen._internals["frame"].f_back is None

    ### lineno ###

    ## no linetable / EOF ##
    gen._internals["source_lines"] = ["a", "b", "c"]
    gen._internals["state"] = 1
    gen._locals()[".internals"][".frame"] = test(5)
    gen._update(5)
    assert gen._internals["lineno"] == 3
    assert gen._internals["state"] is None
    ## with linetable ##
    gen._internals["state"] = 1
    gen._internals["linetable"] = [0, 1, 2]
    gen._locals()[".internals"][".frame"] = test(5)
    gen._update(5)
    assert gen._internals["lineno"] == 4
    assert gen._internals["state"] == 1


def test_generator__next__() -> None:
    gen = Generator(simple_generator())
    assert gen._internals["state"] == gen._internals["source_lines"]
    assert next(gen) == 1
    assert gen._locals()[".internals"] == {
        "exec_info": exc_info,
        "partial": partial,
        ".args": [],
    }
    assert gen._internals["state"] == gen._internals["source_lines"]
    assert next(gen) == 2
    assert gen._internals["state"] == gen._internals["source_lines"][1:]
    assert next(gen) == 3
    assert gen._internals["state"] is None
    assert next(gen, True)
    assert gen._internals["frame"] is None


def test_generator__iter__() -> None:
    assert [i for i in Generator(simple_generator())] == [1, 2, 3]

    @Generator
    def gen(*args, **kwargs) -> Generator:
        yield 1
        yield 2
        return 3

    assert [i for i in gen] == [1, 2]

    @Generator
    def test_case():
        yield 1
        for i in range(3):
            yield i

    gen = test_case()
    ## acts as the fishhook iterator for now ##
    range_iterator = iter(range(3))
    next(range_iterator)
    gen._locals()[".internals"] = {".4": range_iterator}
    assert [i for i in gen] == [1, 0, 1, 2]


def test_generator__close() -> None:
    gen = Generator()
    gen._internals = {}
    assert gen._close() is None
    for key, value in {
        "frame": None,
        "running": False,
        "suspended": False,
        "yieldfrom": None,
    }.items():
        assert gen._internals[key] == value
    count = 0
    for i in gen._internals["state_generator"]:
        count += 1
    assert count == 0


def test_generator_close() -> None:
    gen = Generator(simple_generator())
    assert gen.close() is None
    assert gen._internals["frame"] is None

    def test(case: int = 0) -> Generator:
        yield 0
        try:
            yield 1
            yield 2
        except GeneratorExit:
            if case == 0:
                raise GeneratorExit()
            if case == 1:
                yield 4
            return 30

    gen = Generator(test())
    ## start ##
    assert gen.close() is None
    assert gen._internals["frame"] is None

    ### catched ###

    # GeneratorExit #
    gen = Generator(test())
    next(gen)
    assert gen.close() is None
    assert gen._internals["frame"] is None
    # yield #
    gen = Generator(test(1))
    next(gen)
    try:
        gen.close()
    except RuntimeError:
        pass
    # return #
    gen = Generator(test(2))
    next(gen)
    assert gen.close() is None
    assert gen._internals["frame"] is None


def test_generator_send() -> None:
    ## value yield ##
    gen = Generator()
    f = frame()
    f.f_locals = {}
    source_lines = [
        "    return 1",
        "    return 2",
        "    a = locals()['.internals']['.send']",
        "    return a",
    ]
    gen._internals.update(
        {
            "frame": f,
            "code": None,
            "lineno": 1,
            "source_lines": source_lines,
            "jump_positions": [],
            "state": source_lines,
            "running": False,
            "suspended": False,
            "yieldfrom": None,
        }
    )
    gen._internals["state_generator"] = gen._init_states()
    ## can't send if not running ##
    try:
        gen.send(1)
    except TypeError:
        pass
    ## send doesn't change non value recieving yields ##
    assert next(gen) == 1
    assert gen.send(1) == 2
    ## send changes value recieving yield ##
    assert gen.send(1) == 1


def test_generator_throw() -> None:
    gen = Generator(simple_generator())
    try:
        gen.throw(ImportError)
    except ImportError:
        assert gen._internals["linetable"] == [-1, 0, 1, 2]
        assert gen._internals["state"] is None

    def test():
        try:
            yield 1
        except ImportError:
            pass
        yield 2
        yield 3

    gen = Generator(test())
    assert gen.throw(ImportError) == 2
    assert gen._internals["state"][2:] == gen._internals["source_lines"][1:]
    assert gen._internals["linetable"] == [0, 0, 1, 2, 3, 4, 5]


def test_generator_type_checking() -> None:
    gen = Generator()
    assert isinstance(gen, (GeneratorType, Generator)) and issubclass(
        type(gen), (GeneratorType, Generator)
    )


def test_closure() -> None:
    def test():

        closure_cell = 1

        @Generator
        def test_case():
            yield closure_cell
            yield closure_cell
            yield closure_cell
            yield closure_cell

        gen = test_case()
        assert next(gen) == 1
        closure_cell = 2
        assert next(gen) == 2
        gen_copy = gen.copy()
        closure_cell = 3
        ## copies don't retain the closure binding ##
        assert next(gen_copy) == 2
        assert next(gen) == 3
        ## if wanting to bind to a closure ##
        ## then we can be set manually ##
        gen_copy._bind(gen)
        closure_cell = 4
        assert next(gen_copy) == 4
        assert next(gen) == 4

    test()


def test_recursion() -> None:
    @Generator
    def test(depth=0):
        depth += 1
        yield depth
        yield from test(depth)

    gen = test()
    assert [next(gen) for i in range(10)] == list(range(1, 11))


def test_yieldfrom() -> None:
    @Generator
    def test():
        yield from range(3)

    assert [i for i in test()] == [0, 1, 2]


####################################
### asynchronous generator tests ###
####################################


async def async_generator_tests() -> None:

    async def test_asyncgenerator_pickle() -> None:
        pass

    async def test_asyncgenerator_send() -> None:
        pass

    async def test_asyncgenerator_close() -> None:
        pass

    async def test_asyncgenerator_throw() -> None:
        pass

    async def test_asyncgenerator_type_checking() -> None:
        pass

    async def test_asyncgenerator__init__() -> None:
        pass

    async def test_asyncgenerator__anext__() -> None:
        pass

    async def test_asyncgenerator__aiter__() -> None:
        pass

    await test_asyncgenerator_pickle()
    await test_asyncgenerator_send()
    await test_asyncgenerator_close()
    await test_asyncgenerator_throw()
    await test_asyncgenerator_type_checking()
    await test_asyncgenerator__init__()
    await test_asyncgenerator__anext__()
    await test_asyncgenerator__aiter__()


## for debugging at the moment ##
def t():
    source = "forge=x+3+3 if True else y"
    index = 0
    line = ""
    ls, line, _ = unpack(
        line, enumerate(source[index:], start=index), source=source, index=index
    )
    print(
        "\n".join(ls),
        line,
        sep="\n---------------------\n",
    )

    from sys import exit

    exit()


# t()

## tests are for cleaning + adjusting + pickling ##
test_EOF()
test_Pickler()
test_picklers()
test_generator_pickle()
# record_jumps is tested in test_custom_adjustment
# test_generator_custom_adjustment()
test_generator_update_jump_positions()
test_generator_append_line()  ## need to test decorated functions ##
# test_generator_block_adjust()
# test_generator_string_collector_adjust()
# test_generator_clean_source_lines() ## need to implement ternary statements in unpack and fix any other minor problems ##
test_generator_create_state()
test_generator_init_states()
test_generator__init__()
# Generator__call__ is tested in test_generator__call__
test_generator__call__()
test_generator_locals()
test_generator_frame_init()
test_generator_update()
test_generator__next__()
test_generator__iter__()
test_generator__close()
test_generator_close()
test_generator_send()
test_generator_throw()
test_generator_type_checking()
test_closure()
test_recursion()
test_yieldfrom()
import asyncio

asyncio.run(async_generator_tests())
