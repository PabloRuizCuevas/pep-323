"""
TODO:

  1. finish testing
  2. implement ternary expression handling in unpack (needed but I'd consider it nieche)
  3. implement await statement handling in unpack
     (If we want to be as close to the orginal as possible then it's needed but the
     only difference with it is the ag_await attr which tells the user what object
     is currently being awaited similar to how .yieldfrom e.g. gi_yieldfrom would
     tell the user what's currently being yielded from)

    Currently not working (_clean_source_lines):
     - some value yields in f-strings in statements
     - ternary expressions with and without value yields
     - the decorator/definition adjustments needs testing
     - collect_lambda needs testing
     - a colon is added in a new line instead of the current
       line for while loops adjusted by _block_adjust or unpack

    Finish fixing and testing:

        _clean_source_lines (testing):

         - check _block_adjust
           block_adjust - jump_positions e.g. for yield_adjust used during unpack
         - check the resets in variables in _clean_source_lines
           (i.e. after 'yield' and string_collector_adjust)
         - test collect_lambda
         - test the decorator/definition adjustments
         - test ternary statements
         - test cleaning of sourcelines for lambda expressions

        unpack:

         - ternary statements with and without value yields
         - check collect_lambda

        Non-priority (at the moment) but will be needed later:
        - When do i.e. gi_running and gi_suspended change?
        - clean up everything and document it well

    - try-except-finally with and without multiple except catches
      needs handling implemented in control_flow_adjust

      - need to check except_adjust for this as well

    - expr_getsource + extract_source_from_comparison need to be made
      more precise with eval usage since eval requires the scope used
      e.g. will fail in nieche cases where i.e. there are cell_vars
      or free_vars that are not categorized by the source correctly
      even though they will be captured any way.
"""
