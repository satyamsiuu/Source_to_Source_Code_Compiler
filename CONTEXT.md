# CONTEXT.md — Compressed Codebase State
# HOW TO READ:
#   Resuming?        → read LAST_PHASE_DIFF only (~200 tokens)
#   Full picture?    → read TOTAL_STATE (~800 tokens)
#   Specific phase?  → read PHASE_SNAPSHOTS:PHASE_N
# Agent: update BOTH sections after every phase.

---

## LAST_PHASE_DIFF
```
phase:    Phase 5 — IR Generator
status:   COMPLETE
added:    ir/ir_generator.py (294L)
changed:  —
deleted:  —
next:     Phase 6 → write codegen/python_generator.py, c_generator.py, cpp_generator.py
WORKFLOW: ALWAYS ask user "Ready for Phase N?" before starting any new phase. Never auto-proceed.
```

---

## TOTAL_STATE
```
project:      source-to-source compiler Python↔C↔C++
stack:        Python + Flask + single HTML file
phases_done:  6/9
files_exist:  12  (+ ir/ir_generator.py)

key_decisions:
  ir=neutral_AST        (not TAC — preserves structure for readable output)
  parser=recursive_desc (not PLY/ANTLR — fully traceable, explainable)
  frontend=single_html  (not React — zero setup, one file)
  backend=flask         (not FastAPI — 3 routes, minimal boilerplate)
  for_loops=two_nodes   (ForRangeStmt + ForEachStmt, not one ForStmt)
  print=multi_arg       (PrintStmt.values:list, not single value)
  semantic=two_pass     (Python source only — allows call-before-definition)
  type_promo=silent     (INT+FLOAT→FLOAT, no error)
  empty_array=syntax    (array(int,5) — provides size+type for C codegen)

frozen_after_phase0:
  errors.py, ast_nodes.py, lexer/tokens.py

error_pattern (ALL phases):
  errors = []
  # ... work ...
  if something_wrong: errors.append(CompilerError(...))
  if errors: raise CompilerErrorList(errors)
  return result

scope_rules:
  global: functions + global vars
  function: params + local vars
  for-loop var: scoped to loop body
  nested functions: HARD REJECT

type_rules:
  INT+INT→INT, INT+FLOAT→FLOAT, FLOAT+FLOAT→FLOAT
  wrong-type assign → CompilerError (no coerce except INT→FLOAT)
  x type upgrades in symbol table when INT→FLOAT promotion occurs
```

---

## PHASE_SNAPSHOTS

### PHASE_0 [PENDING]
```
files: errors.py, ast_nodes.py, lexer/tokens.py
exports:
  errors.py     → Phase(Enum), CompilerError(dataclass), CompilerErrorList(Exception)
  ast_nodes.py  → DataType(Enum), ASTNode, Program, FunctionDecl, Param,
                  VarDecl, ArrayDecl, AssignStmt, ArrayAssign,
                  IfStmt, WhileStmt, ForRangeStmt, ForEachStmt,
                  ReturnStmt, PrintStmt, InputStmt, FunctionCall,
                  BinaryOp, UnaryOp, Var, ArrayAccess, Literal
  tokens.py     → TokenType(Enum), Token(dataclass)
status: COMPLETE ✅ — test passed, all imports verified
```

### PHASE_1 [PENDING]
```
file: preprocessor/preprocessor.py
class: Preprocessor
method: process(source:str, lang:str) → {"clean_source":str, "comments":list[str]}
strips: # (python), // (c/cpp), /* */ (c/cpp)
error: unclosed /* → CompilerError(Phase.PREPROCESSOR)
status: COMPLETE ✅ — test passed, Python/C/C++ comments stripped correctly
```

### PHASE_2 [PENDING]
```
files: lexer/python_lexer.py, c_lexer.py, cpp_lexer.py
PythonLexer.tokenize(source:str) → list[Token]
  uses indent_stack=[0] for INDENT/DEDENT generation
  errors: mixed_tabs, bad_dedent, unknown_char, unterminated_string
CLexer.tokenize(source:str) → list[Token]
  no indent stack, uses { } for blocks
CppLexer(CLexer): adds cout,cin,:: tokens
status: COMPLETE ✅ — INDENT/DEDENT verified, bad dedent raises, C/C++ tokenization works
```

### PHASE_3 [PENDING]
```
files: parser/python_parser.py, c_parser.py, cpp_parser.py
all:   recursive descent, collect errors → CompilerErrorList
PythonParser.parse(tokens) → Program  [INDENT='{', DEDENT='}']
CParser.parse(tokens)      → Program  [LBRACE='{', RBRACE='}']
CppParser(CParser):        overrides cout→PrintStmt, cin→InputStmt
output: Program(ast_nodes) — same node types regardless of source language
status: COMPLETE ✅ — all 3 parsers produce correct AST, canonical test verified
```

### PHASE_4 [PENDING]
```
file: semantic/analyzer.py
class: SemanticAnalyzer
analyze(program, source_lang) → (annotated_program, symbol_table:dict)
  python source → two passes
    pass1: collect FunctionDecl signatures → global scope
    pass2: full type+scope check
  c/cpp source → one pass (define-before-use enforced)
scope_stack: list[dict]  {name:(DataType,line)}
enter_scope()/exit_scope(): push/pop scope_stack
errors caught: undeclared_var, redeclaration, type_mismatch,
               wrong_arg_count, return_type_mismatch,
               array_index_not_int, array_oob, void_in_expr,
               foreach_on_non_array
status: COMPLETE ✅ — both tests passed (PASS: symbol table correct, FAIL: 2 errors caught)
```

### PHASE_5 [COMPLETE]
```
file: ir/ir_generator.py (294L)
class: IRGenerator
generate(program) → Program  [integrity check, no transformation — returns same object]
to_dict(program)  → dict     [JSON-serialisable for UI display]
  format: {"node":"FunctionDecl","name":"add","params":[...],"body":[...]}
validation: checks every node type has required fields (name, condition, etc.)
this phase = checkpoint: analysis done, codegen not started
user picks target language after this phase in UI
status: COMPLETE ✅ — generate() returns same Program, to_dict() JSON round-trips
```

### PHASE_6 [PENDING]
```
files: codegen/python_generator.py, c_generator.py, cpp_generator.py
all:   generate(program:Program) → str

PythonGenerator:
  indent via indent_level counter ("    "*indent_level)
  VarDecl     → "name = value"
  FunctionDecl→ "def name(params):\n" + body
  PrintStmt   → "print(v1, v2, ...)"
  InputStmt   → "name = type(input(prompt))"
  ForRangeStmt→ "for i in range(start, stop, step):"
  ForEachStmt → "for x in arr:"

CGenerator:
  prepends #include <stdio.h>
  VarDecl     → "int name = value;"
  FunctionDecl→ "int name(int x) { body }"
  PrintStmt   → printf with dynamic format string
    build_format_string([INT,FLOAT]) → "%d %f\n"
  InputStmt   → scanf with format string
  ForRangeStmt→ "for (int i=start; i<stop; i+=step)"
  ForEachStmt → "for (int _i=0; _i<size; _i++) { type x=arr[_i]; }"

CppGenerator(CGenerator):
  prepends #include <iostream>\nusing namespace std;
  PrintStmt   → "cout << v1 << \" \" << v2 << endl;"
  InputStmt   → "cin >> name;"
status: PENDING
```

### PHASE_7 [PENDING]
```
file: validator/validator.py
class: Validator
validate(src_code,src_lang,tgt_code,tgt_lang,test_inputs=[]) → dict
  returns: {passed:bool, source_out:str, target_out:str, diff:str}
has_input(program) → bool  [checks IR for any InputStmt node]
run_python(code,inputs) → str   [subprocess python3]
run_c(code,inputs)      → str   [gcc compile + run]
run_cpp(code,inputs)    → str   [g++ compile + run]
compare(a,b) → bool
  try float parse both → compare with tolerance 1e-6
  fallback: strip whitespace + exact match
status: PENDING
```

### PHASE_8 [PENDING]
```
files: main.py, frontend/index.html
routes:
  POST /compile  → Phase1-5, returns JSON with all phase results
  POST /generate → Phase6, needs {ir,target_language}
  POST /validate → Phase7, needs {src,src_lang,tgt,tgt_lang,inputs}
UI:
  layout:  editor left 40%, phases right 60%
  phases:  7 rows, dot+name+badge, click→modal
  modals:  phase-specific content, × to close
  tokens:  TYPE:value colored pills
  AST:     text tree default, toggle SVG graphical
  blocked: grey, unclickable
  new_compile: wipes all state first
status: PENDING
```

---

## HARD_REJECTION_LIST
```
pointers           → "Pointers are not supported"
classes/structs    → "Classes and structs are not supported"
templates          → "Templates are not supported"
multiple_files     → "Multiple files are not supported"
import/include     → "Import statements are not supported"
try/except         → "Exception handling is not supported"
lambda             → "Lambda expressions are not supported"
list_comprehension → "List comprehensions are not supported"
global_keyword     → "The global keyword is not supported"
nested_functions   → "Nested functions are not supported"
foreach_non_array  → "For-each only supported over declared arrays"
empty_bracket_arr  → "Use array(type, size) syntax for array declaration"
string_ops         → "String operations are not supported (string literals in print only)"
```
