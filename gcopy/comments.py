"""
TODO:

    Finish fixing:

         _clean_source_lines:

         - Need to check blocks + named statements with value yields
         - indentation + except adjust needs its indentation fixed
         - Docstring is not quite correct by ending with newlines (doesn't really matter though)

        Non-priority (at the moment) but will be needed later:
        - When do i.e. gi_running and gi_suspended change?
        - check all the documentation + docstrings
        - f_back on frame needs checking

    Expansion to other types of generators:

     - Add some async features to AsyncGenerator - will need to work out how I want to do the async stuff
       async has renamings of the dunders as well i.e. methods of interest are __iter__ is __aiter__, __next__
       is __anext__, and it will probably need an __await__ implementation.

     - Consider generator functions decorated with types.coroutine or if making a coroutine type is necessary

     - Maybe need to make an internal generator and then use this generally?

  - Make a Note in the documentation that while loops don't need tracking and
    indentation is enough as an identifier for tracking
"""
