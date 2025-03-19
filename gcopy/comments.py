"""
TODO:

  - review everything and check for any more relevant unforseen cases

  - check lambda expressions with + without value yields and intialized + unintialized

    overview of nieche cases left to fix (value yield related):
      - f-string with value yields needs handling first for the other special syntaxes it uses
        before going ahead with any unpacking or not.
        
      - ternary expressions with value yields

      - decorators and function definitions with value yield arguments (lambda default args as well)
        - check iteration when this is the case

      - determining the correct lineno on a line of encapsualted value yields
        e.g. (yield (yield (yield)))

    Niche use cases to fix (value yield related):

        Currently not working (_clean_source_lines):
        - some value yields in f-strings in statements
        - ternary expressions with and without value yields
        - the decorator/definition adjustments needs testing
        - collect_lambda needs testing
        - a colon is added in a new line instead of the current
          line for while loops adjusted by _block_adjust or unpack

        source_processing:

          string_collector_proxy (string + multiline_string):
          - implement full checking of f-strings to format these correctly since 
            there are different syntaxes allowable in f-strings. This will also
            help with unpacking but is likely very niche.

          unpack:

          - fix nested ternary statements
           - fix the contents recorded then it should work

          - check collect_lambda

          _clean_source_lines (testing):

          - check _block_adjust
            block_adjust - jump_positions e.g. for yield_adjust used during unpack

          - test collect_lambda
          - test the decorator/definition adjustments - can't test any ternary expressions until unpack is finished


          - check the resets in variables in _clean_source_lines
            (i.e. after 'yield' and string_collector_adjust)


          - test ternary statements
          - test cleaning of sourcelines for lambda expressions
          - close all brackets up to the end of the line - implement this in unpack too

          except_adjust:
          - check except_adjust for multiple try-except catches and finally block

        - lineno will need adjusting if wanting to consider value yield edge case via 
          dis._unpack_opargs maybe. Also, will need getframeinfo().positions.col_offset
          as well to determine where it is in i.e. a ternary expression. It's possible
          to fix but it's going to require a lot more work just for a niche use case to
          get working. If so, the minimum version will have to be back at 3.11 because
          of the offset positions.

  Non-priority (at the moment) but will be needed later:
  - When do i.e. gi_running and gi_suspended change?
  - I'm not sure about ag_await it seems to return None in testing.
    Until I learn of an example of how it's used emerges I'll leave
    it out for now; it's not important for most users anyway.
    
    utils:
      - test utils.cli_getsource
    
    Track:
      - fix any distrurbances from hooks created i.e. type checking was an issue previously
"""
