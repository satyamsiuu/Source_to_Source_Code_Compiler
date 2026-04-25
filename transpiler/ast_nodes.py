"""
ast_nodes.py — All AST node definitions for the transpiler.
FROZEN after Phase 0 — do not modify.

Design principle: The AST is LANGUAGE-NEUTRAL. Whether the source is Python, C,
or C++, the parser always produces the same tree structure using these nodes.
This is what makes transpilation possible: parse any language → same AST → 
generate any language.

Why dataclasses?
    - Auto-generates __init__, __repr__, __eq__
    - Fields are explicit and typed (self-documenting)
    - No boilerplate: just declare fields, Python does the rest
    - isinstance(node, IfStmt) reads like English

Why not plain dicts?
    - No type safety: d["conditon"] (typo) silently returns None
    - No IDE autocomplete, no static analysis
    - Dataclass fields are validated at construction time
"""

from dataclasses import dataclass, field  # field() for mutable default values
from enum import Enum                      # for DataType
from typing import Optional                # for nullable type hints


class DataType(Enum):
    """Data types supported by our transpiler.

    INT, FLOAT, BOOL — numeric types that map to all three languages.
    STR — only allowed inside print() calls, not as variables.
    VOID — return type for functions that don't return a value.
    UNKNOWN — temporary placeholder assigned during parsing before the
              semantic analyzer resolves the actual type.
              Example: 'x = 5' → parser creates VarDecl(x, UNKNOWN, Literal(5, INT))
              Then semantic analysis sees Literal is INT → updates x to INT.
    """
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    STR = "str"
    VOID = "void"
    UNKNOWN = "unknown"


@dataclass
class ASTNode:
    """Base class for all AST nodes.

    Why a base class?
    - isinstance(node, ASTNode) can check if something is any AST node
    - All nodes share the 'line' field for error reporting
    - Provides a common parent for type hints: body: list[ASTNode]
    """
    line: int = 0  # source line number where this construct appeared


# ─── PROGRAM STRUCTURE ────────────────────────────────────────────────

@dataclass
class Program(ASTNode):
    """Root node of the entire AST. Every parsed program produces exactly one.

    Why separate functions and globals?
    - C requires functions to be at top level, not inside other functions
    - Global code (Python's module-level statements) needs different treatment:
      in C, they go inside an auto-generated main() function
    - Keeping them separate simplifies both the semantic analyzer and the generators
    """
    functions: list = field(default_factory=list)  # list of FunctionDecl nodes
    globals: list = field(default_factory=list)     # list of top-level statements


@dataclass
class FunctionDecl(ASTNode):
    """A function declaration: name, parameters, return type, and body.

    Example: 'def add(x, y):' → FunctionDecl(name='add', params=[Param(x,INT), Param(y,INT)],
                                              return_type=INT, body=[...])
    """
    name: str = ""
    params: list = field(default_factory=list)  # list of Param nodes
    return_type: DataType = DataType.VOID       # VOID if no return statement
    body: list = field(default_factory=list)     # list of statement ASTNodes


@dataclass
class Param(ASTNode):
    """A single function parameter with name and type.

    In Python source: type is UNKNOWN until semantic analysis infers it.
    In C/C++ source: type is explicit from the declaration.
    """
    name: str = ""
    data_type: DataType = DataType.UNKNOWN


# ─── DECLARATIONS ─────────────────────────────────────────────────────

@dataclass
class VarDecl(ASTNode):
    """Variable declaration: name, type, optional initializer.

    Python: 'x = 5'     → VarDecl(name='x', data_type=UNKNOWN, value=Literal(5,INT))
    C:      'int x = 5' → VarDecl(name='x', data_type=INT, value=Literal(5,INT))
    """
    name: str = ""
    data_type: DataType = DataType.UNKNOWN
    value: Optional[ASTNode] = None  # None means uninitialized: 'int x;'


@dataclass
class ArrayDecl(ASTNode):
    """Array declaration: name, element type, fixed size, optional initial elements.

    Python: 'arr = array(int, 5)'  → ArrayDecl(name='arr', data_type=INT, size=5, elements=[])
    Python: 'arr = [1, 2, 3]'     → ArrayDecl(name='arr', data_type=INT, size=3, elements=[...])
    C:      'int arr[5]'          → ArrayDecl(name='arr', data_type=INT, size=5, elements=[])

    Why fixed size? C needs the size at compile time: 'int arr[N]'.
    Python's dynamic lists can't be directly translated without a known size.
    """
    name: str = ""
    data_type: DataType = DataType.UNKNOWN
    size: int = 0
    elements: list = field(default_factory=list)  # list of ASTNode (the initializer values)


# ─── STATEMENTS ───────────────────────────────────────────────────────

@dataclass
class AssignStmt(ASTNode):
    """Assignment to an existing variable: name = value.

    Different from VarDecl: VarDecl CREATES the variable, AssignStmt UPDATES it.
    The semantic analyzer checks that the variable was previously declared.
    """
    name: str = ""
    value: Optional[ASTNode] = None


@dataclass
class ArrayAssign(ASTNode):
    """Assignment to an array element: arr[index] = value.

    Separate from AssignStmt because it has an index expression.
    The semantic analyzer checks: arr is declared, index is INT, value type matches.
    """
    name: str = ""
    index: Optional[ASTNode] = None   # expression for the index
    value: Optional[ASTNode] = None   # expression for the new value


@dataclass
class IfStmt(ASTNode):
    """If/else statement: condition, then-body, else-body.

    else_body is empty list (not None) when there is no else branch.
    This simplifies generators: they always iterate else_body, it's just empty.
    """
    condition: Optional[ASTNode] = None
    then_body: list = field(default_factory=list)
    else_body: list = field(default_factory=list)


@dataclass
class WhileStmt(ASTNode):
    """While loop: condition + body.

    Maps directly to 'while' in all three target languages.
    """
    condition: Optional[ASTNode] = None
    body: list = field(default_factory=list)


@dataclass
class ForRangeStmt(ASTNode):
    """For loop over a numeric range.

    Python: for i in range(start, stop, step):
    C/C++:  for (int i = start; i < stop; i += step)

    Why a separate node from ForEachStmt?
    Range loops have start/stop/step — numeric bounds.
    For-each loops iterate over an array name.
    One node with optional fields would force every generator to check which kind.
    Two nodes: the generator knows exactly what it has. Cleaner code.
    """
    var: str = ""                          # loop variable name (e.g. 'i')
    start: Optional[ASTNode] = None        # range start (default Literal(0))
    stop: Optional[ASTNode] = None         # range end (exclusive)
    step: Optional[ASTNode] = None         # range step (default Literal(1))
    body: list = field(default_factory=list)


@dataclass
class ForEachStmt(ASTNode):
    """For-each loop over an array.

    Python: for x in arr:
    C/C++:  for (int _i=0; _i<arr_size; _i++) { int x = arr[_i]; ... }

    array_name references a previously declared ArrayDecl.
    The semantic analyzer checks that array_name exists and is indeed an array.
    """
    var: str = ""           # loop variable name (e.g. 'x')
    array_name: str = ""    # name of the array being iterated
    body: list = field(default_factory=list)


@dataclass
class ReturnStmt(ASTNode):
    """Return statement: return value.

    value is None for bare 'return' (void functions).
    The semantic analyzer checks that the return type matches the function's declared type.
    """
    value: Optional[ASTNode] = None


@dataclass
class PrintStmt(ASTNode):
    """Print statement with multiple arguments.

    Python: print(x, y, z)        → PrintStmt(values=[Var(x), Var(y), Var(z)])
    C:      printf("%d %f", x, y) → same node, c_generator builds the format string
    C++:    cout << x << " " << y → same node, cpp_generator chains << operators

    Why values is a list, not a single value?
    print(x, y, z) is common Python. If values were a single node, we'd need
    nested PrintStmt or a wrapper node. A list is the simplest correct model.
    """
    values: list = field(default_factory=list)   # list of expression ASTNodes
    separator: str = " "                          # separator between values (always space)


@dataclass
class InputStmt(ASTNode):
    """Input statement: read a value from stdin into a variable.

    Python: x = int(input("prompt"))  → InputStmt(target='x', data_type=INT, prompt="prompt")
    C:      scanf("%d", &x)           → same node
    C++:    cin >> x                  → same node
    """
    target: str = ""                            # variable name to store the input
    data_type: DataType = DataType.UNKNOWN       # type to parse the input as
    prompt: Optional[str] = None                 # optional prompt string (Python only)


# ─── EXPRESSIONS ──────────────────────────────────────────────────────

@dataclass
class FunctionCall(ASTNode):
    """A function call expression: name(arg1, arg2, ...).

    Can appear as a statement (add(3,4)) or inside an expression (x = add(3,4)).
    The semantic analyzer checks: function exists, arg count matches, arg types match.
    """
    name: str = ""
    args: list = field(default_factory=list)  # list of expression ASTNodes


@dataclass
class BinaryOp(ASTNode):
    """Binary operation: left op right.

    Examples: x + y, a > b, i == 0
    Recursive: BinaryOp('+', BinaryOp('*', a, b), c) represents a*b + c
    The parser builds the correct tree structure based on operator precedence.

    op is a string like '+', '-', '*', '/', '==', '!=', '<', '>', '<=', '>='
    """
    op: str = ""
    left: Optional[ASTNode] = None
    right: Optional[ASTNode] = None


@dataclass
class UnaryOp(ASTNode):
    """Unary operation: op operand.

    Examples: -x, not flag
    op is '-' or 'not'
    """
    op: str = ""
    operand: Optional[ASTNode] = None


@dataclass
class Var(ASTNode):
    """Variable reference in an expression.

    'x + y' → BinaryOp('+', Var('x'), Var('y'))
    The semantic analyzer checks that the variable was previously declared.
    """
    name: str = ""


@dataclass
class ArrayAccess(ASTNode):
    """Array element access: arr[index].

    'arr[i]' → ArrayAccess(name='arr', index=Var('i'))
    The semantic analyzer checks: arr is declared as an array, index type is INT.
    """
    name: str = ""
    index: Optional[ASTNode] = None


@dataclass
class Literal(ASTNode):
    """A literal value: number, string, or boolean.

    5      → Literal(value=5, data_type=INT)
    3.14   → Literal(value=3.14, data_type=FLOAT)
    True   → Literal(value=True, data_type=BOOL)
    "hello"→ Literal(value="hello", data_type=STR)

    Why store data_type inside the literal?
    The semantic analyzer needs to know the type of every expression.
    Literals are the BASE CASE of type inference: their type is known immediately.
    BinaryOp('+', Literal(5,INT), Literal(3.14,FLOAT)) → result type is FLOAT.
    Without data_type on Literal, the analyzer would need a separate lookup table.
    """
    value: object = None                     # the actual value (int, float, bool, str)
    data_type: DataType = DataType.UNKNOWN   # the type of this literal
