"""
TODO:

  1. implement ternary statement handling in unpack
  2. finish testing


    Currently not working (_clean_source_lines):
     - some value yields in f-strings in statements
     - ternary expressions with and without value yields
     - the decorator/definition adjustments needs testing
     - collect_lambda needs testing
     - a colon is added in a new line instead of the current
       line for while loops adjusted by _block_adjust or unpack

    Finish fixing:

        _clean_source_lines (testing):

         - check _block_adjust
         - check the resets in variables in _clean_source_lines
           (i.e. after 'yield' and string_collector_adjust)
         - test collect_lambda
         - test the decorator/definition adjustments
         - test ternary statements
         - test cleaning of sourcelines for lambda expressions

        unpack:
         - ternary statements with and without value yields
         - check collect_lambda

      - reseting a generator is possible but no gurantees are made on saving the initial f_locals
        including nonlocals e.g. closure cells. - maybe copy over the __closure__ cells

        Other testing:
        Make sure track_iter is tested in application with generators and generator expresssions

        Non-priority (at the moment) but will be needed later:
        - When do i.e. gi_running and gi_suspended change?
        - check all the documentation + docstrings
        - remove any unncesesary code, comments etc.
        - maybe export all the cleaning stuff to a cleaner class so the Generator class is
          only Generator related. Same might be desired with the code adjustments maybe


    Expansion to other types of generators:

     - Add some async features to AsyncGenerator - will need to work out how I want to do the async stuff
       async has renamings of the dunders as well i.e. methods of interest are __iter__ is __aiter__, __next__
       is __anext__, and it will probably need an __await__ implementation.

     - Consider generator functions decorated with types.coroutine or if making a coroutine type is necessary

     - Maybe need to make an internal generator and then use this generally?

  Documentation notes:

  - Make a Note in the documentation that while loops don't need tracking and
    indentation is enough as an identifier for tracking

  - Make a note in the documentation that yields in comprehension expressions and exec/eval don't occur
    in python syntax

  - write in the documentation that there is a .internal and it has 'args', 'yieldfrom', 'send',
   'exec_info', .decorator, 'partial', '.continue', '.i', '.error', and the tracking variables (indents e.g. '.4' etc.)

    at the moment only 'partial', 'exec_info', '.args', and '.send' are initialized with '.send'
    being initialized with 'None' every iteration except when the user sends an argument

  - I've decided that we don't record f_back for each state since if you really need
    to record the states then you should do that separately before/after each state is
    used because it's generally considered better that way, the bigger downside is the
    memory consumption of saving all the states as f_back on frames when really we're
    usually only interested in it running and it's current state. The previous states
    variables should be the current versions and the linenos can be recorded in between
    states easily. The other exploration one could do is rerunning states again but why
    not just copy the generator then (as this software was designed for)? So it seems
    unnecessary to save as f_back.

"""
