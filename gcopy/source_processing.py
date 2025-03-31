#################################################
### cleaning/extracting/adjusting source code ###
#################################################
from .utils import *
from inspect import getsource, findsource, signature
from typing import Iterable, Any
from types import GeneratorType, FunctionType, CellType  # , FrameType ## lineno_adjust

## to ensure gcopy.custom_generator.Generator can be used in exec for sign ##
import gcopy


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


## only required when using compound statements ##
# def lineno_adjust(frame: FrameType) -> int:
#     """
#     unpacks a line of compound statements
#     into lines up to the last instruction
#     that determines the adjustment required
#     """
#     line, current_lineno, instructions = (
#         [],
#         frame.f_lineno,
#         get_instructions(frame.f_code),
#     )
#     ## get the instructions at the lineno ##
#     for instruction in instructions:
#         lineno, obj = instruction.positions.lineno, (
#             list(instruction.positions[2:]),
#             instruction.offset,
#         )
#         if not None in obj[0] and lineno == current_lineno:
#             ## exhaust the iter to get all the lines ##
#             line = [obj]
#             for instruction in instructions:
#                 lineno, obj = instruction.positions.lineno, (
#                     list(instruction.positions[2:]),
#                     instruction.offset,
#                 )
#                 if lineno != current_lineno:
#                     break
#                 line += [obj]
#             break
#     ## combine the lines until f_lasti is encountered to return how many lines ##
#     ## futher from the current line would the offset be if split up into lines ##
#     if line:
#         index, current, lasti = 0, [0, 0], frame.f_lasti
#         line.sort()
#         for pos, offset in line:
#             if offset == lasti:
#                 return index
#             if pos[0] > current[1]:  ## independence ##
#                 current = pos
#                 index += 1
#             elif pos[1] > current[1]:  ## intersection ##
#                 current[1] = pos[1]
#     raise ValueError("f_lasti not encountered")


def line_adjust(line: str, lines: list[str], adjust: bool = True) -> str:
    """
    Adds indentation to the lines and colon for statements

    Specific to the unpack_genexpr function where the lines
    will start with 'for' or 'if' when separated

    Note: no need to check for next_char since this is done
    before calling this function
    """
    indent, new_line = " " * 4, ""
    if adjust:
        if line.startswith("if"):
            index = 2
        else:
            index = 3
        new_line, line = line[-index:] + " ", line[:-index]
    line = line.strip()
    ## needed for the first segment that will have no for/if ##
    if line.startswith("for") or line.startswith("if"):
        line += ":"
    return new_line, lines + [indent * len(lines) + line]


def update_line(
    index: int,
    char: str,
    line: str,
    source_iter: Iterable,
    prev: tuple[int, int, str],
    depth: int,
) -> tuple[str, int, tuple[int, int, str]]:
    """Updates the current line specific to unpack_genexpr"""
    if char == "\\":
        line += " "  ## incase it doesn't have any gap ##
    if char in "\\\n":
        return
    ## collect strings
    if char == "'" or char == '"':
        line, prev = string_collector_proxy(index, char, prev, source_iter, line)
        return
    ## we're only interested in when the generator expression ends in terms of the depth ##
    depth = update_depth(depth, char)
    ## accumulate the current line
    line += char
    return line, depth, prev


def unpack_genexpr(source: str) -> list[str]:
    """unpacks a generator expressions' for loops into a list of source lines"""
    lines, line, ID, depth, prev, passed_first_for = (
        [],
        "",
        "",
        0,
        (0, 0, ""),
        False,
    )
    source_iter = enumerate(source[1:-1])
    for index, char in source_iter:
        args = update_line(index, char, line, source_iter, prev, depth)
        if args is None:
            continue
        line, depth, prev = args
        if depth == 0:
            ## collect IDs
            if char.isalnum():
                ID += char
                if ID == "for" or (ID == "if" and passed_first_for):
                    try:
                        next_char = next(source_iter)[1]
                    ## it's not possible to have i.e. ( ... if char == if) ##
                    except StopIteration:
                        raise SyntaxError("Unexpected format encountered")
                    ## adjusts and adds the line to lines ##
                    if next_char in "\\ ":
                        line, lines = line_adjust(line, lines)
                        if not passed_first_for and lines:
                            passed_first_for = True
                    ## otherwise adds to the current line ##
                    else:
                        args = update_line(index, char, line, source_iter, prev, depth)
                        if args is None:
                            continue
                        line, depth, prev = args
                        ID = ""
            else:
                ID = ""
    _, lines = line_adjust(line, lines, False)
    return lines[1:] + [" " * (4 * len(lines)) + "return " + lines[0]]


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
        ## skip decorators ##
        while char == "@":
            while char != "\n":
                index, char = next(source_iter)
            index, char = next(source_iter)
        ## collect the ID ##
        if char.isalnum():
            ID += char
        else:
            if ID == "def" and char in " \\":
                while char != "(":
                    index, char = next(source_iter)
                break
            ID = ""
    ## skip to the end of the function definition ##
    depth = 1
    for index, char in source_iter:
        if char == ":" and depth == 0:
            return source[index + 1 :]
        depth = update_depth(depth, char, ("([{", ")]}"))
    raise SyntaxError("Unexpected format encountered")


def collect_string(
    source_iter: Iterable, index: int, reference: str, source: str = None
) -> tuple[int, str | list[str]]:
    """
    Collects strings in an iterable assuming correct
    python syntax and the char before is a qoutation mark

    Note: make sure source_iter is an enumerated type
    """
    line, backslash, left_brace, lines = reference, False, 0, []
    for index, char in source_iter:
        ## detect f-strings for value yields ##
        if source and char == "{" or left_brace:
            if char != "{" and left_brace % 2:
                ## we could check for yields before unpacking but this is maybe more efficient ##
                adjustments, f_string_contents, _ = unpack(
                    char, source_iter, source, True, index=index
                )
                ## update ##
                lines += adjustments
                line += f_string_contents
                left_brace = 0
                continue
            left_brace += 1
        if char == reference and not backslash:
            line += char
            break
        line += char
        backslash = False
        if char == "\\":
            backslash = True
    if source:
        return index, lines + [line]  ## we have to add it for the f-string case ##
    return index, line


def collect_multiline_string(
    source_iter: Iterable, index: int, reference: str, source: str = None
) -> tuple[int, str | list[str]]:
    """
    Collects multiline strings in an iterable assuming
    correct python syntax and the char before is a
    qoutation mark

    Note: make sure source_iter is an enumerated type

    if a string starts with 3 qoutations
    then it's classed as a multistring
    """
    line, backslash, prev, count, left_brace, lines = reference, False, -2, 0, 0, []
    for index, char in source_iter:
        ## detect f-strings for value yields ##
        if source and char == "{" or left_brace:
            if char != "{" and left_brace % 2:
                ## we could check for yields before unpacking but this is maybe more efficient ##
                adjustments, f_string_contents, _ = unpack(
                    char, source_iter, source, True, index=index
                )
                ## update ##
                lines += adjustments
                line += f_string_contents
                left_brace = 0
                continue
            left_brace += 1
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
    if source:
        return index, lines + [line]  ## we have to add it for the f-string case ##
    return index, line


def string_collector_proxy(
    index: int,
    char: str,
    prev: tuple[int, int, str],
    iterable: Iterable,
    line: str = None,
    f_string: bool = False,
) -> tuple[str, tuple[int, int, str], list[str]]:
    """Proxy function for usage when collecting strings since this block of code gets used repeatedly"""
    ## get the string collector type ##
    if prev[0] + 2 == prev[1] + 1 == index and prev[2] == char:
        string_collector, temp_index = collect_multiline_string, 3
    else:
        string_collector, temp_index = collect_string, 1
    ## determine if we need to look for f-strings in case of value yields ##
    source = None
    if (
        f_string
        and version_info >= (3, 6)
        and len(line) >= temp_index
        and line[-temp_index] == "f"
    ):
        ## use the source to determine the extractions ##
        ## +1 to move one forwards from the 'f' ##
        source = line[1 - temp_index :]
    temp_index, temp_line = string_collector(iterable, index, char, source)
    prev = (index, temp_index, char)
    if f_string:
        if source:
            ## lines (adjustments) + line (string collected) ##
            return temp_line.pop(), prev, temp_line
        return temp_line, prev, []
    if line is not None:
        line += temp_line
    return line, prev


def inverse_bracket(bracket: str) -> str | None:
    """Gets the inverse of the current bracket"""
    ## use .get(..., None) since char == '' is possible ##
    return {
        "(": ")",
        ")": "(",
        "{": "}",
        "}": "{",
        "[": "]",
        "]": "[",
    }.get(bracket, None)


def named_adjust(
    line: str,
    lines: list[str],
    final_line: str,
    line_iter: Iterable,
    ID: str,
    source: str = "",
    index: int = 0,
    depth_total: int = 0,
    depths: dict = {},
) -> tuple[str, list[str], str, dict]:
    """
    Adjusts the lines and final line for named expressions
    and named expressions within named expressions

    a = (b:=next(j)) = c

    next(j)
    b = next(j)
    """
    line += ":="
    ## skip the next iteration to the '=' char ##
    ## for ':=' you can't have ': =' or ':\=' ##
    next(line_iter)
    ## this should mean that we can just unwrap it. ##
    ## If the named expression is a dictionary then ##
    ## it will be the last line added to the new lines ##
    temp = []
    if ID and lines:
        temp = [lines.pop()]
    line, lines, final_line, named, depths = update_lines(
        line,
        lines,
        final_line,
        True,
        line_iter,
        source=source,
        index=index,
        unwrapping=True,
        depth_total=depth_total,
        depths=depths,
    )
    lines += temp
    return line, lines, final_line, depths


def unpack_adjust(line: str) -> list[str]:
    """adjusts the unpacked line for usage and value yields"""
    if line.startswith("yield ") or line.startswith("yield)") or line == "yield":
        return yield_adjust(line, "") + [
            "locals()['.internals']['.args'] += [locals()['.internals']['.send']]"
        ]
    return ["locals()['.internals']['.args'] += [%s]" % line]


operators = ",<=>/|+-*&%@^"


def update_lines(
    line: str,
    lines: list[str],
    final_line: str,
    named: bool = False,
    unwrap: Iterable | None = None,
    bracket_index: int = None,
    operator: str = "",
    yielding: bool = False,
    source: str = "",
    index: int = 0,
    unwrapping: bool = False,
    depth_total: int = 0,
    depths: dict = {},
) -> tuple[str, list[str], str, bool, dict]:
    """
    adds the current line or the unwrapped line to the lines
    if it's not a variable or constant otherwise the line is
    added to the final lines
    """
    if not line.isspace():
        ## unwrapping ##
        if unwrap:
            temp_lines, temp_final_line, _ = unpack(
                source_iter=unwrap,
                source=source,
                unwrapping=True,
                named=named,
                index=index,
                # depth_total=depth_total,
                # depths=depths,
            )
            if yielding:
                ## we have to :-1 since the end bracket gets added ##
                temp_final_line = "yield " + temp_final_line[:-1]
                try_set(depths.get(depth_total, None), -1, len(lines))
                lines += temp_lines + unpack_adjust(temp_final_line.strip())
                ## unwrapping should pop from the end (current expression) ##
                ## Note: bracket_index is relative to the current line length not soruce index ##
                line = line[:bracket_index] + "locals()['.internals']['.args'].pop()"
            else:
                try_set(depths.get(depth_total, None), -1, len(lines))
                lines += temp_lines
                line += temp_final_line
        ## unpacking ##
        else:
            ## variable ##
            if line.strip().isalnum() or named:
                final_line += line
            ## expression ##
            else:
                ## unpacking should pop from the start (since the line is in this order) ##
                final_line += "locals()['.internals']['.args'].pop(0)"
                try_set(depths.get(depth_total, None), -1, len(lines))
                lines += unpack_adjust(line.strip())
            line = ""
    if operator:
        final_line += " " + operator
    return line, lines, final_line, named, depths


def unpack(
    line: str = None,
    source_iter: Iterable = empty_generator(),
    source: str = "",
    unwrapping: bool = False,
    named: bool = False,
    index: int = 0,
    depth_total: int = 0,
    depths: dict = {},
    in_ternary_else: bool = False,
) -> tuple[list[str], str, int]:
    """
    Unpacks value yields from a line into a
    list of lines going towards its right side

    Note:
    depths = {index of the last depth, bracket, equals position, comma position, lines indexes}
    """
    if line is None:
        line_iter = empty_generator()
    else:
        line_iter = enumerate(line, start=index - len(line) + 1)
    line_iter = chain(line_iter, source_iter)
    ## make sure 'space' == -1 for indentation ##
    (
        depth,
        end_index,
        space,
        lines,
        ID,
        line,
        final_line,
        prev,
        operator,
        bracket_index,
    ) = (0, 0, -1, [], "", "", "", (0, 0, ""), 0, None)
    indented = True
    if not unwrapping:
        indented = False
    for end_index, char in line_iter:
        ## record the source for string_collector_proxy (there might be better ways of doing this) ##
        ## collect strings and add to the lines ##
        if char == "'" or char == '"':
            temp_line, prev, temp_lines = string_collector_proxy(
                end_index, char, prev, line_iter, line, True
            )
            line += temp_line
            lines += temp_lines
        elif char == " ":
            line, space, indented = singly_space(end_index, char, line, space, indented)
        ## dictionary assignment ##
        elif char == "[" and prev[-1] not in (" ", ""):
            line, lines, final_line, named, depths = update_lines(
                line + char,
                lines,
                final_line,
                named,
                line_iter,
                source=source,
                index=end_index,
                depth_total=depth_total,
                depths=depths,
            )
        elif char == "\\":
            skip_line_continuation(line_iter, line, end_index)
            if space + 1 != end_index:
                line += " "
                space = end_index
        ## splitting operators ##
        elif char in operators:

            ## maybe replace operator with next_char ##
            if in_ternary_else:
                if char == "=" and source[end_index + 1 : end_index + 2] != "=":
                    try_set(depths.get(depth_total, None), 2, None)
                    break
                elif char == ",":
                    break

            ## since we can have i.e. ** or %= etc. ##
            if end_index - 1 != operator:
                if char == "=":
                    try_set(depths.get(depth_total, None), 2, None)
                line, lines, final_line, named, depths = update_lines(
                    line,
                    lines,
                    final_line,
                    named,
                    operator=char,
                    source=source,
                    index=end_index,
                    depth_total=depth_total,
                    depths=depths,
                )
            else:
                key = {"=": 2, ",": 3}.get(char, None)
                try_set(depths.get(depth_total, None), key, len(line))
                final_line += char
            operator = end_index
        ## split and break condition ##
        elif depth == 0 and char in "#:;\n":
            if char == ":":
                line += ":"
            break
        elif char == ":":  ## must be a named expression if depth is not zero ##
            line, lines, final_line, depths = named_adjust(
                line,
                lines,
                final_line,
                line_iter,
                ID,
                source,
                end_index,
                depth_total,
                depths,
            )
            named = False
            ## since we're going to skip some chars ##
            ID, prev = "", prev[:-1] + (char,)
            depth -= 1
            depths.pop(depth_total, None)
            depth_total -= 1
            continue
        else:
            ## record the current depth ##
            if char in "([{":
                depth_total += 1
                depths[depth] = [len(line), char, None, None, 0]
                if char == "(":
                    depth += 1
                    ## the index is in relation to the current line ##
                    bracket_index = len(line)
            elif char in ")}]":
                depths.pop(depth_total, None)
                depth_total -= 1
                if (
                    unwrapping
                    and depth_total < 0
                    or char != inverse_bracket(depths.get(depth_total, (0, ""))[1])
                ):
                    if not in_ternary_else:
                        line += char
                    break
                if char == ")":
                    depth -= 1
            ## check for unwrapping/updating ##
            if char.isalnum():
                ## in case of ... ... (otherwise you keep appending the ID) ##
                if space + 1 == end_index:
                    ID = ""
                ID += char
                if in_ternary_else and ID == "else":
                    line = line[:-3]
                    break
                adjusted, line, lines, final_line, named, depth, depth_total = check_ID(
                    ID,
                    source_iter,
                    source,
                    line_iter,
                    source[end_index + 1 : end_index + 2],
                    end_index,
                    depths,
                    unwrapping,
                    line,
                    lines,
                    final_line,
                    named,
                    bracket_index,
                    index,
                    depth,
                    depth_total,
                )
                if adjusted:
                    ID, prev = "", prev[:-1] + (char,)
                    del adjusted
                    continue
            else:
                ID = ""
            line += char
            prev = prev[:-1] + (char,)
    if line:
        final_line += line
    if in_ternary_else:
        return lines, final_line, end_index, depths, depth_total
    return lines, final_line, end_index


def get_unpacked_lines(lines: str, reference: int | None) -> list[str]:
    """gets any lines that have been unpacked part of the ternary expression"""
    if reference == 0:
        return [], lines
    temp_lines = lines[reference:]
    lines = lines[:reference]
    return temp_lines, lines


def unpack_ternary(
    reference: int,
    source_iter: Iterable,
    source: str,
    named: bool,
    index: int,
    depth_total: int,
    depths: dict,
) -> tuple[list[str], str, int, list[str], list[str]]:
    """unpacks the ternary expression and retrieves any new lines"""
    lines, final_line, end_index, depths, depth_total = unpack(
        "",
        source_iter,
        source,
        False,
        named,
        index,
        depth_total,
        depths,
        True,
    )
    temp_lines, lines = get_unpacked_lines(lines, reference)
    return lines, end_index, final_line, temp_lines, depths, depth_total


def clean_block(block: str) -> str:
    """removes any extra spaces and brackets"""
    block = block.strip()
    while block and block[-1] in ")]}":
        block = block[:-1]
    while block and block[0] in "([{":
        block = block[1:]
    return block


def check_ID(
    ID: str,
    source_iter: Iterable,
    source: str,
    line_iter: Iterable,
    next_char: str,
    end_index: int,
    depths: dict,
    unwrapping: bool,
    line: str,
    lines: list[str],
    final_line: str,
    named: bool,
    bracket_index: int,
    index: int,
    depth: int = 0,
    depth_total: int = 0,
) -> tuple[str, bool, bool]:
    """Checks the ID for updating the line"""
    adjusted = False
    if ID == "lambda" and next_char in " :\\":
        _, lines = collect_lambda(line, source_iter, source, (0, 0, ""))
        adjusted = True
    ## unwrapping ##
    elif depth and ID == "yield" and next_char in " )]}\n;\\":
        ## what should happen when we unwrap? ##
        ## go from the last bracket onwards for the replacement ##
        line, lines, final_line, named, depths = update_lines(
            line,
            lines,
            final_line,
            named,
            line_iter,
            bracket_index,
            yielding=True,
            source=source,
            index=end_index,
            depth_total=depth_total,
            depths=depths,
        )
        bracket_index = None
        ## since the unwrapping will accumulate up to the next bracket this ##
        ## will go unrecorded on this stack frame recieving but recorded and ##
        ## garbage collected on the recursed stack frame used on unwrapping ##
        depth -= 1
        depths.pop(depth_total, None)
        depth_total -= 1
        adjusted = True  ## to avoid: line += char (we include it in the final_line as the operator or in unwrapping)
    elif 1 < len(ID) < 4 and ID in ("and", "or", "is", "in"):
        line, lines, final_line, named = update_lines(
            line,
            lines,
            final_line,
            named,
            operator=ID,
            source=source,
            index=end_index,
            depth_total=depth_total,
            depths=depths,
        )
        adjusted = True
    ## I don't think you can have a value yield in a 'case' statement otherwise this too is in here ##
    elif (
        next_char in " :\\" and 1 < len(ID) < 6 and ID in ("if", "elif", "while", "for")
    ):
        ## i.e. ID='while' will have 'whil' but no 'e' since the char has not been added ##
        temp_line = line[: -len(ID) + 1]
        if ID == "if" and temp_line.lstrip():
            ## essentially, the final_line will be locals()['.internals']['.args'].pop(0 or None) ##
            ## and new lines will be added ##

            # 1. once you hit an if make sure the unpacking of it and itself
            ## comes before the last unpacking
            # 2. else statements just get added to the new lines
            reference = depths.get(depth_total, 0)

            if reference != 0:
                ## -1 since the 'f' in 'if' has not been added ##
                if_block = line[reference[0] : -1]
                # final_line += line[: reference[0] + 1]

                # NOTE: need to check/test the poping order #

                if reference[1] in "({[":
                    ## unwrapping ##
                    line += "locals()['.internals']['.args'].pop()"
                else:
                    ## unpacking ##
                    line += "locals()['.internals']['.args'].pop(0)"
                reference = reference[-1]
            else:
                ## -1 to get rid of the i in 'if' ##
                if_block = line[:-1]
                line += "locals()['.internals']['.args'].pop(0)"
            ## line should be empty ##
            line = ""
            ## run it through unpack returning on ternary else ##
            ## then putting that current line as locals()['.internals']['.args'] ##
            if_block_lines, lines = get_unpacked_lines(lines, reference)
            lines, end_index, if_condition, if_condition_lines, depths, depth_total = (
                unpack_ternary(
                    reference,
                    source_iter,
                    source,
                    named,
                    index,
                    depth_total,
                    depths,
                )
            )
            length = len(lines)
            ## then run it through unpack one more time to get the rest of the ternary else ##
            lines, end_index, else_block, else_block_lines, depths, depth_total = (
                unpack_ternary(
                    reference,
                    source_iter,
                    source,
                    named,
                    end_index,
                    depth_total,
                    depths,
                )
            )
            ## add all the lines ##
            if_block = ["    " + clean_block(if_block)]
            else_block = ["    " + clean_block(else_block)]
            diff = len(lines) - length
            ## remove the 'not' (only temporary until it's found out why it's not working) ##
            if diff and not else_block[0].isspace():
                else_block = indent_lines(lines[reference:diff])
                lines = lines[:reference]
            upper = (
                if_condition_lines
                + ["if " + if_condition + ":"]
                + indent_lines(if_block_lines)
            )
            new_lines = (
                upper
                + if_block
                + ["else:"]
                + indent_lines(else_block_lines)
                + else_block
            )
            replace = depths.pop("flag", None)
            if replace is not None:
                lines = lines[:replace] + indent_lines(new_lines) + lines[replace:]
            else:
                lines += new_lines
            if if_block[0].isspace():
                ## makes sure on return in the recursion that the recieving ##
                ## frame puts itself into the previous frames if block ##
                upper = reference + len(upper)
                depths["flag"] = upper
            # char = source[end_index]
            # if char in operators:
            #     final_line += char
        else:
            final_line += ID + " "
            line = temp_line
        adjusted = True
    return adjusted, line, lines, final_line, named, depth, depth_total


def collect_definition(
    start_index: int,
    lines: list[str],
    lineno: int,
    source: str,
    source_iter: Iterable,
    reference_indent: int,
    decorator: bool = False,
) -> tuple[int, str, int, list[str]]:
    """
    Collects a block of code from source, specifically a
    definition block in the case of this modules use case
    """
    if decorator:
        lines += ["@locals()['.internals']['.decorator']"]
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


## Note: line.startswith("except") will need to put a try statement in front (if it's not there e.g. is less than the minimum indent) ##
## match case default was introduced in python 3.10


def is_alternative_statement(line: str) -> bool:
    """Checks if a line is an alternative statement"""
    return (
        line.startswith("elif")
        or line.startswith("else")
        or line.startswith("case")
        and line[4] in " :"
    ) or (line.startswith("default") and line[7] in " :")


def is_loop(line: str) -> bool:
    """Checks if a line is a loop"""
    if line.startswith("async "):
        line = line[5:]
        return line[get_indent(line) :].startswith("for ")
    return line.startswith("for ") or line.startswith("while ")


def is_definition(line: str) -> bool:
    """Checks if a line is a definition"""
    if line.startswith("async "):
        line = line[5:]
        return line[get_indent(line) :].startswith("def ")
    return line.startswith("def ") or line.startswith("class ")


########################
### code adjustments ###
########################
def skip_alternative_statements(
    line_iter: Iterable,
    current_min: int,
    check: FunctionType = is_alternative_statement,
) -> tuple[int, str, int]:
    """Skips all alternative statements for the control flow adjustment"""
    adjuster = 0
    for index, line in line_iter:
        temp_indent = get_indent(line)
        temp_line = line[temp_indent:]
        if temp_indent <= current_min and not check(temp_line):
            ## to avoid skipping the non alternative statement ##
            adjuster = 1
            break

    return index, adjuster, line, temp_indent


def skip_alt_stmnt_proxy(
    line_iter: Iterable,
    temp_indent: int,
    indexes: list[int],
    index: int,
    shift: int,
    append_shift: int,
    **kwargs,
) -> tuple[list[int], int, str, bool, int]:
    """skips alternative statments and updates the linetable"""
    breaking = False
    end_index, adjuster, line, temp_indent = skip_alternative_statements(
        line_iter,
        temp_indent,
        **kwargs,
    )
    ## remove from the linetable and update the index ##
    del indexes[
        index + append_shift - shift : end_index + 1 + append_shift - adjuster - shift
    ]
    if not indexes:
        line = ""
    shift += end_index + 1 - adjuster - index
    if adjuster == 0:
        breaking = True
    index = end_index
    return indexes, index, line, breaking, shift


def statement_adjust(
    temp_line: str,
    line_iter: Iterable,
    new_lines: list[str],
    indexes: list[int],
    index: int,
    line: str,
    temp_indent: int,
    shift: int,
    append_shift: int,
    except_adjust: int,
) -> tuple[list[str], list[int], int, str, bool]:
    """Adjusts the current statement for control_flow_adjust"""
    breaking = False
    condition = (temp_line.startswith("except") and temp_line[6] in " :"), (
        temp_line.startswith("finally") and temp_line[7] in " :"
    )
    if condition[0] or condition[1]:
        ## temp_line gets added after ##
        if not new_lines:
            new_lines = [" " * 4 + "try:", " " * 8 + "pass"]
            indexes = [indexes[0], indexes[0]] + indexes
            append_shift += 2
        else:
            new_lines = [" " * 4 + "try:"] + indent_lines(new_lines)
            ## add to the linetable ##
            indexes = [indexes[0]] + indexes
            append_shift += 1
        if except_adjust is None:
            if condition[1]:
                except_adjust = -1
            else:
                except_adjust = temp_indent
    elif is_alternative_statement(temp_line):
        indexes, index, line, breaking, shift = skip_alt_stmnt_proxy(
            line_iter, temp_indent, indexes, index, shift, append_shift
        )
    return new_lines, indexes, index, line, breaking, shift, append_shift, except_adjust


def control_flow_adjust(
    lines: list[str], indexes: list[int], reference_indent: int = 4
) -> tuple[list[str], list[int]]:
    """
    removes unreachable control flow blocks that
    will get in the way of the generators state

    Note: it assumes that the line is cleaned,
    in particular, that it starts with an
    indentation of 4 (4 because we're in a function)

    It will also add 'try:' when there's an 'except'
    or 'finally' line on the next minimum indent
    """
    new_lines, current_min, line_iter, shift, append_shift = (
        [],
        get_indent(lines[0]),
        enumerate(lines),
        0,
        0,
    )
    ## check if the first line is an alternative statement ##
    index, line = next(line_iter)
    temp_indent = get_indent(line)
    new_lines, indexes, index, line, breaking, shift, append_shift, except_adjust = (
        statement_adjust(
            line[temp_indent:],
            line_iter,
            new_lines,
            indexes,
            index,
            line,
            temp_indent,
            shift,
            append_shift,
            None,
        )
    )
    ## add the line (adjust if indentation is not reference_indent) ##
    if current_min != reference_indent:
        ## adjust using the current_min until it's the same as reference_indent ##
        new_lines += [line[current_min - 4 :]]
    else:
        return (
            new_lines + indent_lines(lines[index:], 4 - reference_indent),
            indexes,
        )
    if not breaking:
        for index, line in line_iter:
            temp_indent = get_indent(line)
            temp_line = line[temp_indent:]
            if temp_indent < current_min:
                current_min = temp_indent
                (
                    new_lines,
                    indexes,
                    index,
                    line,
                    breaking,
                    shift,
                    append_shift,
                    except_adjust,
                ) = statement_adjust(
                    temp_line,
                    line_iter,
                    new_lines,
                    indexes,
                    index,
                    line,
                    temp_indent,
                    shift,
                    append_shift,
                    except_adjust,
                )
                if breaking:
                    break
            elif (
                temp_indent == except_adjust
                and temp_line.startswith("except")
                and temp_line[6] in " :"
            ):
                except_adjust = -1  ## so long as it's not x % 4 == 0 or None ##
                indexes, index, line, breaking, shift = skip_alt_stmnt_proxy(
                    line_iter,
                    temp_indent,
                    indexes,
                    index,
                    shift,
                    append_shift,
                    check=lambda line: line.startswith("except") and line[6] in " :",
                )
            ## add the line (adjust if indentation is not reference_indent) ##
            if current_min != reference_indent:
                except_adjust = -1
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


def iter_adjust(line: str, number_of_indents: int) -> str:
    """
    Replaces the iterator of a for loop
    with an adjusted version (for tracking iterators)

    e.g. we extract the second ... in:
    for ... in ...:

    While loops get adjusted on custom adjustment
    """
    temp_line = line[number_of_indents:]
    index, depth, ID, line_iter = (
        0,
        0,
        "",
        enumerate(temp_line, number_of_indents),
    )
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
    ## adjust by 2 to skip the 'n' and ' ' in 'in ' that would've been deduced ##
    index += 2
    iterator = line[index:-1]  ## -1 to remove the end colon ##
    ## remove the leading and trailing whitespace and then it should be a variable name ##
    if iterator.strip().isalnum():
        return line
    return line[:index] + "locals()['.internals']['.%s']:" % number_of_indents


def is_statement(line: str, statement: str) -> bool:
    """To make sure the line is a statement with more accuracy and efficiency"""
    ## check that they're the same ##
    for index, (char1, char2) in enumerate(zip(line, statement)):
        if char1 != char2:
            break
    index += 1
    if index != len(statement):
        return False
    ## check it's not a variable ##
    line = line[index:]
    if line:
        if line[0] in " ;\n":
            return True
        return False
    return True


def skip_blocks(
    new_lines: list[str], line_iter: Iterable, index: int, line: str
) -> tuple[list[str], str, int]:
    """
    Skips over for/while, definition blocks,
    and removes indentation from the line
    """
    indent = get_indent(line)
    temp_line = line[indent:]
    check = lambda temp_line: is_loop(temp_line) or is_definition(temp_line)
    if check(temp_line):
        while check(temp_line):
            new_lines += [line[indent:]]
            temp_indent = None
            for index, line in line_iter:
                temp_indent = get_indent(line)
                if temp_indent <= indent:
                    break
                new_lines += [line[indent:]]
            ## continue back ##
            indent = temp_indent
            temp_line = line[indent:]
        return new_lines, None, None
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
    ## flag determines if we need to complete a sliced loop or simply dedent its complete form ##
    new_lines, flag, line_iter = [], False, enumerate(lines)
    for index, line in line_iter:
        ## skip over for/while and definition blocks ##
        ## since these are complete blocks of their own ##
        ## and don't need to be adjusted ##
        new_lines, temp_line, index = skip_blocks(new_lines, line_iter, index, line)
        if index is None:
            continue
        ## adjustments ##
        if is_statement(temp_line, "continue"):
            flag = True
            new_lines += ["break"]
        elif is_statement(temp_line, "break"):
            flag = True
            new_lines += ["locals()['.internals']['.continue']=False", "break"]
            ## the index can be None since the line should run without errors ##
            indexes = indexes[:index] + [None] + indexes[index:]
        else:
            new_lines += [temp_line]
    ## adjust the outer loops iterator in case it's an iterator that needs its tracked version ##
    temp_line = outer_loop[0]
    number_of_indents = get_indent(temp_line)
    if temp_line[number_of_indents:].startswith("for "):
        outer_loop[0] = iter_adjust(temp_line, number_of_indents)
    if flag:
        ## the loop adjust itself ##
        return [
            "    locals()['.internals']['.continue']=True",
            "    for _ in (None,):",
        ] + indent_lines(new_lines, 8 - get_indent(new_lines[0])) + [
            "    if locals()['.internals']['.continue']:"
            ## add the outer loop (dedented so that it works) ##
        ] + indent_lines(
            outer_loop, 8 - get_indent(outer_loop[0])
        ), [
            ## add all the indexes which are also adjusted for the changes ##
            None,
            None,
        ] + indexes + [
            None,
        ] + list(
            range(*pos)
        )
    ## If it doesn't need any adjustments e.g. continue and break statements ##
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
            ## 11 to get past the yield from
            indent
            + "locals()['.internals']['.%s']=locals()['.internals']['.yieldfrom']=iter(%s)"
            % (len(indent), temp_line[11:]),
            indent
            + "for locals()['.internals']['.i'] in locals()['.internals']['.yieldfrom']:",
            indent + "    return locals()['.internals']['.i']",
            indent + "    if locals()['.internals']['.send']:",
            indent
            + "        return locals()['.internals']['.yieldfrom'].send(locals()['.internals']['.send'])",
        ]
    if (
        temp_line.startswith("yield ")
        or temp_line.startswith("yield)")
        or temp_line == "yield"
    ):
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
        if lineno <= pos[0]:
            break
        if lineno <= pos[1]:
            ## subtract 1 for 0 based indexing; it's only got one specific ##
            ## use case that requires it to be an array accessor ##
            loops += [(pos[0] - 1, pos[1] - 1)]
    return loops


def extract_source_from_comparison(
    code_obj: CodeType,
    source: str,
    extractor: FunctionType,
    globals: dict = None,
    locals: dict = None,
) -> str:
    """
    Extracts source via a comparison of
    extracted source codes code object
    and the current code object
    """
    attrs = (
        "co_freevars",
        "co_cellvars",
        "co_nlocals",
        "co_stacksize",
        "co_code",
        "co_consts",
        "co_names",
        "co_varnames",
        "co_name",
    )
    if isinstance(source, list):
        source = "".join(source)
    extracing_genexpr = getcode(extractor).co_name == "extract_genexpr"
    for col_offset, end_col_offset in extractor(source):
        try:  ## we need to make it a try-except in case of potential syntax errors towards the end of the line/s ##
            ## eval should be safe here assuming we have correctly extracted the expression - we can't use compile because it gives a different result ##
            temp_source = source[col_offset:end_col_offset]
            try:
                genexpr = eval(temp_source, globals, locals)
            except NameError as e:
                if not extracing_genexpr:
                    raise e
                ## NameError since genexpr's first iterator is stored as .0 ##
                name = e.args[0].split("'")[1]
                genexpr = eval(temp_source, globals, locals | {name: locals[".0"]})
            temp_code = getcode(genexpr)
            ## attr_cmp should get most simple cases, code_cmp should cover nonlocal + closures ideally ##
            if attr_cmp(temp_code, code_obj, attrs) or code_cmp(temp_code, code_obj):
                return temp_source
        except SyntaxError:
            pass
    raise Exception("No matches to the original source code found")


def expr_getsource(FUNC: Any) -> str:
    """
    Uses the source code extracting expressions until a
    match is found on a code object basis to get the source

    You can also to some extent use co_positions as well

    Note:
    the extractor should return a string and if using a
    lambda extractor it will take in a string input but
    if using a generator expression extractor it will
    take a list instead
    """
    code_obj = getcode(FUNC)
    if code_obj.co_name == "<lambda>":
        ## here source is a : str
        if is_cli():
            source = cli_findsource()
        else:
            source = getsource(code_obj)
        extractor = extract_lambda
        ## functions don't need their variables defined right away ##

        if isinstance(FUNC, FunctionType):
            globals = FUNC.__globals__
            locals = get_nonlocals(FUNC)
        else:
            frame = getframe(FUNC)
            globals = frame.f_globals
            locals = frame.f_locals
    else:
        frame = getframe(FUNC)
        ## here source is a : list[str]
        if is_cli():
            source = cli_findsource()
        else:
            lineno = frame.f_lineno - 1
            source = findsource(code_obj)[0][lineno:]
        extractor = extract_genexpr
        globals = frame.f_globals
        locals = frame.f_locals
    return extract_source_from_comparison(code_obj, source, extractor, globals, locals)


def extract_genexpr(
    source: str,
    recursion: bool = False,
    depths: dict = {},
    genexpr_depth: int | None = None,
) -> GeneratorType:
    """Extracts each generator expression from a list of the source code lines"""
    ID, depth, prev = (
        "",
        0,
        (0, 0, ""),
    )
    source_iter = enumerate(source)
    for index, char in source_iter:
        ## skip all strings if not in genexpr
        if char == "'" or char == '"':
            _, prev = string_collector_proxy(index, char, prev, source_iter)
        elif ID == "for" and char in " \\":
            if genexpr_depth and depth > genexpr_depth:
                temp_source = source[temp_col_offset:]
                for offsets in extract_genexpr(
                    temp_source, True, depths, genexpr_depth
                ):
                    yield temp_col_offset + offsets[0], temp_col_offset + offsets[1]
            else:
                genexpr_depth, col_offset = depth, depths[depth]
            ID = ""
        ## detect brackets
        elif char == "(":
            depth += 1
            depths[depth] = index
            temp_col_offset = index
        elif char == ")":
            depths.pop(depth, None)
            if depth == genexpr_depth:
                yield col_offset, index + 1
                if recursion:
                    return
                genexpr_depth = None
            depth -= 1
        if depth:
            ## record ID ##
            if char.isalnum():
                ID += char
            else:
                ID = ""


def extract_lambda(source_code: str, recursion: bool = False) -> GeneratorType:
    """Extracts each lambda expression from the source code string"""
    ID, lambda_depth, depth, prev = "", None, 0, (0, 0, "")
    source_iter = enumerate(source_code)
    for index, char in source_iter:
        ## skip all strings (we only want the offsets)
        if char == "'" or char == '"':
            _, prev = string_collector_proxy(index, char, prev, source_iter)
        elif lambda_depth is not None and (char in "\n;," or depth + 1 == lambda_depth):
            # lambda_depth needed in case of brackets; depth + 1 since depth would've got reduced by 1
            yield col_offset, index
            if recursion:
                return
            ## clear the ID since the next index could be the start of a lambda
            ID, lambda_depth = "", None
        elif char in " \\:" and ID == "lambda":
            if lambda_depth is not None:
                temp_source = source_code[index - 6 :]
                for offsets in extract_lambda(temp_source, recursion=True):
                    yield index - 6 + offsets[0], index - 6 + offsets[1]
            else:
                lambda_depth, col_offset = depth, index - 6
            ID = ""
        ## needs to be skipped this way in case of '\n' (since this is considered an end col_offset)
        elif char == "\\":
            skip_line_continuation(source_iter, source_code, index)
        ## detect brackets (lambda can be in all 3 types of brackets) ##
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        if char.isalnum():
            ID += char
        else:
            ID = ""
    ## in case of a current match ending ##
    if lambda_depth is not None:
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
    reference_indent = get_indent(final_line)
    index = 0
    for index, line in enumerate(current_lines[::-1], start=1):
        current_lines[-index] = indent + current_lines[-index]
        reference_indent = get_indent(line)
        if line[reference_indent:].startswith("try"):
            break
    number_of_indents = reference_indent + 8
    current_indent = " " * number_of_indents
    return (
        current_lines[:-index]
        + [" " * reference_indent + "try:"]
        + current_lines[-index:]
        + [
            current_indent[:-4] + "except:",
            current_indent
            + "locals()['.internals']['.error'] = locals()['.internals']['.exc_info']()[1]",
        ]
        + indent_lines(exception_lines, number_of_indents)
        + [current_indent + "raise locals()['.internals']['.error']"]
        + [final_line]
    )


def singly_space(
    index: int, char: str, line: str, space: int, indented: bool
) -> tuple[str, int, bool]:
    """For ensuring all spaces in a line are single spaces"""
    if indented:
        if space + 1 != index:
            line += char
    else:
        line += char
        if space + 1 != index:
            indented = True
    return line, index, indented


def outer_loop_adjust(
    blocks: list[str],
    indexes: list[int],
    source_lines: list[str],
    loops: list[tuple[int, int]],
    end_pos: int,  ## in case no loops
) -> tuple[list[str], list[int]]:
    """Adds all the outer loops with the iterable adjusted to the current block and its indexes"""
    ## add all the outer loops ##
    for start_pos, end_pos in loops[::-1]:
        end_pos += 1  ## since the jump_positions are inclusion based ##
        block = source_lines[start_pos:end_pos]
        if block:
            temp_line = block[0]
            number_of_indents = get_indent(temp_line)
            if temp_line[number_of_indents:].startswith("for "):
                block[0] = iter_adjust(temp_line, number_of_indents)
        blocks += indent_lines(block, 4 - number_of_indents)
        ## we need to add 1 to the end position since it's 0 based ( e.g. to be inclusive) ##
        indexes += list(range(start_pos, end_pos))
    return blocks + source_lines[end_pos:], indexes


def setup_next_line(char: str, indentation: int) -> tuple[str, bool]:
    """sets up the next line with indentation or not"""
    if char in ":;":
        ## assumes the current line is i.e. ; ... ; ... or if ... : ... ; ... ##
        ## if it's not this then we should get an empty line and this assumption ##
        ## will not take effect in modifying lines ##
        return " " * indentation, True
    return "", False


def unpack_lambda(source: str) -> list[str]:
    """Unpacks the lambda into a single source line"""
    depth = 0
    for index, char in enumerate(source):
        if char == ":" and depth == 0:
            return [source[index + 1 :]]
        depth = update_depth(depth, char, ("([{", ")]}"))
    raise SyntaxError("Unexpected format encountered")


def get_signature(line: str, args: bool = False) -> str | tuple[str, str]:
    """Returns the function signature and its arguments if desired"""
    ID, has_definition, has_args = "", False, False
    for index, char in enumerate(line):
        if char == "(":
            has_args = True
            break
        if char.isalnum():
            ID += char
            if not has_definition and ID == "def":
                ID, has_definition = "", True
        else:
            ID = ""
    if args:
        args = ""
        if has_args:
            ## -1 rstrip() -1 since you can have i.e. func( ... ) :
            args = line[index + 1 :].strip()[:-1].rstrip()[:-1]
        return ID, args
    return ID


def collect_lambda(
    line: str, source_iter: Iterable, source: str, prev: tuple[int, int, str]
) -> tuple[str, str]:
    """Collects a lambda function into a single line"""
    depth, in_definition = 0, False
    for index, char in source_iter:
        if char == "'" or char == '"':
            string_collected, prev, adjustments = string_collector_proxy(
                index, char, prev, source_iter, line, source
            )
            line += string_collected
        elif (
            char in "#\n;"
            or (char == ":" and source[index + 1 : index + 2] != "=")
            and in_definition
        ):
            break
        else:
            if not in_definition and char == ":":
                in_definition = True
            else:
                depth = update_depth(depth, char, ("([{", ")]}"))
                if depth == -1:
                    break
            line += char
    return char, line


def sign(
    FUNC: FunctionType,
    FUNC2: FunctionType,
    globals: dict = None,
    boundmethod: bool = False,
    closure: tuple[CellType] = None,
) -> FunctionType:
    """signs a function with the signature of another function"""
    _signature = format(signature(FUNC2))
    if boundmethod:
        _signature = "(self, " + _signature[1:]
    _signature = FUNC2.__name__ + _signature + ":"
    source = skip_source_definition(getsource(FUNC))
    ## create the function ##
    source = "def %s%s" % (_signature, source)
    exec(source, globals, locals(), closure=closure)
    temp = locals()[FUNC2.__name__]
    temp.__source__ = source
    temp.__doc__ = FUNC2.__doc__
    return temp


######################################################
#### Cleaning and adjusting Generator source code ####
######################################################


def record_jumps(self: GeneratorType, number_of_indents: int) -> None:
    """Records the jump positions for the loops (for and while) to help with code adjustments"""
    ## has to be a list since we're assigning ##
    self._internals["jump_positions"] += [[self._internals["lineno"], None]]
    self._internals["jump_stack"] += [
        (number_of_indents, len(self._internals["jump_positions"]) - 1)
    ]


def custom_adjustment(
    self: GeneratorType, line: str, number_of_indents: int = 0
) -> list[str]:
    """
    It does the following to the source lines:

    1. replace all lines that start with yields with returns to start with
    2. make sure the generator is closed on regular returns
    3. save the iterator from the for loops replacing with a nonlocal variation
    4. tend to all yield from ... with the same for loop variation
    5. adjust all value yields either via unwrapping or unpacking
    """
    temp_line = line[number_of_indents:]
    indent = " " * number_of_indents
    ## decorator ##
    if temp_line.startswith("@"):
        self._internals["decorator"] = True
        return [line]
    ## yield ##
    result = yield_adjust(temp_line, indent)
    if temp_line.startswith("yield from "):
        lineno = self._internals["lineno"]
        ## lineno + 1 since this is not a loop ##
        self._internals["jump_positions"] += [[lineno + 1, lineno + len(result)]]
    if result is not None:
        return result
    ## loops ##
    if is_loop(temp_line):
        record_jumps(self, number_of_indents)
        return [line]
    ## return ##
    if temp_line == "return" or temp_line.startswith("return "):
        ## close the generator then return ##
        ## have to use a try-finally in case the user returns a value from locals() ##
        return [indent + "return EOF('" + temp_line[7:] + "')"]
    ## nonlocal ##
    if temp_line.startswith("nonlocal "):
        ## we have to remove the nonlocal keyword since there will be no bindings. ##
        ## The args are collected in __init__ for unintialized function generators; ##
        ## initialized generators already have them in their locals ##
        self._internals["lineno"] -= 1
        return []
    return [line]


def update_jump_positions(
    self: GeneratorType, lines: list[str], reference_indent: int = -1
) -> list[str]:
    """
    Updates the end jump positions in self._internals["jump_positions"].
    It may also append the current lines with adjustments if it's a while
    loop that used a value yield in its condition
    """
    if self._internals["jump_stack"]:
        end_lineno = self._internals["lineno"]
        while (
            self._internals["jump_stack"]
            and reference_indent <= self._internals["jump_stack"][-1][0]
        ):  # -1: top of stack, 0: indent
            index = self._internals["jump_stack"].pop()[1]
            self._internals["jump_positions"][index][1] = end_lineno
            ## add the adjustments
            if (
                self._internals["jump_stack_adjuster"]
                ## check if they're the same lineno ##
                and self._internals["jump_positions"][index][0]
                == self._internals["jump_stack_adjuster"][-1][0]
            ):
                adjustments = self._internals["jump_stack_adjuster"].pop().pop()
                ## add the adjustments ##
                lines += adjustments
                ## make sure with the adjustments that have loops ##
                ## that the loops are recorded and the lineno is adjusted ##
                count = 0
                for self._internals["lineno"], line in enumerate(
                    ## temporarily add an additional adjustment to make ##
                    ## sure the loop positions are recorded properly ##
                    adjustments + [""],
                    start=self._internals["lineno"] + 1,
                ):
                    number_of_indents = get_indent(line)
                    if is_loop(line[number_of_indents:]):
                        count += 1
                        record_jumps(self, number_of_indents)
                    ## we can use -1 since all the loops should be complete ##
                    elif (
                        count
                        and number_of_indents <= self._internals["jump_stack"][-1][0]
                    ):
                        index = self._internals["jump_stack"].pop()[1]
                        self._internals["jump_positions"][index][1] = (
                            self._internals["lineno"] + 1
                        )
                    self._internals["linetable"] += [self._internals["lineno"]]
                ## since we temporarily increased the number of adjustments ##
                self._internals["lineno"] -= 1
                self._internals["linetable"].pop()
    return lines


def append_line(
    self: GeneratorType,
    index: int,
    char: str,
    source: str,
    source_iter: Iterable,
    running: bool,
    line: str,
    lines: list[str],
    indentation: int,
    indent_adjust: int,
) -> tuple[int, str, int, list[str], str, bool, int]:
    """skips comments, adds definitions, appends the line, updates the indentation, and updates the jump positions"""
    ## skip comments ##
    if char == "#":
        for index, char in source_iter:
            if char == "\n":
                break
    ## make sure to include it ##
    if char == ":":
        indentation = get_indent(line) + 4  # in case of ';'
        line += char
    if line and not line.isspace():  ## empty lines are possible ##
        reference_indent = get_indent(line)
        ## make sure the line is corrected if it currently assumes indentation when it shouldn't ##
        if (
            indent_adjust
            and reference_indent - (char == ":") * 4 >= indentation - indent_adjust
        ):
            line = " " * indent_adjust + line
        else:
            indent_adjust = 0
        lines = update_jump_positions(self, lines, reference_indent)
        ## skip the definitions ##
        temp_line = line[reference_indent:]
        if is_definition(temp_line):
            index, char, self._internals["lineno"], lines = collect_definition(
                index - len(line) + 1,
                lines,
                self._internals["lineno"],
                source,
                source_iter,
                reference_indent,
                self._internals["decorator"],
            )
            self._internals["decorator"] = False
        else:
            ## update the lineno before so the loops positions are lineno based ##
            self._internals["lineno"] += 1
            lines += custom_adjustment(self, line, reference_indent)
        line, indented = setup_next_line(char, indentation)
    else:
        reference_indent = indentation
        line, indented = "", False
    ## make a linetable if using a running generator ##
    ## for the linetable e.g. for lineno_adjust e.g. compound statements ##
    if running and char == "\n":
        self._internals["linetable"] += [self._internals["lineno"]]
    # if indent_adjust:
    #     line += " " * indent_adjust
    ## start a new line ##
    return index, char, lines, line, indented, indentation, indent_adjust


def block_adjust(
    self: GeneratorType,
    current_lines: list[str],
    new_lines: list[str],
    final_line: str,
    source: str,
    source_iter: Iterable,
) -> list[str]:
    """
    Checks if lines that were adjusted because of value yields
    are in a block statement and therefore needs adjusting

    Also, the new_lines do need to be indented accordingly
    e.g. to the final_line or specfic adjustment, and the
    jump_positions of any loops need to be recorded (e.g.
    from yield_adjust for 'yield from ...')
    """
    ## make sure any loops are recorded (necessary for 'yield from ...' adjustment) ##
    ## and the lineno is updated ##
    is_loop = False
    for self._internals["lineno"], line in enumerate(
        new_lines, start=self._internals["lineno"] + 1
    ):
        number_of_indents = get_indent(line)
        if is_loop(line[number_of_indents:]):
            record_jumps(self, self._internals["lineno"], number_of_indents)
            is_loop = number_of_indents
            continue
        if number_of_indents <= is_loop:
            self._internals["jump_positions"][-1][1] = self._internals["lineno"]
            is_loop = False
    if is_loop:
        self._internals["jump_positions"][-1][1] = self._internals["lineno"]
    ## check for adjustments in the final line ##
    number_of_indents = get_indent(final_line)
    temp_line = final_line[number_of_indents:]
    check = lambda expr: temp_line.startswith(expr) and temp_line[len(expr)] in " :"
    if temp_line[:1] == "@":
        temp_line = temp_line[1:]
        signature = get_signature(temp_line, True)
        if signature[1]:
            temp_line = "locals()['.internals']['partial'](%s, %s)" % signature
        else:
            temp_line = signature[0]
        if self._internals["decorator"]:
            temp_line = "locals()['.internals']['.decorator'](%s)" % temp_line
        else:
            self._internals["decorator"] = True
        final_line = (
            " " * number_of_indents
            + "locals()['.internals']['.decorator'] = "
            + temp_line
        )
    elif is_definition(temp_line):
        index, char, self._internals["lineno"], lines = collect_definition(
            index - len(line) + 1,
            lines,
            self._internals["lineno"],
            source,
            source_iter,
            number_of_indents,
            self._internals["decorator"],
        )
        self._internals["decorator"] = False
    elif is_loop(temp_line):
        ## the end of the loop needs to be appended with the new_lines ##
        ## locals()[".args"] += next(...)
        ## while locals()[".args"].pop():
        ##     ...
        ##     locals()[".args"] += next(...)
        self._internals["jump_stack_adjuster"] += [
            [self._internals["lineno"]] + indent_lines(new_lines, number_of_indents + 4)
        ]
    ## needs to indent itself and all other lines until the end of the block ##
    ## Note: only elif since if statements should be fine ##
    elif check("elif"):
        ## +4 to encapsulate in an else statement +2 to make it an 'if' statement ##
        final_line = " " * (number_of_indents + 4) + final_line[number_of_indents + 2 :]
        return (
            current_lines
            + [" " * number_of_indents + "else:"]
            + indent_lines(new_lines, number_of_indents + 4)
            + [final_line]
        )
    elif check("except"):
        ## this is the problem ##
        # if current_lines[-2] == ' try:':
        #     current_lines[-2] = ' ' * 8 + 'try:'
        #     final_line = final_line[8:]
        ## except_adjust automatically does the indentation ##
        return except_adjust(current_lines, new_lines, final_line)
    self._internals["lineno"] += 1
    return current_lines + indent_lines(new_lines, number_of_indents) + [final_line]


def string_collector_adjust(
    self: GeneratorType,
    index: int,
    char: str,
    prev: tuple[int, int, str],
    source_iter: Iterable,
    line: str,
    source: str,
    lines: list[str],
) -> tuple[str, int, list[str]]:
    """Adjust the string collector in case of any value yields in the f-strings"""
    string_collected, prev, adjustments = string_collector_proxy(
        index, char, prev, source_iter, line, source
    )
    if adjustments:
        ## since we have adjustments we need to adjust the chars before it ##
        adjustments_start, line_start, index = unpack(line, source=source, index=index)
        line_start = " " * get_indent(line) + line_start.lstrip()
        adjustments_end, line_end, index = unpack(
            source_iter=source_iter, source=source, index=index
        )
        final_adjustments, final_line = (
            adjustments_start + adjustments + adjustments_end,
            line_start + string_collected + line_end,
        )
        return (
            index,
            prev,
            block_adjust(
                self, lines, final_adjustments, final_line, source, source_iter
            ),
        )
    return line + string_collected, prev, lines


def clean_source_lines(self: GeneratorType, running: bool = False) -> list[str]:
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
    (
        self._internals["jump_positions"],
        self._internals["jump_stack"],
        self._internals["jump_stack_adjuster"],
        self._internals["decorator"],
        self._internals["lineno"],
    ) = (
        [],
        [],
        [],
        False,
        0,
    )
    ## setup source as an iterator and making sure the first indentation's correct ##
    source = skip_source_definition(self._internals["source"])
    ## we need to make sure the source is saved for skipping for line continuations ##
    source = source[get_indent(source) :]
    source_iter = enumerate(source)
    ID, depth, line, lines, indented, space, indentation, prev, indent_adjust = (
        "",
        0,
        " " * 4,
        [],
        False,
        0,
        4,
        (0, 0, ""),
        0,
    )
    ## enumerate since I want the loop to use an iterator but the
    ## index is needed to retain it for when it's used on get_indent
    for index, char in source_iter:
        ## collect strings ##
        if char == "'" or char == '"':
            line, prev, lines = string_collector_adjust(
                self, index, char, prev, source_iter, line, source, lines
            )
            if isinstance(line, int):
                depth, ID = 0, ""
                indentation = get_indent(lines[-1])
                line, indented = setup_next_line(source[line], indentation)
                space = index
        ## makes the line singly spaced while retaining the indentation ##
        elif char == " ":
            line, space, indented = singly_space(index, char, line, space, indented)
        ## join everything after the line continuation until the next \n or ; ##
        elif char == "\\":
            skip_line_continuation(source_iter, source, index)
            ## in case of a line continuation without a space before (whitespace after is removed) ##
            ## Note: i.e. 'func        ()' is valid in python ##
            if space + 1 != index:
                line += " "
                space = index
        ## create new line ##
        ## should be able to go depth == 0 ... like in unpack ##
        ## depth == 0 in case of brackets splitting across lines ##
        # depth == 0 and
        elif char in "#\n;" or (char == ":" and source[index + 1 : index + 2] != "="):
            ## 'space' is important (otherwise we get more indents than necessary) ##
            space, char, lines, line, indented, indentation, indent_adjust = (
                append_line(
                    self,
                    index,
                    char,
                    source,
                    source_iter,
                    running,
                    line,
                    lines,
                    indentation,
                    indent_adjust,
                )
            )
            depth, ID = 0, ""
        else:

            ### might move this section into a function ###

            line += char
            ## detect value yields [yield] and {yield} is not possible only (yield) ##
            depth = update_depth(depth, char)
            if char == "=":  ## '... = yield ...' and '... = yield from ...'
                depth += 1
            if depth and char.isalnum():
                ID, line, lines, indented, index, char, space = source_update_ID(
                    self,
                    source,
                    source_iter,
                    prev,
                    space,
                    index,
                    char,
                    ## : index + 2 in case of IndexError ##
                    source[index + 1 : index + 2],
                    ID,
                    line,
                    lines,
                    indented,
                    running,
                )
            else:
                ID = ""
    ## in case you get a for loop at the end and you haven't got the end jump_position ##
    ## then you just pop them all off as being the same end_lineno ##
    ## note: we don't need a reference indent since the line is over e.g. ##
    ## the jump_stack will be popped if it exists ##
    lines = update_jump_positions(self, lines)
    ## are no longer needed ##
    del (
        self._internals["jump_stack"],
        self._internals["jump_stack_adjuster"],
        self._internals["decorator"],
    )
    return lines


def source_update_ID(
    self: GeneratorType,
    source: str,
    source_iter: Iterable,
    prev: tuple[int, int, str],
    space: int,
    index: int,
    char: str,
    next_char: str,
    ID: str,
    line: str,
    lines: list[str],
    indented: bool,
    running: bool,
) -> tuple[str, str, list[str], bool, int, str, int]:
    """Handles ID in clean_source_lines to collect lambdas, value yields, and ternary expressions"""
    ## in case of ... ... (otherwise you keep appending the ID) ##
    if space + 1 == index:
        ID = ""
    ID += char
    if ID == "lambda" and next_char in " :\\":
        char, lines = collect_lambda(line, source_iter, source, prev)
        indentation = get_indent(line)
        line, indented = setup_next_line(char, indentation)
        self._internals["lineno"] += 1
        ID = ""
    elif ID == "yield" and next_char in " )]}\n;\\":
        new_lines, final_line, index = unpack(
            line, source_iter, source=source, index=index
        )
        final_line = " " * get_indent(line) + final_line.lstrip()
        if line[get_indent(line) :].startswith("elif "):
            indent_adjust = 4
        length_before = len(lines)
        lines = block_adjust(self, lines, new_lines, final_line, source, source_iter)
        if running:
            self._internals["linetable"] += [self._internals["lineno"]] * (
                len(lines) - length_before
            )

        if is_definition(final_line[get_indent(final_line) :]):
            line, indented = "", False
        else:
            indentation = get_indent(lines[-1]) + indent_adjust
            line, indented = setup_next_line(source[index], indentation)
        if indent_adjust:
            line = " " * indentation
            space = index
        ID = ""
    ## ternary statement ##
    elif ID == "if" and next_char in " \\" and line[:-2].lstrip():
        new_lines, final_line, _ = unpack(line, source_iter, source=source, index=index)
        lines = self.block_adjust(
            self, lines, new_lines, final_line, source, source_iter
        )
        ## setup for a new line ##
    return ID, line, lines, indented, index, char, space


def clean_lambda(self: GeneratorType, FUNC: FunctionType) -> None:
    """
    determine what expression is formed when the lambda expression gets called
    1. value yields - unpack
    2. generator expression - unpack_genexpr
    """
    self._internals["source"] = expr_getsource(FUNC)
    source = unpack_lambda(self._internals["source"])[0]
    ## tries to figure out what it is ##
    # Non Generator, Generator, generator expression
    type = check_expression(source)
    if type == "<genexpr>":
        genexpr_adjust(self, source)
    ## should only have a single value yield at depth == 1 ##
    elif type == "<Generator>":
        lines, final_line, _ = unpack(source)
        self._internals["source_lines"] = lines + [final_line]
        self._internals["lineno"] = 1
    else:
        raise TypeError(
            "based on the source code retrieved the expression that will be created from the given lambda expression is an invalid initializer for a Generator"
        )


def genexpr_adjust(self: GeneratorType, source: str) -> None:
    """Adjusts for an initialized generator expression"""
    self._internals["source_lines"] = unpack_genexpr(source)
    ## add the jump_positions ##
    positions, length = [], len(self._internals["source_lines"])
    for index, line in enumerate(self._internals["source_lines"], start=1):
        if not line[get_indent(line) :].startswith("for "):
            break
        positions += [[index, length]]
    self._internals["jump_positions"] = positions
    ## set the first iterator and determine the lineno ##
    first_iter = self._locals().pop(".0")
    if ".internals" not in self._locals():
        ## the internally set iterator ##
        self._locals()[".internals"] = {".4": first_iter}
    ## change the offsets into indents ##
    if gcopy.track.track_adjust(self._locals()[".internals"]) or is_running(
        self._locals()[".internals"][".4"]
    ):
        self._internals["lineno"] = length
    else:
        self._internals["lineno"] = 1


def check_expression(source: str) -> str:
    """Checks if there are any yields or if there is a single generator expression present"""
    ID, depth, prev, expression = (
        "",
        0,
        (0, 0, ""),
        "",
    )
    source_iter = enumerate(source)
    for index, char in source_iter:
        ## skip all strings if not in genexpr
        if char == "'" or char == '"':
            _, prev = string_collector_proxy(index, char, prev, source_iter)
        ## detect brackets
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                break
        if depth:
            ## record ID ##
            if char.isalnum():
                ID += char
                if depth == 1:
                    next_char = source[index + 1 : index + 2]
                    if ID == "for" and next_char in " \\":
                        expression = "<genexpr>"
                    if ID == "yield" and next_char in " \\)":
                        expression = "<Generator>"
            else:
                ID = ""
    temp = source[index + 1 :]
    if temp and not temp.isspace():
        return ""
    return expression
