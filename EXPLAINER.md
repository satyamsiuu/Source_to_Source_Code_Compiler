# EXPLAINER.md — Deep Code Explanations for Viva Preparation
# Agent: after each phase completes, ADD a section below.
# DO NOT overwrite previous sections.
# Reader: read the section for whichever phase you're explaining.
# Purpose: you should be able to answer ANY question about ANY line.

---

## HOW TO USE THIS FILE
- Before viva: read section for each phase you want to explain
- Each section covers: WHAT the code does, WHY this design, WHAT breaks if changed
- All concepts explained from first principles

---

## GENERAL CONCEPTS (read before any phase)

### What is a compiler vs a transpiler?
A compiler converts source code to a LOWER level (e.g. C → machine code).
A transpiler (source-to-source compiler) converts between languages at the
SAME level (e.g. Python → C). Both use the same pipeline:
lex → parse → analyze → generate. The difference is only in the backend.

### What is a pipeline?
A series of stages where the output of one stage is the input of the next.
If any stage fails, all subsequent stages are blocked.
This mirrors how real compilers like GCC and Clang work.

### Why Python to build a compiler?
Python's dataclasses make AST nodes clean and readable.
isinstance() checks read like English. No manual memory management.
The compiler's source code is as readable as possible — important for explanation.

### What is the difference between syntax and semantics?
Syntax: is the structure grammatically valid? "if x >" is invalid syntax.
Semantics: does it mean something? "print(z)" is valid syntax but if z
was never declared, it is semantically invalid.
The lexer+parser check syntax. The semantic analyzer checks semantics.

### What is an AST?
Abstract Syntax Tree. A tree where each node represents a construct
(function, if-statement, expression). "Abstract" = syntactic details
(semicolons, braces, indentation) are stripped away.
Two programs with the same meaning but different syntax produce the same AST.
This is why transpilation works: translate to AST, regenerate in target language.

---

## PHASE 0 — Foundation
Phase 0 creates the three foundational files that every other phase imports.
These files are FROZEN after this phase — any change would break all downstream phases.

### errors.py — every concept explained

**@dataclass decorator**
`@dataclass` tells Python to auto-generate `__init__`, `__repr__`, and `__eq__`
from the class's field annotations. Without it, CompilerError would need a manual
`def __init__(self, phase, message, line=None, col=None): self.phase = phase; ...`
— 4 lines of boilerplate per class. With `@dataclass`, we just declare the fields
and Python generates the constructor. This is why every AST node uses it too.

**Phase enum**
`Phase(Enum)` defines named constants for each compiler stage: PREPROCESSOR, LEXER,
PARSER, SEMANTIC, IR, CODEGEN, VALIDATOR. Why not plain strings? If you write
`Phase.LEXR` (typo), Python crashes immediately at import time. If you write
`"lexr"` (string typo), it silently works and the frontend never matches it. Enums
catch bugs at definition time, not at runtime.

**CompilerError fields**
- `phase: Phase` — which stage found this error (used by frontend to show error under correct phase)
- `message: str` — human-readable description ("Undeclared variable 'z'")
- `line: int = None` — 1-based line number (None for errors without location, like "empty source")
- `col: int = None` — 1-based column number
- `to_dict()` — serializes to `{"phase":"lexer","message":"...","line":5,"col":12}` for JSON API

**CompilerErrorList extending Exception**
Why extend Exception instead of returning a list?
When the lexer finds errors, the parser must NOT run on broken tokens. Python's
exception mechanism naturally propagates up: `raise CompilerErrorList(errors)` in
the lexer → caught in main.py → pipeline marks all subsequent phases as "blocked".
If we returned a list instead, every caller would need `if errors: don't proceed`
checks — easy to forget, leading to silent failures.

**Why collect all errors before raising**
GCC shows "5 errors found" because it collects them all. A compiler that stops at
error #1 forces the user to fix one error, recompile, see the next error, fix,
recompile... N iterations for N errors. By collecting ALL errors in a list and
raising once, the user sees everything at once. This saves time and shows competence.

**The collect-then-raise pattern (used in EVERY phase)**
```python
errors = []                  # start with empty list
# ... do work ...
if something_wrong:
    errors.append(CompilerError(Phase.LEXER, "msg", line, col))
# DON'T raise here — continue checking for more errors
# ... more work ...
if errors:                   # only at the END of the phase
    raise CompilerErrorList(errors)
return result                # only reached if zero errors
```
This pattern appears identically in preprocessor, lexer, parser, semantic, IR,
codegen, and validator. It is the single most important pattern in the codebase.

---

### ast_nodes.py — every concept explained

**Why dataclasses for AST nodes**
An AST with 20+ node types would need 20+ `__init__` methods if written manually.
`@dataclass` eliminates this: declare fields, get constructors free. Additionally,
`isinstance(node, IfStmt)` reads like English — pattern matching on node types is
how every phase works: the parser creates nodes, the analyzer switches on types,
the generator switches on types. Dataclasses make this readable and maintainable.

**DataType.UNKNOWN — why it exists**
When the Python parser sees `x = 5`, it doesn't know x's type yet. The literal `5`
is clearly INT, but the variable could be reassigned later. So the parser creates
`VarDecl(name='x', data_type=UNKNOWN, value=Literal(5, INT))`. The semantic
analyzer (Phase 4) then resolves UNKNOWN → INT by looking at the assigned value.
Without UNKNOWN, the parser would need the semantic analyzer's logic — violating
separation of concerns.

**Why ASTNode base class**
All 20 nodes inherit from ASTNode which has a `line: int` field. This means:
1) `isinstance(node, ASTNode)` checks if ANY object is an AST node
2) Every node automatically has source line info for error messages
3) Type hints like `body: list[ASTNode]` express "any statement goes here"
Without a base class, we'd need Union types with all 20 nodes listed.

**Program node — why it has functions AND globals separately**
Python allows code at module level: `x = 5; print(x)` without any function.
C requires everything inside functions. By separating `functions` and `globals`,
the C generator can wrap global statements in an auto-generated `main()` function.
If they were mixed in one list, the generator would need to scan and separate them.

**ForRangeStmt vs ForEachStmt — why two nodes**
ForRangeStmt has `start/stop/step` (numeric bounds) — e.g., `for i in range(10)`.
ForEachStmt has `array_name` (iterate over collection) — e.g., `for x in arr`.
One node with optional fields: every generator needs `if node.array_name: ...`
to detect which kind. Two nodes: `visit_ForRangeStmt` and `visit_ForEachStmt`
are separate methods. The AST expresses MEANING, not syntax.

**PrintStmt.values as list — why not single value**
`print(x, y, z)` is common Python. If values were a single ASTNode, we'd need
nested PrintStmts or a tuple wrapper node. A list naturally represents "print
these things separated by spaces". The C generator maps this to a printf format
string: `printf("%d %f %s\n", x, y, z)` — one format specifier per list element.

**Literal.data_type — why store type inside the literal**
Type inference works bottom-up: the type of `x + y` depends on the types of x and y.
Literals are the BASE CASE: `5` is INT, `3.14` is FLOAT, `True` is BOOL.
If Literal didn't store its type, the semantic analyzer would need a separate
function to infer types from values (`isinstance(5, int) → INT`). Storing it in
the node means type info flows naturally up the tree during analysis.

**BinaryOp recursion — how it handles nested expressions**
`a * b + c` → `BinaryOp('+', BinaryOp('*', Var(a), Var(b)), Var(c))`
The `*` is deeper in the tree (higher precedence), evaluated first.
The `+` is at the root, evaluated last. This tree structure naturally encodes
operator precedence. The parser creates the right nesting by having separate
functions for each precedence level (expression → comparison → term → factor).

---

### lexer/tokens.py — every concept explained

**What is a token**
A token is the smallest meaningful unit of source code. The string `if x > 0` has
four tokens: `IF`, `NAME:x`, `GT`, `NUMBER:0`. Whitespace between tokens is
consumed but not stored. The lexer converts a stream of characters into a stream
of tokens — this is called "lexical analysis" or "scanning".

**Why TokenType is an Enum not strings**
`TokenType.IFF` → Python crash at import. `"IFF"` → silent bug at runtime.
Enums are a closed set: you can iterate `TokenType` to see all valid types.
The parser can exhaustively match on them. Adding a new token type requires adding
it to the Enum — all existing code still works, and new code can handle it.

**Why store line and col in Token**
The parser and semantic analyzer work with tokens, not raw source text.
When the parser sees an unexpected token, it needs to say "Error at line 5, col 12".
Since the parser doesn't have the raw source, the lexer must embed this position
info into each token. Without it, error messages would say "Error somewhere" — useless.

**Why INDENT and DEDENT are token types**
Python uses indentation for blocks. C uses `{` and `}`. To make the parser work
the same way for both, the Python lexer emits INDENT tokens (= block start, like `{`)
and DEDENT tokens (= block end, like `}`). The parser then treats INDENT/DEDENT
exactly like LBRACE/RBRACE. This is how CPython's real lexer works too — it's a
well-established technique called "offside rule tokenization".

---

## PHASE 1 — Preprocessor
The preprocessor is the first stage of the pipeline. It strips comments from
source code so the lexer doesn't need to handle comment syntax.

**What a preprocessor does and why it runs before the lexer**
In production compilers (GCC, Clang), the preprocessor handles `#include`,
`#define`, macro expansion, and conditional compilation. Our preprocessor is
simpler: it only strips comments. It runs BEFORE the lexer because if comments
weren't removed, the lexer would need to handle `#` inside strings vs `#`
starting a comment, `//` as division vs `//` as comment, etc. Separation of
concerns: preprocessor deals with comments, lexer deals with tokens.

**Why comments must be stripped before lexing**
Consider: `x = 5 # this is a comment`. If the lexer sees this raw, it would try
to tokenize `#`, `this`, `is`, `a`, `comment` — all as variable names or unknown
characters. By stripping comments first, the lexer only sees `x = 5 `, which
tokenizes cleanly to `NAME:x, ASSIGN, NUMBER:5`.

**How C multi-line comments differ from Python single-line comments**
Python comments are trivial: `#` to end of line. Always one line.
C block comments `/* ... */` can span multiple lines and can appear in the MIDDLE
of a line: `int /* type */ x = 5;`. The preprocessor must track state (am I inside
a block comment?) and handle the case where `*/` is never found (unclosed comment).
This is why C comment stripping uses a character-by-character state machine while
Python comment stripping works line-by-line.

**Why save stripped comments instead of discarding them**
The UI's Preprocessor modal shows "Comments found: [list]". This serves two purposes:
1) The user can verify their comments were correctly identified (not accidentally
   stripping code that looks like a comment inside a string).
2) It demonstrates the preprocessor's work — in a demo or viva, you can show that
   the preprocessor correctly identified and separated comments from code.

**The unclosed comment error — what happens without this check**
`int x = 5; /* this comment never ends` — without the check, the rest of the file
(including actual code) would be silently consumed as part of the comment. The
program would appear empty to the lexer, producing confusing errors like "empty
source" instead of the real problem. By detecting unclosed `/*`, we give a precise
error: "Unclosed block comment at line 3" — pointing to exactly where the `/*` started.

---

## PHASE 2 — Lexer
The lexer converts raw source text into a stream of tokens. Three lexers are
implemented: PythonLexer, CLexer, and CppLexer (extends CLexer).

**What a lexer does (full explanation)**
The lexer (also called "scanner" or "tokenizer") reads source code character by
character and groups characters into tokens. `if x > 0` becomes four tokens:
`IF`, `NAME:x`, `GT`, `NUMBER:0`. Whitespace between tokens is consumed but not
stored. The lexer also classifies each token: is `if` a keyword or a variable name?
Is `32` a number or two separate characters? This classification is what makes
the parser's job tractable — it works with typed tokens, not raw characters.

**INDENT/DEDENT algorithm — step by step walkthrough**
```
Source:          "if x:\n    y = 1\n    z = 2\nw = 3\n"
indent_stack:    [0]

Line 1: "if x:"        indent=0, stack[-1]=0 → same level → no INDENT/DEDENT
    tokens: IF, NAME:x, COLON, NEWLINE

Line 2: "    y = 1"    indent=4, stack[-1]=0 → 4>0 → push 4, emit INDENT
    stack: [0, 4]
    tokens: INDENT, NAME:y, ASSIGN, NUMBER:1, NEWLINE

Line 3: "    z = 2"    indent=4, stack[-1]=4 → same level → no change
    tokens: NAME:z, ASSIGN, NUMBER:2, NEWLINE

Line 4: "w = 3"        indent=0, stack[-1]=4 → 0<4 → pop 4, emit DEDENT
    stack: [0]
    tokens: DEDENT, NAME:w, ASSIGN, NUMBER:3, NEWLINE

EOF: stack=[0] → only base level, no more DEDENTs needed
    tokens: EOF
```

**Why the indent_stack starts at [0]**
Column 0 represents "no indentation" — the leftmost position. All top-level code
starts at column 0. The stack must always have at least one entry to compare against.
Starting at [0] means the very first line of code doesn't trigger a false INDENT.

**What happens at end-of-file with open blocks**
If the source ends inside an indented block (e.g., last line is inside a function),
the parser expects DEDENT tokens to close those blocks. Without EOF DEDENTs, the
parser would think the function body never ended. `_close_indents()` pops all
remaining levels from the indent stack, emitting one DEDENT per level.

**Why reject mixed tabs and spaces**
A tab might be 4 spaces or 8 spaces depending on the editor. The string
`"\t    x"` has indent=5 in our counter but could look like indent=8+4=12 in some
editors. This ambiguity makes it impossible to determine nesting reliably.
CPython also rejects mixed tabs/spaces (TabError). We follow the same rule.

**What is a bad dedent and why it is an error**
```
if x:
    y = 1       ← indent 4
  z = 2         ← indent 2 (not in stack!)
```
After popping 4, the stack has [0]. But the new indent is 2, not 0. This means
the programmer used an indentation level that was never opened. It's like writing
`}` in C without a matching `{`. Our lexer reports: "Inconsistent dedent".

**Why CLexer does not need an indent stack**
C uses explicit `{` and `}` for blocks. Whitespace (spaces, tabs, newlines) is
meaningless between tokens — it's just a separator. The CLexer emits LBRACE and
RBRACE tokens for `{` and `}`. The parser treats these exactly like the Python
parser treats INDENT and DEDENT, but no stack tracking is needed.

**Why CppLexer extends CLexer instead of being separate**
C++ is a superset of C (almost). The tokenization logic is 95% identical.
CppLexer only adds: `cout` keyword, `cin` keyword, `::` operator. By extending
CLexer and overriding `get_keywords()` and `get_two_char_ops()`, CppLexer reuses
all tokenization code without any duplication. This is the Template Method pattern:
the base class defines the algorithm, subclasses customize specific steps.

---

## PHASE 3 — Parser
Three parsers convert token streams to ASTs: PythonParser, CParser, CppParser.
All produce the same language-neutral AST node types.

**What a parser does — from tokens to tree**
The parser takes a flat list of tokens (from the lexer) and builds a TREE that
represents the program's structure. `IF NAME:x GT NUMBER:0 COLON NEWLINE INDENT
RETURN NAME:x NEWLINE DEDENT` becomes `IfStmt(BinaryOp(">", Var("x"), Literal(0)),
[ReturnStmt(Var("x"))], [])`. The tree captures nesting: the ReturnStmt is INSIDE
the IfStmt's body. This nesting is invisible in a flat token list.

**What is recursive descent parsing**
Each grammar rule becomes a function. `_parse_if()` calls `_parse_expression()`
for the condition, then `_parse_block()` for the body. `_parse_expression()` calls
`_parse_comparison()`, which calls `_parse_addition()`, etc. This mutual recursion
mirrors the grammar structure — hence "recursive descent". The parser "descends"
through rule functions to build the tree bottom-up.

**How operator precedence is handled (the grammar rule nesting trick)**
`2 + 3 * 4` must parse as `2 + (3 * 4)`, not `(2 + 3) * 4`. We achieve this by
nesting functions: `_parse_addition` calls `_parse_multiplication` for its operands.
Since multiplication is parsed DEEPER (bound TIGHTER), `3 * 4` becomes a single
BinaryOp before addition ever sees it. The precedence chain is:
`expression → or → and → not → comparison → addition → multiplication → unary → primary`
Higher in the chain = lower precedence. Primary (literals, variables) = highest.

**How INDENT/DEDENT replace braces in python_parser**
In `_parse_block()`, the Python parser does `_expect(INDENT)` then loops until
`DEDENT`, then `_expect(DEDENT)`. The C parser does `_expect(LBRACE)` then loops
until `RBRACE`, then `_expect(RBRACE)`. The logic is identical — only the delimiter
tokens differ. This is why the lexer emits INDENT/DEDENT: it unifies the block
structure so both parsers can use the same pattern.

**Why all three parsers produce the same AST node types**
This is the KEY to transpilation. `def add(x,y): return x+y` (Python) and
`int add(int x, int y) { return x+y; }` (C) look nothing alike syntactically,
but both produce `FunctionDecl(name="add", params=[...], body=[ReturnStmt(...)])`.
The generators then read this same AST and emit their target language. If each
parser used different node types, you'd need N×M translation functions instead of
N parsers + M generators.

**Error recovery — synchronisation tokens**
When the parser encounters an unexpected token, it doesn't crash — it records a
CompilerError and skips to a "synchronization point": NEWLINE (Python) or
SEMICOLON (C). This lets the parser continue and find MORE errors in the rest
of the file. Without recovery, the first syntax error would hide all others.

**How ForRangeStmt vs ForEachStmt is detected in the parser**
In Python: `for NAME in ...`. If RANGE follows IN → ForRangeStmt (numeric bounds).
If NAME follows IN → ForEachStmt (iterate over array). The parser peeks at the
token after IN to decide. In C: all `for(;;)` loops → ForRangeStmt (C has no
native for-each). In C++: CppParser inherits C's for-loop handling.

---

## PHASE 4 — Semantic Analyzer
The semantic analyzer walks the AST and checks that the program **means** something
valid — not just that it is syntactically correct. File: `semantic/analyzer.py` (365 lines).

**What semantic analysis does that parsing cannot**
The parser checks STRUCTURE: is `if x > 0:` followed by an indented block? Yes → valid
syntax. But the parser never asks: "was `x` declared?" or "is `x` a number that can be
compared with `>`?" Those are MEANING questions. `print(z)` parses perfectly — it's a
PrintStmt with a Var("z"). But if z was never declared, the program will crash at runtime.
The semantic analyzer catches this at compile time. It also checks: are function arguments
the right count and type? Does a return statement match the function's return type? Is an
array index an integer? These are all questions about meaning, not structure.

**What a symbol table is and why it is needed**
A symbol table is a dictionary mapping variable/function names to their metadata:
`{"x": {"kind": "var", "type": INT, "line": 3}}`. Every time a VarDecl is analyzed,
the name is added to the symbol table. Every time a Var is used in an expression, the
analyzer looks it up. If it's not found → "Undeclared variable" error. If it IS found,
the analyzer knows its type and can check operations on it. Without a symbol table,
the analyzer would have no memory of what was declared where. The flat `symbol_table`
dict is also returned to the UI for display in the Semantic modal.

**What a scope stack is — full explanation with example**
A scope stack is a `list[dict]` where each dict represents a scope level. Index 0 is the
global scope. When entering a function, a new dict is pushed; when exiting, it's popped.
```
scope_stack = [
  {"add": {kind:func, ...}},          ← global scope (index 0)
  {"x": {kind:var, type:INT}, "y":..} ← function scope (index 1, inside add())
]
```
Lookup searches from top to bottom: `_lookup("x")` checks index 1 first, finds it.
`_lookup("add")` checks index 1, not found, checks index 0, found. This means local
variables shadow globals with the same name — exactly like Python and C. When we
`_exit_scope()`, the function dict is popped, and x/y are no longer visible.
For-loops also get their own scope: the loop variable is declared inside it, so it
doesn't leak into the enclosing scope.

**Two-pass analysis — why it is needed for Python source**
In Python, you can call a function before its definition:
```python
result = add(3, 4)    # line 1 — add() not defined yet
def add(x, y):        # line 2 — defined here
    return x + y
```
In a single pass, when the analyzer reaches line 1, `add` is not in the symbol table
→ "Undeclared function" error. But the program is valid Python! Pass 1 solves this by
scanning ALL FunctionDecl nodes first, registering their signatures (name + param count)
in the global scope. Then Pass 2 walks the full AST — when it encounters `add(3, 4)`,
the function is already registered. C doesn't need this: C mandates define-before-use,
so a single pass suffices (and is what real C compilers do).

**Pass 1 — exactly what it collects and why**
Pass 1 (`_pass1`) iterates `program.functions` only. For each FunctionDecl, it:
1. Checks for duplicate function names (error if already registered)
2. Extracts param info: `[(name, data_type)]` — types may be UNKNOWN for Python source
3. Creates a func entry dict with kind, params, return_type, and a reference to the
   AST node (`"decl": func`) for on-demand body analysis later
4. Stores in `self.functions` (quick lookup) and `self.scope_stack[0]` (global scope)
5. Records in `self.symbol_table` for UI display
This is intentionally lightweight — no body analysis, no type inference. Just signatures.

**Pass 2 — full walkthrough**
Pass 2 (`_pass2`) does two things in order:
1. Analyzes global statements first. When a function call like `add(3, 4)` is encountered,
   `_resolve_call` infers param types from the arguments (x=INT, y=INT), updates the
   function registry, and triggers ON-DEMAND body analysis of `add()`. This determines
   the return type (INT), which is used to type the variable `result`.
2. Analyzes any function bodies not yet triggered by calls (e.g., functions never called
   in global scope). These are analyzed with whatever param types are known.
The on-demand approach solves the chicken-and-egg problem: we need arg types to know
param types, and we need param types to know the return type. By analyzing the call site
first, then the function body, we get both.

**Type checking — how it works on BinaryOp nodes**
`_resolve_binop` determines the result type of `left op right`:
1. Recursively resolve left's type and right's type
2. If op is a comparison (`==`, `<`, etc.) or logical (`and`, `or`) → result is BOOL
3. Otherwise (arithmetic: `+`, `-`, `*`, `/`) → apply promotion via `_promote()`:
   - INT + INT → INT
   - INT + FLOAT → FLOAT (either side being FLOAT promotes the result)
   - FLOAT + FLOAT → FLOAT
   - UNKNOWN + X → X (best-guess: use the known type)
This is recursive: `a * b + c` → BinaryOp('+', BinaryOp('*', a, b), c). The inner
`*` resolves first, its result type feeds into the outer `+`.

**Silent INT→FLOAT promotion — how it is implemented**
In `_do_assign`, when assigning a FLOAT value to an INT variable:
```python
if sym["type"] == DataType.INT and vt == DataType.FLOAT:
    sym["type"] = DataType.FLOAT  # update the variable's type in scope
```
The variable's type is UPGRADED in the scope dict. No error is raised. This matches
Python semantics: `x = 5; x = x + 3.14` is valid — x becomes a float. The updated
type persists in the symbol table, so when the C generator later emits code for x,
it uses `float x = 5;` instead of `int x = 5;`. The reverse (FLOAT var, INT value)
is also allowed silently because INT values fit in FLOAT variables.

**ForEachStmt validation — what checks are needed**
`_do_for_each` performs three checks:
1. The array name must exist in scope: `_lookup(node.array_name)` — if None, error
   "Undeclared array"
2. The symbol must actually be an array: `sym["kind"] != "array"` — if it's a regular
   variable, error "For-each only supported over declared arrays"
3. The loop variable gets the array's element type: if `arr` is `array(int, 5)`, then
   `x` in `for x in arr` is declared as INT in the loop's scope
The loop body runs in its own scope (pushed before, popped after), so the loop variable
doesn't leak into the enclosing scope.

---

## PHASE 5 — IR Generator
The IR Generator validates the AST's structural integrity and converts it to a
JSON-serialisable dictionary for the frontend. File: `ir/ir_generator.py` (294 lines).

**Why have an IR phase if the AST is already the IR**
In production compilers, the IR is a separate representation (TAC, SSA, LLVM IR) that
sits between the frontend and backend. Our IR is the AST itself — a "neutral AST".
Why? TAC would flatten `return x + y` into `t1 = x + y; return t1`, destroying the
program's structure. LLVM IR requires SSA form and the LLVM toolchain — a black box
that can't be explained in a viva. Our AST preserves the program's high-level structure
so that code generators produce readable, idiomatic output. The trade-off: no
machine-level optimizations (constant folding, dead code elimination). This is
acceptable because optimization is out of scope for this transpiler.

So why have this phase at all? Three reasons:
1. **Integrity gate**: It verifies the AST is well-formed before codegen processes it.
   If the semantic analyzer has a bug that produces a FunctionDecl with no name, or a
   BinaryOp with a missing left operand, this phase catches it with a clear error.
2. **Serialisation**: `to_dict()` converts the AST to JSON for the UI's IR modal.
3. **Architectural boundary**: Everything before Phase 5 is source-language-dependent.
   Everything after is target-language-dependent. This phase marks the transition point.

**What to_dict() does and why it is needed**
`to_dict()` recursively walks the AST and converts each node to a JSON-serialisable
Python dict. Each node becomes `{"node": "TypeName", ...fields...}`. DataType enum
values are converted to strings via `.value` (e.g., `DataType.INT` → `"int"`), because
JSON cannot encode Python Enum objects directly. List fields (like `body`, `params`)
become JSON arrays. Optional fields that are None become JSON `null`.

The frontend receives this dict as JSON in the `/compile` API response. The IR modal
displays it as a coloured node dump — the user can inspect the exact tree structure
that will be fed to the code generator. This transparency is valuable for debugging
(did the parser build the right tree?) and for demonstration (you can show the
examiner exactly what the compiler understood from the source code).

Without `to_dict()`, the UI would have no way to display the internal representation.
Python dataclass objects can't be sent over HTTP — they must be serialised to JSON first.

**Why this is the checkpoint for target language selection**
In the UI, the user writes source code, selects the source language, and clicks
"Compile". This runs Phases 1–5: preprocess, lex, parse, analyse, generate IR.
All of these phases are SOURCE-dependent — they interpret the code's structure and
semantics according to the source language's rules. Only after all five phases
succeed does the user choose a TARGET language (Python, C, or C++) and click
"Generate". This triggers Phase 6 (codegen), which is TARGET-dependent.

The IR phase is the pivot point. If it passes, the compiler has fully understood the
source program. If it fails, something went wrong in the frontend pipeline and codegen
should not run on a broken tree. This is why the frontend shows the IR phase result
before enabling the target language selector.

**What integrity checking means in this context**
Integrity checking verifies that every AST node has its required fields populated
correctly. The semantic analyzer (Phase 4) already checked semantics (types, scopes,
declarations), but it didn't check whether the AST's STRUCTURE is valid. Examples
of structural integrity violations:
- A FunctionDecl with an empty `name` field (the parser should have set it)
- A BinaryOp with `op=""` (should be "+", "-", etc.)
- An IfStmt with `condition=None` (every if needs a condition)
- A ForRangeStmt with no `stop` expression (range needs an upper bound)
- A non-ASTNode object inside the tree (e.g., a raw string instead of a Var node)

The integrity checker walks every node recursively, using the same isinstance-dispatch
pattern as the semantic analyzer. For each node type, it checks specific required
fields. All violations are collected into the `errors` list, and a CompilerErrorList
is raised once at the end — following the project-wide collect-then-raise pattern.

The `generate()` method returns the SAME Program object it received. It does not
transform or copy the AST. This is intentional: our IR IS the AST. The only purpose
of `generate()` is validation, not transformation.

---

## PHASE 6 — Code Generators
Three generators convert the language-neutral AST to target source code:
PythonGenerator, CGenerator (extended by CppGenerator).

**What a code generator does — tree to text**
The code generator walks the AST recursively and emits text in the target language.
Each AST node type has a corresponding generation method. `VarDecl(name='x',
data_type=INT, value=Literal(5, INT))` becomes `"x = 5"` in Python or `"int x = 5;"`
in C. The generator doesn't need to understand the source language — it only reads
the language-neutral AST. This is why N parsers + M generators gives N×M translations
with only N+M code paths, instead of N×M separate translators.

**How indent_level works in python_generator**
Python uses indentation for blocks, not braces. `indent_level` is an integer counter
starting at 0. Each `_emit(line)` prepends `"    " * indent_level` to the line.
When entering a block (function body, if body, for body), we increment indent_level.
When exiting, we decrement. This produces correct Python indentation:
```
indent_level=0: def add(x, y):
indent_level=1:     return (x + y)
indent_level=0: print(add(3, 4))
```
CGenerator uses the same counter, but for cosmetic formatting — C doesn't require it.

**Why python_generator omits type annotations**
Python is dynamically typed: `x = 5` is valid Python, `int x = 5` is not. The AST
stores types in VarDecl.data_type, but the Python generator ignores them — it only
uses the name and value. The C generator reads data_type to emit `int x = 5;`. This
is an example of the same AST node being rendered differently per target language.

**How build_format_string works in c_generator**
`printf` needs a format string: `printf("%d %f\n", x, y)`. The generator builds it
dynamically from the PrintStmt.values list. For each value, `_infer_type()` determines
its DataType. FMT_SPEC maps: INT→`%d`, FLOAT→`%f`, BOOL→`%d`, STR→`%s`. The format
specifiers are joined with spaces and `\n` is appended. The actual values are passed
as comma-separated arguments after the format string.

**Why #include is added automatically by c_generator**
C requires `#include <stdio.h>` for printf/scanf. The user's source code (Python)
has no includes. The generator's `_emit_preamble()` adds them automatically. This
is a target-language detail that doesn't exist in the AST. CppGenerator overrides
this to emit `#include <iostream>` and `using namespace std;` instead.

**ForRangeStmt → C for loop — exact translation logic**
`ForRangeStmt(var='i', start=0, stop=Var('n'), step=1)` becomes:
- Python: `for i in range(n):` (simplified from range(0, n, 1))
- C:      `for (int i = 0; i < n; i += 1) { ... }`
The Python generator simplifies: `range(0, n, 1)` → `range(n)`, `range(a, b, 1)` →
`range(a, b)`. The C generator always emits the full form for clarity.

**ForEachStmt → C for loop — the _i counter trick**
C has no native for-each. `for x in arr:` becomes:
`for (int _i = 0; _i < arr_size; _i++) { int x = arr[_i]; ... }`
The generator looks up `arr` in its symbol table to get the size. `_i` is a generated
variable name (underscore prefix avoids collision with user variables). Inside the loop,
a local variable `x` is declared and assigned `arr[_i]` on each iteration.

**Why cpp_generator extends c_generator**
C++ is mostly a superset of C. Function declarations, variable declarations, for loops,
while loops, if/else, expressions — all use the same C syntax. Only I/O differs:
`printf` → `cout <<`, `scanf` → `cin >>`. CppGenerator inherits ALL generation methods
from CGenerator and overrides only three: `_emit_preamble()`, `_gen_print()`,
`_gen_input()`. This is 54 lines vs 272 — zero code duplication.

**Round-trip test — why Python→Python is the best first test**
Python→Python means the source and target are the same language. If the generated output
produces different behavior than the original, we know the pipeline has a bug — not a
translation issue. We exec() both the original and the generated code and compare stdout.
The test `def add(x,y): return x+y; print(add(3,4))` must produce "7" from both.
This isolates the pipeline from cross-language complications.

---

## PHASE 7 — Validator
Dynamic validation: run source + target code, compare stdout to verify translation.

**What dynamic validation means vs static validation**
Static validation (Phase 4, semantic analyzer) checks code WITHOUT running it: "Is this
variable declared? Do these types match?" Dynamic validation RUNS the code and checks if
the OUTPUT is correct. This catches bugs that static analysis cannot: for example, if the
C generator builds the wrong format string, `printf` might print garbage. Static analysis
sees valid C code; dynamic validation sees wrong output and reports FAIL. Dynamic
validation is the ultimate test: if both sides produce the same output, the translation
is correct for that input.

**Why subprocess instead of exec() for all languages**
`exec()` runs Python code in the current process — a bug in generated code (infinite loop,
exception) would crash the compiler itself. `subprocess.run()` runs code in an ISOLATED
process with a timeout. If it hangs → timeout kills it. If it crashes → returncode != 0.
For C/C++, there's no choice: gcc must compile to a binary, and the binary must run as
a separate process. Using subprocess for Python too gives uniform error handling: timeout,
returncode, stderr capture — all work the same way regardless of language.

**How float comparison with tolerance works**
`print(1/3)` in Python outputs `0.3333333333333333`. In C, `printf("%f", 1.0/3.0)` outputs
`0.333333`. Different string representations, same mathematical value. `_float_compare`
tries to parse both strings as floats: `abs(float(a) - float(b)) < 1e-6`. If the
difference is less than one millionth, they're considered equal. If either string isn't
a valid float (e.g., "hello"), `ValueError` is caught and the comparison returns False,
falling through to exact string matching.

**How test inputs are passed as stdin**
Programs with `scanf`/`input()` need stdin data. The UI sends `test_inputs` as a list of
strings (e.g., `["42", "3.14"]`). The validator joins them with newlines: `"42\n3.14\n"`.
This string is passed as `subprocess.run(input=...)` — Python feeds it to the child
process's stdin. Both source and target receive the SAME input, so their outputs should
match. If no test_inputs are provided, stdin is empty — programs with input statements
will block until timeout and fail.

**What has_input() does and why it is needed before running**
`has_input(program)` walks the AST recursively, checking for any `InputStmt` node. If
found, it returns True. The UI uses this BEFORE showing the validate button: if the
program has input statements, the UI prompts the user to enter test input values.
Without this check, the user might click "Validate" without providing inputs, causing
both processes to hang waiting for stdin until the timeout kills them — a confusing
experience. The check is done on the AST (not the source text) so it works regardless
of whether the source was Python (`input()`), C (`scanf`), or C++ (`cin`).

---

## PHASE 8 — Web UI
Phase 8 connects the backend compiler pipeline to a browser-based user interface.

**Why Flask for the backend**
Flask is a micro-framework that is perfect for a 3-route API like this. It requires zero
boilerplate (no complex project structures like Django) and handles JSON requests and
static file serving natively. Since the compiler's logic is all in pure Python, Flask
simply acts as a lightweight wrapper to expose that logic to the web.

**The three routes — what each one does**
1. `POST /compile`: Runs Phase 1 to 5. It takes source code and returns the results
   of each stage. It implements the "first-fail" rule: if any stage fails, it stops
   and marks the rest as "blocked", preventing codegen from running on an invalid tree.
2. `POST /generate`: Runs Phase 6. It takes the validated source info and target
   language selection, then returns the final generated code.
3. `POST /validate`: Runs Phase 7. It takes both source and target code, executes
   them in isolated processes, and compares their outputs for semantic equivalence.

**Why single HTML file**
A single HTML file containing HTML, CSS, and JS ensures the project has ZERO frontend
dependencies. No React, no npm, no build steps. It opens in any browser and is fully
auditable. This makes the project portable and easy to explain during a viva — the
entire UI logic is in one place.

**How the modal system works (open/close/populate)**
The UI uses a generic modal overlay. When a phase is clicked, `showModal(id)` is called.
It looks up the result for that phase in the `state` object, generates the HTML
content (like token pills or symbol table pre-blocks), and sets `display: flex` on
the overlay. Clicking the '×' or the background sets `display: none`. This is a clean
and efficient way to show detailed phase data without leaving the main page.

**Why new compile wipes all state — the stale data problem**
If the user edits the source code and clicks "Compile", the results of the PREVIOUS
compilation are now "stale" — they no longer match the code in the editor. To prevent
confusion (like seeing a "Pass" dot for code that now has an error), the UI resets
all phase statuses to "pending" or "blocked" immediately when the "Compile" button is
clicked. Only the new results are shown.

**How the AST text tree is displayed**
For Phase 3 (Parser), the UI displays the `ast_text` provided by the backend. This text
is generated by the `Program.__str__` method, which recursively visits each node to
create a human-readable indented tree structure. This shows the hierarchical nature
of the code (which statement is inside which block) in a way that is easy to read.

**How token pills are colored by type**
In Phase 2 (Lexer), the UI receives a list of token dicts. For each token, a `<span>`
is created with a CSS class matching the token's type (e.g., `class="pill KEYWORD"`).
The CSS defines specific background and text colors for each category (keywords, names,
numbers, etc.). This makes the token stream visually scannable and helps the user
distinguish between different types of lexical units.

**The blocked phase state — how it is enforced in JS**
The `state.results` object stores the status of each phase. When rendering the phase list,
any phase with status "blocked" is given a `blocked` CSS class. This class applies
`opacity: 0.5` and `cursor: not-allowed`. Additionally, the `onclick` handler for
the phase row returns early if the status is "blocked", preventing the modal from
opening for phases that haven't run.

---

## VIVA Q&A — General Questions

### Q: What is the difference between a compiler and an interpreter?
A compiler translates the entire source program to another form before execution.
An interpreter executes the program line by line directly.
Our transpiler is a compiler: it translates the whole program to the target
language. The validator then runs the result — that is interpretation/execution,
not part of the compiler itself.

### Q: Why do you need all these phases? Can you go directly from source to target?
You could write a Python→C converter that uses string manipulation and regex.
It would break on any non-trivial program. The multi-phase approach builds a
complete semantic model of the program first — the AST — so that code generation
works from understood meaning, not from text patterns. This is why real compilers
like GCC and Clang use the same pipeline.

### Q: What is the time complexity of your compiler?
Lexer: O(n) where n = characters in source
Parser: O(n) where n = tokens (recursive descent on unambiguous grammar is linear)
Semantic: O(n) where n = AST nodes
Codegen: O(n) where n = AST nodes
Total: O(n) — linear in source size. This is optimal.

### Q: What would you add if you had more time?
1. Optimization phase between IR and codegen (constant folding: 2+3 → 5 at compile time)
2. Better error recovery in the parser (continue after errors to find more)
3. Support for structs (would require extending ast_nodes and all generators)
4. Type inference for function return types instead of requiring annotation

### Q: Why does the validator actually run the code? Isn't that dangerous?
The code runs in a subprocess with a timeout. It cannot access files outside
the temp directory. For a demonstration compiler on trusted input this is
acceptable. In a production system you would use sandboxing (Docker, seccomp).

### Q: How does your compiler handle x = 5 followed by x = x + 3.14?
Phase 3 (parser): first x=5 → VarDecl(x, UNKNOWN, Literal(5,INT))
Phase 4 (semantic pass 2): 
  - sees VarDecl → declares x as INT in symbol table
  - sees AssignStmt x = x + 3.14 → resolves BinaryOp type → FLOAT
  - x is INT but value is FLOAT → trigger silent promotion
  - update symbol table: x type → FLOAT
Phase 6 (codegen):
  - C generator sees x is FLOAT → emits "float x = 5;" not "int x = 5;"
  - This is correct: if x ends up float, it should be declared float in C

### Q: What happens if the same variable name is used in two different functions?
The scope stack handles this. Each function push a new scope dict.
Variables are looked up from top of stack downward.
Two functions each having local variable x: they live in different scope dicts,
no conflict. Removing the scope stack and using a flat dict would cause false
redeclaration errors for every shared variable name.
