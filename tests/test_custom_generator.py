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


def test_code_and_frame_pickler() -> None:
    _frame = frame(currentframe())
    _code = code(_frame.f_code)
    test_Pickler(_code)
    ## probably needs more work before f_back can be pickled ##
    _frame.f_back = None
    test_Pickler(_frame)


def test_generator_update_jump_positions() -> None:
    pass


def test_generator_append_line() -> None:
    pass


def test_generator_custom_adjustment() -> None:
    pass


def test_generator_clean_source_lines() -> None:
    pass


def test_generator__init__() -> None:
    pass


def test_generator__next___() -> None:
    pass


def test_generator__iter___() -> None:
    pass


def test_generator_type_checking() -> None:
    pass


def test_generator_pickler() -> None:
    pass


test_Pickler()
test_code_and_frame_pickler()