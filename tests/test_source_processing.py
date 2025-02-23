from gcopy.source_processing import *
from types import FunctionType


def assert_cases(FUNC: FunctionType, *args, compare: list = []) -> None:
    if compare:
        for arg in args:
            assert FUNC(arg) == compare.pop(0)
        return
    for arg in args:
        assert FUNC(arg)


def test_update_depth() -> None:
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


def test_line_adjust() -> None:
    ## adjusted ##
    assert line_adjust("for i in ... if ...", []) == ("... ", ["for i in ... if:"])
    ## not adjusted ##
    assert line_adjust("i if ... else ...", [], False) == ("", ["i if ... else ..."])
    assert line_adjust(" ...", [], False) == ("", ["..."])


def test_unpack_genexpr() -> None:
    """
    Note: line_adjust is tested within this test
    """

    assert unpack_genexpr("(i for\\i in range(3))") == [
        "    for i in range(3):",
        "        return i",
    ]
    assert unpack_genexpr("(i for i in range(3) for j in range(5))") == [
        "    for i in range(3):",
        "        for j in range(5):",
        "            return i",
    ]
    assert unpack_genexpr("(i for i in range(3) for j in range(5) if i==True)") == [
        "    for i in range(3):",
        "        for j in range(5):",
        "            if i==True:",
        "                return i",
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


def test(source: str, f_string: bool = False) -> tuple[Iterable, str, str]:
    """for setting up the string collector tests"""
    source_iter = enumerate(source)
    for i in range(1 + f_string):
        index, char = next(source_iter)
    return source_iter, char, source


def test_collect_string() -> None:

    ## normal string ##

    source_iter, char, source = test('"""hello world"""')
    assert collect_string(source_iter, char, source) == (1, ['""'])
    next(source_iter)
    assert collect_string(source_iter, char, source) == (14, ['"hello world"'])
    next(source_iter)
    assert collect_string(source_iter, char, source) == (16, ['""'])

    ## f-string ##

    # single bracket #
    source_iter, char, source = test('f"asdf{(yield 3)}" -----', True)
    assert collect_string(source_iter, char, source) == (
        17,
        [
            "return  3",
            "locals()['.args'] += [locals()['.send']]",
            "\"asdf{locals()['.args'].pop(0)}\"",
        ],
    )
    # double bracket #
    source_iter, char, source = test('f"asdf{{(yield 3)}}"', True)
    assert collect_string(source_iter, char, source) == (19, ['"asdf{{(yield 3)}}"'])


def test_collect_multiline_string() -> None:
    source_iter, char, source = test('"""hello world"""')
    assert collect_multiline_string(source_iter, char, source) == (
        len(source) - 1,
        [source],
    )

    ## f-string ##

    # single bracket #
    source_iter, char, source = test('f"""hello {(yield 3)} world"""', True)
    assert collect_multiline_string(source_iter, char, source) == (
        29,
        [
            "return  3",
            "locals()['.args'] += [locals()['.send']]",
            '"""hello {locals()[\'.args\'].pop(0)} world"""',
        ],
    )
    # double bracket #
    source_iter, char, source = test('f"""hello {{(yield 3)}} world"""', True)
    assert collect_multiline_string(source_iter, char, source) == (
        31,
        ['"""hello {{(yield 3)}} world"""'],
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


def test_inverse_bracket():
    compare = list("([{}])")
    assert_cases(inverse_bracket, *compare[:3], compare=compare[3:][::-1])


def test_unpack() -> None:
    """
    Note:

    unpack_adjust
    update_lines
    named_adjust

    may not all be separately tested as independent testable
    units since they are tied closely in with the unpack
    function using it in recursion, therefore, these will
    get tested along with the unpack function.
    """

    test = lambda line: unpack("", enumerate(line))

    ## unpacking ##

    # general unpacking #
    assert test("a = yield 3 *= 5 == 5") == (
        ["return 3", "locals()['.args'] += [locals()['.send']]"],
        "a =locals()['.args'].pop(0)*= 5 == 5",
        20,
    )

    # tuple unpacking #
    assert test("a = (yield 3),(yield 5),(yield 7) = 5") == (
        [
            "return  3",
            "locals()['.args'] += [locals()['.send']]",
            "locals()['.args'] += [locals()['.args'].pop(0)]",
            "return  5",
            "locals()['.args'] += [locals()['.send']]",
            "locals()['.args'] += [locals()['.args'].pop(0)]",
            "return  7",
            "locals()['.args'] += [locals()['.send']]",
            "locals()['.args'] += [locals()['.args'].pop(0)]",
        ],
        "a =locals()['.args'].pop(0),locals()['.args'].pop(0),locals()['.args'].pop(0)= 5",
        36,
    )

    ## unwrapping ##

    assert test("(yield 3)") == (
        ["return  3", "locals()['.args'] += [locals()['.send']]"],
        "locals()['.args'].pop(0)",
        5,
    )

    assert test("(yield 3,(yield 5))") == (
        [
            "return  5",
            "locals()['.args'] += [locals()['.send']]",
            "return  3,locals()['.args'].pop(0)",
            "locals()['.args'] += [locals()['.send']]",
        ],
        "locals()['.args'].pop(0)",
        5,
    )

    assert test("a = yield (     yield    (yield 3 )  ) = 5") == (
        [
            "return  3",
            "locals()['.args'] += [locals()['.send']]",
            "return  locals()['.args'].pop(0)",
            "locals()['.args'] += [locals()['.send']]",
            "return locals()['.args'].pop(0)",
            "locals()['.args'] += [locals()['.send']]",
        ],
        "a =locals()['.args'].pop(0)= 5",
        41,
    )

    assert test("(yield 3),(yield (yield 3))") == (
        [
            "return  3",
            "locals()['.args'] += [locals()['.send']]",
            "locals()['.args'] += [locals()['.args'].pop(0)]",
            "return  3",
            "locals()['.args'] += [locals()['.send']]",
            "return  locals()['.args'].pop(0)",  ## should be -1 ##
            "locals()['.args'] += [locals()['.send']]",
        ],
        "locals()['.args'].pop(0),locals()['.args'].pop(0)",
        15,
    )

    ## with named expression ##

    assert test("a = (b:=(c:=next(j)) ) = 5") == ([], "a = (b:=(c:=next(j)) ) = 5", 6)

    assert test("a = (b:=next(j) ) = 5") == ([], "a = (b:=next(j) ) = 5", 20)

    assert test("a = (b:=(yield 3) +a) = 5") == (
        ["return  3", "locals()['.args'] += [locals()['.send']]"],
        "a = (b:=locals()['.args'].pop(0) +a) = 5",
        24,
    )

    ## f-string ##

    assert test("a = f'hi{(yield 3)}' = yield 3 = 5") == (
        [
            "return  3",
            "locals()['.args'] += [locals()['.send']]",
            "locals()['.args'] += [f'hi{locals()['.args'].pop(0)}']",
            "return 3",
            "locals()['.args'] += [locals()['.send']]",
        ],
        "a =locals()['.args'].pop(0)=locals()['.args'].pop(0)= 5",
        33,
    )

    ## needs fixing ##
    assert test("a = f'hi{(yield 3),(yield (yield 3))}' = yield 3 = 5") == (
        [
            "return  3",
            "locals()['.args'] += [locals()['.send']]",
            "locals()['.args'] += [locals()['.args'].pop(0)]",
            "return  3",
            "locals()['.args'] += [locals()['.send']]",
            "return  locals()['.args'].pop(0)",  ### should be -1 ###
            "locals()['.args'] += [locals()['.send']]",
            "locals()['.args'] += [f'hi{locals()['.args'].pop(0),locals()['.args'].pop(0)}']",
            "return 3",
            "locals()['.args'] += [locals()['.send']]",
        ],
        "a =locals()['.args'].pop(0)=locals()['.args'].pop(0)= 5",
        51,
    )

    ## with dictionary assignment ##
    assert test(
        "a = locals()['a'+next(j)] = 'hi '+'hi{(yield 3)} (yield 3)' = yield 3 = 5 = "
    ) == (
        [
            "locals()['.args'] += ['a']",
            "locals()['.args'] += [locals()[locals()['.args'].pop(0)+next(j)]]",
            "locals()['.args'] += ['hi ']",
            "locals()['.args'] += ['hi{(yield 3)} (yield 3)']",
            "return 3",
            "locals()['.args'] += [locals()['.send']]",
        ],
        "a =locals()['.args'].pop(0)=locals()['.args'].pop(0)+locals()['.args'].pop(0)=locals()['.args'].pop(0)= 5 = ",
        75,
    )


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


def test_is_loop() -> None:
    assert_cases(is_loop, "for ", "while ")


def test_is_alternative_statement() -> None:
    assert_cases(is_alternative_statement, "elif:", "else:")
    if (3, 10) <= version_info:
        assert_cases(is_alternative_statement, "case:", "default:")


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
        "    match ...:",
        "        case ...:",
        "            if True:",
        "                0",
        "            elif True:",
        "                1",
        "            else:",
        "                2",
        "            try:",
        "                3",
        "            except:",
        "                4",
        "        case ...:",
        "            5",
        "        default:",
        "            6",
    ]
    ## the loop ##
    end_pos = len(blocks)
    test = lambda start_pos: control_flow_adjust(
        blocks[start_pos:], list(range(start_pos + 1, end_pos))
    )
    assert test(0) == (blocks, list(range(1, end_pos)))
    assert test(2) == (indent_lines(blocks[2:12], -8), list(range(3, 13)))
    temp = lambda index: (
        [blocks[index][12:]] + indent_lines(blocks[8:12], -8),
        [index + 1] + list(range(9, 16)),
    )
    for i in range(3, 13, 2):
        assert test(3) == temp(3)
    assert test(13) == ([blocks[13][8:]], [13 + 1])
    assert test(15) == ([blocks[15][8:]], [])


def test_indent_lines() -> None:
    lines = ["line 1", "line 2", "line 3"]
    indented_lines = indent_lines(lines)
    assert indented_lines == ["    line 1", "    line 2", "    line 3"]
    assert indent_lines(indented_lines, -4) == lines
    assert indent_lines(lines, 0) == lines


def test_iter_adjust() -> None:
    indents = 4
    test = lambda test_case: (" " * indents + "%s i in range(3):" % test_case, indents)
    assert iter_adjust(*test("for")) == "    for i in locals()['.4']:"
    assert iter_adjust(*test("while")) == "    while i in locals()['.4']:"


def test_is_statement() -> None:
    assert is_statement("continue", "continue")
    assert is_statement("continue\\", "continue") == False
    assert is_statement("continued", "continue") == False


def test_skip_blocks() -> None:
    blocks = [
        "    for i in range(3):",
        "        0",
        "    while True:",
        "        1",
        "    def func():",
        "        2",
        "    async def func():",
        "        3",
        "    class func:",
        "        4",
        "    async class func:",
        "        5",
    ]
    length = len(blocks)
    for shift in range(0, length, 2):
        line_iter = enumerate(blocks[shift:])
        index, line = next(line_iter)
        assert skip_blocks([], line_iter, index, line) == (
            indent_lines(blocks[shift:], -4),
            None,
            None,
        )


def test_loop_adjust() -> None:
    block = [
        "    for i in range(3):",
        "        for j in range(5):",
        "            continue",
        "            break",
        "            while True:",
        "                pass",
        "            def func():",
        "                pass",
        "            for k in range(7):",
        "                pass",
        "            print('hi')",
    ]
    length = len(block)
    indexes = list(range(1, length + 1))
    ## adjustments ##
    assert loop_adjust(block[2:], indexes, block[1:], *(1, length)) == (
        [
            "    locals()['.continue']=True",
            "    for _ in (None,):",
            "        break",
            "        locals()['.continue']=False",
            "        break",
            "        while True:",
            "            pass",
            "        def func():",
            "            pass",
            "        for k in range(7):",
            "            pass",
            "    if locals()['.continue']:",
            "        for j in locals()['.8']:",
            "            continue",
            "            break",
            "            while True:",
            "                pass",
            "            def func():",
            "                pass",
            "            for k in range(7):",
            "                pass",
            "            print('hi')",
        ],
        [2, 2, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 2, 1, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    )
    ## no adjustments ##
    assert loop_adjust(block[6:], indexes, block[1:], *(1, length)) == (
        [
            "    def func():",
            "        pass",
            "    for k in range(7):",
            "        pass",
            "    print('hi')",
            "    for j in locals()['.8']:",
            "        continue",
            "        break",
            "        while True:",
            "            pass",
            "        def func():",
            "            pass",
            "        for k in range(7):",
            "            pass",
            "        print('hi')",
        ],
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    )


def test_yield_adjust() -> None:

    assert yield_adjust("yield 3", "") == ["return 3"]

    assert yield_adjust("yield from range(3)", "") == [
        "locals()['.yieldfrom']=range(3)",
        "for locals()['.i'] in locals()['.yieldfrom']:",
        "    return locals()['.i']",
    ]


def test_get_loops() -> None:
    assert get_loops(3, [(1, 5), (2, 4), (6, 8)]) == [(0, 4), (1, 3)]


def test_extract_source_from_positions() -> None:
    ## genexpr extractor ##
    code_obj = eval("(i for i \\\n   in range(3))").gi_code
    source = "iter1, iter2 = (i for i in range(3)), (j for j in (i for i in range(5)) if j in (i for i in range(2)) )"
    assert extract_source_from_positions(code_obj, source) == "(i for i in range(3))"
    ## lambda extractor ##
    code_obj = eval("lambda x: print('hi')").__code__
    source = "lambda x:x,lambda y:lambda z:z, lambda a:a, lambda x: print('hi')"
    assert extract_source_from_positions(code_obj, source) == "lambda x: print('hi')"


def test_extract_source_from_comparison() -> None:
    ## genexpr extractor ##
    code_obj = eval("(i for i \\\n   in range(3))").gi_code
    source = "iter1, iter2 = (i for i in range(3)), (j for j in (i for i in range(5)) if j in (i for i in range(2)) )"
    assert (
        extract_source_from_comparison(code_obj, source, extract_genexpr)
        == "(i for i in range(3))"
    )
    ## lambda extractor ##
    code_obj = eval("lambda x: print('hi')").__code__
    source = "lambda x:x,lambda y:lambda z:z, lambda a:a, lambda x: print('hi')"
    assert (
        extract_source_from_comparison(code_obj, source, extract_lambda)
        == "lambda x: print('hi')"
    )


def test_expr_getsource() -> None:
    for FUNC in (eval("(i for i \\\n   in range(3))"), eval("lambda x: print('hi')")):
        print(expr_getsource(FUNC))


def test_extract_genexpr() -> None:
    source = "iter1, iter2 = (i for i in range(3)), (j for j in (i for i in range(5)) if j in (i for i in range(2)) )"
    pos = [(15, 36), (50, 71), (80, 101), (38, 103)]
    for offsets in extract_genexpr(source):
        assert offsets == pos.pop(0)


def test_extract_lambda() -> None:
    source = "lambda x:x,lambda y:lambda z:z, lambda a:a"
    pos = [(0, 10), (20, 30), (11, 30), (32, None)]
    for offsets in extract_lambda(source):
        assert offsets == pos.pop(0)


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


def test_singly_space() -> None:
    line, source, indented, space = "    for i in [1    , 3  , 5]:  ", "", False, -1
    for index, char in enumerate(line):
        if char == " ":
            source, index, indented = singly_space(index, char, source, space, indented)
            space = index
        else:
            source += char

    assert source == "    for i in [1 , 3 , 5]: "


## Note: commented out tests are not working yet ##
test_update_depth()
test_get_indent()
# test_lineno_adjust()            ## needs checking ##
test_line_adjust()
## is tested in unpack_genexpr: update_line
test_unpack_genexpr()
test_skip_line_continuation()
test_skip_source_definition()
test_collect_string()
test_collect_multiline_string()
test_string_collector_proxy()
test_inverse_bracket()
## are tested in test_unpack: named_adjust, unpack_adjust, update_lines
test_unpack()  ## need to fix the ordering of popping ##
test_collect_definition()
test_is_alternative_statement()
test_is_loop()
test_is_definition()
test_skip_alternative_statements()
test_control_flow_adjust()
test_indent_lines()
test_iter_adjust()
test_is_statement()
test_skip_blocks()
test_loop_adjust()  ## need to check indexes ##
test_yield_adjust()
test_get_loops()
# test_extract_source_from_positions()
test_extract_source_from_comparison()
# test_expr_getsource()
test_extract_genexpr()
test_extract_lambda()
test_except_adjust()
test_singly_space()
