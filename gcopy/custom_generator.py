##################################
### picklable/copyable objects ###
##################################
from types import FunctionType, GeneratorType, CodeType
from inspect import currentframe
from copy import deepcopy, copy
from textwrap import dedent
from gcopy.source_processing import *
from gcopy.track import offset_adjust
from sys import exc_info
from functools import partial

try:
    from typing import NoReturn
except:
    ## for 3.5 since 3.6.2; there might be alternatives that are better than this for 3.5 ##
    NoReturn = {"NoReturn"}


## minium version supported ##
## if positions in get_instructions does not happen ##
## for lower versions this will have to be 3.11 ##
# if version_info < (3, 5):
if version_info < (3, 11):
    raise ImportError("Python version 3.11 or above is required")


class Pickler:
    """
    class for allowing general copying and pickling of
    some otherwise uncopyable or unpicklable objects
    """

    _not_allowed = tuple()

    def _copier(self, FUNC: FunctionType) -> object:
        """copying will create a new generator object out of a copied version of the current instance"""
        obj = type(self)()
        obj.__setstate__(self.__getstate__(FUNC))
        return obj

    ## for copying ##
    def __copy__(self) -> object:
        return self._copier(copy)

    def __deepcopy__(self, memo: dict) -> object:
        return self._copier(deepcopy)

    def copy(self, deep: bool = True) -> object:
        """short hand method for copying"""
        if deep:
            return deepcopy(self)
        return copy(self)

    def _pickler_get(obj):
        if issubclass(type(obj), Pickler):
            ## subclasses of Pickler will remove attributes on pickling ##
            for attr in obj._not_allowed:
                if hasattr(obj, attr):
                    delattr(obj, attr)
        return obj

    ## for pickling ##
    def __getstate__(self, FUNC: FunctionType = _pickler_get) -> dict:
        """Serializing pickle (what object you want serialized)"""
        dct = dict()
        attrs, has, get = self._attrs, hasattr, getattr
        is_internals = attrs == ("_internals",)
        if is_internals:
            attrs = self._internals
            has = lambda self, attr: attr in attrs
            get = lambda self, attr: attrs.get(attr)
        for attr in attrs:
            if has(self, attr) and not attr in self._not_allowed:
                dct[attr] = FUNC(get(self, attr))
        if is_internals:
            return {"_internals": dct}
        return dct

    def __setstate__(self, state: dict) -> None:
        """Deserializing pickle (returns an instance of the object with state)"""
        for key, value in state.items():
            setattr(self, key, value)


class code(Pickler):
    """For pickling and copying code objects"""

    _attrs = code_attrs()

    def __init__(self, code_obj: CodeType = None) -> None:
        if code_obj:
            for attr in self._attrs:
                setattr(self, attr, getattr(code_obj, attr, None))

    def __bool__(self) -> bool:
        """Used on i.e. if code_obj:"""
        return hasattrs(self, self._attrs)

    def __eq__(self, obj: Any) -> bool:
        return attr_cmp(self, obj, self._attrs)


class frame(Pickler):
    """
    acts as the initial FrameType

    Note: on pickling ensure f_locals and f_back can be pickled

    Also, this class treats global frames as having no local variables
    to avoid errors in pickling e.g. global frame (on f_back) will have
    its f_locals equal 'None'.
    """

    _attrs = (
        "f_back",
        "f_code",
        "f_lasti",
        "f_lineno",
        "f_locals",
        "f_globals",
        "f_builtins",
        "f_trace",
        "f_trace_lines",
        "f_trace_opcodes",
    )
    _not_allowed = ("f_globals", "f_builtins")

    def __init__(self, frame: FrameType = None) -> None:
        if frame:
            for attr in self._attrs[2:]:
                setattr(self, attr, getattr(frame, attr, None))
            ## to prevent interferrence with pickling
            self.f_back = type(self)(getattr(frame, "f_back", None))
            self.f_code = code(getattr(frame, "f_code", None))
            if self.f_globals == self.f_locals:
                self.f_locals = {}
                ## we have to do this as well since in co_consts you ##
                ## get records of globally defined code objects      ##
                self.f_code = code()
            return
        self.f_locals = {}

    def clear(self) -> None:
        """clears f_locals e.g. 'most references held by the frame'"""
        self.f_locals = {}

    ## we have to implement this if I'm going to go 'if frame:' (i.e. in frame.__init__) ##
    def __bool__(self) -> bool:
        """Used on i.e. if frame:"""
        return hasattrs(self, ("f_code", "f_lasti", "f_lineno", "f_locals"))

    def __eq__(self, obj: Any) -> bool:
        attrs = list(self._attrs)
        for attr in self._not_allowed:
            attrs.remove(attr)
        attrs.remove("f_back")
        return attr_cmp(self, obj, attrs)


class EOF(StopIteration):
    """Custom exception to exit out of the generator on return statements"""

    pass


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

    _attrs = ("_internals",)  ## for Pickler ##
    _not_allowed = ("state_generator",)

    def _api_setup(self) -> None:
        """sets up the api; subclasses should override this method for alternate api setup"""
        self._internals = {
            "prefix": "gi_",
            "type": "GeneratorType",  ## has to be a string, otherwise doesn't get pickled ##
            "version": "",  ## specific to 'async ' Generators for _frame_init ##
        }

    def __init__(
        self,
        FUNC: FunctionType | GeneratorType | str = None,
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
        ## for the api setup ##
        self._api_setup()
        ## __setstate__ from Pickler._copier ##
        if FUNC:
            ## needed to identify certain attributes ##
            prefix = self._internals["prefix"]
            ## running generator ##
            if hasattr(FUNC, prefix + "code"):
                self._internals.update(
                    {
                        "linetable": [],
                        "frame": frame(getframe(FUNC)),
                        "code": code(getcode(FUNC)),
                    }
                )
                ## co_name is readonly e.g. can't be changed by user ##
                if FUNC.gi_code.co_name == "<genexpr>":
                    self._internals["source"] = expr_getsource(FUNC)
                    self._internals["source_lines"] = unpack_genexpr(
                        self._internals["source"]
                    )
                    ## change the offsets into indents ##
                    self._internals["frame"].f_locals = offset_adjust(self._locals())
                    self._internals["lineno"] = len(self._internals["source_lines"])
                ## must be a function ##
                else:
                    self._internals["source"] = dedent(getsource(getcode(FUNC)))
                    self._internals["source_lines"] = clean_source_lines(self, True)
                    ## Might implement at another time but this is just for compound statements ##
                    ## and therefore not strictly necessary from the standpoint of the style guide ##
                    self._internals["lineno"] = (
                        self._internals["frame"].f_lineno
                        - self._internals["code"].co_firstlineno
                        + 1
                    )
                    # self._internals["lineno"] = self._internals["linetable"][
                    #     self._internals["frame"].f_lineno - self._internals["code"].co_firstlineno
                    # ]  + lineno_adjust(self._internals["frame"])
                ## 'gi_yieldfrom' was introduced in python version 3.5 and yield from ... in 3.3 ##
                self._internals.update(
                    {
                        "yieldfrom": getattr(FUNC, prefix + "yieldfrom", None),
                        "suspended": True,
                        "running": False,
                    }
                )
                ## setup api if it's currently running ##
                for key in ("code", "frame", "suspended", "yieldfrom", "running"):
                    setattr(self, prefix + key, self._internals[key])
            ## uninitialized generator ##
            else:
                ## generator function ##
                if isinstance(FUNC, FunctionType):
                    ## add its closure if it has one. It shouldn't ##
                    ## effect the existing locals, only adds the attribute ##
                    if hasattr(FUNC, "__closure__"):
                        self.__closure__ = FUNC.__closure__
                    self.__code__ = self._internals["code"] = code(FUNC.__code__)
                    ## since it's uninitialized we can bind the signature to __call__ ##
                    ## and overwrite the __call__ signature + other metadata with the functions ##
                    self.__call__ = sign(Generator__call__, FUNC, True)
                    if FUNC.__code__.co_name == "<lambda>":
                        self._internals["source"] = expr_getsource(FUNC)
                        self._internals["source_lines"] = unpack_lambda(
                            self._internals["source"]
                        )
                    else:
                        self._internals["source"] = dedent(getsource(FUNC))
                        self._internals["source_lines"] = clean_source_lines(self)
                        self._internals["name"] = self._internals["code"].co_name
                ## source code string ##
                elif isinstance(FUNC, str):
                    self._internals["source"] = FUNC
                    self._internals["source_lines"] = clean_source_lines(self)
                    self._internals["code"] = code(
                        compile(FUNC, currentframe().f_code.co_filename, "exec")
                    )
                ## code object - use a decompilation library and send in as a string ##
                else:
                    raise TypeError(
                        "type '%s' is an invalid initializer for a Generator"
                        % type(FUNC)
                    )
                self._internals.update(
                    {
                        "frame": frame(),
                        "suspended": False,
                        "yieldfrom": None,
                        ## modified every time __next__ is called; always start at line 1 ##
                        "lineno": 1,
                        "running": False,
                    }
                )
            ## create the states ##
            self._internals["state"] = self._internals["source_lines"]
            self._internals["state_generator"] = self._init_states()

    def _init_states(self) -> GeneratorType:
        """Initializes the state generation as a generator"""
        self._internals["loops"] = get_loops(
            self._internals["lineno"], self._internals["jump_positions"]
        )
        ## if no state then it must be EOF ##
        while self._internals["state"]:
            yield self._create_state()

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
        ## jump_positions are in linenos but get_loops automatically sets the indexing to 0 based ##
        loops = self._internals["loops"]
        index = self._internals["lineno"] - 1  ## for 0 based indexing ##
        if loops:
            start_pos, end_pos = loops.pop()
            ## adjustment ##
            blocks, indexes = self._internals["source_lines"][index:end_pos], []
            if index < end_pos and blocks:
                blocks, indexes = control_flow_adjust(
                    blocks,
                    list(range(index, end_pos)),
                    get_indent(self._internals["source_lines"][start_pos]),
                )
                blocks, indexes = loop_adjust(
                    blocks,
                    indexes,
                    self._internals["source_lines"][start_pos:end_pos],
                    *(start_pos, end_pos)
                )
            else:
                loops += [[start_pos, end_pos]]
            self._internals["state"], self._internals["linetable"] = outer_loop_adjust(
                blocks, indexes, self._internals["source_lines"], loops, end_pos
            )
            return
        self._internals["state"], self._internals["linetable"] = control_flow_adjust(
            self._internals["source_lines"][index:],
            list(range(index, len(self._internals["source_lines"]))),
        )

    def _locals(self) -> dict:
        """
        proxy to replace locals within 'next_state' within
        __next__ while still retaining the same functionality
        """
        return self._internals["frame"].f_locals

    def _frame_init(
        self, exception: str = "", close: bool = False, sending=False
    ) -> tuple[int, FunctionType]:
        """
        initializes the frame with the current
        states variables and the _locals proxy
        but also adjusts the current state
        """
        try:
            # set the next state and setup the function; it will raise a StopIteration for us
            next(self._internals["state_generator"])
        except StopIteration as e:
            self._close()
            raise e
        ## adjust the current state ##
        if close:
            self._internals["state"] = exit_adjust(self._internals["state"])
        temp = get_indent(self._internals["state"][0])
        if exception:
            if self._internals["state"][0][temp:].startswith("try:"):
                self._internals["state"] = [
                    self._internals["state"][0],
                    " " * (temp + 4) + "raise " + exception,
                ] + self._internals["state"][1:]
                index_0 = self._internals["linetable"][0]
                self._internals["linetable"] = [index_0, index_0] + self._internals[
                    "linetable"
                ][1:]
            else:
                self._internals["state"] = [
                    " " * temp + "raise " + exception
                ] + self._internals["state"]
                ## -1 so that on +1 (on _update) it will be correct ##
                self._internals["linetable"] = [
                    self._internals["linetable"][0] - 1
                ] + self._internals["linetable"]
        ## initialize the internal locals ##
        f_locals = self._locals()
        if not sending:
            ## we can have this inside the not sending clause since .send is
            ## used only when the generator has been initialized ##
            if ".internals" not in f_locals:
                f_locals[".internals"] = {
                    "exec_info": exc_info,
                    "partial": partial,
                    ".args": [],
                    ".send": None,
                }
            else:
                ## initialize variables for the frame ##
                f_locals[".internals"].update({".send": None})
        ## make sure if it has a closure that it's updating the locals ##
        f_locals.update(get_nonlocals(self))
        name = self._internals.get("name", "next_state")
        ## adjust the initializers ##
        indent = " " * 4
        init = [
            self._internals["version"] + "def %s():" % name,
            ## get the variables to update the frame
            indent + "frame = currentframe()",
            indent + "self = frame.f_back.f_locals['self']",
            indent + "self._locals()['.internals']['.frame'] = frame",
            indent + "locals().update(self._locals())",
            indent + "locals()['.internals']['.self'] = self",
            indent + "del frame, self",
        ]
        ## make sure variables are initialized ##
        for key in f_locals:
            if isinstance(key, str) and key.isidentifier() and key != "locals":
                init += [
                    " " * 4
                    + "%s=locals()['.internals']['.self']._locals()[%s]"
                    % (key, repr(key))
                ]
        ## needs to be added if not already there so it can be appended to ##
        ## try not to use variables here (otherwise it can mess with the state); ##
        ## 'return EOF()' is appended to help return after a loop ##
        ######################################################################
        ## we need to give the original filename before using exec for the code_context to ##
        ## be correct in track_iter therefore we compile first to provide a filename then exec ##
        self.__source__ = init + self._internals["state"] + ["    return EOF()"]
        code_obj = compile("\n".join(self.__source__), "<Generator>", "exec")
        exec(code_obj, globals(), locals())
        return len(init), locals()[name]

    def __iter__(self) -> GeneratorType:
        """Converts the generator function into an iterable"""
        while True:
            try:
                yield next(self)
            except StopIteration:
                break

    def __next__(
        self, exception: str = "", close: bool = False, sending: bool = False
    ) -> Any:
        """updates the current state and returns the result"""
        ## update with the new state and get the frame ##
        init_length, next_state = self._frame_init(exception, close, sending)
        try:
            self._internals["running"] = True
            result = next_state()
            if isinstance(result, EOF):
                raise result
        except Exception as e:
            self._close()
            raise e
        self._internals["running"] = False
        self._update(init_length)
        return result

    def _update(self, init_length: int) -> None:
        """Update the line position and frame"""
        _frame = self._internals["frame"] = frame(
            self._locals()[".internals"][".frame"]
        )

        #### update f_locals ####

        f_locals = _frame.f_locals
        ## remove variables that interfere with pickling ##
        f_locals.pop("locals", None)
        if ".internals" in f_locals:
            f_locals[".internals"].pop(".send", None)
            f_locals[".internals"].pop(".frame", None)
            f_locals[".internals"].pop(".self", None)

        _frame.f_back = None
        if ".yieldfrom" in _frame.f_locals[".internals"]:
            self._internals["yieldfrom"] = _frame.f_locals[".internals"][".yieldfrom"]

        #### update lineno ####

        ## update the frames lineno in accordance with its state ##
        adjusted_lineno = _frame.f_lineno - init_length - 1
        end_index = len(self._internals["linetable"]) - 1
        ## empty linetable ##
        if end_index == -1:
            ## EOF ##
            self._internals["state"] = None
            self._internals["lineno"] = len(self._internals["source_lines"])
        else:
            self._internals["lineno"] = (
                self._internals["linetable"][adjusted_lineno] + 1
            )
            loops = self._internals["loops"] = get_loops(
                self._internals["lineno"], self._internals["jump_positions"]
            )
            if not loops:
                if end_index > adjusted_lineno:
                    self._internals["lineno"] += 1
                else:
                    ## EOF ##
                    self._internals["state"] = None
                    self._internals["lineno"] = len(self._internals["source_lines"])
            elif self._internals["lineno"] < loops[-1][1]:
                self._internals["lineno"] += 1

    def send(self, arg: Any) -> Any:
        """
        Send takes exactly one arguement 'arg' that
        is sent to the functions yield variable
        """
        if arg is not None and self._internals["lineno"] == 1:
            raise TypeError("can't send non-None value to a just-started generator")
        self._locals()[".internals"][".send"] = arg
        return self.__next__(sending=True)

    def _close(self) -> None:
        self._internals.update(
            {
                "state_generator": empty_generator(),
                "state": None,
                "frame": None,
                "running": False,
                "suspended": False,
                "yieldfrom": None,
            }
        )

    def close(self) -> None:
        """
        Throws a GeneratorExit and closes the generator clearing its
        frame, state_generator, and yieldfrom

        return = return
        yield  = return 1
        """
        try:
            if self.__next__("GeneratorExit()", True):
                raise RuntimeError("generator ignored GeneratorExit")
        except GeneratorExit:
            ## This error is internally ignored by generators during closing ##
            pass
        finally:
            self._close()

    def throw(self, exception: Exception) -> NoReturn:
        """
        Raises an exception from the last line in the
        current state e.g. only from what has been
        """
        if issubclass(exception, BaseException):
            if isinstance(exception, type):
                exception = exception.__name__
            else:
                exception = repr(exception)
            return self.__next__(exception)
        raise TypeError(
            "exceptions must be classes or instances deriving from BaseException, not %s"
            % type(exception)
        )

    def __call__(self, *args, **kwargs) -> GeneratorType:
        """
        Calls the instances call method if it has one (only for unintialized Function generators)
        """
        if isinstance(self, type):
            raise TypeError(
                "Only instances of types/classes are allowed (Note: this method is for instances of the Generator type)"
            )
        return self.__call__(self, *args, **kwargs)

    def __instancecheck__(self, instance: object) -> bool:
        return isinstance(instance, eval(self._internals["type"]) | type(self))

    def __subclasscheck__(self, subclass: type) -> bool:
        return issubclass(subclass, eval(self._internals["type"]) | type(self))

    def __setstate__(self, state: dict) -> None:
        Pickler.__setstate__(self, state)
        ## setup the state generator + api ##
        prefix = self._internals["prefix"]
        for key in ("code", "frame", "suspended", "yieldfrom", "running"):
            try:
                setattr(self, prefix + key, self._internals[key])
            except KeyError:
                ## if it doesn't have one of them it shouldn't have any of them ##
                break
        self._internals["state_generator"] = self._init_states()


def Generator__call__(self, *args, **kwargs) -> GeneratorType:
    """
    initializes the generators locals with arguements and keyword arguements
    but is also a shorthand method to initialize the state generator

    Note: this method must be set on initialisation otherwise for some reason
    it still tries to call this method rather than what sometimes should be
    called is the dynamically created method
    """
    ## get the arguments from the function call ##
    arguments = locals()
    ## for the api setup ##
    prefix = self._internals["prefix"]
    for key in ("code", "frame", "suspended", "yieldfrom", "running"):
        setattr(self, prefix + key, self._internals[key])
    if len(arguments) > 1:
        del arguments["self"]
        self._locals().update(arguments)
    self._internals["state_generator"] = self._init_states()
    return self
