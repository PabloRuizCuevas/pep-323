"""
TODO:

1. general testing and fixing to make sure everything works before any more changes are made

    Finish fixing:
     - collect_string and collect_multiline_string for the f-string detection
     - unpack
     - get_instructions .positions needs implementing for versions < 3.11 if possible (might not be)

    Needs checking:

    - check lineno_adjust to ensure that it's robust, not sure if it works in all cases.
      It relies on a single line containing all the code, it might be possible that you
      can have multiple independent expressions in one line but I haven't checked. -
      This function is only to help with users that choose to use compound statements.

    - check overwrite in __init__

    - check __init__ on string and code object initialisation options
    
    - check .send on generator expressions and in general for those that don't use it

    - check throw

    - check that the returns work now e.g. using next(self) and for i in self: ...

    Expansion to other types of generators:

     - Add some async features to AsyncGenerator - will need to work out how I want to do the async stuff

     - Consider generator functions decorated with types.coroutine or if making a coroutine type is necessary

     - Maybe need to make an internal generator and then use this generally?

2. write tests

control_flow_adjust - test to see if except does get included as a first line of a state (it shouldn't)
need to test what happens when there are no lines e.g. empty lines or no state / EOF

"""