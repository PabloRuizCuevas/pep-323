"""
TODO:

1. general testing and fixing to make sure everything works before any more changes are made

    Finish fixing:
        Priority (in order):
        --------------------
        - custom_generator -
        --------------------
          _custom_adjust
          _frame_init
          _record_jumps
          --------------------------------
          string_collector_proxy (f-strings)
          _block_adjust
          _update_jump_positions
          _string_collector_adjust
          _append_line
          ----------------------------------------
          _create_state
          _init_states
          _update
          __next__
          __iter__
          send
          throw
          ----------------------------------------
          __init__
    
        Needs checking:
    
        - check overwrite in __init__
    
        - check __init__ on string and code object initialisation options
        
        - check .send on generator expressions and in general for those that don't use it
    
        - check throw
    
        - check that the returns work now e.g. using next(self) and for i in self: ...


        control_flow_adjust - test to see if except does get included as a first line of a state (it shouldn't)
        need to test what happens when there are no lines e.g. empty lines or no state / EOF
    
        Do after:
        - unpack - fix ordering of list popping when doing recursion
        - lineno_adjust can be done later with track_iter.
        
        Non-priority (at the moment) but will be needed later:
        - get_instructions .positions needs implementing for versions < 3.11 if possible (might not be)
        - check track_iter and probably add more conditional checks?
        - check all the documentation + docstrings
        - f_back on frame needs checking
        - check lineno_adjust to ensure that it's robust, not sure if it works in all cases.
          It relies on a single line containing all the code, it might be possible that you
          can have multiple independent expressions in one line but I haven't checked. -
          This function is only to help with users that choose to use compound statements.

    Expansion to other types of generators:

     - Add some async features to AsyncGenerator - will need to work out how I want to do the async stuff
       async has renamings of the dunders as well i.e. methods of interest are __iter__ is __aiter__, __next__ 
       is __anext__, and it will probably need an __await__ implementation.

     - Consider generator functions decorated with types.coroutine or if making a coroutine type is necessary

     - Maybe need to make an internal generator and then use this generally?

"""
