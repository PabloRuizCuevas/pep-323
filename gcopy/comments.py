"""
TODO:

    Finish fixing:

        _clean_source_lines (testing):

         - check _block_adjust
         - check the resets in variables in _clean_source_lines
           (i.e. after 'yield' and string_collector_adjust)
         - test collect_lambda
         - test the decorator/definition adjustments
         - test ternary statements

        unpack:
         - ternary statements with and without value yields
         - check collect_lambda

        - fix up tests from new implementations

        Other testing:
        Make sure track_iter is tested in application with generators and generator expresssions

        Non-priority (at the moment) but will be needed later:
        - When do i.e. gi_running and gi_suspended change?
        - check all the documentation + docstrings
        - After stopIteration the frame should be None
        - remove any unncesesary code, comments etc.
        - consider unpacking ternary statements in generator expressions, will have to for lambdas
        - maybe export all the cleaning stuff to a cleaner class so the Generator class is
          only Generator related. Same might be desired with the code adjustments maybe

    Expansion to other types of generators:

     - Add some async features to AsyncGenerator - will need to work out how I want to do the async stuff
       async has renamings of the dunders as well i.e. methods of interest are __iter__ is __aiter__, __next__
       is __anext__, and it will probably need an __await__ implementation.

     - Consider generator functions decorated with types.coroutine or if making a coroutine type is necessary

     - Maybe need to make an internal generator and then use this generally?

  - Make a Note in the documentation that while loops don't need tracking and
    indentation is enough as an identifier for tracking

  - Make a note in the documentation that yields in comprehension expressions and exec/eval don't occur
    in python syntax

  - write in the documentation that there is a .internal and it has 'args', 'yieldfrom', 'send',
   'exec_info', .decorator, 'partial', '.continue', '.i', '.error', and the tracking variables (indents e.g. '.4' etc.)

    at the moment only 'partial', 'exec_info', '.args', and '.send' are initialized with '.send'
    being initialized with 'None' every iteration except when the user sends an argument

"""
