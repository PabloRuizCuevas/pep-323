from gcopy.my_copy import Code, my_copy


def gtest5(a):
    a = a + 2
    yield a
    while True:
        a += 1
        yield a
        a += 2


t1 = gtest5(10)
assert next(t1) == 12
assert next(t1) == 13

code = Code.from_generator(t1)
print(code)
tc = my_copy(t1)
assert next(tc) == 16
