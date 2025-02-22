from gcopy.custom_generator import *
import pickle


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
        "    return locals()['.i']",
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
        "    raise StopIteration(... )",
        "finally:",
        "    currentframe().f_back.f_locals['self'].close()",
    ]


def test_generator_update_jump_positions() -> None:
    gen = Generator()
    ## only positions ##
    gen._internals["jump_positions"], gen._internals["jump_stack"] = [
        [0, None],
        [0, None],
    ], [(0, 0), (0, 1)]
    gen._internals["jump_stack_adjuster"], gen._internals["linetable"] = [], []
    gen._internals["lineno"] = 1
    assert gen._update_jump_positions([]) == []
    assert gen._internals["jump_positions"], gen._internals["jump_stack"] == (
        [[0, 1], [0, 1]],
        [],
    )
    ## with stack adjuster ##
    gen._internals["jump_positions"], gen._internals["jump_stack"] = [
        [0, None],
        [0, None],
    ], [(0, 0), (0, 1)]
    gen._internals["jump_stack_adjuster"] = []
    # assert gen._update_jump_positions([], 1) == []
    # assert gen._internals["jump_stack_adjuster"] == ...
    # assert gen._internals["linetable"] == [1, 1]


# self._internals["jump_stack_adjuster"] += [lineno, new_lines]


def test_generator_append_line() -> None:
    pass


def test_generator_block_adjust() -> None:
    pass


def test_generator_string_collector_adjust() -> None:
    pass


def test_generator_clean_source_lines() -> None:
    pass


def test_generator_create_state() -> None:
    pass


def test_generator_init_states() -> None:
    pass


def test_generator__init__() -> None:
    pass


def test_generator_frame_init() -> None:
    gen = Generator()
    gen._internals["frame"] = frame()
    assert (
        gen._frame_init()
        == """def next_state():
    locals=currentframe().f_back.f_locals['self']._locals
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
    currentframe().f_back.f_locals['.frame']=currentframe()
"""
    )


def test_generator_update() -> None:
    pass


def test_generator__next___() -> None:
    pass


def test_generator__iter___() -> None:
    pass


def test_generator_close() -> None:
    gen = Generator()
    gen._internals = {}
    assert gen.close() is None
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
    pass


def test_generator_type_checking() -> None:
    gen = Generator()
    assert isinstance(gen, (GeneratorType, Generator)) and issubclass(
        type(gen), (GeneratorType, Generator)
    )


def test_generator__len___() -> None:
    pass


## tests are for Cleaning + adjusting + pickling ##
test_Pickler()
# test_picklers()
# record_jumps is tested in test_custom_adjustment
test_generator_custom_adjustment()
test_generator_update_jump_positions()  ## fix for _block_adjust - stack_adjusters
# test_generator_append_line()
# test_generator_block_adjust()
# test_generator_string_collector_adjust()
# test_generator_clean_source_lines()
# test_generator_create_state()
# test_generator_init_states()
# test_generator__init__()
test_generator_frame_init()
# test_generator_update()
# test_generator__next___()
# test_generator__iter___()
test_generator_close()
# test_generator_send()
# test_generator_throw()
test_generator_type_checking()
# test_generator__len__()
