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

        Non-priority (at the moment) but will be needed later:
        - When do i.e. gi_running and gi_suspended change?
        - check all the documentation + docstrings
        - remove any unncesesary code, comments etc.


      - check if 'async for ...' messes with anything
      - Async should in concept integrate with what we have
        so far but just need to test this.

    Expansion to other types of generators:

     - async generators can't be used in await (all await does is pause for the return vaulue;
       generators only yield on next (in this case anext()))

     - they can use anext() does the same as next but uses anext and returns an awaitable object
       e.g. async_generator_asend type

     - they can use aiter(); make sure it's StopAsyncIteration

     - athrow, asend, aclose basically does the same things as generator but uses anext

     - ag_await and cr_await are when you use i.e asyncio.create_task:

        import asyncio

        async def some_task():
            await asyncio.sleep(0.1)

        task = asyncio.create_task(some_task())
        ## delay to allow it to start ##
        await asyncio.sleep(0.1)
        print(task._coro.cr_await)

        This and the fact that you can have i.e.
        await (await ... ), await (await ... ), ...

        Means we'd need to us the unpack function exactly how we would for
        yields but instead of adjusting for yields it would be adjusting
        for awaits (just to know what object is currently being awaited)

     - coroutines are now using await/async syntax since 3.8 deprecated asycnio.coroutine that now
       disallows generator based coroutines e.g. only generators and async generators are possible.
"""
