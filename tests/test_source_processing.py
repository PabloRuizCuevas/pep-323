from gcopy.source_processing import *
from types import FunctionType


def assert_cases(FUNC: FunctionType, *args) -> None:
    for arg in args:
        assert FUNC(arg)


def test_depth() -> None:
    assert update_depth(0, "(") == 1
    assert update_depth(0, ")") == -1


def test_get_indent() -> None:
    assert get_indent("  asdf") == 2


def test_lineno_adjust() -> None:
    from inspect import currentframe

    frame = currentframe()
    True
    True
    print(frame.f_lasti)
    import dis

    dis.dis(frame.f_code)
    # print(lineno_adjust(frame))


def test_unpack_genexpr() -> None:
    assert unpack_genexpr("(i for i in range(3))") == ["for i in range(3)", "    i"]
    assert unpack_genexpr("(i for i in range(3) if i==True)") == [
        " " * 4 + "for i in range(3):",
        " " * 8 + "if i==True:",
        " " * 12 + "i",
    ]


def test_skip_line_continuation() -> None:
    source = "\     \n     hi"
    source_iter = enumerate(source)
    index, char = next(source_iter)
    skip_line_continuation(source_iter, source, index)
    assert "".join(char for index, char in source_iter) == "hi"


def test_skip_source_definition() -> None:
    source = """@method1
@method2(*args,**kwargs)
def function():pass"""
    assert skip_source_definition(source) == "pass"


def test_collect_string() -> None:
    source = '"""hello world"""'
    source_iter = enumerate(source)
    index, char = next(source_iter)
    assert collect_string(source_iter, char, source) == (1, ['""'])
    next(source_iter)
    assert collect_string(source_iter, char, source) == (14, ['"hello world"'])
    next(source_iter)
    assert collect_string(source_iter, char, source) == (16, ['""'])


def test_collect_multiline_string() -> None:
    source = '"""hello world"""'
    source_iter = enumerate(source)
    index, char = next(source_iter)
    assert collect_multiline_string(source_iter, char, source) == (
        len(source) - 1,
        [source],
    )


def test_string_collector_proxy(recursion: int = 1) -> None:
    """Checks for both skipping and collection cases"""
    source = '"""hello world"""'
    source_iter = enumerate(source)
    prev = (0, 0, "")
    line = ""
    if recursion:
        temp = ['""', '"""hello world"""']
    else:
        temp = [None, None]
    answer = [(temp.pop(0), (0, 1, '"')), (temp.pop(0), (2, 16, '"'))]
    for index, char in source_iter:
        ## collect strings ##
        if char == "'" or char == '"':
            args = (index, char, prev, source_iter)
            if recursion:
                args += (line,)
            ## we need to save line and prev ##
            line, prev = string_collector_proxy(*args)
            assert (line, prev) == answer.pop(0)
    if recursion:
        test_string_collector_proxy(0)


def test_update_lines() -> None:
    update_lines()


def test_unwrap() -> None:
    line = ""
    lines, final_line, end_index = unwrap(line)
    assert lines == []
    assert final_line == ""
    assert end_index == 0


def test_unpack() -> None:
    line = ""
    lines, final_line, end_index = unpack(line)
    assert lines == []
    assert final_line == ""
    assert end_index == 0


def test_unpack_fstring() -> None:
    pass


def test_collect_definition() -> None:
    source = """def function():
    pass
    print('''hello world''')"""
    index, char, lineno, lines = collect_definition(
        None, [], 0, source, enumerate(source), 0
    )
    assert index == len(source) - 1
    assert char == ")"
    assert lineno == 3
    assert lines == source.split("\n")


def test_skip() -> None:
    i = iter(range(3))
    skip(i, 2)
    assert next(i) == 2


def test_is_alternative_statement() -> None:
    assert_cases(is_alternative_statement, "elif", "else")
    if (3, 10) <= version_info:
        assert_cases(is_alternative_statement, "case", "default")


def test_is_definition() -> None:
    assert_cases(is_definition, "def ", "async def ", "class ", "async class ")


def test_skip_alternative_statements() -> None:
    blocks = [
        "    if True:",
        "        pass",
        "    elif True:",
        "        pass",
        "    else:",
        "        pass",
        "try:",
        "    pass",
        "except:",
        "    pass",
    ]
    ## shouldn't skip ##
    assert skip_alternative_statements(enumerate(blocks), 4) == (
        0,
        blocks[0],
        get_indent(blocks[0]),
    )
    ## should skip through all through 1:4 ##
    assert skip_alternative_statements(enumerate(blocks[1:4]), 4) == (
        2,
        blocks[1 + 2],
        get_indent(blocks[1 + 2]),
    )  ## shift is 1
    ## should skip all through towards the 'try:' (excepts are not skipped since you could still be have an exception) ##
    for shift in range(1, 6):
        assert skip_alternative_statements(enumerate(blocks[shift:]), 4) == (
            6 - shift,
            blocks[6],
            get_indent(blocks[6]),
        )
    blocks = [
        "match 'word':",
        "    case 'word 1':",
        "        return 1",
        "    case 'word 2':",
        "        return 2",
        "    default:",
        "        return 3",
    ]
    for shift in range(1, 6):
        ## it should skip over all of them ##
        assert skip_alternative_statements(enumerate(blocks[shift:]), 4) == (
            6 - shift,
            blocks[-1],
            get_indent(blocks[-1]),
        )


def test_control_flow_adjust() -> None:
    ## you need to test for if/elif/else/try/except/match/case/default and when these are sliced ##
    ## and what the resulting index changes are ##
    blocks = [
        "    if True:",
        "        pass",
        "    else:",
        "        pass",
        "try:",
        "    pass",
        "except:",
        "    pass",
    ]
    source_lines = ["for i in range(3):"] + blocks
    ## the loop ##
    start_pos, end_pos = 1, len(blocks)
    temp_lineno = 2
    control_flow_adjust(
        blocks,
        list(range(temp_lineno, end_pos)),
        get_indent(source_lines[start_pos]),
    )


def test_indent_lines() -> None:
    lines = ["line 1", "line 2", "line 3"]
    indented_lines = indent_lines(lines)
    assert indented_lines == ["    line 1", "    line 2", "    line 3"]
    assert indent_lines(indented_lines, -4) == lines
    assert indent_lines(lines, 0) == lines


def test_extract_iter() -> None:
    ## Note: test cases are clean e.g. we expect: for ... in ... :
    number_of_indents = 4
    test_case = " " * number_of_indents + "for ... in ...:"
    assert (
        extract_iter(test_case, number_of_indents)
        == test_case[:-4] + "locals()['.%s']:" % number_of_indents
    )


def test_iter_adjust() -> None:
    indents = 4
    create_case = lambda test_case: [
        " " * indents + "%s i in range(3):" % test_case,
        " " * (indents + 4) + "return i",
    ]
    assert iter_adjust(create_case("for")) == (
        True,
        [
            " " * indents + "%s i in locals()['.%s']:" % ("for", indents),
            " " * (indents + 4) + "return i",
        ],
    )
    assert iter_adjust(create_case("while")) == (False, create_case("while"))


def test_skip_blocks() -> None:
    blocks = [
        "    if True:",
        "        return 1",
        "    elif True:",
        "        return 2",
        "    else:",
        "        return 3",
        "    for i in range(3):",
        "        return 4",
        "    while True:",
        "        return 5",
        "    print('hi')",
    ]
    for shift in range(6, len(blocks)):
        line_iter = enumerate(blocks[shift:])
        print(skip_blocks([], line_iter, shift, blocks[shift]))


def test_loop_adjust() -> None:
    pass


def test_has_node() -> None:
    pass


def test_send_adjust() -> None:
    pass


def test_get_loops() -> None:
    assert get_loops(3, [(1, 5), (2, 4), (6, 8)]) == [(0, 4), (1, 3)]


def test_expr_getsource() -> None:
    pass


def test_extract_genexpr() -> None:
    source = "iter1, iter2 = (i for i in range(3)), (j for j in (i for i in range(3)) if j in (i for i in range(3)) )"
    pos = [(15, 36), (38,)]
    for iterator in extract_genexpr(source):
        assert iterator == source[slice(*pos.pop(0))]


def test_extract_lambda() -> None:
    pass


def test_except_adjust() -> None:
    result = except_adjust(
        ["try:", "    pass"],
        ["return value", "locals()['.args'] += [locals()['.send']]"],
        "except locals()['.args'].pop():",
    )
    answer = """try:
    try:
        pass
    except:
        locals()['.error'] = exc_info()[1]
        return value
        locals()['.args'] += [locals()['.send']]
        raise locals()['.error']
except locals()['.args'].pop():"""
    assert "\n".join(result) == answer


def test_collect_string_with_fstring() -> None:
    pass


def test_collect_multiline_string_with_fstring() -> None:
    pass


def test_string_collector_proxy_with_fstring() -> None:
    pass


## Note: commented out tests are not working yet ##
## normal case tests ##
test_depth()
test_get_indent()
# test_lineno_adjust()
# test_unpack_genexpr()
test_skip_line_continuation()
test_skip_source_definition()
test_collect_string()
test_collect_multiline_string()
test_string_collector_proxy()
# test_update_lines() ------ not finished
# test_unwrap()
# test_unpack()
# test_unpack_fstring()
test_collect_definition()
test_skip()
test_is_alternative_statement()
test_is_definition()
test_skip_alternative_statements()
# test_control_flow_adjust()
test_indent_lines()
test_extract_iter()
test_iter_adjust()
# test_skip_blocks()
# test_loop_adjust()
test_get_loops()
# test_expr_getsource()
# test_extract_genexpr()
# test_extract_lambda()
test_except_adjust()
## special case tests ##
# test_collect_string_with_fstring()
# test_collect_multiline_string_with_fstring()
# test_string_collector_proxy_with_fstring()
