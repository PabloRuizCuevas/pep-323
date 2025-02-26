"""
TODO:

1. general testing and fixing to make sure everything works before any more changes are made

    Finish fixing:
        Priority (in order):
        --------------------
        - custom_generator -
        --------------------
          _append_line
          _clean_source_lines
        ----------------------------------------
          _create_state
          _init_states
          __next__
          __iter__
        ----------------------------------------
          __init__

    
        Do after:
        - unpack - fix ordering of list popping when doing recursion
        
        Non-priority (at the moment) but will be needed later:
        - When do i.e. gi_running and gi_suspended change?
        - check all the documentation + docstrings
        - f_back on frame needs checking
        - get_instructions .positions needs implementing for versions < 3.11 if possible
          (only used for track_iter for generator/lambda expressions)

    Expansion to other types of generators:

     - Add some async features to AsyncGenerator - will need to work out how I want to do the async stuff
       async has renamings of the dunders as well i.e. methods of interest are __iter__ is __aiter__, __next__ 
       is __anext__, and it will probably need an __await__ implementation.

     - Consider generator functions decorated with types.coroutine or if making a coroutine type is necessary

     - Maybe need to make an internal generator and then use this generally?

"""
