#################################################
### cleaning/extracting/adjusting source code ###
#################################################
from .utils import *
from inspect import getsource, findsource
from typing import Iterable, Any
from types import GeneratorType, FrameType, FunctionType


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


def line_adjust(line: str, lines: list[str], adjust: bool = True) -> str:
    """
    Adds indentation to the lines and colon for statements

    Specific to the unpack_genexpr function where the lines
    will start with 'for' or 'if' when separated
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
                        temp = next(source_iter)[1]
                    ## it's not possible to have i.e. ( ... if char == if) ##
                    except StopIteration:
                        raise SyntaxError("Unexpected format encountered")
                    ## adjusts and adds the line to lines ##
                    if temp in "\\ ":
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
    source_iter: Iterable, reference: str, source: str = None
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
                adjustments, f_string_contents, _ = unpack(char, source_iter, True)
                # print(f"{line,adjustments,f_string_contents=}")
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
    source_iter: Iterable, reference: str, source: str = None
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
                adjustments, f_string_contents, _ = unpack(char, source_iter, True)
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
) -> tuple[list[str], str, int]:
    """Proxy function for usage when collecting strings since this block of code gets used repeatedly"""
    ## get the string collector type ##
    if prev[0] + 2 == prev[1] + 1 == index and prev[2] == char:
        string_collector, temp_index = collect_multiline_string, 3
    else:
        string_collector, temp_index = collect_string, 1
    ## determine if we need to look for f-strings in case of value yields ##
    # print(line,temp_index,char,)
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
    temp_index, temp_line = string_collector(iterable, char, source)
    prev = (index, temp_index, char)
    if f_string:
        if source:
            ## lines (adjustments) + line (string collected) ##
            return temp_line.pop(), prev, temp_line
        return temp_line, prev, []
    if line is not None:
        line += temp_line
    return line, prev


def inverse_bracket(bracket: str) -> str:
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
) -> tuple[list[str], str, str, int]:
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
    named = True
    line, lines, final_line, named = update_lines(
        line, lines, final_line, named, line_iter
    )
    lines += temp
    return line, lines, final_line, named


def unpack_adjust(line: str) -> list[str]:
    """adjusts the unpacked line for usage and value yields"""
    if line.startswith("yield "):
        return yield_adjust(line, "") + ["locals()['.args'] += [locals()['.send']]"]
    return ["locals()['.args'] += [%s]" % line]


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
) -> tuple[list[str], str]:
    """
    adds the current line or the unwrapped line to the lines
    if it's not a variable or constant otherwise the line is
    added to the final lines
    """
    if not line.isspace():
        ## unwrapping ##
        if unwrap:
            temp_lines, temp_final_line, _ = unpack(
                source_iter=unwrap, unwrapping=True, named=named
            )
            if yielding:
                temp_final_line = "yield " + temp_final_line[:-1]
                lines += temp_lines + unpack_adjust(temp_final_line.strip())
                line = line[:bracket_index] + "locals()['.args'].pop(0)"
            else:
                lines += temp_lines
                line += temp_final_line
        ## unpacking ##
        else:
            ## variable ##
            if line.strip().isalnum() or named:
                final_line += line
            ## expression ##
            else:
                final_line += "locals()['.args'].pop(0)"
                lines += unpack_adjust(line.strip())
            line = ""
    if operator:
        final_line += operator
    return line, lines, final_line, named


def unpack(
    line: str = empty_generator(),
    source_iter: Iterable = empty_generator(),
    unwrapping: bool = False,
    named: bool = False,
) -> tuple[list[str], str, int]:
    """
    Unpacks value yields from a line into a
    list of lines going towards its right side
    """
    line_iter = chain(enumerate(line), source_iter)
    ## make sure 'space' == -1 for indentation ##
    (
        depth,
        depth_total,
        end_index,
        space,
        lines,
        bracket,
        ID,
        line,
        final_line,
        prev,
        operator,
        bracket_index,
    ) = (0, 0, 0, -1, [], "", "", "", "", (0, 0, ""), 0, None)
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
            line, lines, final_line, named = update_lines(
                line + char, lines, final_line, named, line_iter
            )
        elif char == "\\":
            skip_line_continuation(line_iter, line, end_index)
            if space + 1 != end_index:
                line += " "
                space = end_index
        ## splitting operators ##
        elif char in operators:
            ## since we can have i.e. ** or %= etc. ##
            if end_index - 1 != operator:
                line, lines, final_line, named = update_lines(
                    line, lines, final_line, named, operator=char
                )
            else:
                final_line += char
            operator = end_index
        elif depth == 0 and char in "#:;\n":  ## split and break condition ##
            if char == ":":
                line += ":"
            ## not sure if this is needed or not yet ... ##
            # if lines:
            #     lines += [line]
            break
        elif char == ":":  ## must be a named expression if depth is not zero ##
            line, lines, final_line, named = named_adjust(
                line, lines, final_line, line_iter, ID
            )
            ## since we're going to skip some chars ##
            ID, prev = "", prev[:-1] + (char,)
        else:
            ## record the current depth ##
            if char in "([{":
                depth_total += 1
                bracket = char
            elif char in ")}]":
                depth_total -= 1
                if unwrapping and depth_total < 0 or char != inverse_bracket(bracket):
                    line += char
                    break
            if char == "(":
                depth += 1
                ## the index is in relation to the current line ##
                bracket_index = len(line)
            elif char == ")":
                depth -= 1
            ## check for unwrapping/updating ##
            if char.isalnum():
                ## in case of ... ... (otherwise you keep appending the ID) ##
                if space + 1 == end_index:
                    ID = ""
                ID += char
                if depth and ID == "yield":  ## unwrapping ##
                    ## what should happen when we unwrap? ##
                    ## go from the last bracket onwards for the replacement ##
                    line, lines, final_line, named = update_lines(
                        line,
                        lines,
                        final_line,
                        named,
                        line_iter,
                        bracket_index,
                        yielding=True,
                    )
                    ID, prev, bracket_index = "", prev[:-1] + (char,), None
                    ## since the unwrapping will accumulate up to the next bracket this ##
                    ## will go unrecorded on this stack frame recieving but recorded and ##
                    ## garbage collected on the recursed stack frame used on unwrapping ##
                    depth -= 1
                    depth_total -= 1
                    continue  ## to avoid: line += char (we include it in the final_line as the operator or in unwrapping)
                elif 1 < len(ID) < 4 and ID in ("and", "or", "is", "in"):
                    line, lines, final_line, named = update_lines(
                        line, lines, final_line, named, operator=ID
                    )
                    ID, prev = "", prev[:-1] + (char,)
                    continue
            else:
                ID = ""
            line += char
            prev = prev[:-1] + (char,)
    if line:
        final_line += line
    return lines, final_line, end_index


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
    return line.startswith("for ") or line.startswith("while ")


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
    new_lines, current_min, line_iter, end = (
        [],
        get_indent(lines[0]),
        enumerate(lines),
        len(lines) - 1,
    )
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
                if end_index == end:
                    break
            current_min = temp_indent
            ## we have to adjust in case of except but not match ##
            ## (since if you're in a match you're being adjusted in which ever case you're in) ##
            if temp_line.startswith("except") and temp_line[6] in " :":
                ## temp_line gets added after ##
                new_lines = [" " * 4 + "try:"] + indent_lines(new_lines)
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


def iter_adjust(line: str, number_of_indents: int) -> str:
    """
    Replaces the iterator of a for loop
    with an adjusted version (for tracking iterators)

    e.g. we extract the second ... in:
    for ... in ...:
    """
    index, depth, ID, line_iter = (
        0,
        0,
        "",
        enumerate(line[number_of_indents:], number_of_indents),
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
    return line[:index] + "locals()['.%s']:" % number_of_indents


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
            new_lines += ["locals()['.continue']=False", "break"]
            indexes = indexes[index:] + [indexes[index]] + indexes[:index]
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
            "    locals()['.continue']=True",
            "    for _ in (None,):",
        ] + indent_lines(new_lines, 8 - get_indent(new_lines[0])) + [
            "    if locals()['.continue']:"
            ## add the outer loop (dedented so that it works) ##
        ] + indent_lines(
            outer_loop, 8 - get_indent(outer_loop[0])
        ), [
            ## add all the indexes which are also adjusted for the changes ##
            indexes[0],
            indexes[0],
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
            ## 11 to get past the yield from
            indent + "locals()['.yieldfrom']=" + temp_line[11:],
            indent + "for locals()['.i'] in locals()['.yieldfrom']:",
            indent + "    if locals()['.send']:",
            indent + "        return locals()['.i'].send(locals()['.send'])",
            indent + "    else:",
            indent + "        return locals()['.i']",
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


def extract_source_from_positions(code_obj: CodeType, source: str) -> str:
    """
    Uses co_positions from version 3.11
    to extract the correct source code
    """
    # start_line, end_line, start_col, end_col
    positions = code_obj.co_positions()
    is_source_list = isinstance(source, list)
    pos = next(positions, (None, None, None, None))[1:]
    current_min, current_max = pos[1:]
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


def extract_source_from_comparison(
    code_obj: CodeType, source: str, extractor: FunctionType
) -> str:
    """
    Extracts source via a comparison of
    extracted source codes code object
    and the current code object
    """
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
            temp_source = source[col_offset:end_col_offset]
            temp_code = getcode(eval(temp_source))
            if attr_cmp(temp_code, code_obj, attrs):
                return temp_source
        except SyntaxError:
            pass
    raise Exception("No matches to the original source code found")


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
        if is_cli():
            source = cli_findsource()
        else:
            source = getsource(code_obj)
        extractor = extract_lambda
    else:
        ## here source is a : list[str]
        if is_cli():
            source = cli_findsource()
        else:
            lineno = getframe(FUNC).f_lineno - 1
            source = findsource(code_obj)[0][lineno:]
        extractor = extract_genexpr
    ## get the rest of the source ##
    if False:
        if (3, 11) <= version_info and not is_cli():
            return extract_source_from_positions(code_obj, source)
    ## otherwise match with generator expressions in the original source to get the source code ##
    return extract_source_from_comparison(code_obj, source, extractor)


def extract_genexpr(source: str, recursion: bool = False) -> GeneratorType:
    """Extracts each generator expression from a list of the source code lines"""
    ID, depth, prev, genexpr_depth = (
        "",
        0,
        (0, 0, ""),
        None,
    )
    source_iter = enumerate(source)
    for index, char in source_iter:
        ## skip all strings if not in genexpr
        if char == "'" or char == '"':
            _, prev = string_collector_proxy(index, char, prev, source_iter)
        elif char == " " and ID == "for":
            if genexpr_depth and depth > genexpr_depth:
                temp_source = source[temp_col_offset:]
                for offsets in extract_genexpr(temp_source, recursion=True):
                    yield temp_col_offset + offsets[0], temp_col_offset + offsets[1]
            else:
                genexpr_depth, col_offset = depth, temp_col_offset
            ID = ""
        ## detect brackets
        elif char == "(":
            temp_col_offset = index
            depth += 1
        elif char == ")":
            if depth == genexpr_depth:
                yield col_offset, index + 1
                if recursion:
                    return
                genexpr_depth = None
            depth -= 1
        elif depth:
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
        elif char == " " and ID == "lambda":
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
        elif char.isalnum():
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
            current_indent + "locals()['.error'] = exc_info()[1]",
        ]
        + indent_lines(exception_lines, number_of_indents)
        + [current_indent + "raise locals()['.error']"]
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


def exit_adjust(state: str) -> str:
    """
    Adjusts the source code for the generator exit
    e.g. replaces all 'return ...' with
    raise RuntimeError("generator ignored GeneratorExit")
    """
    state = state.split("\n")
    for index, line in enumerate(state):
        number_of_indents = get_indent(line)
        temp = line[number_of_indents:]
        if temp == "return" or temp.startswith("return "):
            line = " " * number_of_indents + "return"
            if not temp[7:].lstrip().startswith("EOF("):
                line += " 1"
        state[index] = line
    return "\n".join(state)
