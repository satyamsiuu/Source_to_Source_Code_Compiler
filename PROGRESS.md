# PROGRESS.md — Build Tracker
# Agent: update after EVERY phase. Never skip.
# Reader: check statuses + test results only for quick orientation.

STATUS_KEY: [ ]=not started  [~]=in progress  [x]=complete  [!]=blocked  [E]=has errors

---

OVERALL: 3/9 phases complete
LAST_COMPLETED_PHASE: Phase 2
LAST_UPDATED: 2026-04-25

---

## PHASE 0 — Foundation
Status: [x]
Files:
  [x] errors.py          target:55   actual:86
  [x] ast_nodes.py       target:175  actual:326
  [x] lexer/tokens.py    target:95   actual:132
Test: python -c "from errors import CompilerError,Phase; from ast_nodes import Program; from lexer.tokens import Token,TokenType; print('OK')"
Test result: PASS ✅
Completed: 2026-04-25

---

## PHASE 1 — Preprocessor
Status: [x]  |  Depends: Phase 0
Files:
  [x] preprocessor/preprocessor.py  target:150  actual:218
Test:
  input:  "x = 1  # comment\ny = 2"  lang:"python"
  expect: clean has no "# comment", comments==["# comment"]
Test result: PASS ✅
Completed: 2026-04-25

---

## PHASE 2 — Lexer
Status: [x]  |  Depends: Phase 1
Files:
  [x] lexer/python_lexer.py  target:260  actual:294
  [x] lexer/c_lexer.py       target:225  actual:257
  [x] lexer/cpp_lexer.py     target:85   actual:64
Test python INDENT/DEDENT:
  input:  "if x > 0:\n    return x\n"
  expect: INDENT and DEDENT tokens present in output
Test bad dedent (must raise):
  input:  "if x:\n    y=1\n  z=2\n"
  expect: CompilerErrorList raised
Test result: PASS ✅
Completed: 2026-04-25

---

## PHASE 3 — Parser
Status: [ ]  |  Depends: Phase 2
Files:
  [ ] parser/python_parser.py  target:400  actual:0
  [ ] parser/c_parser.py       target:380  actual:0
  [ ] parser/cpp_parser.py     target:110  actual:0
Test:
  input:  tokens from "if x > 0:\n    return x\n"
  expect: Program containing IfStmt with BinaryOp and ReturnStmt
Test result: PENDING
Completed: —

---

## PHASE 4 — Semantic Analyzer
Status: [ ]  |  Depends: Phase 3
Files:
  [ ] semantic/analyzer.py  target:320  actual:0
Test PASS:
  input:  "def add(x,y):\n    return x+y\nresult=add(3,4)\nprint(result)\n"
  expect: no errors, symbol table has add/x/y/result
Test FAIL (must catch 2 errors):
  input:  "print(z)\nx=1\nx=2\n"
  expect: [undeclared 'z', redeclaration 'x']
Test result: PENDING
Completed: —

---

## PHASE 5 — IR Generator
Status: [ ]  |  Depends: Phase 4
Files:
  [ ] ir/ir_generator.py  target:200  actual:0
Test:
  input:  validated Program from Phase 4 PASS test
  expect: ir.generate() returns same Program, ir.to_dict() returns valid dict
Test result: PENDING
Completed: —

---

## PHASE 6 — Code Generators
Status: [ ]  |  Depends: Phase 5
Files:
  [ ] codegen/python_generator.py  target:250  actual:0
  [ ] codegen/c_generator.py       target:280  actual:0
  [ ] codegen/cpp_generator.py     target:110  actual:0
Test round-trip:
  input:  "def add(x,y):\n    return x+y\nprint(add(3,4))\n"
  expect: python_generator output when exec'd prints "7"
Test C output:
  input:  same program
  expect: c_generator produces valid C, gcc compiles it, runs, prints "7"
Test result: PENDING
Completed: —

---

## PHASE 7 — Validator
Status: [ ]  |  Depends: Phase 6
Files:
  [ ] validator/validator.py  target:190  actual:0
Test PASS:  Python print(7) vs C printf("%d\n",7)  → passed:True
Test FAIL:  Python print(7) vs C printf("%d\n",8)  → passed:False
Test result: PENDING
Completed: —

---

## PHASE 8 — Web UI
Status: [ ]  |  Depends: Phase 7
Files:
  [ ] main.py              target:130  actual:0
  [ ] frontend/index.html  target:550  actual:0
Manual checklist:
  [ ] Editor left 40%, phases right 60%
  [ ] Token pills show TYPE:value with correct colors
  [ ] Parser modal: text tree + graphical SVG toggle
  [ ] Blocked phases unclickable
  [ ] New compile wipes all previous phase data
  [ ] Target selector appears only after IR passes
  [ ] Validator shows side-by-side stdout + PASS/FAIL
  [ ] Error modal shows line/col/snippet
Completed: —

---

## LINE COUNT SUMMARY
| File                          | Target | Actual | Status  |
|-------------------------------|--------|--------|---------|
| errors.py                     | 55     | 86     | ✅ done |
| ast_nodes.py                  | 175    | 326    | ✅ done |
| lexer/tokens.py               | 95     | 132    | ✅ done |
| preprocessor/preprocessor.py  | 150    | 218    | ✅ done |
| lexer/python_lexer.py         | 260    | 294    | ✅ done |
| lexer/c_lexer.py              | 225    | 257    | ✅ done |
| lexer/cpp_lexer.py            | 85     | 64     | ✅ done |
| parser/python_parser.py       | 400    | 0      | pending |
| parser/c_parser.py            | 380    | 0      | pending |
| parser/cpp_parser.py          | 110    | 0      | pending |
| semantic/analyzer.py          | 320    | 0      | pending |
| ir/ir_generator.py            | 200    | 0      | pending |
| codegen/python_generator.py   | 250    | 0      | pending |
| codegen/c_generator.py        | 280    | 0      | pending |
| codegen/cpp_generator.py      | 110    | 0      | pending |
| validator/validator.py        | 190    | 0      | pending |
| visualizer/ast_visualizer.py  | 130    | 0      | pending |
| main.py                       | 130    | 0      | pending |
| frontend/index.html           | 550    | 0      | pending |
| **TOTAL**                     | **3875**| **0** | —       |
