from gcopy.track import *


def test_track_iter():
    patch_iterators()
    for i in range(1):
        for j in range(1):
            pass
    assert (
        type(locals()[".internals"][".4"]).__name__
        == type(locals()[".internals"][".8"]).__name__
        == "range_iterator"
    )


def test_offset_adjust():
    assert list(offset_adjust({".1": None, ".2": None, ".3": None}).keys()) == [
        ".4",
        ".8",
        ".12",
    ]


## Note: instance checks will fail because of the monkey patching i.e.    ##
## isinstance("hi",str) will fail because of the fishhook monkey patching ##
## therefore I've ran the tests backwards so that it works
test_offset_adjust()
test_track_iter()
