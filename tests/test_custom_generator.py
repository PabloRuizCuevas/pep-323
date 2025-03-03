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

    #### Note: jump_positions are by lineno not by index ####

    gen = setup()
    gen._internals["lineno"] += 1  ## it won't occur on the same lineno ##
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
    gen._internals["lineno"] += 1
    new_lines = ["    pass", "    for i in range(3)", "        pass"]
    gen._internals["jump_stack_adjuster"] = [[1, new_lines]]
    ## check: lines, lineno, linetable, jump_positions, jump_stack_adjuster ##
    assert gen._update_jump_positions([]) == new_lines
    assert gen._internals["jump_stack_adjuster"] == []
    ## since we're on lineno == 2 the new_lines will be 3, 4, 5 ##
    assert gen._internals["linetable"] == [3, 4, 5]
    assert gen._internals["lineno"] == 5
    assert gen._internals["jump_positions"] == [[1, 2], [1, 2], [4, 7]]


def test_generator_append_line() -> None:

    def test(start: int, index: int, indentation: int = 0) -> None:
        source = "    print('hi')\n    print('hi');\nprint('hi')\n    def hi():\n        print('hi')\n print() ## comment\n    if True:"
        return gen._append_line(
            index,
            source[index],
            source,
            enumerate(source[index + 1 :], start=index + 1),
            True,
            source[start:index],
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
    assert test(0, 15) == (15, "\n", ["    print('hi')"], "", False, 0)
    ## semi-colon ##
    assert test(16, 31) == (31, ";", ["    print('hi')"], "", True, 0)
    ## skip definitions ##
    gen._internals["lineno"] = 1
    assert test(45, 57) == (
        78,
        "\n",
        ["    def hi():", "        print('hi')"],
        "",
        False,
        8,
    )
    assert gen._internals["lineno"] == 3
    ## comments ##
    assert test(79, 88) == (98, "\n", [" print() "], "", False, 0)
    ## statements/colon ##
    assert test(99, 110) == (110, ":", ["    if True:"], "        ", True, 8)


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
    ## for ##
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
    ## while ##
    gen._internals["lineno"], gen._internals["jump_stack_adjuster"] = 0, []
    assert test_answer("while")
    assert gen._internals["lineno"] == 3
    assert gen._internals["jump_stack_adjuster"] == [
        [2] + ["        return  3", "        locals()['.args'] += [locals()['.send']]"]
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
    ## string f-string ##
    test(
        48,
        59,
        *(
            "'hello {{(yield 3)}}'",
            (59, 79, "'"),
            [],
        )
    )


def test_generator_clean_source_lines() -> None:

    ### write one test case that has everything ###
    ## does the line continuation adjustment work  e.g. space + 1 != index ??

    ## value yields ##
    ## comments ##
    ## definitions ##
    ## statements ##
    ## named expressions ##
    ## strings ##
    ## f-strings ##
    ## returns ##
    pass


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
    start_indexes = [0, 2, 4]
    end_indexes = [11, 12, 13]
    ## they get reduced by one in get_loops and originally they are linenos ##
    gen._internals["jump_positions"] = [
        (pos[0] + 1, pos[1] + 1) for pos in zip(start_indexes, end_indexes)
    ]
    assert test(8) == (
        [
            "    return 2",
            "    return 4",
            "    for k in locals()['.12']:",
            "       return 1",
            "       if True:",
            "           return 2",
            "       else:",
            "           return 3",
            "       return 4",
            "    for j in locals()['.8']:",
            "        print(j)",
            "        for k in range(4):",
            "           return 1",
            "           if True:",
            "               return 2",
            "           else:",
            "               return 3",
            "           return 4",
            "        print(j)",
            "    for i in locals()['.4']:",
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
        ],
    )


def test_generator_init_states() -> None:
    gen = Generator(simple_generator())
    ## show the api is setup correctly ##
    for key in dir(gen):
        if key.startswith("gi_"):
            assert getattr(gen, key) is gen._internals[key[3:]]
    assert gen._internals["state"] is None
    ## show the state_generator is dependent on external variables ##
    for _ in range(2):
        next(gen._internals["state_generator"])
        assert gen._internals["state"] == gen._internals["source_lines"]
    ## EOF ##
    gen._internals["state"] = None
    assert next(gen._internals["state_generator"], True)


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
    gen = (i for i in range(3))
    # check(gen)
    ## string ##
    check("(i for i in range(3))")


def test_generator_frame_init() -> None:
    gen = Generator(simple_generator())
    ### state adjustments ###
    ## close/exit ##
    gen._frame_init(close=True)
    assert gen._internals["state"] == ["    return 1" for _ in range(3)]
    ## exception ##
    gen._frame_init("Exception")
    gen._internals["state"] == [
        "    Exception",
        "    return 1",
        "    return 2",
        "    return 3",
    ]

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
        "        Exception",
        "        return 3",
        "    except:",
        "        pass",
    ]
    ### frame adjustments ###
    ## no local variables stored ##
    init, _ = gen._frame_init()
    assert init == [
        "def next_state():",
        "    locals=currentframe().f_back.f_locals['self']._locals",
        '    locals()[".args"] = []',
        "    currentframe().f_back.f_locals['.frame']=currentframe()",
    ]
    ## with local variables stored ##
    gen._internals["frame"].f_locals.update({"a": 3, "b": 2, "c": 1})
    init, _ = gen._frame_init()
    assert init == [
        "def next_state():",
        "    locals=currentframe().f_back.f_locals['self']._locals",
        "    a=locals()[a]",
        "    b=locals()[b]",
        "    c=locals()[c]",
        '    locals()[".args"] = []',
        "    currentframe().f_back.f_locals['.frame']=currentframe()",
    ]


def check_attrs(_frame):
    for attr in frame._attrs:
        print(attr, ": ", end="", sep="")
        try:
            print(getattr(_frame, attr))
        except:
            print()


def test_generator_update() -> None:
    gen = Generator()
    gen._internals.update(
        {
            "frame": None,
            "linetable": [],
            "source_lines": [],
        }
    )
    ## No frame e.g. exception would have occurred ##
    gen._update(None, "")
    # assert gen._internals["frame"] == frame(None)
    assert gen._internals["frame"] == frame()
    assert gen._internals["state"] is None
    assert gen._internals["running"] == False

    ### With frame ###
    ## No previous frame ##
    def test():
        new_frame = frame()
        new_frame.f_locals = {"a": 1, "b": 2, "c": 3, ".send": 1, "locals": gen._locals}
        # for __bool__
        new_frame.f_code = 1
        new_frame.f_lasti = 1
        return new_frame

    gen._internals["frame"] = None
    gen._update(test(), "")
    assert gen._internals["frame"].f_locals == {"a": 1, "b": 2, "c": 3}
    assert gen._internals["frame"].f_back is None
    ## With previous frame ##
    gen._internals["frame"] = temp = test()
    temp.f_locals = {"a": 0, "b": 1, "c": 2}
    gen._update(test(), "")
    ## new frame locals takes precedence ##
    assert gen._internals["frame"].f_locals == {"a": 1, "b": 2, "c": 3}
    ## old frame locals are preserved ##
    assert gen._internals["frame"].f_back.f_locals == temp.f_locals
    ## With lineo ##
    # 3. init
    # 4. lineno - internals
    # 5. source_lines - internals
    ## EOF ##


def test_generator__next__() -> None:
    assert next(Generator(simple_generator())) == 1


def test_generator__iter__() -> None:
    # assert [i for i in Generator(simple_generator())] == [1, 2, 3]
    print([i for i in Generator(simple_generator())])


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
# test_generator_custom_adjustment()
test_generator_update_jump_positions()
test_generator_append_line()
test_generator_block_adjust()
test_generator_string_collector_adjust()
# test_generator_clean_source_lines()
test_generator_create_state()  ## check end_pos and the test case setup used ##
test_generator_init_states()
test_generator__init__()  ## check overwrite + the generator getsource ##
test_generator_frame_init()
test_generator_update()  ## finish the linenos and EOF
# test_generator__next__()
# test_generator__iter__()
test_generator__close()
# test_generator_close()
# test_generator_send()
# test_generator_throw()
test_generator_type_checking()
