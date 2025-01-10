# pep-323
Copyable Iterators (Generators)

This repo tries to implement a way of copying iterators.

We use code inspection and execution for achiving the result.


we create a new piece of code and use exec for producing a new generator
that would mimic the state of the previous one.

for instance for the generator being executed:

def gen_test():
    a = 1
    b = 2
    b +=10
    yield a
    while True:
        yield b    X code is here now
        b +=1

t = gen_test()
next(t) -> 1
next(b) -> 11

my_copy(t) -> produces a artificial generator as TEXT:

    def gen_test():
        a,b = 1, 11 # from the variables stored

        b +=1 # the rest of the while loop
        while True:  # the while loop untouched
            yield b    X code is here now
            b +=1
and then executes it using exec and saves variables with it.

we  may need to store locals globals as well for the pickling

