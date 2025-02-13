## minium version supported ##
if version_info < (3, 5):
    ## if positions in get_instructions does not happen ##
    ## for lower versions this will have to be 3.11 ##
    raise ImportError("Python version 3.5 or above is required")
##################################
### picklable/copyable objects ###
##################################
from types import FunctionType, GeneratorType, CodeType
from inspect import currentframe
from copy import deepcopy, copy
from textwrap import dedent
from source_processing import *
from track import offset_adjust

try:
    from typing import NoReturn
except:
    NoReturn = {
        "NoReturn"
    }  ## for 3.5 since 3.6.2; there might be alternatives that are better than this for 3.5 ##


class Pickler:
    """
    class for allowing general copying and pickling of
    some otherwise uncopyable or unpicklable objects
    """

    _not_allowed = tuple()

    def _copier(self, FUNC: FunctionType) -> object:
        """copying will create a new generator object but the copier will determine its depth"""
        obj = type(self)()
        obj.__setstate__(obj.__getstate__(obj, FUNC))
        return obj

    ## for copying ##
    def __copy__(self) -> object:
        return self._copier(copy)

    def __deepcopy__(self, memo: dict) -> object:
        return self._copier(deepcopy)

    ## for pickling ##
    def __getstate__(self, FUNC: FunctionType = lambda x: x) -> dict:
        """Serializing pickle (what object you want serialized)"""
        dct = dict()
        for attr in self._attrs:
            if hasattr(self, attr) and not attr in self._not_allowed:
                dct[attr] = FUNC(getattr(self, attr))
        return dct

    def __setstate__(self, state: dict) -> None:
        """Deserializing pickle (returns an instance of the object with state)"""
        for key, value in state.items():
            setattr(self, key, value)


class frame(Pickler):
    """
    acts as the initial FrameType

    Note: on pickling ensure f_locals
    and f_back can be pickled
    """

    _attrs = (
        "f_back",
        "f_code",
        "f_lasti",
        "f_lineno",
        "f_locals",
        "f_trace",
        "f_trace_lines",
        "f_trace_opcodes",
    )
    _not_allowed = ("f_globals",)
    f_locals = {}
    f_lineno = 1
    f_globals = globals()
    f_builtins = __builtins__

    def __init__(self, frame: FrameType = None) -> None:
        if frame:
            if hasattr(
                frame, "f_back"
            ):  ## make sure all other frames are the custom type as well ##
                self.f_back = type(self)(frame.f_back)
            if hasattr(frame, "f_code"):  ## make sure it can be pickled
                self.f_code = code(frame.f_code)
            for attr in self._attrs[2:]:
                setattr(self, attr, getattr(frame, attr))

    def clear(self) -> None:
        """clears f_locals e.g. 'most references held by the frame'"""
        self.f_locals = {}

    ## we have to implement this if I'm going to go 'if frame:' (i.e. in frame.__init__) ##
    def __bool__(self) -> bool:
        """Used on i.e. if frame:"""
        return hasattrs(self, ("f_code", "f_lasti", "f_lineno", "f_locals"))


class code(Pickler):
    """For pickling and copying code objects"""

    _attrs = code_attrs()

    def __init__(self, code_obj: CodeType = None) -> None:
        if code_obj:
            for attr in self._attrs:
                setattr(self, attr, getattr(code_obj, attr))

    def __bool__(self) -> bool:
        """Used on i.e. if code_obj:"""
        return hasattrs(self, self._attrs)


#################
### Generator ###
#################
class Generator(Pickler):
    """
    Converts a generator function into a generator
    function that is copyable (e.g. shallow and deepcopy)
    and potentially pickle-able

    This should be very portable or at least closely so across
    python implementations ideally.

    The dependencies for this to work only requires that you
    can retrieve your functions source code as a string via
    inspect.getsource.

    How it works:

    Basically we emulate the generator process by converting
    it into an on the fly evaluation iterable thus enabling
    it to be easily copied (Note: deepcopying assumes the
    local variables in the frame can also be copied so if
    you happen to be using a function generator within
    another function generator then make sure that all
    function generators (past one iteration) are of the
    Generator type)

    Note: this class emulates what the GeneratorType
    could be and therefore is treated as a GeneratorType
    in terms of its class/type. This means it's type
    and subclass checked as a Generator or GeneratorType

    The api setup is done via _internals which is a dictionary.
    Essentially, for the various kinds of generator you could
    have you want to assign a prefix and a type. The prefix
    is there to denote i.e. gi_ for Generator, ag_ for
    AsyncGenerator and cr_ for Coroutine such that it's
    very easy to integrate across different implementations
    without losing the familiar api.
    """

    ## Note: by default GeneratorType does not have the  ##
    ## __bool__ (or __nonzero__ in python 2.x) attribute ##
    ## so we don't necessarily have to implement one ##

    _internals = {
        "prefix": "gi_",
        "type": GeneratorType,
        "version": "",
    }  ## for the api setup ##
    _attrs = ("_internals",)  ## for Pickler ##

    def _custom_adjustment(self, line: str, lineno: int) -> list[str]:
        """
        It does the following to the source lines:

        1. replace all lines that start with yields with returns to start with
        2. make sure the generator is closed on regular returns
        3. save the iterator from the for loops replacing with a nonlocal variation
        4. tend to all yield from ... with the same for loop variation
        5. adjust all value yields either via unwrapping or unpacking
        """
        number_of_indents = get_indent(line)
        temp_line = line[number_of_indents:]
        indent = " " * number_of_indents
        if temp_line.startswith("yield from "):
            return [
                indent
                + "currentframe().f_back.f_locals['.yieldfrom']="
                + temp_line[11:],
                indent
                + "for currentframe().f_back.f_locals['.i'] in currentframe().f_back.f_locals['.yieldfrom']:",
                indent + "    return currentframe().f_back.f_locals['.i']",
            ]
        if temp_line.startswith("yield "):
            return [indent + "return" + temp_line[5:]]  ## 5 to retain the whitespace ##
        if temp_line.startswith("for ") or temp_line.startswith("while "):
            self._internals["jump_positions"] += [
                [lineno, None]
            ]  ## has to be a list since we're assigning ##
            self._internals["jump_stack"] += [
                (number_of_indents, len(self._internals["jump_positions"]) - 1)
            ]  ## doesn't have to be a list since it'll get popped e.g. it's not really meant to be modified as is ##
            return [line]
        if temp_line.startswith("return "):
            ## close the generator then return ##
            ## have to use a try-finally in case the user returns from the locals ##
            return [
                indent + "try:",
                indent + "    raise StopIteration(" + line[7:] + ")",
                indent + "finally:",
                indent + "    currentframe().f_back.f_locals['self'].close()",
            ]
        ## handles the .send method ##
        flag, adjustment = send_adjust(temp_line)
        if flag:
            if flag == 2:
                ## 5: to get past the 'yield'
                return [indent + "return" + adjustment[0][5:], indent + adjustment[1]]
            else:
                ## 11: to get past the 'yield from'
                return [
                    indent
                    + "currentframe().f_back.f_locals['.yieldfrom']="
                    + adjustment[0][11:],
                    indent
                    + "for currentframe().f_back.f_locals['.i'] in currentframe().f_back.f_locals['.yieldfrom']:",
                    indent + "    return currentframe().f_back.f_locals['.i']",
                    indent
                    + "    %scurrentframe().f_back.f_locals['.yieldfrom'].send(currentframe().f_back.f_locals['.send'])"
                    % adjustment[1],
                ]
        return [line]

    def _update_jump_positions(
        self, lines: list[str], reference_indent: int = -1
    ) -> None:
        """Updates the end jump positions in self._internals["jump_positions"]"""
        if self._internals["jump_stack"]:
            end_lineno = len(lines) + 1
            while (
                self._internals["jump_stack"]
                and reference_indent <= self._internals["jump_stack"][-1][0]
            ):  # -1: top of stack, 0: indent
                self._internals["jump_positions"][
                    self._internals["jump_stack"].pop()[1]
                ][1] = end_lineno

    def _append_line(
        self,
        source: str,
        source_iter: Iterable,
        running: bool,
        line: str,
        lines: list[str],
        lineno: int,
        indentation: int,
        prev: tuple[int, int, str],
    ) -> tuple[int, str, int, list[str], str, bool, int]:
        ## skip comments ##
        if char == "#":
            for index, char in source_iter:
                if char == "\n":
                    break
        ## make sure to include it ##
        if char == ":":
            indentation = get_indent(line) + 4  # in case of ';'
            line += char
        if not line.isspace():  ## empty lines are possible ##
            reference_indent = get_indent(line)
            self._update_jump_positions(self, lines, reference_indent)
            ## skip the definitions ##
            if is_definition(line[reference_indent:]):
                index, char, lineno, lines = collect_definition(
                    line, lines, lineno, source, source_iter, reference_indent, prev
                )
            else:
                lineno += 1
                lines += self._custom_adjustment(line, lineno)
                ## make a linetable if using a running generator ##
                if running and char == "\n":
                    self._internals["linetable"] += [lineno]
        ## start a new line ##
        if char in ":;":
            # just in case
            indented, line = True, " " * indentation
        else:
            indented, line = False, ""
        return index, char, lineno, lines, line, indented, indentation

    def _clean_source_lines(self, running: bool = False) -> list[str]:
        """
        source: str

        returns source_lines: list[str],return_linenos: list[int]

        1. fixes any indentation issues (when ';' is used) and skips empty lines
        2. split on "\n", ";", and ":"
        3. join up the line continuations i.e. "\ ... " will be skipped

        additionally, custom_adjustment will be called on each line formation as well

        Note:
        jump_positions: are the fixed list of (lineno,end_lineno) for the loops (for and while)
        jump_stack: jump_positions currently being recorded (gets popped into jump_positions once
                     the reference indent has been met or lower for the next line that does so)
                     it records a tuple of (reference_indent,jump_position_index)
        """
        ## for loop adjustments ##
        self._internals["jump_positions"], self._internals["jump_stack"], lineno = (
            [],
            [],
            0,
        )
        ## setup source as an iterator and making sure the first indentation's correct ##
        source = skip_source_definition(self._internals["source"])
        source = source[
            get_indent(source) :
        ]  ## we need to make sure the source is saved for skipping for line continuations ##
        source_iter = enumerate(source)
        line, lines, indented, space, indentation, prev = (
            " " * 4,
            [],
            False,
            0,
            4,
            (0, 0, ""),
        )
        ID, depth = "", 0
        ## enumerate since I want the loop to use an iterator but the
        ## index is needed to retain it for when it's used on get_indent
        for index, char in source_iter:
            ## collect strings ##
            if char == "'" or char == '"':
                line, prev, lines = string_collector_adjust(
                    index, char, prev, source_iter, line, source, lines
                )
            ## makes the line singly spaced while retaining the indentation ##
            elif char == " ":
                if indented:
                    if space + 1 != index:
                        line += char
                else:
                    line += char
                    if space + 1 != index:
                        indented = True
                space = index
            ## join everything after the line continuation until the next \n or ; ##
            elif char == "\\":
                skip_line_continuation(source_iter, source, index)
                line += " "  ## in case of a line continuation without a space before or after ##
            ## create new line ##
            elif char in "#\n;:":
                index, char, lineno, lines, line, indented, indentation = (
                    self._append_line(
                        source,
                        source_iter,
                        running,
                        line,
                        lines,
                        lineno,
                        indentation,
                        prev,
                    )
                )
                space = index  ## this is important (otherwise we get more indents than necessary) ##
            else:
                line += char
                ## detect value yields ##
                depth = update_depth(
                    depth, char
                )  ## [yield] and {yield} is not possible only (yield) ##
                if depth and char.isalnum():
                    ID += char
                    if ID == "yield":
                        temp, line, lines = (
                            len(lines),
                            "",
                            except_adjust(lines, *unpack(line, source_iter)[:-1]),
                        )
                        lineno += 1
                        if running:
                            self._internals["linetable"] += [lineno] * (
                                len(lines) - temp
                            )
                else:
                    ID = ""
        ## in case you get a for loop at the end and you haven't got the end jump_position ##
        ## then you just pop them all off as being the same end_lineno ##
        self._update_jump_positions(self, lines)
        ## jump_stack is no longer needed ##
        del self._internals["jump_stack"]
        return lines

    def _create_state(self) -> None:
        """
        creates a section of modified source code to be used in a
        function to act as a generators state

        The approach is as follows:

        Use the entire source code, reducing from the last lineno.
        Adjust the current source code reduction further out of
        control flow statements, loops, etc. then set the adjusted
        source code as the generators state

        Adjusts source code about control flow statements
        so that it can be used in a single directional flow
        as the generators states

        to handle nesting of loops it will simply join
        all the loops together and run them where the
        outermost nesting will be the final section that
        also contains the rest of the source lines as well
        """
        loops = get_loops(self._internals["lineno"], self._internals["jump_positions"])
        self._internals["loops"] = len(loops)
        temp_lineno = self._internals["lineno"] - 1  ## for 0 based indexing ##
        if loops:
            start_pos, end_pos = loops.pop()
            ## adjustment ##
            blocks, indexes = control_flow_adjust(
                self._internals["source_lines"][temp_lineno:end_pos],
                list(range(temp_lineno, end_pos)),
                get_indent(self._internals["source_lines"][start_pos]),
            )
            blocks, indexes = loop_adjust(
                blocks,
                indexes,
                self._internals["source_lines"][start_pos:end_pos],
                *(start_pos, end_pos)
            )
            self._internals["linetable"] = indexes
            ## add all the outer loops ##
            for start_pos, end_pos in loops[::-1]:
                flag, block = iter_adjust(
                    self._internals["source_lines"][start_pos:end_pos]
                )
                blocks += indent_lines(block, 4 - get_indent(block[0]))
                if flag:
                    self._internals["linetable"] += [start_pos]
                self._internals["linetable"] += list(range(start_pos, end_pos))
            self._internals["state"] = "\n".join(
                blocks + self._internals["source_lines"][end_pos:]
            )
            return
        block, self._internals["linetable"] = control_flow_adjust(
            self._internals["source_lines"][temp_lineno:],
            list(range(temp_lineno, len(self._internals["source_lines"]))),
        )
        self._internals["state"] = "\n".join(block)

    def _locals(self) -> dict:
        """
        proxy to replace locals within 'next_state' within
        __next__ while still retaining the same functionality
        """
        return self._internals["frame"].f_locals

    def _frame_init(self) -> str:
        """
        initializes the frame with the current
        states variables and the _locals proxy
        """
        assign = []
        for key in self._internals["frame"].f_locals:
            if isinstance(key, str) and key.isalnum() and key != "locals":
                assign += [" " * 4 + "%s=locals()[%s]" % (key, key)]
        if assign:
            assign = "\n" + "\n".join(assign)
        else:
            assign = ""
        ## try not to use variables here (otherwise it can mess with the state) ##
        return (
            self._internals["version"]
            + """def next_state():
    locals=currentframe().f_back.f_locals['self']._locals%s
    currentframe().f_back.f_locals['.frame']=currentframe()
"""
            % assign
        )

    def init_states(self) -> GeneratorType:
        """Initializes the state generation as a generator"""
        ## api setup ##
        prefix = self._internals["prefix"]
        for key in ("code", "frame", "suspended", "yieldfrom", "running"):
            setattr(self, prefix + key, self._internals[key])
        del prefix
        ## since self._internals["state"] starts as 'None' ##
        yield self._create_state()
        ## if no state or then it must be EOF, but, if we're in a loop then we need to finish it ##
        while (
            self._internals["state"]
            and self._internals["linetable"] > self._internals["frame"].f_lineno
        ) or self._internals["loops"]:
            yield self._create_state()

    def __init__(
        self,
        FUNC: FunctionType | GeneratorType | CodeType | str = None,
        overwrite: bool = False,
    ) -> None:
        """
        Takes in a function/generator or its source code as the first arguement

        If FUNC=None it will simply initialize as without any attributes, this
        is for the __setstate__ method in Pickler._copier use case

        Note:
         - gi_running: is the generator currently being executed
         - gi_suspended: is the generator currently paused e.g. state is saved

        Also, all attributes are set internally first and then exposed to the api.
        The interals are accessible via the _internals dictionary
        """
        ## __setstate__ from Pickler._copier ##
        if FUNC:
            prefix = self._internals[
                "prefix"
            ]  ## needed to identify certain attributes ##
            ## running generator ##
            if hasattr(FUNC, prefix + "code"):
                self._internals["linetable"] = []
                self._internals["frame"] = frame(getframe(FUNC))
                if (
                    FUNC.gi_code.co_name == "<genexpr>"
                ):  ## co_name is readonly e.g. can't be changed by user ##
                    self._internals["source"] = expr_getsource(FUNC)
                    self._internals["source_lines"] = unpack_genexpr(
                        self._internals["source"]
                    )
                    ## change the offsets into indents ##
                    self._internals["frame"].f_locals = offset_adjust(
                        self._internals["frame"].f_locals
                    )
                else:
                    self._internals["source"] = dedent(getsource(getcode(FUNC)))
                    self._internals["source_lines"] = self._clean_source_lines(True)
                    self._internals["lineno"] = self._internals["linetable"][
                        getframe(FUNC).f_lineno - 1
                    ] + lineno_adjust(FUNC)
                self._internals["code"] = code(getcode(FUNC))
                ## 'gi_yieldfrom' was introduced in python version 3.5 and yield from ... in 3.3 ##
                if hasattr(FUNC, prefix + "yieldfrom"):
                    self._internals["yieldfrom"] = getattr(FUNC, prefix + "yieldfrom")
                else:
                    self._internals["yieldfrom"] = None
                self._internals["suspended"] = True
            ## uninitialized generator ##
            else:
                ## generator function ##
                if isinstance(FUNC, FunctionType):
                    if FUNC.__code__.co_name == "<lambda>":
                        self._internals["source"] = expr_getsource(FUNC)
                    else:
                        self._internals["source"] = dedent(getsource(FUNC))
                    self._internals["code"] = code(FUNC.__code__)
                ## source code string ##
                elif isinstance(FUNC, str):
                    self._internals["source"] = FUNC
                    self._internals["code"] = code(compile(FUNC, "", "eval"))
                ## code object
                elif isinstance(FUNC, CodeType):
                    self._internals["source"] = getsource(FUNC)
                    self._internals["code"] = FUNC
                else:
                    raise TypeError(
                        "type '%s' is an invalid initializer for a Generator"
                        % type(FUNC)
                    )
                ## make sure the source code is standardized and usable by this generator ##
                self._internals["source_lines"] = self._clean_source_lines()
                ## create the states ##
                self._internals["frame"] = frame()
                self._internals["suspended"] = False
                self._internals["yieldfrom"] = None
                self._internals["lineno"] = (
                    1  ## modified every time __next__ is called; always start at line 1 ##
                )
            self._internals["running"] = False
            self._internals["state"] = None
            self._internals["state_generator"] = self.init_states()
            if overwrite:  ## this might not actually work??
                currentframe().f_back.f_locals[getcode(FUNC).co_name] = self

    def __len__(self) -> int:
        """
        Gets the number of states for generators with
        yield statements indented exactly 4 spaces.

        In general, you shouldn't be able to get the length
        of a generator function, but if it's very predictably
        defined then you can.
        """

        def number_of_yields():
            """Gets the number of yields that are indented exactly 4 spaces"""
            for line in self._internals["state"]:
                indents = get_indent(line)
                temp = line[indents:]
                if temp.startswith("yield") and not temp.startswith("yield from"):
                    if indents > 4:
                        raise TypeError(
                            "__len__ is only available where all yield statements are indented exactly 4 spaces"
                        )
                    yield 1

        return sum(number_of_yields())

    def __iter__(self) -> GeneratorType:
        """Converts the generator function into an iterable"""
        while True:
            try:
                yield next(self)
            except StopIteration:
                break

    def __next__(self) -> Any:
        """updates the current state and returns the result"""
        # set the next state and setup the function
        next(
            self._internals["state_generator"]
        )  ## it will raise a StopIteration for us
        ## update with the new state and get the frame ##
        exec(self._frame_init() + self._internals["state"], globals(), locals())
        self._internals["running"] = True
        ## if an error does occur it will be formatted correctly in cpython (just incorrect frame and line number) ##
        try:
            return locals()["next_state"]()
        finally:
            ## update the line position and frame ##
            self._internals["running"] = False
            ## update the frame ##
            f_back = self._internals["frame"]
            self._internals["frame"] = locals()[".frame"]
            if self._internals["frame"]:
                self._internals["frame"] = frame(self._internals["frame"])
                ## remove locals from memory since it interferes with pickling ##
                del self._internals["frame"].f_locals["locals"]
                self._internals["frame"].f_back = f_back
                ## update f_locals ##
                if f_back:
                    f_back.f_locals.update(self._internals["frame"].f_locals)
                    self._internals["frame"].f_locals = f_back.f_locals
                self._internals["frame"].f_locals[".send"] = None
                self._internals["frame"].f_lineno = self._internals[
                    "frame"
                ].f_lineno - self.init.count("\n")
                if (
                    len(self._internals["linetable"])
                    > self._internals["frame"].f_lineno
                ):
                    self._internals["lineno"] = (
                        self._internals["linetable"][self._internals["frame"].f_lineno]
                        + 1
                    )  ## +1 to get the next lineno after returning ##
                else:
                    ## EOF ##
                    self._internals["lineno"] = len(self._internals["source_lines"]) + 1

    def send(self, arg: Any) -> Any:
        """
        Send takes exactly one arguement 'arg' that
        is sent to the functions yield variable
        """
        if self._internals["lineno"] == 1:
            raise TypeError("can't send non-None value to a just-started generator")
        if self._internals["yieldfrom"]:
            self._internals["yieldfrom"].send(arg)
        else:
            self._internals["frame"].f_locals[".send"] = arg
            return next(self)

    def close(self) -> None:
        """Closes the generator clearing its frame, state_generator, and yieldfrom"""
        self._internals.update(
            {
                "state_generator": empty_generator(),
                "frame": None,
                "running": False,
                "suspended": False,
                "yieldfrom": None,
            }
        )

    def throw(self, exception: Exception) -> NoReturn:
        """
        Raises an exception from the last line in the
        current state e.g. only from what has been
        """
        raise exception

    def __setstate__(self, state: dict) -> None:
        Pickler.__setstate__(self, state)
        self._internals["state_generator"] = self.init_states()

    def __instancecheck__(self, instance: object) -> bool:
        return isinstance(instance, self._internals["type"] | type(self))

    def __subclasscheck__(self, subclass: type) -> bool:
        return issubclass(subclass, self._internals["type"] | type(self))
