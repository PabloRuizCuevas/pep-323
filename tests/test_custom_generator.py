from gcopy.custom_generator import *
import pickle
from types import NoneType


## classes need to be globally defined for it to be picklable ##
## e.g. cannot pickle locally defined classes/types ##
class pickler(Pickler):
    _attrs = ("a", "b", "c")


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
        try:
            assert attr_cmp(
                test_loaded, pickler_test, ("_attrs",) + pickler_test._attrs
            )
        except:
            ## it'll be the frame ##
            print(
                " --- %s attr comparison == False: test_Pickler"
                % (pickler_test.__class__.__name__)
            )


def test_picklers() -> None:
    _frame = frame(currentframe())
    _code = code(_frame.f_code)
    test_Pickler(_code)
    ## probably needs more work before f_back can be pickled ##
    _frame.f_back = None
    test_Pickler(_frame)
    test_Pickler(Generator())


def test_generator_custom_adjustment() -> None:
    gen = Generator()
    gen._internals["lineno"] = 0
    test = gen._custom_adjustment
    ## yield ##
    assert test("yield ... ") == ["return ... "]
    ## yield from ##
    assert test("yield from ... ") == [
        "locals()['.yieldfrom']=... ",
        "for locals()['.i'] in locals()['.yieldfrom']:",
        "    if locals()['.send']:",
        "        return locals()['.i'].send(locals()['.send'])",
        "    else:",
        "        return locals()['.i']",
    ]
    ## for/while positions + default case return ##
    gen._internals["jump_positions"], gen._internals["jump_stack"] = [], []
    assert test("for ") == ["for "]
    assert gen._internals["jump_positions"], gen._internals["jump_stack"] == (
        [[0, None]],
        [(0, 0)],
    )
    assert test("while ") == ["while "]
    assert gen._internals["jump_positions"], gen._internals["jump_stack"] == (
        [[0, None], [0, None]],
        [(0, 0), (0, 1)],
    )
    ## return ##
    assert test("return ... ") == [
        "try:",
        "    return EOF('... ')",
        "finally:",
        "    currentframe().f_back.f_locals['self'].close()",
    ]


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


def test_generator_update_jump_positions() -> None:
    gen = setup()
    ## only positions ##
    # with reference indent #
    assert gen._update_jump_positions([], 4) == []
    assert gen._internals["jump_positions"] == [[1, None], [1, None]]
    assert gen._internals["jump_stack"] == [(0, 0), (0, 1)]
    # without reference indent #
    assert gen._update_jump_positions([]) == []
    assert gen._internals["jump_positions"] == [[1, 2], [1, 2]]
    assert gen._internals["jump_stack"] == []
    ## with stack adjuster ##
    gen = setup()
    new_lines = ["    pass", "    for i in range(3)", "        pass"]
    gen._internals["jump_stack_adjuster"] = [[1, new_lines]]
    ## check: lines, lineno, linetable, jump_positions, jump_stack_adjuster ##
    assert gen._update_jump_positions([]) == new_lines
    assert gen._internals["jump_stack_adjuster"] == []
    assert gen._internals["linetable"] == [2, 3, 4]
    assert gen._internals["lineno"] == 4
    assert gen._internals["jump_positions"] == [[1, 2], [1, 2], [3, 6]]


def test_generator_append_line() -> None:
    # index: int,
    # char: str,
    # source: str,
    # source_iter: Iterable,
    # running: bool,
    # line: str,
    # lines: list[str],
    # indentation: int

    def test(start: int, indentation: int = 0) -> None:
        source = "    print('hi')\n    print('hi');print('hi')\n    def hi():\n        print('hi')\n print() ## comment\n    if True:"
        line = source[: start + 1].split("\n")[-1]
        return gen._append_line(
            start,
            source[start],
            source,
            enumerate(source[start + 1 :], start=start + 1),
            True,
            line,
            [],
            indentation,
        )

    ## empty line ##

    gen = setup()
    assert gen._append_line(0, "", "", "", "", "", [], 0) == (0, "", [], "", True, 0)
    assert gen._append_line(0, "", "", "", "", "         ", [], 0) == (
        0,
        "",
        [],
        "",
        True,
        0,
    )

    ## normal line ##

    test(15)

    ## skip definitions ##

    test(15)

    ## comments ##

    ## statements/colon ##

    ## semi-colon ##


def test_generator_block_adjust() -> None:
    gen = Generator()
    gen._internals["lineno"], gen._internals["jump_stack_adjuster"] = 0, []
    ## if ##
    ## Note: definitions fall under the same as if statements ##
    test = lambda line, current=[]: gen._block_adjust(
        current, *unpack(source_iter=enumerate(line))[:-1]
    )
    assert test("    if     (yield 3):\n        return 4\n") == [
        "    return  3",
        "    locals()['.args'] += [locals()['.send']]",
        "    if locals()['.args'].pop(0):",
    ]
    ## elif ##
    assert test("    elif (yield 3):\n        return 4\n") == [
        "    else:",
        "        return  3",
        "        locals()['.args'] += [locals()['.send']]",
        "        if locals()['.args'].pop(0):",
    ]
    ## except ##
    assert test(
        "    except (yield 3):\n        return 4\n", ["    try:", "        pass"]
    ) == [
        "    try:",
        "        try:",
        "            pass",
        "        except:",
        "            locals()['.error'] = exc_info()[1]",
        "            return  3",
        "            locals()['.args'] += [locals()['.send']]",
        "            raise locals()['.error']",
        "    except locals()['.args'].pop(0):",
    ]
    ## for/while ##
    new_lines = ["    return  3", "    locals()['.args'] += [locals()['.send']]"]
    test_answer = lambda expr: test(
        "    %s (yield 3):\n        return 4\n" % expr
    ) == new_lines + ["    %s locals()['.args'].pop(0):" % expr]
    gen._internals["lineno"], gen._internals["jump_stack_adjuster"] = 0, []
    assert test_answer("for")
    assert gen._internals["lineno"] == 3
    assert gen._internals["jump_stack_adjuster"] == [
        [2] + ["        return  3", "        locals()['.args'] += [locals()['.send']]"]
    ]
    gen._internals["lineno"], gen._internals["jump_stack_adjuster"] = 0, []
    assert test_answer("while")
    assert gen._internals["lineno"] == 3
    assert gen._internals["jump_stack_adjuster"] == [
        [2] + ["        return  3", "        locals()['.args'] += [locals()['.send']]"]
    ]


def test_generator_string_collector_adjust() -> None:
    gen = Generator()
    source = "    print('hi')\n    print(f'hello {(yield 3)}')\n"
    gen._internals["lineno"] = 1

    def test(
        line_start: int, start: int, *answer: tuple[str, tuple[int, int, str], list]
    ) -> tuple[Iterable, int, str]:
        line = source[line_start:start]
        source_iter = enumerate(source[start:], start=start)
        assert (
            gen._string_collector_adjust(
                *next(source_iter), (0, 0, ""), source_iter, line, source, []
            )
            == answer
        )

    ## string collection ##
    test(None, 10, *("'hi'", (10, 13, "'"), []))
    ## f-string ##
    test(
        16,
        27,
        *(
            "",
            (27, 45, "'"),
            [
                "    return  3",
                "    locals()['.args'] += [locals()['.send']]",
                "    print(f'hello {locals()['.args'].pop(0)}')",
            ],
        )
    )


def test_generator_clean_source_lines() -> None:
    ## value yields ##
    ## comments ##
    ## definitions ##
    ## statements ##
    ## named expressions ##
    ## strings ##
    ## f-strings ##
    ## returns - if you have more than one return statement then return ##
    pass


def test_generator_create_state() -> None:
    pass


def test_generator_init_states() -> None:
    gen = Generator(simple_generator())
    ## show the state_generator is dependent on external variables ##
    assert next(gen._internals["state_generator"]) == next(
        gen._internals["state_generator"]
    )
    ## change external variables ##


def simple_generator() -> GeneratorType:
    yield 1
    yield 2
    yield 3


def test_generator__init__() -> None:
    def check(FUNC: Any) -> None:
        """
        Does two checks:
        1. has the attrs
        2. the attrs values are of the correct type
        """
        gen = Generator(FUNC)
        for key, value in {
            "state": NoneType,
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
            "type": type,
            "frame": frame,
        }.items():
            try:
                obj = gen._internals[key]
            except KeyError:
                if key != "linetable":
                    raise AssertionError("Missing key: %s" % key)
                continue
            if isinstance(obj, list):
                if obj:
                    assert isinstance(obj[0], value)
            else:
                assert isinstance(obj, value)

    ## check overwrite in __init__; do we want overwrite? ##

    ## function generator ##
    # uninitilized #
    check(simple_generator)
    # initilized #
    check(simple_generator())
    ## generator expression ##
    # check((i for i in range(3)))
    ## string ##
    check("(i for i in range(3))")


def test_generator_frame_init() -> None:
    gen = Generator()
    gen._internals["frame"] = frame()
    assert (
        gen._frame_init()
        == """def next_state():
    locals=currentframe().f_back.f_locals['self']._locals
    locals()[".args"] = []
    currentframe().f_back.f_locals['.frame']=currentframe()
"""
    )
    gen._internals["frame"].f_locals.update({"a": 3, "b": 2, "c": 1})
    assert (
        gen._frame_init()
        == """def next_state():
    locals=currentframe().f_back.f_locals['self']._locals
    a=locals()[a]
    b=locals()[b]
    c=locals()[c]
    locals()[".args"] = []
    currentframe().f_back.f_locals['.frame']=currentframe()
"""
    )


def test_generator_update() -> None:
    gen = Generator()
    (
        gen._internals["frame"],
        gen._internals["linetable"],
        gen._internals["source_lines"],
    ) = (frame(), [], [])
    _frame = currentframe()
    _frame.f_locals["locals"] = None
    gen._update(_frame, gen._frame_init())
    assert isinstance(gen._internals["frame"], frame)
    assert isinstance(gen._internals["frame"].f_back, frame)
    assert "locals" not in gen._internals["frame"].f_locals
    # print(gen._internals["frame"].f_lineno)
    # assert gen._internals["frame"].f_lineno == 0


def test_generator__next___() -> None:
    assert next(Generator(simple_generator())) == 1


def test_generator__iter___() -> None:
    assert [i for i in Generator(simple_generator())] == [1, 2, 3]


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


def test_generator_send() -> None:
    pass


def test_generator_throw() -> None:
    gen = Generator((i for i in range(3)))
    gen.throw()


def test_generator_type_checking() -> None:
    gen = Generator()
    assert isinstance(gen, (GeneratorType, Generator)) and issubclass(
        type(gen), (GeneratorType, Generator)
    )


## tests are for cleaning + adjusting + pickling ##
test_Pickler()
# test_picklers() ## check Generator
# record_jumps is tested in test_custom_adjustment
test_generator_custom_adjustment()
test_generator_update_jump_positions()
test_generator_append_line()  ## needs more work
test_generator_block_adjust()
test_generator_string_collector_adjust()
# test_generator_clean_source_lines() ## needs more work
# test_generator_create_state()
# test_generator_init_states() ## change the external variables
test_generator__init__()  ## uncomment out the line after expr_getsource is ready + check overwrite
test_generator_frame_init()  ## needs more
test_generator_update()  ## needs more
test_generator__next___()
test_generator__iter___()
test_generator__close()
# test_generator_close()
# test_generator_send()
# test_generator_throw()
test_generator_type_checking()
