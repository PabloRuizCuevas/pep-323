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
 - return_linenos
 - reciever
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
