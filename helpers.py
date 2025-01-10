import inspect
import textwrap
import gc
from collections.abc import Iterable 


class Code:
    """ This class helps manipulating code """
    def __init__(self, code, running_line=0):
        self.code = code # all code not in lines
        self.running_line = running_line
        
    @classmethod
    def from_generator(cls, running_gen):
        return cls(inspect.getsource(running_gen.gi_code), cls.get_runnning_line(running_gen))

    @property
    def lines(self):
        return self.code.split("\n")
    
    @staticmethod
    def get_runnning_line(running_gen):
        return running_gen.gi_frame.f_lineno - running_gen.gi_code.co_firstlineno
    
    @property
    def dedent(self):
        return Code(textwrap.dedent(self.code))
    
    @property
    def indent(self):
        return textwrap.indent(str(self), "    ")
    
    def __getitem__(self, key):
        if isinstance(key, int):
            return self.lines[key]
        return Code("\n".join(self.lines[key]))

    def __str__(self):
        return self.code # "\n".join(self.lines)
    
    def __repr__(self):
        return "\n".join(self.lines)

    def __radd__(self,b):
        return Code(str(b)+self.code+"\n")
    
    def __add__(self,b):
        return Code(self.code+str(b)+"\n")
    
    @property
    def running_level(self):
        return self.line_level(self.running_line)
    
    @property
    def running_line_txt(self):
        return self[self.running_line]
    
    @property
    def running_in_block(self):
        return self.running_level > 1
    
    @property
    def block(self):
        if self.running_in_block:
            return self[self.block_start_line].strip().split(" ")[0]
        else:
            return "root"
        
    @property
    def block_start_line(self):
        line = self.running_line-1
        while self.running_level == self.line_level(line):
            line -= 1
        return line 
    
    @property
    def scope_after(self):
        return self[self.running_line+1:self.line_scope_after]
    
    @property
    def line_scope_after(self):
        line = self.running_line
        while self.running_level == self.line_level(line):
            line += 1
        return line
    
    @property
    def next_scope_line(self):
        return self.line_scope_after+1
    
    def line_level(self, line: int):
        return self.level(self[line])
    
    @staticmethod
    def level(line: str):
        stripped = line.lstrip()
        level = len(line) - len(stripped)
        return level//4

def get_implicit_iterator_in_for_loop(a):
    """ gets the implicit iterator in a for loop, this is as hacky as it could be,
    reliying in python internals that are only be exposed to the garbage collector.
    
    a = [1,2,3]
    for i in a:
        h = get_implicit_iterator_in_for_loop(a)
        next(h) => 2 
    
    """
    for i in [obj for obj in gc.get_referrers(a)  if isinstance(obj, Iterable)]:
        if str(type(i)) == "<class 'list_iterator'>":
            return i    

def get_implicit_iterator_in_for_loop_everywhere():
    """ gets the implicit iterator in a for loop, this is as hacky as it could be,
    reliying in python internals that are only be exposed to the garbage collector.
    
    for i in [1,2,3]:
        h = get_implicit_iterator_in_for_loop(a)
        next(h) => 2 
    
    """
    for i in [obj for obj in gc.get_objects()  if isinstance(obj, Iterable)]:
        if str(type(i)) == "<class 'list_iterator'>":
            return i    
    
        
### como copiar, 
#cuando serialices, guarda el codigo en texto y las variables, haz que el codigo sea una funcion con cualquier nombre
#cuando deserialices executa el codigo con las variables guardadas.


def my_copy(generator):
    code = Code.from_generator(generator)
    args = generator.gi_frame.f_locals.copy()
    args = ",".join(f"{k}={v}" for k,v in args.items())
    
    # function def, not really needed, but fine
    new_code = Code(f"def saved({args}):\n")
    line = code.running_line+1
    
    if code.block in ["if", "else:", "elif"]:
        new_code+="    if True:"
        new_code+="        pass"
    elif code.block == "while":
        new_code+=code.scope_after.dedent.indent
        line=code.block_start_line
        

    # main code
    new_code += code[line:]
    
    # executor
    new_code += f"n = saved({args})"  
    # print(new_code.code)
    exec(new_code.code)
    return eval("n")

def gtest1():
    yield 10
    yield 20
    yield 30

def test_1():
    t1 = gtest1()
    tc = my_copy(t1)
    assert next(tc) == 10
    assert next(tc) == 20
    
    assert next(t1) == 10
    tc = my_copy(t1)
    assert next(tc) == 20
  
def gtest2(a):
    yield 10
    if a:
        yield 20
    yield 30

def test_2():
    t1 = gtest2(1)
    tc = my_copy(t1)
    assert next(tc) == 10

    t1 =  gtest2(2)
    assert next(t1) == 10
    tc = my_copy(t1)
    assert next(tc) == 20
    assert next(tc) == 30
    assert next(t1) == 20
    
def gtest3(a):
    yield 10
    if a:
        yield 20
    else:
        yield 40
    yield 30

def test_3():
    t1 = gtest3(True)
    assert next(t1) == 10
    assert next(t1) == 20
    tc = my_copy(t1)
    assert next(tc) == 30 
    
    t1 = gtest3(False)
    assert next(t1) == 10
    assert next(t1) == 40
    tc = my_copy(t1)
    assert next(tc) == 30 
      
def gtest4(a):
    b = 10
    yield b
    if a:
        b+=10
        yield b
        b+=10
    else:
        b+=30
        yield b
        b-=10
    yield b
    
def test_4():
    t1 = gtest4(True)
    assert next(t1) == 10
    assert next(t1) == 20
    tc = my_copy(t1)
    assert next(tc) == 30 
    
    t1 = gtest3(False)
    assert next(t1) == 10
    assert next(t1) == 40
    tc = my_copy(t1)
    assert next(tc) == 30 
    
def gtest5(a):
    a = a +2
    yield a 
    while True:
        a +=1 
        yield a 
        a+=2

def test_5(): #avg
    t1 = gtest5(10)
    assert next(t1) == 12
    assert next(t1) == 13
    tc = my_copy(t1)
    assert next(tc) == 16 
    assert next(t1) == 16
    

        
def tests():
    test_1()
    test_2()
    test_3()
    test_4()
    test_5()
    
print("testing")
tests()
