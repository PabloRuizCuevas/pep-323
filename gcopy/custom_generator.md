## Documentation for custom_generator

in this file I'll be exploring the custom_generator.py file at a high level explaining what the core pipeline of the conceptual process is at a high level and then explaining what each and every function does and how it's related to each other in terms of what goals each achieves at a lower level e.g. one of more nuance.

## custom_generator.py

This file implements a class called Generator to emulate what a function generator does in cpython.

Note: it's currently not finished yet; see the TODO comment on top of the Generator class.

## approach:

To emulate a generator we essentially evaluate source code on the fly sectioning the source code by its yield statements (shouldn't do inner functions however) and using these sections of the source code as each generators state. Using source code is much easier to manipulate (especially across different versions of cpython) and means all the work to get it working is mostly in initialisation and adjusting the source code per iteration.

There are two parts that make up the process on the whole e.g. initialisation and generation:

# Detailed overview

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

# Running the Generator:

## Assumptions

The idea is actually very simple e.g. emulate what a generator does.

In order to achieve this the following assumptions are assumed to be true for the software design to conceptually work:

1. you can retrieve the correct source code of your generator expression or generator function.

2. There are no compound statements present in the source code of your generator functions that have yields or yield froms.

This assumption has been somewhat relaxed with the implementation of ```lineno_adjust``` and the use of ```get_instructions``` however this is not guranteed to work across all python versions since 3.11 is when python introduced ```CodeType.co_positions``` enabling source code positions with column offsets but in general using compound statements is not recommended when trying to initialize a ```Generator``` instance from a running generator.

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

## initialisation

1. The source code of your generator is retrieved via ```inspect.getsource``` and ```expr_getsource``` for function generators and expressions respectively and you can pass in a string of source code as well.
2. standardize the source code retrieved and split it into lines so that it's in a usable format using ```Generator._clean_source_lines```. 

e.g. 
- makes sure the indents are correct where using ";" (since they don't have to start with an indentation of 4)

- split on "\n" and ";"

- join up the line continuations i.e. "\ ... " will be skipped

translate certain sections of the source code into a usable format by the generator with ```Generator._custom_adjustment```
e.g. 
 - ```yield``` statements are written as returns to give the temporary exiting; this helps with the code adjustments later that gives the continuation.

 - ```yield from``` statements are written as for loops with returns to give the same effect as yields.

 - ```return``` statements are replaced with a ```StopIteration``` of the return value written in a try-finally clause to then close the generator after doing so and end the state generations.

 - Definitions e.g. ```def, async def, class, async class``` are left untouched since these are classes/functions of their own.

 - assignment yields e.g. ```...=yield ...``` are adjusted so that it's more accessible to recieving values sent to it via the ```Generator.send``` method

 - Records the start and end ```lineno``` positions for the for and while loops for later use when needing to adjust the current source code inside a loop encapsulation. These positions are recorded in the ```Generator._internals["jump_positions"]``` variable. Temporarily, a ```jump_stack``` is also used to later detect the end position and then update this in the jump_position back in ```Generator._clean_source_lines```.

Also, value yields are handled via ```Generator._clean_source_lines``` and both string collector functions (or ```string_collector_proxy```)  e.g. yields of the form ```(yield ...)``` (yield statement with brackets around it).

Value yields need adjustment via ```value_yield_adjust``` by inserting new lines into the current source lines as the value yields need to be evaluated prior to usage e.g. value yields yield values but also returns a value (e.g. if you send a value to it via ```Generator.send``` rather than running ```next()``` otherwise its return value is by default ```None```) therefore the idea is to yield the values before (will work the same since the entire line is ran like this e.g. anything before the yield will also need to be saved into the stack since the yield could yield from an i.e. iterable and therefore depends on what line ran before), save their returns into a temporary stack, pop the stack / unpack all the value into its expression.

```value_yield_adjust``` recieves the source line and the current index which is the index associated with the identification that the source code cleaner has encountered a value yield and therefore needs to adjust it. What it does is go from left to right unpacking and unwrapping the expressions into lines in correct order of execution so that it can be usable by the Generator making sure to save the return values of each yield in a stack that gets popped as the replacement for the adjustment.

Each value yield individually will simply be adjusted as a send or assignment yield to work in the Generator.

4. initialize the generator ```_internals``` with attributes (should resemble a generators attrs but some are new add ons for better accessibility):
 - gi_code
 - gi_frame
 - gi_running
 - gi_suspended
 - gi_yieldfrom
 - lineno
 - state
 - jump_positions
 - state_generator

Note: I've made the attrs available under ```_internals``` to seperate the familiar api and the attrs used and may likely changes this from a dictionary to a class or attrdict if desirable for example since I also want to make separate the initializer/preparation methods. This also helps with translating the Generator function to ```AsyncGenerator``` since it means only needing to setup the prefix and type as seen in the code:
```python
class AsyncGenerator(Generator):
    _internals={"prefix":"ag_","type":AsyncGeneratorType}
```
So this means the attrs starting with a prefix will be accessible via i.e. ```Generator(FUNC).gi_frame``` but the others only via ```Generator(FUNC)._internals```.

5. The state generator (```Generator()._internals.state_generator```) is created via ```Generator.init_states```. This firstly sets up the API to ensure all attributes using the prefix that are accessed by the user should be set and then sets the state generator as an evaluation loop where with each iteration the code is adjusted by ```Generator._create_state```.

Adjustments are with ```get_loops``` and ```lineno``` to slice the source code to the current ```lineno```, finish the current loop encapsulating the current line, and adjust the current control flow. ```get_loops``` gets the loops encapsulating the current line. It does a linear search to check which one.

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
e.g. which of the loop positions together encapsulate the current ```lineno```

In ```Generator._create_state``` we can adjust by ```lineno``` because the code is split up into lines and there are no yields present in the function body excluding inner definitions. This should mean that every line is a single execution and therefore no two lines should (by design) show up thereby allowing a clear iteration progression.

Additionally, the ```control_flow_adjust``` function is used to address unreachable code that occurs since we simply slice the source code by a lineno e.g.:

i.e. the following code would not run due to a ```SyntaxError```

```python

    print("hi")
else:
    print("done")
```
Examples such as these are possible because we are simply slicing based on the ```f_lineno``` and trying to exec this.

Lastly the ```loop_adjust``` is responsible for ensuring that all loops have been iterated through correctly under the same approach of simply slicing the source code lines.

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
locals()['.continue']=True
for _ in (None,):
    print(1)
    break # continue adjustment
    break # break adjustment
    locals()[".continue"]=False
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

It's also important to note that doing such adjustments e.g. ```control_flow_adjust``` and ```loop_adjust``` will change the source code and thus the line numbers, therefore, to ensure we can still perform our slicing we need to create a ```linetable``` for determining the current ```lineno``` correctly after each ```state``` completion.

## Generation

How the ```next()``` (e.g. the ```__next__``` builtin special/magic/dunder method implementation) usages works is to run:
1. ```next()``` on ```state_generator``` to get the next ```state``` e.g. a sliced string (by the current lineno (this is why splitting the source code into lines before was important)) of the pre prepared source code with adjustments. The adjustments are done via the ```Generator()._internals.state_generator``` iterations/yield function (```Generator().init_states```) as mentioned.
   
3. exec a new temporary function into the current local scope with an initialisation header that makes sure to first load in the previous states local variables to retain the current state.

The header is created from ```Generator._frame_init``` and is used to monkey patch the locals with the ```Generator._locals``` proxy (since apparently it may have variations between versions as to how it works), set up the previous frames locals, save the current frame in the previous frame e.g. inside ```Generator.__next__``` so the generator can update its state.

5. run this function returning the result then updating the state and ```lineno```  using a try-finally block. Because the source code may get adjusted, a linetable is used to determine the ```lineno```.

Note: "locals" in i.e. ```Generator().gi_frame``` (```Generator._locals``` that monkey patched ```locals```) is deleted from the frame locals during this try-finally block since this may/should not be pickled but shouldn't be in there anyway since it was only a proxy to ensure consistency.

## copying + pickling

So long as the assumptions mentioned under the assumptions section of this document hold and the frame locals are copyable/pickleable then it should be possible to copy/pickle a generator under these conditions.

How copying and pickling is done is via an inheritance (since more than one class made use of the same methods) of the ```Pickler``` class on definition of the ```Generator``` class. Essentially the idea is simple e.g. if you can copy/pickle the attributes that comprise of the objects state then just copy/unpickle these to make up the object since we cannot directly copy/pickle the object.

This ends up being very simple in implementation as for pickling we are effectively running a for loop on a selection or array of attrs that get a ```getattr``` and ```setattr``` applied for ```__getstate__``` and ```__setstate__``` respectively. For copying we are essentially making use of ```__getstate__``` but applying the desired copier to the attribute e.g. ```copy.copy``` or ```copy.deepcopy```.

You should see that I've made a custom ```code``` and ```frame``` class that also inherit the ```Pickler``` class to ensure that these objects are also pickleable since they are by default not allowed to be pickled.
