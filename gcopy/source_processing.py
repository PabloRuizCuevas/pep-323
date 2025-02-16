#################################################
### cleaning/extracting/adjusting source code ###
#################################################
from .utils import *
from inspect import getsource, findsource
from typing import Iterable, Any
from types import GeneratorType, FrameType


def update_depth(depth: int, char: str, selection: tuple[str, str] = ("(", ")")) -> int:
    """Updates the depth of brackets"""
    if char in selection[0]:
        depth += 1
    elif char in selection[1]:
        depth -= 1
    return depth


def get_indent(line: str) -> int:
    """Gets the number of spaces used in an indentation"""
    count = 0
    for char in line:
        if char != " ":
            break
        count += 1
    return count


def lineno_adjust(frame: FrameType) -> int:
    """
    unpacks a line of compound statements
    into lines up to the last instruction
    that determines the adjustment required
    """
    line, current_lineno, instructions = (
        [],
        frame.f_lineno,
        get_instructions(frame.f_code),
    )
    ## get the instructions at the lineno ##
    for instruction in instructions:
        lineno, obj = instruction.positions.lineno, (
            list(instruction.positions[2:]),
            instruction.offset,
        )
        if not None in obj[0] and lineno == current_lineno:
            ## exhaust the iter to get all the lines ##
            line = [obj]
            for instruction in instructions:
                lineno, obj = instruction.positions.lineno, (
                    list(instruction.positions[2:]),
                    instruction.offset,
                )
                if lineno != current_lineno:
                    break
                line += [obj]
            break
    ## combine the lines until f_lasti is encountered to return how many lines ##
    ## futher from the current line would the offset be if split up into lines ##
    if line:
        index, current, lasti = 0, [0, 0], frame.f_lasti
        line.sort()
        for pos, offset in line:
            if offset == lasti:
                return index
            if pos[0] > current[1]:  ## independence ##
                current = pos
                index += 1
            elif pos[1] > current[1]:  ## intersection ##
                current[1] = pos[1]
    raise ValueError("f_lasti not encountered")


def unpack_genexpr(source: str) -> list[str]:
    """unpacks a generator expressions' for loops into a list of source lines"""
    lines, line, ID, depth, prev, has_for, has_end_if = (
        [],
        "",
        "",
        0,
        (0, 0, ""),
        False,
        False,
    )
    source_iter = enumerate(source[1:-1])
    for index, char in source_iter:
        if char in "\\\n":
            continue
        ## collect strings
        if char == "'" or char == '"':
            line, prev = string_collector_proxy(index, char, prev, source_iter, line)
            continue
        ## we're only interested in when the generator expression ends in terms of the depth ##
        depth = update_depth(depth, char)
        ## accumulate the current line
        line += char
        ## collect IDs
        if char.isalnum():
            ID += char
        else:
            ID = ""
        if depth == 0:
            if ID == "for" or ID == "if" and next(source_iter)[1] == " ":
                if ID == "for":
                    lines += [line[:-3]]
                    line = line[-3:]  # +" "
                    if not has_for:
                        has_for = len(lines)  ## should be 1 anyway
                elif has_for:
                    lines += [
                        line[:-2],
                        source[index:-1],
                    ]  ## -1 to remove the end bracket - is this necessary?
                    has_end_if = True
                    break
                else:
                    lines += [line[:-2]]
                    line = line[-2:] + " "
                # ID="" ## isn't necessary because you don't get i.e. 'for for' or 'if if' in python syntax
    if has_end_if:
        lines = lines[has_for:-1] + (lines[:has_for] + [lines[-1]])[::-1]
    else:
        print("here:", lines)
        lines = lines[has_for:] + (lines[:has_for])[::-1]
    ## arrange into lines
    indent = " " * 4
    return [indent * index + line for index, line in enumerate(lines, start=1)]


def skip_line_continuation(source_iter: Iterable, source: str, index: int) -> None:
    """skips line continuations in source"""
    whitespace = get_indent(source[index + 1 :])  ## +1 since 'index:' is inclusive ##
    ## skip the whitespace after newline ##
    ## skip the current char, whitespace, newline and whitespace after ##
    skip(source_iter, whitespace + 1 + get_indent(source[index + 1 + whitespace + 1 :]))


def skip_source_definition(source: str) -> str:
    """Skips the function definition and decorators in the source code"""
    ID, source_iter = "", enumerate(source)
    for index, char in source_iter:
        ## decorators are ignored ##
        while char == "@":
            while char != "\n":
                index, char = next(source_iter)
            index, char = next(source_iter)
        if char.isalnum():
            ID += char
            if len(ID) == 3:
                if ID == "def" and next(source_iter)[1] == " ":
                    while char != "(":
                        index, char = next(source_iter)
                    break
                return source
        else:
            ID = ""
    depth = 1
    for index, char in source_iter:
        if char == ":" and depth == 0:
            return source[index + 1 :]
        depth = update_depth(depth, char, ("([{", ")]}"))
    raise SyntaxError("Unexpected format encountered")


def collect_string(
    source_iter: Iterable, reference: str, source: str = False
) -> tuple[int, str | list[str]]:
    """
    Collects strings in an iterable assuming correct
    python syntax and the char before is a qoutation mark

    Note: make sure source_iter is an enumerated type
    """
    line, backslash, left_brace, lines = reference, False, -2, []
    for index, char in source_iter:
        if char == reference and not backslash:
            line += char
            break
        line += char
        backslash = False
        if char == "\\":
            backslash = True
        ## detect f-strings for value yields ##
        if source and char == "{":
            if index - 1 != left_brace:
                temp_lines, final_line, right_brace = unpack_fstring(
                    source, source_iter, left_brace
                )
                ## update ##
                lines += temp_lines
                line += final_line
            left_brace = index
    if source:
        return index, lines + [line]  ## we have to add it for the f-string case ##
    return index, line


def collect_multiline_string(
    source_iter: Iterable, reference: str, source: str = False
) -> tuple[int, str | list[str]]:
    """
    Collects multiline strings in an iterable assuming
    correct python syntax and the char before is a
    qoutation mark

    Note: make sure source_iter is an enumerated type

    if a string starts with 3 qoutations
    then it's classed as a multistring
    """
    line, backslash, prev, count, left_brace, lines = reference, False, -2, 0, None, []
    for index, char in source_iter:
        if char == reference and not backslash:
            if index - prev == 1:
                count += 1
            else:
                count = 0
            prev = index
            if count == 2:
                line += char
                break
        line += char
        backslash = False
        if char == "\\":
            backslash = True
        ## detect f-strings for value yields ##
        if source and char == "{":

            ## needs fixing ##
            if left_brace and index - 1 != left_brace:
                temp_lines, final_line, right_brace = unpack_fstring(
                    source, source_iter, left_brace
                )
                ## update ##
                lines += temp_lines
                line += final_line
            left_brace = index
    if source:
        return index, lines + [line]  ## we have to add it for the f-string case ##
    return index, line


def string_collector_proxy(
    index: int,
    char: str,
    prev: tuple[int, int, str],
    iterable: Iterable,
    line: str = None,
    source: str = None,
) -> tuple[list[str], str, int]:
    """Proxy function for usage when collecting strings since this block of code gets used repeatedly"""
    # get the string collector type ##
    if prev[0] + 2 == prev[1] + 1 == index and prev[2] == char:
        string_collector, temp_index = collect_multiline_string, 3
    else:
        string_collector, temp_index = collect_string, 1
    ## determine if we need to look for f-strings in case of value yields ##
    f_string = False
    if source and version_info >= (3, 6) and source[index - temp_index] == "f":
        f_string = source[index:]  ## use the source to determine the extractions ##
    temp_index, temp_line = string_collector(iterable, char, f_string)
    prev = (index, temp_index, char)
    if source:
        ## lines (adjustments) + line (string collected) ##
        return temp_line.pop(), prev, temp_line
    if line is not None:
        line += temp_line
    return line, prev


def named_adjust(
    end_index: int,
    char: str,
    line: str,
    lines: list[str],
    final_line: str,
    line_iter: Iterable,
    ID: str,
) -> tuple[list[str], str, str, int]:
    """
    Adjusts the lines and final line for named expressions
    and named expressions within named expressions
    """
    ## you can't have ': =' or ':\=' ##
    final_line += char + "="
    ## skip the next iteration ##
    next(line_iter)
    ## this should mean that we can just unwrap it. ##
    ## If the named expression is a dictionary then ##
    ## it will be the last line added to the lines ##
    if not ID:
        temp = [lines.pop()]
    else:
        temp = []
    line, lines, final_line = update_lines(
        end_index, char, line, lines, final_line, unwrap=line_iter
    )
    lines += temp
    return lines, final_line, line, end_index


def update_lines(
    char: str,
    line: str,
    lines: list[str],
    final_line: str,
    not_end: bool = True,
    unwrap: Iterable | None = None,
) -> tuple[list[str], str]:
    """
    adds the current line or the unwrapped line to the lines
    if it's not a variable or constant otherwise the line is
    added to the final lines
    """
    if line.strip().isalnum():
        final_line += line
    else:
        final_line += "locals()[.'args'].pop() "
        if unwrap:
            temp_lines, temp_final_line, _ = unpack(line, unwrap, True)
            lines += temp_lines + [temp_final_line]
        else:
            lines += [line]
    if not_end:
        final_line += char + " "
    return "", lines, final_line


def unpack(
    line: str = empty_generator(),
    source_iter: Iterable = empty_generator(),
    unwrapping: bool = False,
) -> tuple[list[str], str, int]:
    """
    Unpacks value yields from a line into a
    list of lines going towards its right side
    """
    (
        depth,
        depth_total,
        end_index,
        space,
        lines,
        ID,
        line,
        final_line,
        prev,
        indented,
        operator,
    ) = (0, 0, 0, 0, [], "", "", "", (0, 0, ""), False, 0)
    source = ""
    line_iter = chain(enumerate(line), source_iter)
    for end_index, char in line_iter:
        ## record the source for string_collector_proxy (there might be better ways of doing this) ##
        source += char
        ## collect strings and add to the lines ##
        if char == "'" or char == '"':
            ## it should unpack f-strings as well ##
            line, prev, temp_lines = string_collector_proxy(
                end_index, char, prev, line_iter, source, source  ## is this correct??
            )
            lines += temp_lines
            ## make sure the length of the source is corrected ##
            source += " " * (prev[1] - prev[0])
        ## makes the line singly spaced while retaining the indentation ##
        elif char == " ":
            line, space, indented = singly_space(end_index, char, line, space, indented)
        ## dictionary assignment ##
        elif char == "[" and prev[-1] not in (" ", ""):
            line, lines, final_line = update_lines(char, line, lines, final_line)
        elif char == "\\":
            skip_line_continuation(line_iter, line, end_index)
            if space + 1 != end_index:
                line += " "
                space = end_index
        ## splitting operators ##
        elif char in ",<=>/|+-*&%@^":
            ## since we can have i.e. ** or %= etc. ##
            if end_index - 1 != operator:
                line, lines, final_line = update_lines(char, line, lines, final_line)
            operator = end_index
        elif depth == 0 and char in "#:;\n":  ## split and break condition ##
            lines += [line]
            break
        elif char == ":":  ## must be a named expression if depth is not zero ##
            line, lines, final_line = named_adjust(
                char, line, lines, final_line, line_iter, ID
            )
        else:
            ## record the current depth ##
            depth_total = update_depth(depth_total, char, ("([{", "}])"))
            depth = update_depth(depth, char)
            if unwrapping and depth_total < 0:
                final_line += char
                break
            ## check for unwrapping/updating ##
            if char.isalnum():
                ## in case of ... ... (otherwise you keep appending the ID) ##
                if space + 1 == end_index:
                    ID = ""
                ID += char
                if depth and ID == "yield":  ## unwrapping ##
                    ## what should happen when we unwrap? ##
                    ## go from the last bracket onwards for the replacement ##
                    line, lines, final_line = update_lines(
                        char, line, lines, final_line, unwrap=line_iter
                    )
                elif 1 < len(ID) < 4 and ID in ("and", "or", "is", "in"):
                    line, lines, final_line = update_lines(
                        char, line, lines, final_line
                    )
            else:
                ID = ""
            line += char
            prev = prev[:-1] + (char,)
    if line:
        line, lines, final_line = update_lines(char, line, lines, final_line, False)
    return lines, final_line, end_index


def unpack_fstring(
    source: str, source_iter: Iterable, start_index: int
) -> tuple[list[str], str, int]:
    """detects a value yield then adjusts the line for f-strings"""
    line, ID, depth, break_check, lines = "", "", 0, 0, []
    for index, char in source_iter:
        ## may need so that we can detect break_check < 0 to break e.g. } (f-string) ##
        break_check = update_depth(break_check, char, ("{", "}"))
        if break_check < 0:
            break
        line += char
        depth = update_depth(depth, char)
        if char.isalnum():
            ID += char
            if char == "yield" and depth == 1:
                ## value_yield adjust will collect the entire line (f-string in this case) ##
                return unpack(source[start_index:], source_iter, index, True)
        else:
            ID = ""
    return lines, "", index


def collect_definition(
    start_index: int,
    lines: list[str],
    lineno: int,
    source: str,
    source_iter: Iterable,
    reference_indent: int,
) -> tuple[int, str, int, list[str]]:
    """
    Collects a block of code from source, specifically a
    definition block in the case of this modules use case
    """
    indent = reference_indent + 1
    while reference_indent < indent:
        ## we're not specific about formatting the definitions ##
        ## we just need to make sure to include them ##
        for end_index, char in source_iter:
            ## newline ##
            if char == "\n":
                break
        ## add the line and get the indentation to check if continuing ##
        lineno += 1
        lines += [source[start_index:end_index]]
        indent = get_indent(source[end_index + 1 :])
        start_index = end_index + 1
    if char != "\n":
        lines[-1] += char
    ## make sure to return the index and char for the indentation ##
    return end_index, char, lineno, lines


def skip(iter_val: Iterable, n: int) -> None:
    """Skips the next n iterations in a for loop"""
    for _ in range(n):
        next(iter_val)


## Note: line.startswith("except") will need to put a try statement in front (if it's not there e.g. is less than the minimum indent) ##
## match case default was introduced in python 3.10
if version_info < (3, 10):

    def is_alternative_statement(line: str) -> bool:
        return line.startswith("elif") or line.startswith("else")

else:

    def is_alternative_statement(line: str) -> bool:
        return (
            line.startswith("elif")
            or line.startswith("else")
            or line.startswith("case")
            or line.startswith("default")
        )


is_alternative_statement.__doc__ = "Checks if a line is an alternative statement"


def is_definition(line: str) -> bool:
    """Checks if a line is a definition"""
    return (
        line.startswith("def ")
        or line.startswith("async def ")
        or line.startswith("class ")
        or line.startswith("async class ")
    )


########################
### code adjustments ###
########################
def skip_alternative_statements(
    line_iter: Iterable, current_min: int
) -> tuple[int, str, int]:
    """Skips all alternative statements for the control flow adjustment"""
    for index, line in line_iter:
        temp_indent = get_indent(line)
        temp_line = line[temp_indent:]
        if temp_indent <= current_min and not is_alternative_statement(temp_line):
            break
    return index, line, temp_indent


def control_flow_adjust(
    lines: list[str], indexes: list[int], reference_indent: int = 4
) -> tuple[list[str], list[int]]:
    """
    removes unreachable control flow blocks that
    will get in the way of the generators state

    Note: it assumes that the line is cleaned,
    in particular, that it starts with an
    indentation of 4 (4 because we're in a function)

    It will also add 'try:' when there's an
    'except' line on the next minimum indent
    """
    new_lines, current_min, line_iter = [], get_indent(lines[0]), enumerate(lines)
    for index, line in line_iter:
        temp_indent = get_indent(line)
        temp_line = line[temp_indent:]
        if temp_indent < current_min:
            ## skip over all alternative statements until it's not an alternative statement ##
            ## and the indent is back to the current min ##
            if is_alternative_statement(temp_line):
                end_index, line, temp_indent = skip_alternative_statements(
                    line_iter, temp_indent
                )
                ## remove from the linetable and update the index ##
                del indexes[index:end_index]
                index = end_index
            current_min = temp_indent
            if temp_line.startswith("except"):
                new_lines = (
                    [" " * 4 + "try:"]
                    + indent_lines(new_lines)
                    + [
                        line[current_min - 4 :]
                    ]  ## -4 since we're in a function for the code execution ##
                )
                ## add to the linetable ##
                indexes = [indexes[0]] + indexes
        ## add the line (adjust if indentation is not reference_indent) ##
        if current_min != reference_indent:
            ## adjust using the current_min until it's the same as reference_indent ##
            new_lines += [line[current_min - 4 :]]
        else:
            return (
                new_lines + indent_lines(lines[index:], 4 - reference_indent),
                indexes,
            )
    return new_lines, indexes


def indent_lines(lines: list[str], indent: int = 4) -> list[str]:
    """indents a list of strings acting as lines"""
    if indent > 0:
        return [" " * indent + line for line in lines]
    if indent < 0:
        indent = -indent
        return [line[indent:] for line in lines]
    return lines


def extract_iter(line: str, number_of_indents: int) -> str:
    """
    Extracts the iterator from a for loop

    e.g. we extract the second ... in:
    for ... in ...:
    """
    depth, ID, line_iter = 0, "", enumerate(line[number_of_indents:], number_of_indents)
    for index, char in line_iter:
        ## the 'in' key word must be avoided in all forms of loop comprehension ##
        depth = update_depth(depth, char, ("([{", ")]}"))
        if char.isalnum() and depth == 0:
            ID += char
            if ID == "in":
                if next(line_iter)[1] == " ":
                    break
                ID = ""
        else:
            ID = ""
    index += (
        2  ## adjust by 2 to skip the 'n' and ' ' in 'in ' that would've been deduced ##
    )
    iterator = line[index:-1]  ## -1 to remove the end colon ##
    ## remove the leading and trailing whitespace and then it should be a variable name ##
    if iterator.strip().isalnum():
        return line
    return line[:index] + "locals()['.%s']:" % number_of_indents


def iter_adjust(outer_loop: list[str]) -> tuple[bool, list[str]]:
    """adjust an outer loop with its tracked iterator if it uses one"""
    flag, line = False, outer_loop[0]
    number_of_indents = get_indent(line)
    if line[number_of_indents:].startswith("for "):
        outer_loop[0] = extract_iter(line, number_of_indents)
        flag = True
    return flag, outer_loop


def skip_blocks(
    new_lines: list[str], line_iter: Iterable, index: int, line: str
) -> None:
    """
    Skips over for/while and definition blocks
    and removes indentation from the line
    """
    indent = get_indent(line)
    temp_line = line[indent:]
    while (
        temp_line.startswith("for ")
        or temp_line.startswith("while ")
        or is_definition(temp_line)
    ):
        for index, line in line_iter:
            temp_indent = get_indent(line)
            if temp_indent <= indent:
                break
            new_lines += [line]
        ## continue back ##
        indent = temp_indent
        temp_line = line[indent:]
    return new_lines, temp_line, index


def loop_adjust(
    lines: list[str], indexes: list[int], outer_loop: list[str], *pos: tuple[int, int]
) -> tuple[list[str], list[int]]:
    """
    Formats the current code block
    being executed such that all the
    continue -> break;
    break -> empty the current iter; break;

    This allows us to use the control
    flow statements by implementing a
    simple for loop and if statement
    to finish the current loop
    """
    new_lines, flag, line_iter = [], False, enumerate(lines)
    for index, line in line_iter:
        ## skip over for/while and definition blocks ##
        ## since these are complete blocks of their own ##
        ## and don't need to be adjusted ##
        new_lines, temp_line, index = skip_blocks(new_lines, line_iter, index, line)
        ## adjustments ##
        if temp_line.startswith("continue"):
            flag = True
            new_lines += ["break"]
        elif temp_line.startswith("break"):
            flag = True
            new_lines += ["locals()['.continue']=False", "break"]
            indexes = indexes[index:] + indexes[index] + indexes[:index]
        else:
            new_lines += [line]
    ## adjust it in case it's an iterator ##
    flag, outer_loop = iter_adjust(
        outer_loop
    )  ## why does this get to dicate the 'flag' ?? ##
    if flag:
        ## the loop adjust itself ##
        return [
            "    locals()['.continue']=True",
            "    for _ in (None,):",
        ] + indent_lines(new_lines, 8 - get_indent(new_lines[0])) + [
            "    if locals()['.continue']:"
        ] + indent_lines(
            outer_loop,
            8
            - get_indent(
                outer_loop[0]
            ),  ## add the outer loop (dedented so that it works) ##
        ), [
            indexes[0],
            indexes[
                0
            ],  ## add all the indexes which are also adjusted for the changes ##
        ] + indexes + [
            pos[0]
        ] + list(
            range(*pos)
        )
    ## If it doesn't need any adjustments e.g. to continue and break statements ##
    ## then we just dedent the current lines and add the outer loop ##
    return indent_lines(lines, 4 - get_indent(lines[0])) + indent_lines(
        outer_loop, 4 - get_indent(outer_loop[0])
    ), indexes + list(range(*pos))


def yield_adjust(temp_line: str, indent: str) -> list[str]:
    """
    temp_line: line trimmed at the start by its indent
    indent: the current indent in string form
    """
    if temp_line.startswith("yield from "):
        return [
            indent
            + "locals()['.yieldfrom']="
            + temp_line[11:],  ## 11 to get past the yield from
            indent + "for locals()['.i'] in locals()['.yieldfrom']:",
            indent + "    return locals()['.i']",
        ]
    if temp_line.startswith("yield "):
        return [indent + "return" + temp_line[5:]]  ## 5 to retain the whitespace ##


def get_loops(
    lineno: int, jump_positions: list[tuple[int, int]]
) -> list[tuple[int, int]]:
    """
    returns a list of tuples (start_lineno,end_lineno) for the loop
    positions in the source code that encapsulate the current lineno
    """
    ## get the outer loops that contian the current lineno ##
    loops = []
    ## jump_positions are in the form (start_lineno,end_lineno) ##
    for pos in jump_positions:

        ## importantly we go from start to finish to capture nesting loops ##
        ## make sure the lineno is contained within the position for a ##
        ## loop adjustment and because the jump positions are ordered we ##
        ## can also break when the start lineno is beyond the current lineno ##
        if lineno < pos[0]:
            break
        if lineno < pos[1]:
            ## subtract 1 for 0 based indexing; it's only got one specific ##
            ## use case that requires it to be an array accessor ##
            loops += [(pos[0] - 1, pos[1] - 1)]
    return loops


def expr_getsource(FUNC: Any) -> str:
    """
    Uses co_positions or otherwise goes through the source code
    extracting expressions until a match is found on a code object
    basis to get the source

    Note:
    the extractor should return a string and if using a
    lambda extractor it will take in a string input but
    if using a generator expression extractor it will
    take a list instead
    """
    code_obj = getcode(FUNC)
    if code_obj.co_name == "<lambda>":
        ## here source is a : str
        source = getsource(code_obj)
        extractor = extract_lambda
    else:
        lineno = getframe(FUNC).f_lineno - 1
        ## here source is a : list[str]
        source = findsource(code_obj)[0][lineno:]
        extractor = extract_genexpr
    ## get the rest of the source ##
    if (3, 11) <= version_info:
        # start_line, end_line, start_col, end_col
        positions = code_obj.co_positions()
        is_source_list = isinstance(source, list)
        pos = next(positions, (None, None, None))[1:]
        current_min, current_max = pos[2:]
        if is_source_list:
            current_max_lineno = pos[1]
        for pos in positions:
            if pos[-2] and pos[-2] < current_min:
                current_min = pos[-2]
            if pos[-1] and pos[-1] > current_max:
                current_min = pos[-1]
            if is_source_list and pos[1] and pos[1] > current_max_lineno:
                current_max_lineno = pos[1]
        if is_source_list:
            source = "\n".join(source[: current_max_lineno + 1])
        return source[current_min:current_max]
    ## otherwise match with generator expressions in the original source to get the source code ##
    attrs = (
        "co_freevars",
        "co_cellvars",
        "co_firstlineno",
        "co_nlocals",
        "co_stacksize",
        "co_flags",
        "co_code",
        "co_consts",
        "co_names",
        "co_varnames",
        "co_name",
    )
    if (3, 3) <= version_info:
        attrs += ("co_qualname",)
    if isinstance(source, list):
        source = "\n".join(source)
    for col_offset, end_col_offset in extractor(source):
        try:  ## we need to make it a try-except in case of potential syntax errors towards the end of the line/s ##
            ## eval should be safe here assuming we have correctly extracted the expression - we can't use compile because it gives a different result ##
            temp_code = getcode(eval(source[col_offset:end_col_offset]))
            if attr_cmp(temp_code, code_obj, attrs):
                return source
        except:
            pass
    raise Exception("No matches to the original source code found")


###############
### genexpr ###
###############
def extract_genexpr(source: str) -> GeneratorType:
    """Extracts each generator expression from a list of the source code lines"""
    ID, depth, prev = "", 0, (0, 0, "")
    source_iter = enumerate(source)
    for index, char in source_iter:
        ## skip all strings if not in genexpr
        if char == "'" or char == '"':
            _, prev = string_collector_proxy(index, char, prev, source_iter)
            continue
        ## detect brackets
        elif char == "(":
            temp_col_offset = index
            depth += 1
        elif char == ")":
            if genexpr_depth and depth == genexpr_depth:
                yield col_offset, index + 1
                genexpr_depth = None
            depth -= 1
            continue
        if depth and genexpr_depth is not None:
            ## record ID ##
            if char.isalnum():
                ID += char
                ## detect a for loop
                if ID == "for":
                    ID, genexpr_depth, col_offset = "", depth, temp_col_offset
            else:
                ID = ""


##############
### lambda ###
##############
def extract_lambda(source_code: str) -> GeneratorType:
    """Extracts each lambda expression from the source code string"""
    ID, lambda_depth, depth, prev = "", None, 0, (0, 0, "")
    source_code = enumerate(source_code)
    for index, char in source_code:
        ## skip all strings (we only want the offsets)
        if char == "'" or char == '"':
            _, prev = string_collector_proxy(index, char, prev, source_code)
            continue
        ## detect brackets (lambda can be in all 3 types of brackets) ##
        depth = update_depth(depth, char, ("([{", ")]}"))
        ## record source code ##
        if lambda_depth:
            # lambda_depth needed in case of brackets; depth+1 since depth would've got reduced by 1
            if char == "\n;" or depth + 1 == lambda_depth:
                yield col_offset, index + 1
                lambda_depth = None
        else:
            ## record ID ##
            if char.isalnum():
                ID += char
                ## detect a lambda
                if ID == "lambda" and depth <= 1:
                    ID, lambda_depth, col_offset = "", depth, index - 6
            else:
                ID = ""
    ## in case of a current match ending ##
    if lambda_depth:
        yield col_offset, None


def except_adjust(
    current_lines: list[str], exception_lines: list[str], final_line: str
) -> list[str]:
    """
    Checks if lines that were adjusted because of value yields
    were in an except statement and therefore needs adjusting
    """
    ## except statement with its adjustments ##
    indent = " " * 4
    for index, line in enumerate(current_lines[::-1], start=1):
        current_lines[-index] = indent + current_lines[-index]
        reference_indent = get_indent(line)
        if line[reference_indent].startswith("try"):
            break
    number_of_indents = reference_indent + 8
    current_indent = " " * number_of_indents
    return (
        current_lines[:-index]
        + [" " * reference_indent + "try:"]
        + current_lines[-index:]
        + [
            current_indent[:-4] + "except:",
            current_indent + "locals()['.error'] = exc_info()[1]",
        ]
        + indent_lines(exception_lines, number_of_indents)
        + [current_indent + "raise locals()['.error']"]
        + [final_line]
    )


def singly_space(index: int, char: str, line: str, space: int, indented: bool) -> str:
    """For ensuring all spaces in a line are single spaces"""
    if indented:
        if space + 1 != index:
            line += char
    else:
        line += char
        if space + 1 != index:
            indented = True
    return line, index, indented
