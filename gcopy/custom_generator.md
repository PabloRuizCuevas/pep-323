# custom_generator.py

This file implements a class called Generator to emulate what a function generator does in cpython.

Note: it's currently not finished yet; see the TODO comment on top of the Generator class.

## approach:

To emulate a generator we essentially evaluate source code on fly (section the source code by its yield statements (shouldn't do inner functions however)) using the source code as part fo the generators state. Using source code is much easier to manipulate (especially across different versions of cpython) and means all the work to get it working is mostly in adjusting the source code per iteration when it's needed.

To handle Sends I've thought about using a Send class and using that to make the code explicit though I don't really like this from a user stand point even though it makes the lexing/parsing easier for me I think it'd be better if it were not needed and we find a way around it.

## backwards compatibility:

This is mentioned in the comment I made at the top of the file. Fortuneatly this results in simply using if statements and no preprocessing thus far should be needed.

## copying + pickling

Once we've finished the emulation of the generator well then this should be fairly easy. I've only roughly detailed in what needs to happen, but it's not particularly difficult. The same is true with pickling because so long as the emulation works we should be fine.
