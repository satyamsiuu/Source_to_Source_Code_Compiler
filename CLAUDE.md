# CLAUDE.md — Agent Instructions
# Works with: Claude (Opus/Sonnet), Gemini, GPT-4, or any LLM
# Last updated: Phase 0 not started
# READ THIS ENTIRE FILE BEFORE WRITING A SINGLE LINE OF CODE

---

## WHAT YOU ARE BUILDING
Source-to-source compiler (transpiler): Python ↔ C ↔ C++
Demonstrates full compiler pipeline with web UI showing each phase.
Language: Python. Backend: Flask. Frontend: single index.html + vanilla JS.
No frameworks. No npm. No build steps.

---

## YOUR ROLE AS AGENT
- Build one phase at a time in strict order
- After each phase: update PROGRESS.md, CONTEXT.md, EXPLAINER.md
- **ALWAYS ask the user "Ready for Phase N?" before starting any new phase. Never auto-proceed.**
- Never start next phase until current phase tests pass
- Never modify errors.py or ast_nodes.py after Phase 0 without explicit note
- If you are resuming: read CONTEXT.md → LAST_PHASE_DIFF first, then TOTAL_STATE

---

## HOW TO READ THESE FILES (token-efficient workflow)
- Resuming mid-project? Read CONTEXT.md:LAST_PHASE_DIFF (~200 tokens)
- Need full picture? Read CONTEXT.md:TOTAL_STATE (~800 tokens)
- Need to explain code? Read EXPLAINER.md:PHASE_N section
- Check what's done? Read PROGRESS.md phase statuses only

---

## PHASE BUILD ORDER (strict — no skipping)
```
Phase 0  →  errors.py + ast_nodes.py + tokens.py         [FOUNDATION — FROZEN AFTER]
Phase 1  →  preprocessor/preprocessor.py
Phase 2  →  lexer/python_lexer.py → c_lexer.py → cpp_lexer.py
Phase 3  →  parser/python_parser.py → c_parser.py → cpp_parser.py
Phase 4  →  semantic/analyzer.py
Phase 5  →  ir/ir_generator.py
Phase 6  →  codegen/python_generator.py → c_generator.py → cpp_generator.py
Phase 7  →  validator/validator.py
Phase 8  →  main.py + frontend/index.html
```

---

## AFTER EVERY PHASE — MANDATORY STEPS (no exceptions)
```
1. Run the phase test (defined in PROGRESS.md)
2. Confirm test passes
3. Mark phase COMPLETE in PROGRESS.md with actual line count
4. Update CONTEXT.md: LAST_PHASE_DIFF + TOTAL_STATE
5. Update EXPLAINER.md with line-by-line explanation of new code
6. Only then move to next phase
```

---

## FILE STRUCTURE
```
transpiler/
├── errors.py                ~55 lines   [FROZEN after Phase 0]
├── ast_nodes.py             ~175 lines  [FROZEN after Phase 0]
├── main.py                  ~130 lines
├── preprocessor/
│   └── preprocessor.py      ~150 lines
├── lexer/
│   ├── tokens.py            ~95 lines   [FROZEN after Phase 0]
│   ├── python_lexer.py      ~260 lines
│   ├── c_lexer.py           ~225 lines
│   └── cpp_lexer.py         ~85 lines   [extends c_lexer — NO copy-paste]
├── parser/
│   ├── python_parser.py     ~400 lines
│   ├── c_parser.py          ~380 lines
│   └── cpp_parser.py        ~110 lines  [extends c_parser — NO copy-paste]
├── semantic/
│   └── analyzer.py          ~320 lines
├── ir/
│   └── ir_generator.py      ~200 lines
├── codegen/
│   ├── python_generator.py  ~250 lines
│   ├── c_generator.py       ~280 lines
│   └── cpp_generator.py     ~110 lines  [extends c_generator — NO copy-paste]
├── validator/
│   └── validator.py         ~190 lines
├── visualizer/
│   └── ast_visualizer.py    ~130 lines
└── frontend/
    └── index.html           ~550 lines
TOTAL: ~3875 lines
```

---

## CODING RULES (enforce always)
1. Every error → CompilerError from errors.py, never raw exceptions
2. Every phase → collect ALL errors → raise CompilerErrorList once at end
3. No file > 400 lines (index.html exception: 550)
4. Unsupported feature → CompilerError with clear message, never silent ignore
5. cpp_lexer extends c_lexer (import, don't copy)
6. cpp_parser extends c_parser (import, don't copy)
7. cpp_generator extends c_generator (import, don't copy)
8. errors.py and ast_nodes.py FROZEN after Phase 0

---

## LOCKED FEATURE SCOPE

### SUPPORTED
- Types: int, float, bool, str (print-only)
- Ops: + - * / == != < > <= >=
- Control: if/else, while
- For loops: range(n), range(start,n), range(start,n,step), for-each over 1D array
- Functions: declare + call, no overloading
- Arrays: 1D fixed-size, declared as array(int, 5) for empty or [1,2,3] for init
- Print: multiple args → print(x, y, z)
- Input: scanf/input()/cin
- Comments: single-line and multi-line (preprocessor strips)
- Call-before-definition: allowed in Python source (two-pass semantic)

### HARD REJECT (raise CompilerError immediately)
pointers, classes, structs, templates, multiple files, import/include,
try/except, lambda, list comprehension, global keyword, nested functions,
for-each over non-array, string operations, empty [] arrays

---

## AST NODES (frozen after Phase 0)
```
DataType(Enum):  INT, FLOAT, BOOL, STR, VOID, UNKNOWN

Program:         functions:list[FunctionDecl], globals:list[ASTNode]
FunctionDecl:    name:str, params:list[Param], return_type:DataType, body:list
Param:           name:str, data_type:DataType
VarDecl:         name:str, data_type:DataType, value:ASTNode|None
ArrayDecl:       name:str, data_type:DataType, size:int, elements:list[ASTNode]
AssignStmt:      name:str, value:ASTNode
ArrayAssign:     name:str, index:ASTNode, value:ASTNode
IfStmt:          condition:ASTNode, then_body:list, else_body:list
WhileStmt:       condition:ASTNode, body:list
ForRangeStmt:    var:str, start:ASTNode, stop:ASTNode, step:ASTNode, body:list
ForEachStmt:     var:str, array_name:str, body:list
ReturnStmt:      value:ASTNode|None
PrintStmt:       values:list[ASTNode], separator:str=" "
InputStmt:       target:str, data_type:DataType, prompt:str|None
FunctionCall:    name:str, args:list[ASTNode]
BinaryOp:        op:str, left:ASTNode, right:ASTNode
UnaryOp:         op:str, operand:ASTNode
Var:             name:str
ArrayAccess:     name:str, index:ASTNode
Literal:         value, data_type:DataType
```

---

## TOKEN TYPES (frozen after Phase 0)
```
Keywords:    IF ELSE WHILE FOR DEF RETURN PRINT INPUT TRUE FALSE VOID
             INT_KW FLOAT_KW BOOL_KW ARRAY
C/CPP only:  INCLUDE COUT CIN MAIN PRINTF SCANF
Literals:    NUMBER STRING NAME
Operators:   PLUS MINUS STAR SLASH EQ NEQ LT GT LEQ GEQ ASSIGN
Delimiters:  LPAREN RPAREN LBRACE RBRACE LBRACKET RBRACKET COMMA SEMICOLON COLON SCOPE
Python-only: INDENT DEDENT NEWLINE
Meta:        EOF
```

---

## KEY ALGORITHMS

### INDENT/DEDENT (python_lexer.py)
```
indent_stack = [0]
for each non-blank line:
    indent = count leading spaces
    if '\t' in leading chars → error: mixed tabs/spaces
    if indent > stack[-1]   → push indent, emit INDENT token
    elif indent < stack[-1] →
        while stack[-1] > indent: pop, emit DEDENT
        if stack[-1] != indent  → error: bad dedent
    tokenize rest of line
    emit NEWLINE
at EOF: emit DEDENT for each remaining level > 0
```

### TWO-PASS SEMANTIC (analyzer.py)
```
Pass 1: walk program.functions only
        → add each FunctionDecl signature to global scope
        → {name: (param_types, return_type)}
Pass 2: walk entire AST
        → type-check, scope-check, validate all calls
        → uses pass-1 signatures for forward-call resolution
Note: C source = one pass only (define-before-use enforced)
```

### DYNAMIC FORMAT STRING (c_generator.py)
```
PrintStmt.values = [x, y, z] with types [INT, FLOAT, STR]
→ format = "%d %f %s\n"
→ emit: printf("%d %f %s\n", x, y, z);
DataType.INT   → %d
DataType.FLOAT → %f
DataType.BOOL  → %d
DataType.STR   → %s
```

### FOR LOOP TRANSLATION
```
ForRangeStmt(var=i, start=0, stop=n, step=1):
  Python → for i in range(n):
  C/C++  → for (int i = 0; i < n; i += 1)

ForRangeStmt(var=i, start=a, stop=b, step=s):
  Python → for i in range(a, b, s):
  C/C++  → for (int i = a; i < b; i += s)

ForEachStmt(var=x, array_name=arr):
  Python → for x in arr:
  C/C++  → for (int _i=0; _i<arr_size; _i++) { int x = arr[_i]; ... }
  Note: arr_size must be known from ArrayDecl in symbol table
```

### TYPE PROMOTION
```
INT + INT   → INT
INT + FLOAT → FLOAT  (silent promotion, no error)
FLOAT + INT → FLOAT  (silent promotion)
x = 5       → VarDecl(x, INT)
x = x+3.14  → AssignStmt(x, ...) + x type upgraded to FLOAT in symbol table
```

---

## FLASK ROUTES (main.py)
```
POST /compile   → runs Phase 1-5, returns all phase outputs as JSON
POST /generate  → runs Phase 6 (codegen), needs {ir, target_language}
POST /validate  → runs Phase 7, needs {src_code, src_lang, tgt_code, tgt_lang, inputs}
```

### Response format for /compile
```json
{
  "preprocessor": {"status":"pass","comments":[]},
  "lexer":        {"status":"pass","tokens":[]},
  "parser":       {"status":"pass","ast":{}},
  "semantic":     {"status":"error","errors":[]},
  "ir":           {"status":"blocked"},
  "codegen":      {"status":"blocked"},
  "validator":    {"status":"blocked"}
}
```
Rule: first phase with status=error → all subsequent phases status=blocked

---

## UI SPEC (index.html)

### Layout
```
┌─────────────────────────────────────────────────────┐
│  [Python][C][C++]              source-to-source     │
├──────────────────────┬──────────────────────────────┤
│                      │  ● Preprocessor    [pass]    │
│  Source code editor  │  ● Lexer           [pass]    │
│  (left 40%)          │  ● Parser          [errors]  │
│                      │  ○ Semantic        [blocked] │
│  [Upload] [Compile]  │  ○ IR              [blocked] │
│                      │  ○ Codegen         [blocked] │
│                      │  ○ Validator       [blocked] │
│                      │  ──────────────────────────  │
│                      │  Target:[C▾] [Generate]      │
└──────────────────────┴──────────────────────────────┘
```

### Phase click behavior
- GREEN phase clicked  → modal opens with phase output
- RED phase clicked    → modal opens with error blocks
- GREY/blocked phase   → click does nothing
- New compile          → ALL phase data wiped before results shown
- Modal close          → × button or click outside

### Token pill colors (format: TYPE:value)
```
KEYWORD  → bg:#EEEDFE  text:#3C3489
NAME     → bg:#E1F5EE  text:#085041
NUMBER   → bg:#FAEEDA  text:#633806
OPERATOR → bg:#FAECE7  text:#712B13
STRING   → bg:#FBEAF0  text:#72243E
INDENT/DEDENT → bg:#E6F1FB  text:#0C447C
DELIMITER     → bg:secondary  text:secondary
NEWLINE/EOF   → bg:tertiary   text:tertiary
```

### Modal contents per phase
```
Preprocessor → list of stripped comments
Lexer        → TYPE:value colored pills
Parser       → text tree (default) + toggle to SVG graphical tree
Semantic     → symbol table (pass) OR error blocks (fail)
IR           → colored node dump
Codegen      → syntax-highlighted generated code
Validator    → side-by-side stdout comparison + PASS/FAIL result
```

### Error block format
```
[PhaseName] ERROR at Line N, Col N
→ error message
| source code snippet
```

---

## ARCHITECTURAL DECISIONS (for teacher/examiner questions)

### Why Neutral AST as IR, not TAC?
TAC (three-address code) flattens `return x+y` to `t1=x+y; return t1`.
Destroys program structure. Our goal is readable target code.
Neutral AST preserves structure → clean idiomatic output in all 3 languages.
Trade-off: no machine-level optimization. Acceptable: optimization out of scope.

### Why not LLVM IR?
Production IR used by Clang/Rust/Swift. Requires LLVM toolchain install,
SSA form knowledge (graduate-level), complex API. Black box — can't explain.
Our IR is plain Python dataclasses. Every field is readable and traceable.

### Why recursive descent parser, not PLY/ANTLR?
Parser generators produce unreadable generated code. Can't trace decisions.
Recursive descent: one function per grammar rule, fully transparent.
Every parsing decision is a function call we can point to and explain.

### Why single HTML file, not React/Vue?
React requires Node.js, npm, build step, JSX knowledge.
Single HTML: opens in any browser, zero setup, entire frontend in one file.
Examiner can read every line. Perfect for demo and explanation.

### Why Flask, not FastAPI/Django?
3 synchronous routes. No async needed. Flask = 3 lines setup + decorators.
FastAPI adds Pydantic/async complexity that serves no purpose here.
Django is for large apps. This is a 3-route API.

### Why ForRangeStmt + ForEachStmt (2 nodes), not 1 ForStmt?
One node with optional fields forces every generator to detect which kind.
Two nodes: intent is explicit. Generator has one method per loop type.
Follows principle: AST expresses meaning, not syntax.

### Why two-pass semantic for Python, one-pass for C?
C standard mandates declare-before-use. C compilers make one forward pass.
Python resolves names at call time — forward calls are valid Python.
Our compiler respects each language's own semantics.

### Why silent INT→FLOAT promotion?
Python is dynamically typed — x=5 then x=x+3.14 is valid Python.
Rejecting it would make valid Python programs fail in our compiler.
Promotion is logged in symbol table. Codegen uses updated type for printf format.

### Why array(int, 5) syntax for empty arrays?
Python's [] gives no size or type information.
C needs both: int arr[5]. Without size, codegen cannot emit valid C.
array(int, 5) is minimal syntax that provides exactly what codegen needs.
Rejected: inferring size from later assignments (too complex, error-prone).

---

## TESTS PER PHASE

### Phase 0
```python
from errors import CompilerError, Phase
from ast_nodes import Program, FunctionDecl, BinaryOp
from lexer.tokens import Token, TokenType
print("OK")
```

### Phase 1
```python
p = Preprocessor()
r = p.process("x = 1  # comment\ny = 2", "python")
assert "# comment" not in r["clean_source"]
assert r["comments"] == ["# comment"]
```

### Phase 2 (python)
```
input:  "if x > 0:\n    return x\n"
expect: [..., INDENT, KEYWORD:return, NAME:x, NEWLINE, DEDENT, ...]
```

### Phase 3 (python)
```
input:  above token stream
expect: Program with IfStmt(BinaryOp(">",Var("x"),Literal(0)), [ReturnStmt(Var("x"))], [])
```

### Phase 4 — should PASS
```python
def add(x, y):
    return x + y
result = add(3, 4)
print(result)
```

### Phase 4 — should FAIL (2 errors)
```python
print(z)
x = 1
x = 2
```
Expected: undeclared 'z', redeclaration 'x'

### Phase 6 round-trip
```
Python "def add(x,y):\n    return x+y\nprint(add(3,4))\n"
→ python_generator → exec → stdout must be "7"
```

### Phase 7
```
Python print(7) vs C printf("%d\n",7) → PASSED
Python print(7) vs C printf("%d\n",8) → FAILED
```
