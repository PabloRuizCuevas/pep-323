# -*- coding: utf-8 -*- 
"""
License:

MIT License

Copyright (c) 2025 Benj1bear

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

------------------------------------------------------------------------------------

In order to make this module as backwards compatible as possible 
some of the functions used will be written out manually and a 
preprocessor or otherwise condition statement will go over what 
changes will be made if any

Backwards compatibility notes of relevance at the moment:

reference for versions not available on the 
cpython github repo or as an alternative for 
where documentation is lacking: https://hg.python.org/cpython/file/2.2

(2.2 since this is when generators were introduced)

For python 2:

 - classes are not automatically inherited from object
   and therefore you have to do this explicitly
 
 - you need to add a comment specifying an encoding at 
   the the first line of the file

 - range returns a list (use xrange instead)

 - type annotations and the typing module were introduced in python 3.5

 - f-strings were introduced in python 3.6 (use i.e. "%s" % ... instead)
 
 - builtin function 'next' was introduced in 2.6

 - dedent from textwrap module and get_history_item were introduced in 2.3

 - before version 3.0 __bool__ was __nonzero__

 - dis.get_instructions was introduced in 3.4

 - CodeType.co_positions was introduced in 3.11

 - Asynchronous generators were introduced in 3.6

 - ternary conditionals were introduced in python 2.5

 - match case default statements where introduced in python 3.10
"""

from types import FunctionType,GeneratorType
from inspect import getsource,currentframe,findsource,getframeinfo
from copy import deepcopy,copy
from sys import version_info

## minium version supported ##
if version_info < (2,2):
    raise ImportError("""Python version 2.2 or above is required.

Note:

Python version 2.2 is when PEP 255 and 234 were implemented ('Simple Generators' and 'iterators') to the extent they
were implemented allowing for function generators with the 'yield' keyword and iterators. Version 2.4 introduced 
Generator expressions. Therefore, this python module/library is only useful for python versions 2.2 and above.
""")

if version_info < (2,4):
    from warnings import warn
    warn("Python version 2.4 or above is required for generator expressions",UserWarning)

#########################
### utility functions ###
#########################

if version_info < (2,3):
    from warnings import warn
    warn("Python version 2.3 or above is required for get_history_item for usage on CLIs",UserWarning)
    
    def is_cli():
        return False
    
    def enumerate(gen,start=0):
        """Enumerates a generator/iterator"""
        for i in gen:
            yield start,i
            start+=1
else:
    from readline import get_history_item

    def is_cli():
        """Determines if using get_history_item is possible e.g. for CLIs"""
        try:
            get_history_item(0)
            return True
        except IndexError:
            return False

if version_info < (3,):
    range = xrange

if version_info < (3,4):
    def get_instructions(code_obj):
        """Returns a generator of the instructions used by a given code object"""
        pass
else:
    from dis import get_instructions

if version_info < (2,6):
    def next(iter_val,*args):
        """
        Return the next item from the iterator. If default is given and 
        the iterator is exhausted, it is returned instead of raising StopIteration.
        """
        if len(args) > 1:
            raise TypeError("next expected at most 2 arguments, got %s" % len(args))
        if args:
            try:
                return iter_val.next()
            except StopIteration:
                return args[0]
        return iter_val.next()

if version_info < (3,11):
    def get_col_offset(frame):
        lasti=frame.f_lasti
        for instruction in get_instructions(frame.f_code):
            if instruction.offset==lasti:
                return instruction.positions.col_offset
        raise ValueError("f_lasti not encountered")
else:
    ## make an attr dict out of the tuple ##
    def get_col_offset(frame):
        return getframeinfo(frame).positions.col_offset

def empty_generator():
    """Creates a simple empty generator"""
    return
    yield

def dedent(text):
    """
    simplified version of dedent from textwrap that 
    removes purely whitespace indentation from a string
    to the minimum indentation

    If you have python version 2.3 or higher you can use
    textwrap.dedent but I've decided to make an implementation
    specific version for python 2.2 and it should ideally be 
    faster for its specific use case
    """
    ## because I'm only using this for functions source code ##
    ## we can use the indent from the first line as the ##
    ## minimum indent and remove unnecessary whitespace ##
    indent=get_indent(text)
    if indent==0:
        return text
    text_iter,line,dedented,text=enumerate(text),-1,False,""
    for index,char in text_iter:
        ## dedent the current line ##
        if not dedented:
            while char==" ":
                if not index-prev_split <= indent:
                    line=""
                    break
                line+=char
                index,char=next(text_iter)
            dedented=True
        ## collect the current line ##
        if char=="\n":
            prev_split,dedented=index,False
            if line.isspace(): ## remove unnecessary whitespace ##
                line=""
            text+=line+"\n"
            line=""
        ## gather the chars ##
        else:
            line+=char
    ## add the last line if it exists ##
    if line:
        text+=line
    return text

def get_indent(line):
    """Gets the number of spaces used in an indentation"""
    count=0
    for char in line:
        if char!=" ":
            break
        count+=1
    return count

def lineno_adjust(FUNC,frame=None):
    """
    unpacks a line of compound statements
    into lines up to the last instruction 
    that determines the adjustment required
    """
    if frame is None:
        frame=getframe(FUNC)
    line,current_lineno,instructions=[],frame.f_lineno,get_instructions(frame.f_code)
    ## get the instructions at the lineno ##
    for instruction in instructions:
        lineno,obj=instruction.positions.lineno,(list(instruction.positions[2:]),instruction.offset)
        if not None in obj[0] and lineno==current_lineno:
            ## get the lines ##
            line=[obj]
            for instruction in instructions:
                lineno,obj=instruction.positions.lineno,(list(instruction.positions[2:]),instruction.offset)
                if lineno!=current_lineno:
                    break
                line+=[obj]
            break
    ## add the lines
    if line:
        index,current,lasti=0,[0,0],frame.f_lasti
        for pos,offset in line.sort():
            if offset==lasti:
                return index
            if pos[0] > current[1]: ## independence ##
                current=pos
                index+=1
            elif pos[1] > current[1]: ## intersection ##
                current[1]=pos[1]
    raise ValueError("f_lasti not encountered")

def unpack_genexpr(source):
    """unpacks a generator expressions' for loops into a list of source lines"""
    lines,line,ID,depth,prev,has_for,has_end_if=[],"","",0,(0,""),False,False
    source_iter=enumerate(source[1:-1])
    for index,char in source_iter:
        if char in "\\\n":
            continue
        ## collect strings
        if char=="'" or char=='"':
            if prev[0]-1==index and char==prev[1]:
                string_collector=collect_multiline_string
            else:
                string_collector=collect_string
            index,temp_line=string_collector(source_iter,char)
            prev=(index,char)
            line+=temp_line
            continue
        if char=="(": ## we're only interested in when the generator expression ends in terms of the depth ##
            depth+=1
        elif char==")":
            depth-=1
        ## accumulate the current line
        line+=char
        ## collect IDs
        if char.isalnum():
            ID+=char
        else:
            ID=""
        if depth==0:
            if ID == "for" or ID == "if" and next(source_iter)[1] == " ":
                if ID =="for":
                    lines+=[line[:-3]]
                    line=line[-3:]#+" "
                    if not has_for:
                        has_for=len(lines) ## should be 1 anyway
                elif has_for:
                    lines+=[line[:-2],source[index:-1]] ## -1 to remove the end bracket - is this necessary?
                    has_end_if=True
                    break
                else:
                    lines+=[line[:-2]]
                    line=line[-2:]+" "
                # ID="" ## isn't necessary because you don't get i.e. 'for for' or 'if if' in python syntax
    if has_end_if:
        lines=lines[has_for:-1]+(lines[:has_for]+[lines[-1]])[::-1]
    else:
        lines=lines[has_for:]+(lines[:has_for])[::-1]
    ## arrange into lines
    indent=" "*4
    return [indent*index+line for index,line in enumerate(lines,start=1)]

################
### tracking ###
################

def track_iter(obj):
    """
    Tracks an iterator in the local scope initiated by a for loop
    
    This function has a specific use case where the initialization
    of an iterator via a for loop implictely does not allow for 
    reliable extraction from the garbage collector and thus manually
    assigning the iterator for tracking is used

    Note: variables are signified as '.%s' % number_of_indents
    i.e.
        for i in range(3) is 4 indents and thus is assigned '.4'
    
    This way makes it more effective to retrieve the iterator
    rather than appending iterators. This means only numbers
    that are divisble by 4 should not be used in general usage
    by users.

    Using in generator expressions uses the col_offset instead
    """
    obj=iter(obj)
    frame=currentframe().f_back
    if frame.f_code.co_name=="<genexpr>":
        key="%s.%s" % (frame.f_lineno,get_col_offset(frame)) ## add the lineno since the offset could be anywhere and might override the indents that haven't finished ##
    else:
        if is_cli():
            code_context=get_history_item(-frame.f_lineno)
        else:
            code_context=getframeinfo(frame).code_context[0]
        key=get_indent(code_context)
        ## won't work for compound statements that are in block statements ##
        ## therefore, we check for a block statement and add 4 if so ##
        temp=code_context[key:]
        if (temp.startswith("if ") or temp.startswith("for ") or \
            temp.startswith("while ") or is_definition(temp)) and lineno_adjust(frame.f_code,frame)==0:
            key+=4
    frame.f_locals[".%s" % key]=obj
    return obj

############################
### cleaning source code ###
############################

def skip_source_definition(source):
    """Skips the function definition and decorators in the source code"""
    ID,source_iter="",enumerate(source)
    for index,char in source_iter:
        ## decorators are ignored ##
        while char=="@":
            while char!="\n":
                index,char=next(source_iter)
            index,char=next(source_iter)
        if char.isalnum():
            ID+=char
            if len(ID)==3:
                if ID=="def" and next(source_iter)[1]==" ":
                    while char!="(":
                        index,char=next(source_iter)
                    break
                return source
        else:
            ID=""
    depth=1
    for index,char in source_iter:
        if char==":" and depth==0:
            return source[index+1:]
        if char in "([{":
            depth+=1
        elif char in ")]}":
            depth-=1
    raise SyntaxError("Unexpected format encountered")


def string_collector_proxy(index,char,prev,iterable,line=None):
    """Proxy function for usage when collecting strings since this block of code gets used repeatedly"""
    if prev[0]+2==prev[1]+1==index and prev[2]==char:
        string_collector=collect_multiline_string
    else:
        string_collector=collect_string
    temp_index,temp_line=string_collector(iterable,char)
    prev=(index,temp_index,char)
    if line is not None:
        line+=temp_line
    return line,prev

def collect_string(source_iter,reference,source=False):
    """
    Collects strings in an iterable assuming correct 
    python syntax and the char before is a qoutation mark
    
    Note: make sure source_iter is an enumerated type
    """
    line,backslash,ID,depth,lines,in_f_string,limit=reference,False,"",0,[],False,-2
    for index,char in source_iter:
        if char==reference and not backslash:
            line+=char
            break
        line+=char
        backslash=False
        if char=="\\":
            backslash=True
        ## detect f-strings for value yields ##
        if source:
            if char=="{":
                if index-1==limit:
                    in_f_string=(in_f_string + 1) % 2
                else:
                    in_f_string=True
                limit=index
            elif in_f_string: ## in an f-string ##
                if char=="(": ## only () will contain a value yield ##
                    depth+=1
                elif char==")":
                    depth-=1
                if char.isalnum():
                    ID+=char
                    if char == "yield":
                        temp_line=value_yield_adjust(source,source_iter,index,limit)
                        line=temp_line.pop()
                        lines+=temp_line
                        in_f_string=False
                else:
                    ID=""
    if source:
        return index,lines+[line]
    return index,line

def collect_multiline_string(source_iter,reference,source=False):
    """
    Collects multiline strings in an iterable assuming 
    correct python syntax and the char before is a 
    qoutation mark
    
    Note: make sure source_iter is an enumerated type
    
    if a string starts with 3 qoutations
    then it's classed as a multistring
    """
    line,backslash,prev,count,ID,depth,lines,in_f_string,limit=reference,False,-2,0,"",0,[],False,-2
    for index,char in source_iter:
        if char==reference and not backslash:
            if index-prev==1:
                count+=1
            else:
                count=0
            prev=index
            if count==2:
                line+=char
                break
        line+=char
        backslash=False
        if char=="\\":
            backslash=True
        ## detect f-strings for value yields ##
        if source:
            if char=="{":
                if index-1==limit:
                    in_f_string=(in_f_string + 1) % 2
                else:
                    in_f_string=True
                limit=index
            elif in_f_string: ## in an f-string ##
                if char=="(": ## only () will contain a value yield ##
                    depth+=1
                elif char==")":
                    depth-=1
                if char.isalnum():
                    ID+=char
                    if char == "yield" and depth==1:
                        temp_line=value_yield_adjust(source[index-len(line):],source_iter,index,limit)
                        line=temp_line.pop()
                        lines+=temp_line
                        in_f_string=False
                else:
                    ID=""
    if source:
        return index,lines+[line]
    return index,line

def collect_definition(line,lines,lineno,source,source_iter,reference_indent,prev):
    """
    Collects a block of code from source, specifically a 
    definition block in the case of this modules use case
    """
    indent=reference_indent+1
    while reference_indent < indent:
        ## we're not specific about formatting the definitions ##
        ## we just need to make sure to include them ##
        for index,char in source_iter:
            ## collect strings ##
            if char=="'" or char=='"':
                line,prev=string_collector_proxy(index,char,prev,source_iter,line)
            ## newline ##
            elif char == "\n":
                break
            else:
                line+=char
        ## add the line and get the indentation to check if continuing ##
        lineno+=1
        lines+=[line]
        line,indent="",get_indent(source[index+1:])
    ## make sure to return the index and char for the indentation ##
    return index,char,lineno,lines

def skip(iter_val,n):
    """Skips the next n iterations in a for loop"""
    for _ in range(n):
        next(iter_val)

## Note: line.startswith("except") will need to put a try statement in front (if it's not there e.g. is less than the minimum indent) ##
## match case default was introduced in python 3.10
if version_info < (3,10):
    def is_alternative_statement(line):
        return line.startswith("elif") or line.startswith("else")
else:
    def is_alternative_statement(line):
        return line.startswith("elif") or line.startswith("else") or line.startswith("case") or line.startswith("default")
is_alternative_statement.__doc__="Checks if a line is an alternative statement"

def is_definition(line):
    """Checks if a line is a definition"""
    return line.startswith("def ") or line.startswith("async def ") or\
           line.startswith("class ") or line.startswith("async class ")

########################
### code adjustments ###
########################
def skip_alternative_statements(line_iter,current_min):
    """Skips all alternative statements for the control flow adjustment"""
    for index,line in line_iter:
        temp_indent=get_indent(line)
        temp_line=line[temp_indent:]
        if temp_indent <= current_min and not is_alternative_statement(temp_line):
            break
    return index,line,temp_indent

def offset_adjust(f_locals):
    """
    Adjusts the track_iter created variables
    used in generator expressions from offset
    based to indentation based

    We have to do this because generator expressions
    can only have offset based trackers whereas
    when we format the source lines it requires
    indentation based

    Note: only needed on the current variables
    in the frame that use offset based trackers
    """
    ## the first offset will probably get in the way ##
    lineno=0 ## every line will increase the indentation by 4 ##
    for key,value in f_locals.items():
        if isinstance(key,str) and key[0]=="." and key[1:].isdigit():
            del f_locals[key]
            lineno+=1
            f_locals[4*lineno]=value
    return f_locals

def control_flow_adjust(lines,indexes,reference_indent=4):
    """
    removes unreachable control flow blocks that 
    will get in the way of the generators state

    Note: it assumes that the line is cleaned,
    in particular, that it starts with an 
    indentation of 4 (4 because we're in a function)

    It will also add 'try:' when there's an
    'except' line on the next minimum indent
    """
    new_lines,current_min=[],get_indent(lines[0])
    line_iter=enumerate(lines)
    for index,line in line_iter:
        temp_indent=get_indent(line)
        temp_line=line[temp_indent:]
        if temp_indent < current_min:
            ## skip over all alternative statements until it's not an alternative statement ##
            ## and the indent is back to the current min ##
            if is_alternative_statement(temp_line):
                end_index,line,temp_indent=skip_alternative_statements(line_iter,temp_indent)
                del indexes[index:end_index]
                index=end_index
            current_min=temp_indent
            if temp_line.startswith("except"):
                new_lines=[" "*4+"try:"]+indent_lines(new_lines)+[line[current_min-4:]]
                indexes=[indexes[0]]+indexes
        ## add the line (adjust if indentation is not reference_indent) ##
        if current_min != reference_indent:
            ## adjust using the current_min until it's the same as reference_indent ##
            new_lines+=[line[current_min-4:]]
        else:
            return new_lines+indent_lines(lines[index:],4-reference_indent),indexes
    return new_lines,indexes

def indent_lines(lines,indent=4):
    """indents a list of strings acting as lines"""
    if indent > 0:
        return [" "*indent+line for line in lines]
    if indent < 0:
        indent=-indent
        return [line[indent:] for line in lines]
    return lines

def extract_iter(line,number_of_indents):
    """
    Extracts the iterator from a for loop
    
    e.g. we extract the second ... in:
    for ... in ...:
    """
    depth,ID,line_iter=0,"",enumerate(line)
    for index,char in line_iter:
        ## the 'in' key word must be avoided in all forms of loop comprehension ##
        if char in "([{":
            depth+=1
        elif char in ")]}":
            depth-=1
        if char.isalnum() and depth==0:
            ID+=char
            if ID=="in":
                if next(line_iter)[1]==" ":
                    break
                ID=""
        else:
            ID=""
    index+=2 ## adjust by 2 to skip the 'n' and ' ' in 'in ' that would've been deduced ##
    iterator=line[index:-1] ## -1 to remove the end colon ##
    ## remove the leading and trailing whitespace and then it should be a variable name ##
    if iterator.strip().isalnum():
        return line
    return line[:index]+"locals()['.%s']:" % number_of_indents

def iter_adjust(outer_loop):
    """adjust an outer loop with its tracked iterator if it uses one"""
    flag,line=False,outer_loop[0]
    number_of_indents=get_indent(line)
    if line[number_of_indents:].startswith("for "):
        outer_loop[0]=extract_iter(line,number_of_indents)
        flag=True
    return flag,outer_loop

def loop_adjust(lines,indexes,outer_loop,*pos):
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
    new_lines,flag,line_iter=[],False,enumerate(lines)
    for index,line in line_iter:
        indent=get_indent(line)
        temp_line=line[indent:]
        ## skip over for/while and definition blocks ##
        while temp_line.startswith("for ") or temp_line.startswith("while ") or is_definition(temp_line):
            for index,line in line_iter:
                temp_indent=get_indent(line)
                if temp_indent <= indent:
                    break
                new_lines+=[line]
            ## continue back ##
            indent=temp_indent
            temp_line=line[indent:]
        if temp_line.startswith("continue"):
            flag=True
            new_lines+=["break"]
        elif temp_line.startswith("break"):
            flag=True
            new_lines+=["locals()['.continue']=False","break"]
            indexes=indexes[index:]+indexes[index]+indexes[:index]
        else:
            new_lines+=[line]
    ## adjust it in case it's an iterator ##
    flag,outer_loop=iter_adjust(outer_loop)
    if flag:
        return ["    locals()['.continue']=True","    for _ in ():"]+indent_lines(new_lines,8-get_indent(new_lines[0]))+\
               ["    if locals()['.continue']:"]+indent_lines(outer_loop,8-get_indent(outer_loop[0])),\
               [indexes[0],indexes[0]]+indexes+[pos[0]]+list(range(*pos))
    return indent_lines(lines,4-get_indent(lines[0]))+indent_lines(outer_loop,4-get_indent(outer_loop[0])),indexes+list(range(*pos))

def has_node(line,node):
    """Checks if a node has starting IDs that match"""
    ID,nodes,checks="",[],node.split()
    for char in line:
        ## no strings allowed ##
        if char=="'" or char=='"':
            return False
        if char.isalnum():
            ID+=char
        elif char==" ":
            if ID:
                nodes+=[ID]
                for node,check in zip(nodes,checks):
                    if node!=check:
                        return False
                if len(nodes)==len(checks):
                    return True
    return False

def send_adjust(line):
    """Checks for variables assigned to yields for making adjustments"""
    parts,flag=line.split("="),0
    for index,node in enumerate(parts):
        node=node[get_indent(node):]
        if has_node(node,"yield from "):
            flag=1
            break
        if has_node(node,"yield "):
            flag=2
            break
    if flag:
        reciever="="
        if flag == 2:
            reciever+="locals()['.send']"
        ## indicator       yield statement            assignments
        return flag,["=".join(parts[index:]),"=".join(parts[:index])+reciever]
    return None,None

def get_loops(lineno,jump_positions):
    """
    returns a list of tuples (start_lineno,end_lineno) for the loop 
    positions in the source code that encapsulate the current lineno
    """
    ## get the outer loops that contian the current lineno ##
    loops=[]
    ## jump_positions are in the form (start_lineno,end_lineno) ##
    for pos in jump_positions: ## importantly we go from start to finish to capture nesting loops ##
        ## make sure the lineno is contained within the position for a ##
        ## loop adjustment and because the jump positions are ordered we ##
        ## can also break when the start lineno is beyond the current lineno ##
        if lineno < pos[0]:
            break
        if lineno < pos[1]:
            loops+=[pos]
    return loops

######################
### expr_getsource ###
######################
def code_attrs():
    """
    all the attrs used by a CodeType object in 
    order of types.CodeType function signature 
    ideally and correct to the current version
    """
    attrs=("co_argcount",)
    if (3,8) <= version_info:
        attrs+=("co_posonlyargcount",)
    attrs+=("co_kwonlyargcount","co_nlocals","co_stacksize","co_flags","co_code",
            "co_consts", "co_names", "co_varnames", "co_filename", "co_name")
    if (3,3) <= version_info:
        attrs+=("co_qualname",)
    attrs+=("co_firstlineno",)
    if (3,10) <= version_info:
        attrs+=("co_linetable",)
    else:
        attrs+=("co_lnotab",)
    if (3,11) <= version_info:
        attrs+=("co_exceptiontable",)
    attrs+=("co_freevars","co_cellvars")
    return attrs

def attr_cmp(obj1,obj2,attrs):
    """Compares two objects by a collection of their attrs"""
    for attr in attrs:
        if getattr(obj1,attr)!=getattr(obj2,attr):
            return False
    return True

def getcode(obj):
    """Gets the code object from an object via commonly used attrs"""
    for attr in ["__code__","gi_code","ag_code","cr_code"]:
        if hasattr(obj,attr):
            return getattr(obj,attr)
    raise AttributeError("code object not found")

def getframe(obj):
    """Gets the frame object from an object via commonly used attrs"""
    for attr in ["gi_frame","ag_frame","cr_frame"]:
        if hasattr(obj,attr):
            return getattr(obj,attr)
    raise AttributeError("frame object not found")

def hasattrs(self,attrs):
    """hasattr check over a collection of attrs"""
    for attr in attrs:
        if not hasattr(self,attr):
            return False
    return True

def expr_getsource(FUNC):
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
    code_obj=getcode(FUNC)
    if code_obj.co_name=="<lambda>":
        ## here source is a : str
        source=getsource(code_obj)
        extractor=extract_lambda
    else:
        lineno=getframe(FUNC).f_lineno-1
        ## here source is a : list[str]
        source=findsource(code_obj)[0][lineno:]
        extractor=extract_genexpr
    ## get the rest of the source ##
    if (3,11) <= version_info:
        # start_line, end_line, start_col, end_col
        positions=code_obj.co_positions()
        is_source_list=isinstance(source,list)
        pos=next(positions,(None,None,None))[1:]
        current_min,current_max=pos[2:]
        if is_source_list:
            current_max_lineno=pos[1]
        for pos in positions:
            if pos[-2] and pos[-2] < current_min:
                current_min=pos[-2]
            if pos[-1] and pos[-1] > current_max:
                current_min=pos[-1]
            if is_source_list and pos[1] and pos[1] > current_max_lineno:
                current_max_lineno=pos[1]
        if is_source_list:
            source="\n".join(source[:current_max_lineno+1])
        return source[current_min:current_max]
    ## otherwise match with generator expressions in the original source to get the source code ##
    attrs=("co_freevars","co_cellvars","co_firstlineno","co_nlocals","co_stacksize","co_flags","co_code","co_consts", "co_names", "co_varnames","co_name")
    if (3,3) <= version_info:
        attrs+=("co_qualname",)
    if isinstance(source,list):
        source="\n".join(source)
    for col_offset,end_col_offset in extractor(source):
        try: ## we need to make it a try-except in case of potential syntax errors towards the end of the line/s ##
            ## eval should be safe here assuming we have correctly extracted the expression - we can't use compile because it gives a different result ##
            temp_code=getcode(eval(source[col_offset:end_col_offset]))
            if attr_cmp(temp_code,code_obj,attrs):
                return source
        except:
            pass
    raise Exception("No matches to the original source code found")
###############
### genexpr ###
###############
def extract_genexpr(source):
    """Extracts each generator expression from a list of the source code lines"""
    ID,is_genexpr,depth,prev="",False,0,(0,0,"")
    source_iter=enumerate(source)
    for index,char in source_iter:
        ## skip all strings if not in genexpr
        if char=="'" or char=='"':
            _,prev=string_collector_proxy(index,char,prev,source_iter,_)
            continue
        ## detect brackets
        elif char=="(":
            temp_col_offset=index
            depth+=1
        elif char==")":
            depth-=1
            if is_genexpr and depth+1==genexpr_depth:
                yield col_offset,index+1
                number_of_expressions+=1
                ID,is_genexpr="",False
            continue
        ## record source code ##
        if depth and not is_genexpr:
            ## record ID ##
            if char.isalnum():
                ID+=char
                ## detect a for loop
                if ID=="for":
                    genexpr_depth,is_genexpr,col_offset=depth,True,temp_col_offset
            else:
                ID=""

##############
### lambda ###
##############
def extract_lambda(source_code):
    """Extracts each lambda expression from the source code string"""
    ID,is_lambda,lambda_depth,prev="",False,0,(0,0,"")
    source_code=enumerate(source_code)
    for index,char in source_code:
        ## skip all strings (we only want the offsets)
        if char=="'" or char=='"':
            _,prev=string_collector_proxy(index,char,prev,source_code)
            continue
        ## detect brackets (lambda can be in all 3 types of brackets) ##
        elif char in "({[":
            depth+=1
        elif char in "]})":
            depth-=1
        ## record source code ##
        if is_lambda:
            if char=="\n;" or (char==")" and depth+1==lambda_depth): # lambda_depth needed in case of brackets; depth+1 since depth would've got reduced by 1
                yield col_offset,index+1
                ID,is_lambda="",False
        else:
            ## record ID ##
            if char.isalnum():
                ID+=char
                ## detect a lambda
                if ID == "lambda" and depth <= 1:
                    lambda_depth,is_lambda,col_offset=depth,True,index-6
            else:
                ID=""
    ## in case of a current match ending ##
    if is_lambda:
        yield col_offset,None

"""
TODO
Needs checking and fixing:

unpack
unpack_adjust
assign_adjust
"""
def unpack(line,index):
    """
    Unpacks value yields from a line into a list of lines
    going towards its right side then the left side since
    the right side will have to be unpacked whereas the left
    side will be adjusted based on how the initial identification
    of value yields occurs
    """
    depth,lines,ID,line,end_index=0,[],"","",0
    line_iter=enumerate(line[index:])
    for end_index,char in line_iter:
        
        ## collect strings and add to the lines ##

        if char=="\\":
            whitespace=get_indent(line[end_index+1:])
            skip(line_iter,whitespace)
            skip(line_iter,get_indent(line[end_index+whitespace+2:]))
            line+=" "
            continue
        if char==",":
            lines+=[line]
        elif depth < 0 or char in ";\n":
            lines+=[line]
            break
        if char=="(":
            depth+=1
        elif char==")":
            depth-=1
        if depth:
            if char.isalnum():
                ID+=char
                if ID=="yield":
                    ## once the right side has been unpacked we collect up the left using unpack_adjust ##
                    temp_lines,offsets=unpack_adjust(unpack(line,end_index))
                    lines+=temp_lines
                    line=line[:offsets[0]]+"locals()['.args'].pop()" ## reduce the line + add the replacement
                    ## udpate the variables
                    line_iter=enumerate(line[offsets[1]:])
                    end_index+=offsets[1]-index
            else:
                ID=""
        else:
            line+=char
    return lines,(index,end_index)

def extract_id(line_iter):
    """Extracts a variable name from a line"""
    line=""
    for index,char in line_iter:
        if not char.isalnum():
            break
        line+=char
    return line,index,char

def assign_adjust(line,line_iter,reference_index):
    """
    Adjusts assignments made in a line containing value yields
    i.e. possible cases:
    # a=(b:=next(j))=c=(d:=3)=f,(yield next(j))

    # a=(b:=next(j))
    # b=c=(d:=3)
    # ...
    # d=...

    ## 1.

    # k=f,(yield next(j))
    # a=(b:=next(j))=k
    
    ## named expressions pass
    # a=b=next(j)
    # ...
    # b=...

    ## You can't have functions in assignment, but you can have dictionary like assignments from functions
    # func()[next(j)]=k

    ## function dictionary assignments
    # locals()[".args"].append(func())
    # locals()[".args"].append(next(j))
    # ...
    # locals()[".args"].pop()[locals()[".args"].pop()]=...
    """
    ## split by equals sign, sort out the dictionary assignments ##
    depth,line,lines,in_key,in_dict,name,prev=0,"",[],None,None,"",(0,0,"")
    for index,char in line_iter:
        ## collect strings ##
        if char=="'" or char=='"':
            ## get the string collector type ##
            line,prev=string_collector_proxy(index,char,prev,line_iter,line)
            continue
        if char=="[" and depth==in_key:
            in_dict=depth
            in_key=None
        elif char=="(" and in_dict==depth-1:
            in_dict=None
            line,index,char=extract_id(line_iter)
        if char=="=":
            if depth:
                lines+=[line]
            else:
                ## named expression ##
                name,index,char=extract_id(line_iter)
        if char == "(":
            depth+=1
        elif char == ")":
            depth-=1
        if char == "]" and depth: ## must be a dictionary assignment ##
            in_key=depth
        line+=char
    return lines

def unpack_adjust(line,offsets):
    """adjusts the left side of the line containing a value yield to ensure that it works correctly"""
    ## left - will not contain any value yields therefore is simply collecting the remaining items ##
    ## it should break when it encounters an '=' with depth 0
    depth,col_offset=0
    line_iter=enumerate(line[:offsets[0]][::-1])
    for col_offset,char in line_iter:
        ## collect strings ##
        if char=="'" or char=='"':
            ## get the string collector type ##
            line,prev=string_collector_proxy(col_offset,char,prev,line_iter,line)
            continue
        if char == ",":
            lines+=[line]
            break
        if char=="(":
            depth+=1
        elif char==")":
            depth-=1
        if (char == "=" and depth == 0) or depth > 1: ## how to skip ':=' ??
            return assign_adjust(line,line_iter,offsets[0])+[line]+lines,(col_offset,offsets[1])
        line+=char
    return [line]+lines,(col_offset,offsets[1])

def value_yield_adjust(line,source_iter=None,index=None):
    """
    adjusts the current line for value yields
    
    1. Extracts the segment
    2. makes back new lines
    3. replaces the segment
    4. skips the iterable
    5. gives back new lines
    """
    lines,offsets=unpack_adjust(unpack(line,index))
    if source_iter:
        skip(source_iter,offsets[1])
    ## unpack the changes into their places ##
    return lines+[line[offsets[0]:]+",".join(["locals()['.args].pop(0)" for i in lines])]

########################
### pickling/copying ###
########################
class Pickler(object):
    """
    class for allowing general copying and pickling of 
    some otherwise uncopyable or unpicklable objects
    """
    _not_allowed=tuple()

    def _copier(self,FUNC):
        """copying will create a new generator object but the copier will determine its depth"""
        obj=type(self)()
        obj.__setstate__(obj.__getstate__(obj,FUNC))
        return obj

    ## for copying ##
    def __copy__(self):
        return self._copier(copy)

    def __deepcopy__(self,memo):
        return self._copier(deepcopy)
    ## for pickling ##
    def __getstate__(self,FUNC=lambda x:x):
        """Serializing pickle (what object you want serialized)"""
        dct=dict()
        for attr in self._attrs:
            if hasattr(self,attr) and not attr in self._not_allowed:
                dct[attr]=FUNC(getattr(self,attr))
        return dct

    def __setstate__(self,state):
        """Deserializing pickle (returns an instance of the object with state)"""
        for key,value in state.items():
            setattr(self,key,value)

class frame(Pickler):
    """
    acts as the initial FrameType
    
    Note: on pickling ensure f_locals 
    and f_back can be pickled
    """
    _attrs=('f_back','f_code','f_lasti','f_lineno','f_locals',
            'f_trace','f_trace_lines','f_trace_opcodes')
    _not_allowed=("f_globals",)
    f_locals={}
    f_lineno=1
    f_globals=globals()
    f_builtins=__builtins__

    def __init__(self,frame=None):
        if frame:
            if hasattr(frame,"f_back"): ## make sure all other frames are the custom type as well ##
                self.f_back=type(self)(frame.f_back)
            if hasattr(frame,"f_code"): ## make sure it can be pickled
                self.f_code=code(frame.f_code)
            for attr in self._attrs[2:]:
                setattr(self,attr,getattr(frame,attr))
    
    def clear(self):
        """clears f_locals e.g. 'most references held by the frame'"""
        self.f_locals={}
    
    ## we have to implement this if I'm going to go 'if frame:' (i.e. in frame.__init__) ##
    def __bool__(self):
        """Used on i.e. if frame:"""
        return hasattrs(self,('f_code','f_lasti','f_lineno','f_locals'))

    if version_info < (3,0):
        __nonzero__=__bool__

class code(Pickler):
    """For pickling and copying code objects"""

    _attrs=code_attrs()

    def __init__(self,code_obj=None):
        if code_obj:
            for attr in self._attrs:
                setattr(self,attr,getattr(code_obj,attr))

    def __bool__(self):
        """Used on i.e. if code_obj:"""
        return hasattrs(self,self._attrs)

    if version_info < (3,0):
        __nonzero__=__bool__

#################
### Generator ###
#################
"""
TODO:

1. general testing and fixing to make sure everything works before any more changes are made

    Finish fixing:
     - unpack
     - unpack_adjust
     - assign_adjust

    Needs checking:

    - check overwrite in __init__

    - check track_iter since it now uses the line as well as the offset

    - check that the returns work now e.g. using next(self) and for i in self: ...
    
    - check .send on generator expressions and in general for those that don't use it

    - check lineno_adjust to ensure that it's robust, not sure if it works in all cases.
      It relies on a single line containing all the code, it might be possible that you
      can have multiple independent expressions in one line but I haven't checked. -
      This function is only to help with users that choose to use compound statements.

    format errors
    - maybe edit or add to the exception traceback in __next__ so that the file and line number are correct
    - with throw, extract the first line from self._internals["state"] (for cpython) and then create an exception traceback out of that
    (if wanting to port onto jupyter notebook you'd use the entire self._internals["source_lines"] and then point to the lineno)

    -----------------------------------------------
    Backwards compatibility:
    -----------------------------------------------
    - finish get_instructions - make sure the positions and offsets are correct
      - used to get the current col_offset for track_iter on genexprs + for lineno_adjust
    -----------------------------------------------
 
    Add some async features to AsyncGenerator

2. write tests

control_flow_adjust - test to see if except does get included as a first line of a state (it shouldn't)
need to test what happens when there are no lines e.g. empty lines or no state / EOF

"""
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

    _internals={"prefix":"gi_","type":GeneratorType} ## for the api setup ##
    _attrs=("_internals",) ## for Pickler ##

    def _custom_adjustment(self,line,lineno):
        """
        It does the following to the source lines:

        1. replace all lines that start with yields with returns to start with
        2. make sure the generator is closed on regular returns
        3. save the iterator from the for loops replacing with a nonlocal variation
        4. tend to all yield from ... with the same for loop variation
        5. adjust all value yields either via unwrapping or unpacking
        """
        number_of_indents=get_indent(line)
        temp_line=line[number_of_indents:]
        indent=" "*number_of_indents
        if temp_line.startswith("yield from "):
            return [indent+"currentframe().f_back.f_locals['.yieldfrom']="+temp_line[11:],
                    indent+"for currentframe().f_back.f_locals['.i'] in currentframe().f_back.f_locals['.yieldfrom']:",
                    indent+"    return currentframe().f_back.f_locals['.i']"]
        if temp_line.startswith("yield "):
            return [indent+"return"+temp_line[5:]] ## 5 to retain the whitespace ##
        if temp_line.startswith("for ") or temp_line.startswith("while "):
            self._internals["jump_positions"]+=[[lineno,None]] ## has to be a list since we're assigning ##
            self._internals["jump_stack"]+=[(number_of_indents,len(self._internals["jump_positions"])-1)] ## doesn't have to be a list since it'll get popped e.g. it's not really meant to be modified as is ##
            return [line]
        if temp_line.startswith("return "):
            ## close the generator then return ##
            ## have to use a try-finally in case the user returns from the locals ##
            return [indent+"try:",
                    indent+"    raise StopIteration("+line[7:]+")",
                    indent+"finally:",
                    indent+"    currentframe().f_back.f_locals['self'].close()"]
        ## handles the .send method ##
        flag,adjustment=send_adjust(temp_line)
        if flag:
            if flag==2:
                ## 5: to get past the 'yield'
                return [indent+"return"+adjustment[0][5:],
                        indent+adjustment[1]]
            else:
                ## 11: to get past the 'yield from'
                return [indent+"currentframe().f_back.f_locals['.yieldfrom']="+adjustment[0][11:],
                        indent+"for currentframe().f_back.f_locals['.i'] in currentframe().f_back.f_locals['.yieldfrom']:",
                        indent+"    return currentframe().f_back.f_locals['.i']",
                        indent+"    %scurrentframe().f_back.f_locals['.yieldfrom'].send(currentframe().f_back.f_locals['.send'])" % adjustment[1]]
        return [line]

    def _clean_source_lines(self,running=False):
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
        self._internals["jump_positions"],self._internals["jump_stack"],lineno=[],[],0
        ## setup source as an iterator and making sure the first indentation's correct ##
        source=skip_source_definition(self._internals["source"])
        source=source[get_indent(source):] ## we need to make sure the source is saved for skipping for line continuations ##
        source_iter=enumerate(source)
        line,lines,indented,space,indentation,prev=" "*4,[],False,0,4,(0,0,"")
        ID,depth="",0
        ## enumerate since I want the loop to use an iterator but the 
        ## index is needed to retain it for when it's used on get_indent
        for index,char in source_iter:
            ## collect strings ##
            if char=="'" or char=='"':
                ## get the string collector type ##
                if prev[0]+2==prev[1]+1==index and prev[2]==char:
                    string_collector,temp_index=collect_multiline_string,3
                else:
                    string_collector,temp_index=collect_string,1
                ## determine if we need to look for f-strings in case of value yields ##
                if version_info < (3,6): ## f-strings ##
                    f_string=False
                else:
                    f_string=(source[index-temp_index]=="f")
                    if f_string:
                        f_string=source[index:] ## use the source to determine the extractions ##
                temp_index,temp_line=string_collector(source_iter,char,f_string)
                prev=(index,temp_index,char)
                line+=temp_line
            ## makes the line singly spaced while retaining the indentation ##
            elif char==" ":
                if indented:
                    if space+1!=index:
                        line+=char
                else:
                    line+=char
                    if space+1!=index:
                        indented=True
                space=index
            ## join everything after the line continuation until the next \n or ; ##
            elif char=="\\":
                whitespace=get_indent(source[index+1:]) ## +1 since 'index:' is inclusive ##
                ## skip the whitespace before newline ##
                skip(source_iter,whitespace)
                ## skip the whitespace after newline ##
                skip(source_iter,get_indent(source[index+whitespace+2:]))
                line+=" " ## in case of a line continuation without a space before or after ##
            ## create new line ##
            elif char in "#\n;:":
                ## skip comments ##
                if char=="#":
                    for index,char in source_iter:
                        if char == "\n":
                            break
                ## make sure to include it ##
                if char==":":
                    indentation=get_indent(line)+4 # in case of ';'
                    line+=char
                if not line.isspace(): ## empty lines are possible ##
                    reference_indent=get_indent(line)
                    if self._internals["jump_stack"]:
                        end_lineno=len(lines)+1
                        while self._internals["jump_stack"] and reference_indent <= self._internals["jump_stack"][-1][0]: # -1: top of stack, 0: start lineno
                            self._internals["jump_positions"][self._internals["jump_stack"].pop()[1]][1]=end_lineno ## +1 assuming exclusion slicing on the stop index ##
                    ## skip the definitions ##
                    if is_definition(line[reference_indent:]):
                        index,char,lineno,lines=collect_definition(line,lines,lineno,source,source_iter,reference_indent,prev)
                    else:
                        lineno+=1
                        lines+=self._custom_adjustment(line,lineno)
                        ## make a linetable if using a running generator ##
                        if running and char=="\n":
                            self._internals["linetable"]+=[lineno]
                ## start a new line ##
                if char in ":;":
                    # just in case
                    indented,line=True," "*indentation
                else:
                    indented,line=False,""
                space=index ## this is important (otherwise we get more indents than necessary) ##
            else:
                line+=char
                ## detect value yields ##
                if char=="(": ## [yield] and {yield} is not possible only (yield) ##
                    depth+=1
                elif char==")":
                    depth-=1
                if depth and char.isalnum():
                    ID+=char
                    if ID=="yield":
                        temp_line=value_yield_adjust(source[index-len(line):],source_iter,index)
                        line+=temp_line.pop()
                        lines+=temp_line
                else:
                    ID=""
        ## in case you get a for loop at the end and you haven't got the end jump_position ##
        ## then you just pop them all off as being the same end_lineno ##
        end_lineno=len(lines)+1
        while self._internals["jump_stack"]:
            self._internals["jump_positions"][self._internals["jump_stack"].pop()[1]][1]=end_lineno
        ## are not used by this generator (was only for formatting source code and 
        ## recording the jump positions needed in the for loop adjustments) ##
        del self._internals["jump_stack"]
        return lines

    def _create_state(self,loops):
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
        temp_lineno=self._internals["lineno"]-1 ## for 0 based indexing ##
        if loops:
            start_pos,end_pos=loops.pop()
            ## for 0 based indexing since they're linenos ##
            start_pos-=1
            end_pos-=1
            ## adjustment ##
            blocks,indexes=control_flow_adjust(
                self._internals["source_lines"][temp_lineno:end_pos],
                list(range(temp_lineno,end_pos)),
                get_indent(self._internals["source_lines"][start_pos])
            )
            blocks,indexes=loop_adjust(
                blocks,indexes,
                self._internals["source_lines"][start_pos:end_pos],
                *(start_pos,end_pos)
            )
            self._internals["linetable"]=indexes
            ## add all the outer loops ##
            for start_pos,end_pos in loops[::-1]:
                start_pos-=1
                end_pos-=1
                flag,block=iter_adjust(self._internals["source_lines"][start_pos:end_pos])
                blocks+=indent_lines(block,4-get_indent(block[0]))
                if flag:
                    self._internals["linetable"]+=[start_pos]
                self._internals["linetable"]+=list(range(start_pos,end_pos))
            self._internals["state"]="\n".join(blocks+self._internals["source_lines"][end_pos:])
            return
        block,self._internals["linetable"]=control_flow_adjust(
            self._internals["source_lines"][temp_lineno:],
            list(range(temp_lineno,len(self._internals["source_lines"])))
        )
        self._internals["state"]="\n".join(block)

    def _locals(self):
        """
        proxy to replace locals within 'next_state' within 
        __next__ while still retaining the same functionality
        """
        return self._internals["frame"].f_locals
    
    def _frame_init(self):
        """
        initializes the frame with the current 
        states variables and the _locals proxy
        """
        assign=[]
        for key in self._internals["frame"].f_locals:
            if isinstance(key,str) and key.isalnum() and key!="locals":
                assign+=[" "*4+"%s=locals()[%s]" % (key,key)]
        if assign:
            assign="\n"+"\n".join(assign)
        else:
            assign=""
        ## try not to use variables here (otherwise it can mess with the state) ##
        return """def next_state():
    locals=currentframe().f_back.f_locals['self']._locals%s
    currentframe().f_back.f_locals['.frame']=currentframe()
""" % assign

    def init_states(self):
        """Initializes the state generation as a generator"""
        ## api setup ##
        prefix=self._internals["prefix"]
        for key in ("code","frame","suspended","yieldfrom","running"):
            setattr(self,prefix+key,self._internals[key])
        del prefix
        ## since self._internals["state"] starts as 'None' ##
        yield self._create_state(get_loops(self._internals["lineno"],self._internals["jump_positions"]))
        loops=get_loops(self._internals["lineno"],self._internals["jump_positions"])
        while (self._internals["state"] and len(self._internals["linetable"]) > self._internals["frame"].f_lineno) or loops:
            yield self._create_state(loops)
            loops=get_loops(self._internals["lineno"],self._internals["jump_positions"])

    def __init__(self,FUNC=None,overwrite=False):
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
            prefix=self._internals["prefix"] ## needed to identify certain attributes ##
            ## running generator ##
            if hasattr(FUNC,prefix+"code"):
                self._internals["linetable"]=[]
                self._internals["frame"]=frame(getframe(FUNC))
                if FUNC.gi_code.co_name=="<genexpr>": ## co_name is readonly e.g. can't be changed by user ##
                    self._internals["source"]=expr_getsource(FUNC)
                    self._internals["source_lines"]=unpack_genexpr(self._internals["source"])
                    ## change the offsets into indents ##
                    self._internals["frame"].f_locals=offset_adjust(self._internals["frame"].f_locals)
                else:
                    self._internals["source"]=dedent(getsource(getcode(FUNC)))
                    self._internals["source_lines"]=self._clean_source_lines(True)
                    self._internals["lineno"]=self._internals["linetable"][getframe(FUNC).f_lineno-1]+lineno_adjust(FUNC)
                self._internals["code"]=code(getcode(FUNC))
                ## 'gi_yieldfrom' was introduced in python version 3.5 and yield from ... in 3.3 ##
                if hasattr(FUNC,prefix+"yieldfrom"):
                    self._internals["yieldfrom"]=getattr(FUNC,prefix+"yieldfrom")
                else:
                    self._internals["yieldfrom"]=None
                self._internals["suspended"]=True
            ## uninitialized generator ##
            else:
                ## source code string ##
                if isinstance(FUNC,str):
                    self._internals["source"]=FUNC
                    self._internals["code"]=code(compile(FUNC,"","eval"))
                ## generator function ##
                elif isinstance(FUNC,FunctionType):
                    if FUNC.__code__.co_name=="<lambda>":
                        self._internals["source"]=expr_getsource(FUNC)
                    else:
                        self._internals["source"]=dedent(getsource(FUNC))
                    self._internals["code"]=code(FUNC.__code__)
                else:
                    raise TypeError("type '%s' is an invalid initializer for a Generator" % type(FUNC))
                ## make sure the source code is standardized and usable by this generator ##
                self._internals["source_lines"]=self._clean_source_lines()
                ## create the states ##
                self._internals["frame"]=frame()
                self._internals["suspended"]=False
                self._internals["yieldfrom"]=None
                self._internals["lineno"]=1 ## modified every time __next__ is called; always start at line 1 ##
            self._internals["running"]=False
            self._internals["state"]=None
            self._internals["state_generator"]=self.init_states()
            if overwrite: ## this might not actually work??
                currentframe().f_back.f_locals[getcode(FUNC).co_name]=self

    def __len__(self):
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
                indents=get_indent(line)
                temp=line[indents:]
                if temp.startswith("yield") and not temp.startswith("yield from"):
                    if indents > 4:
                        raise TypeError("__len__ is only available where all yield statements are indented exactly 4 spaces")
                    yield 1
        return sum(number_of_yields())

    def __iter__(self):
        """Converts the generator function into an iterable"""
        while True:
            try:
                yield next(self)
            except StopIteration:
                break

    def __next__(self):
        """updates the current state and returns the result"""
        # set the next state and setup the function
        next(self._internals["state_generator"]) ## it will raise a StopIteration for us
        ## update with the new state and get the frame ##
        exec(self._frame_init()+self._internals["state"],globals(),locals())
        self._internals["running"]=True
        ## if an error does occur it will be formatted correctly in cpython (just incorrect frame and line number) ##
        try:
            return locals()["next_state"]()
        finally:
            ## update the line position and frame ##
            self._internals["running"]=False
            ## update the frame ##
            f_back=self._internals["frame"]
            self._internals["frame"]=locals()[".frame"]
            if self._internals["frame"]:
                self._internals["frame"]=frame(self._internals["frame"])
                ## remove locals from memory since it interferes with pickling ##
                del self._internals["frame"].f_locals["locals"]
                self._internals["frame"].f_back=f_back
                ## update f_locals ##
                if f_back:
                    f_back.f_locals.update(self._internals["frame"].f_locals)
                    self._internals["frame"].f_locals=f_back.f_locals
                self._internals["frame"].f_locals[".send"]=None
                self._internals["frame"].f_lineno=self._internals["frame"].f_lineno-self.init.count("\n")
                if len(self._internals["linetable"]) > self._internals["frame"].f_lineno:
                    self._internals["lineno"]=self._internals["linetable"][self._internals["frame"].f_lineno]+1 ## +1 to get the next lineno after returning ##
                else:
                    ## EOF ##
                    self._internals["lineno"]=len(self._internals["source_lines"])+1

    def send(self,arg):
        """
        Send takes exactly one arguement 'arg' that 
        is sent to the functions yield variable
        """
        if self._internals["lineno"] == 1:
            raise TypeError("can't send non-None value to a just-started generator")
        if self._internals["yieldfrom"]:
            self._internals["yieldfrom"].send(arg)
        else:
            self._internals["frame"].f_locals[".send"]=arg
            return next(self)

    def close(self):
        """Closes the generator clearing its frame, state_generator, and yieldfrom"""
        self._internals.update(
            {
                "state_generator":empty_generator(),
                "frame":None,
                "running":False,
                "suspended":False,
                "yieldfrom":None
            }
        )

    def throw(self,exception):
        """
        Raises an exception from the last line in the 
        current state e.g. only from what has been
        """
        raise exception

    def __setstate__(self,state):
        Pickler.__setstate__(self,state)
        self._internals["state_generator"]=self.init_states()

    def __instancecheck__(self, instance):
        return isinstance(instance,self._internals["type"]|type(self))

    def __subclasscheck__(self, subclass):
        return issubclass(subclass,self._internals["type"]|type(self))

AnyGeneratorType=GeneratorType|Generator

## add the type annotations if the version is 3.5 or higher ##
if (3,6) <= version_info:
    from types import AsyncGeneratorType
    AnyGeneratorType|=AsyncGeneratorType
    class AsyncGenerator(Generator):
        _internals={"prefix":"ag_","type":AsyncGeneratorType}

if (3,5) <= version_info:
    from typing import Callable,Any,NoReturn,Iterable
    from types import CodeType,FrameType
    ## utility functions ##
    empty_generator.__annotations__={"return":GeneratorType}
    lineno_adjust.__annotations__={"FUNC":AnyGeneratorType,"frame":FrameType|None,"return":int}
    is_cli.__annotations__={"return":bool}
    unpack_genexpr.__annotations__={"source":str,"return":list[str]}
    ## tracking ##
    track_iter.__annotations__={"obj":object,"return":Iterable}
    ## cleaning source code ##
    skip_source_definition.__annotations__={"source":str,"return":str}
    string_collector_proxy.__annotations__={"index":int,"char":str,"prev":tuple[int,int,str],"iterable":Iterable,"line":str|None,"return":tuple[str|None,tuple[int,int,str]]}
    collect_string.__annotations__={"iter_val":enumerate,"reference":str,"f_string":bool,"return":tuple[int,str]}
    collect_multiline_string.__annotations__={"iter_val":enumerate,"reference":str,"f_string":bool,"return":tuple[int,str]}
    collect_definition.__annotations__ = {"line": str,"lines": list[str],"lineno": int,"source": str,"source_iter": enumerate,"reference_indent": int,"prev": tuple[int, str],"return": tuple[int, str, int,list[str]]}
    dedent.__annotations__={"text":str,"return":str}
    get_indent.__annotations__={"line":str,"return":int}
    skip.__annotations__={"iter_val":Iterable,"n":int,"return":None}
    is_alternative_statement.__annotations__={"line":str,"return":bool}
    ## code adjustments ##
    skip_alternative_statements.__annotations__={"line_iter":enumerate,"return":tuple[int,str,int]}
    offset_adjust.__annotations__={"f_locals":dict,"return":dict}
    control_flow_adjust.__annotations__={"lines":list[str],"indexes":list[int],"return":tuple[bool,list[str],list[int]]}
    indent_lines.__annotations__={"lines":list[str],"indent":int,"return":list[str]}
    extract_iter.__annotations__={"line":str,"number_of_indents":int|None,"return":str}
    iter_adjust.__annotations__={"outer_loop":list[str],"return":tuple[bool,list[str]]}
    loop_adjust.__annotations__={"lines":list[str],"indexes":list[int],"outer_loop":list[str],"pos":tuple[int,int],"return":tuple[list[str],list[int]]}
    has_node.__annotations__={"line":str,"node":str,"return":bool}
    send_adjust.__annotations__={"line":str,"return":tuple[None|int,None|list[str,str]]}
    unpack.__annotations__={"line":str,"source_iter":None|Iterable,"index":None|int,"left_limit":None|int,"return":list[str]}
    unpack_adjust.__annotations__={"line":str,"source_iter":None|Iterable,"index":None|int,"return":list[str]}
    extract_id.__annotations__={"line_iter":None|Iterable,"return":tuple[str,int,str]}
    assign_adjust.__annotations__={"line":str,"source_iter":None|Iterable,"index":None|int,"return":list[str]}
    value_yield_adjust.__annotations__={"line":str,"source_iter":None|Iterable,"index":None|int,"return":list[str]}
    get_loops.__annotations__={"lineno":int,"jump_positions":list[tuple[int,int]],"return":list[tuple[int,int]]}
    ## expr_getsource ##
    code_attrs.__annotations__={"return":tuple[str,...]}
    attr_cmp.__annotations__={"obj1":object,"obj2":object,"attr":tuple[str,...],"return":bool}
    getcode.__annotations__={"obj":AnyGeneratorType,"return":CodeType}
    getframe.__annotations__={"obj":AnyGeneratorType,"return":FrameType}
    hasattrs.__annotations__={"attrs":tuple[str,...],"return":bool}
    expr_getsource.__annotations__={"FUNC":AnyGeneratorType,"return":str}
    ## genexpr ##
    extract_genexpr.__annotations__={"source_lines":list[str],"return":GeneratorType}
    ## lambda ##
    extract_lambda.__annotations__={"source_code":str,"return":GeneratorType}
    ### copying/pickling ###
    Pickler.__copy__.__annotations__={"return":Pickler}
    Pickler.__deepcopy__.__annotations__={"memo":dict,"return":Pickler}
    Pickler.__getstate__.__annotations__={"return":dict}
    Pickler.__setstate__.__annotations__={"state":dict,"return":None}
    frame.__init__.__annotations__={"frame":FrameType|None,"return":None}
    frame.clear.__annotations__={"return":None}
    frame.__bool__.__annotations__={"return":bool}
    code.__init__.__annotations__={"code":CodeType|None,"return":None}
    code.__bool__.__annotations__={"return":bool}
    ### Generator ###
    Generator._custom_adjustment.__annotations__={"line":str,"lineno":int,"return":list[str]}
    Generator._clean_source_lines.__annotations__={"return":list[str]}
    Generator._create_state.__annotations__={"return":None}
    Generator.init_states.__annotations__={"return":Iterable}
    Generator._frame_init.__annotations__={"return":str}
    Generator.__init__.__annotations__={"FUNC":AnyGeneratorType|str|None,"return":None}
    Generator.__len__.__annotations__={"return":int}
    Generator.__iter__.__annotations__={"return":Iterable}
    Generator.__next__.__annotations__={"return":Any}
    Generator.send.__annotations__={"arg":Any,"return":Any}
    Generator.close.__annotations__={"return":None}
    Generator.throw.__annotations__={"exception":Exception,"return":NoReturn}
    Generator._copier.__annotations__={"FUNC":Callable,"return":Generator}
    Generator.__copy__.__annotations__={"return":Generator}
    Generator.__deepcopy__.__annotations__={"memo":dict,"return":Generator}
    Generator.__instancecheck__.__annotations__={"instance":object,"return":bool}
    Generator.__subclasscheck__.__annotations__={"subclass":type,"return":bool}
