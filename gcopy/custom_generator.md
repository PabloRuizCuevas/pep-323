# custom_generator.py

This file implements a class called Generator to emulate what a function generator does in cpython.

Note: it's currently not finished yet; see the TODO comment on top of the Generator class.

## approach:

To emulate a generator we essentially evaluate source code on fly (section the source code by its yield statements (shouldn't do inner functions however)) using the source code as part fo the generators state. Using source code is much easier to manipulate (especially across different versions of cpython) and means all the work to get it working is mostly in adjusting the source code per iteration when it's needed.

So, specifically what happens is the following:
1. inspect.getsource is called on your function generator (else it will use the string given to it if you're doing that)
2. standardize the source code retrieved and split it by line so that it's in a usable format e.g. makes sure the idents are correct where using ";" (since they don't have to start with an indentation of 4), join up the line continuations i.e. "\ ... " will be skipped, and split on "\n" and ";"
3. translate the source code into a usable format by the generator (Note: this step is still experimental and could change) e.g. some loops might be rewritten into a more usable form.
4. initialize the generator with attributes (should resemble a generators attrs but some are new add ons for better accessibility):
 - gi_code
 - gi_frame
 - gi_running
 - gi_suspended
 - gi_yieldfrom
 - lineno
 - state
 - jump_positions
 - state_generator

From here the generator should be usable.

How the ```next()``` usages work on it (e.g. the \_\_next\_\_ builtin special/magic/dunder method implementation) is to run:
1. ```next()``` on ```state_generator``` to get the next ```state```
2. exec a new temporary function into the current local scope that allows a frame of variables to be passed in and the use of nonlocals
3. run this function returning the result
4. If it ran successfully we're good otherwise the exception will be caught and it will get formatted (how it would be in regular generators; note: this step is optional e.g. it's not a priority to format it's exceptions this way only more beneficial)

## backwards compatibility:

This is mentioned in the comment I made at the top of the file. Fortuneatly this results in simply using if statements and no preprocessing thus far should be needed.

## copying + pickling

Once we've finished the emulation of the generator well then this should be fairly easy. I've only roughly detailed in what needs to happen, but it's not particularly difficult. The same is true with pickling because so long as the emulation works we should be fine.

## Documentation for custom_generator

in this file I'll be exploring the custom_generator.py file at a high level explaining what the core pipeline of the conceptual process is at a high level and then explaining what each and every function does and how it's related to each other in terms of what goals each achieves at a lower level e.g. one of more nuance.

# High level overview:

## code layout

The python module custom_generator can be categorized into sections identified by the comments I've made above these sections e.g.:

 - utility functions:
 - tracking
 - cleaning source code
 - code adjustments
 - expr_getsource
 - genexpr
 - lambda
 - Generator

## proof of concept

The idea is actually very simple e.g. emulate what a generator does.

In order to achieve this the following assumptions are assumed to be true for the software design to conceptually work:

1. you can retrieve the correct source code of your generator expression or generator function.

2. There are no compound statements present in the source code of your generator functions that have yields or yield froms.

We may consider implementing a way to determine the relevant col_offsets required to achieve this (in python version 3.11 we got co_positions which allows this), however, this is discouraged in the python style guide and thus this is not as considerably necessary in light of this view.

Therefore, if there is/are compound statements, there's no way to tell where the states get split up unless we develop and/or utilize such methods that are also robust.

3. you can retrieve the last line of execution in relation to your source code i.e. if ```gen``` is your generator then you should be able to go ```gen.gi_frame.f_lineno``` to retrieve this.

4. all required variables in its current state can be retrieved.

i.e. if again ```gen``` is your generator then you should be able to go ```gen.gi_frame.f_locals``` to retrieve the locals.

One problem is that all implictely defined for loop iterators may not be explicitly located and retrieved from memory. 

e.g. how would you retrieve the iterator defined here reliably (bear in mind that you might also have other range iterators in memory as well):

```python
for i in range(3):
    ...
```
This makes determining where in memory ```iter(range(3))``` is more difficult but is maybe possible in further investigations though from some investigationing it seems at least naievely that it's not possible.

For now this means using our track_iter function; for ease of use we recommend importing the monkey patches that utilize track_iter.

When these assumptions hold the following conceptual design framework follows:

## How does Generator in custom_generator work?

The Generator from custom_generator is initialized through stages starting from the  \_\_init\_\_ method and then after finishing allows the user to access its core implementations desired methods (i.e. \_\_next\_\_,\_\_copy\_\_,\_\_deepcopy\_\_,\_\_getstate\_\_,\_\_setstate\_\_).

These are the stages of initialization in order:

1. determine how to set the attributes based on the type of object passed and then proceed to setting them

2. get the source code

3. clean and format the source lines into lines

 - cleaning: involves removing empty lines, making sure any compound statements that shouldn't have yields are split into lines and their indents are correctly 4 spaces (+ the current indent more if inside a code block)
 
        Note: cleaning doesn't touch defintions

 - formating: this involves changing yields to returns, yield froms to for loops, returns to closing the generator then returning, yields that handle sends with an additional line to catch the recieved value. It also tracks the start and end positions of for/while loops for later temporary adjustments to ensure the code runs correctly.

4. setup the state generator

Setting up the state generator is about adjusting the current state e.g. source code from the current ```f_lineno``` downwards (relative to the new cleaned source lines).

There are 2 adjustments that are be made on creation of its states to ensure the generator runs correctly:

1. ```control_flow_adjust```
    - this is about removal of unreachable code that would otherwise cause syntax errors

    i.e. the following code would not run
    ```python

        print("hi")
    else:
        print("done")
    ```
    Examples such as these are possible because we are simply slicing based on the ```f_lineno``` and trying to exec this.

2. ```temporary_loop_adjust```
    - this is to ensure we are running through the current and outer loops correctly despite slicing through the source as mentioned.

    For example, if this is our source and the dashed line is the cut off from the current ```f_lineno``` this is what running ```temporary_loop_adjust``` is trying to achieve after running ```get_loops```:

    ```python
    for i in range(3):
        for j in range(5):
            print(0)
            for k in range(7):
                if True:
                -----------------------------
                    print(1)
                    continue
                else:
                    print("done")
                break
            print(2)
            for k in range(9):
                print(3)
            print(4)
        print(5)
    ```
    should map to:
    ```python
    while True:
        print(1)
        break
        locals()[".continue"]=False
        break
        break # this break is here by default since the while loop is to help with control flow
    ## next section ##
    if locals()[".continue"]:
        for k in range(7):
            if True:
                print(1)
                continue
            else:
                print("done")
            break
    ## next section ##
    print(2)
    for k in range(9):
        print(3)
    print(4)
    ## next section ##
    for j in range(5):
        print(0)
        for k in range(7):
            if True:
                print(1)
                continue
            else:
                print("done")
            break
        print(2)
        for k in range(9):
            print(3)
        print(4)
    ## next section ##
    for i in range(3):
        for j in range(5):
            print(0)
            for k in range(7):
                if True:
                    print(1)
                    continue
                else:
                    print("done")
                break
            print(2)
            for k in range(9):
                print(3)
            print(4)
        print(5)
    ```

    To illustrate ```get_loops``` it simply tries to identify the following:

    (Note: each colum is a jump_position with its start and end position identified via '-'; '|' indicates the correct selection)

```
               |  |  |
            -  -  -
        -
        -   -        -
f_lineno 
          -    -
                     -
          -
                  -
```
e.g. which of the loop positions together encapsulate the current lineno

based on this we should clearly tell how this relates to the conditional statements in ```get_loops``` source code. The jump positions as mentioned get recorded on ```_custom_adjustment``` (bear in mind that the ordering of ```jump_positions``` recorded on ```_custom_adjustment``` are in order; which means from outer most loop to any encapsulated loops within it).
    
Once, adjusted from source and then adjusted from current state, we can then essentially exec the code and return the result thus completing the emulation of a generator via an on the fly executable source code adjustment iterator.
