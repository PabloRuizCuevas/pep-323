from gcopy.my_copy import my_copy


def gtest1():
    yield 10
    yield 20
    yield 30


def test_1():
    t1 = gtest1()
    tc = my_copy(t1)
    assert next(tc) == 10
    assert next(tc) == 20

    assert next(t1) == 10
    tc = my_copy(t1)
    assert next(tc) == 20


def gtest2(a):
    yield 10
    if a:
        yield 20
    yield 30


def test_2():
    t1 = gtest2(1)
    tc = my_copy(t1)
    assert next(tc) == 10

    t1 = gtest2(2)
    assert next(t1) == 10
    tc = my_copy(t1)
    assert next(tc) == 20
    assert next(tc) == 30
    assert next(t1) == 20


def gtest3(a):
    yield 10
    if a:
        yield 20
    else:
        yield 40
    yield 30


def test_3():
    t1 = gtest3(True)
    assert next(t1) == 10
    assert next(t1) == 20
    tc = my_copy(t1)
    assert next(tc) == 30

    t1 = gtest3(False)
    assert next(t1) == 10
    assert next(t1) == 40
    tc = my_copy(t1)
    assert next(tc) == 30


def gtest4(a):
    b = 10
    yield b
    if a:
        b += 10
        yield b
        b += 10
    else:
        b += 30
        yield b
        b -= 10
    yield b


def test_4():
    t1 = gtest4(True)
    assert next(t1) == 10
    assert next(t1) == 20
    tc = my_copy(t1)
    assert next(tc) == 30

    t1 = gtest3(False)
    assert next(t1) == 10
    assert next(t1) == 40
    tc = my_copy(t1)
    assert next(tc) == 30


def gtest5(a):
    a = a + 2
    yield a
    while True:
        a += 1
        yield a
        a += 2


def test_5():  # avg
    t1 = gtest5(10)
    assert next(t1) == 12
    assert next(t1) == 13
    tc = my_copy(t1)
    assert next(tc) == 16
    assert next(t1) == 16


def tests():
    test_1()
    test_2()
    test_3()
    test_4()
    test_5()
