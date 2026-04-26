"""
semantic/analyzer.py — Type checking, scope validation, symbol table construction.
Phase 4 of the compiler pipeline.

Two-pass for Python (forward calls allowed):
  Pass 1: collect FunctionDecl signatures → global scope
  Pass 2: full type+scope check (globals first, then remaining function bodies)
Single-pass for C/C++ (define-before-use enforced).

Scope stack: list[dict], each dict maps name → {kind, type, line, ...}.
Error pattern: collect ALL errors → raise CompilerErrorList once at end.
"""
try:
    from transpiler.errors import CompilerError, CompilerErrorList, Phase
    from transpiler.ast_nodes import (
        DataType, Program, FunctionDecl, Param, VarDecl, ArrayDecl,
        AssignStmt, ArrayAssign, IfStmt, WhileStmt, ForRangeStmt,
        ForEachStmt, ReturnStmt, PrintStmt, InputStmt, FunctionCall,
        BinaryOp, UnaryOp, Var, ArrayAccess, Literal)
except ModuleNotFoundError:
    from errors import CompilerError, CompilerErrorList, Phase
    from ast_nodes import (
        DataType, Program, FunctionDecl, Param, VarDecl, ArrayDecl,
        AssignStmt, ArrayAssign, IfStmt, WhileStmt, ForRangeStmt,
        ForEachStmt, ReturnStmt, PrintStmt, InputStmt, FunctionCall,
        BinaryOp, UnaryOp, Var, ArrayAccess, Literal)


class SemanticAnalyzer:
    """Performs semantic analysis: type-check, scope-check, build symbol table."""

    def analyze(self, program: Program, source_lang: str = "python"):
        """Entry point. Returns (annotated_program, flat_symbol_table_dict)."""
        self.errors, self.scope_stack = [], [{}]   # global scope at index 0
        self.functions = {}          # name → func info for quick lookup
        self.source_lang = source_lang
        self.current_function = None # which FunctionDecl body we're inside
        self.symbol_table = {}       # flat output for UI display
        self._analyzed = set()       # tracks body-analyzed function names
        if source_lang == "python":
            self._pass1(program)     # collect signatures (enables forward calls)
            self._pass2(program)     # full analysis
        else:
            self._single_pass(program)  # C/C++: define-before-use
        if self.errors:
            raise CompilerErrorList(self.errors)
        return program, self.symbol_table

    # ── Scope helpers ─────────────────────────────────────────────────

    def _enter_scope(self):
        self.scope_stack.append({})

    def _exit_scope(self):
        if len(self.scope_stack) > 1:  # never pop global scope
            self.scope_stack.pop()

    def _declare(self, name, info, line):
        """Declare symbol in current scope; error if already declared."""
        scope = self.scope_stack[-1]
        if name in scope:
            self.errors.append(CompilerError(Phase.SEMANTIC,
                f"Redeclaration of '{name}' (already declared at line {scope[name]['line']})", line))
            return
        info["line"] = line
        scope[name] = info
        # Record in flat table for UI (scoped key: "func.var" or just "var")
        sn = self.current_function.name if self.current_function else "global"
        key = f"{sn}.{name}" if sn != "global" else name
        self.symbol_table[key] = {
            "kind": info["kind"], "scope": sn, "line": line,
            "type": info["type"].value if isinstance(info.get("type"), DataType) else str(info.get("type", "")),
        }

    def _lookup(self, name):
        """Search scopes from innermost to global. Returns info dict or None."""
        for scope in reversed(self.scope_stack):
            if name in scope:
                return scope[name]
        return None

    # ── Pass 1: collect function signatures (Python only) ─────────────

    def _pass1(self, program):
        for func in program.functions:
            if func.name in self.functions:
                self.errors.append(CompilerError(Phase.SEMANTIC,
                    f"Duplicate function definition '{func.name}'", func.line))
                continue
            params = [(p.name, p.data_type) for p in func.params]
            entry = {"kind": "func", "type": DataType.VOID, "params": params,
                     "return_type": func.return_type, "decl": func, "line": func.line}
            self.functions[func.name] = entry
            self.scope_stack[0][func.name] = entry  # visible in global scope
            self.symbol_table[func.name] = {
                "kind": "function", "type": func.return_type.value,
                "params": [(p.name, p.data_type.value) for p in func.params],
                "scope": "global", "line": func.line}

    # ── Pass 2: full analysis (Python) ────────────────────────────────

    def _pass2(self, program):
        # Globals first — calls trigger on-demand function body analysis
        for stmt in program.globals:
            self._analyze_stmt(stmt)
        # Then any function bodies not yet triggered
        for func in program.functions:
            if func.name not in self._analyzed:
                self._analyze_func_body(func)

    # ── Single-pass analysis (C/C++) ──────────────────────────────────

    def _single_pass(self, program):
        for func in program.functions:
            if func.name not in self.functions:
                params = [(p.name, p.data_type) for p in func.params]
                entry = {"kind": "func", "type": func.return_type, "params": params,
                         "return_type": func.return_type, "decl": func, "line": func.line}
                self.functions[func.name] = entry
                self.scope_stack[0][func.name] = entry
                self.symbol_table[func.name] = {
                    "kind": "function", "type": func.return_type.value,
                    "params": [(p.name, p.data_type.value) for p in func.params],
                    "scope": "global", "line": func.line}
            self._analyze_func_body(func)
        for stmt in program.globals:
            self._analyze_stmt(stmt)

    # ── Function body analysis ────────────────────────────────────────

    def _analyze_func_body(self, func):
        """Analyze one function: declare params, walk body, resolve return type."""
        self._analyzed.add(func.name)
        prev = self.current_function
        self.current_function = func
        self._enter_scope()
        # Declare params (use call-inferred types if available)
        fi = self.functions.get(func.name, {})
        pl = fi.get("params", [])
        for i, param in enumerate(func.params):
            pt = pl[i][1] if i < len(pl) else param.data_type
            if pt == DataType.UNKNOWN:
                pt = DataType.INT  # fallback for untyped params
            param.data_type = pt   # annotate AST
            self._declare(param.name, {"kind": "var", "type": pt}, param.line)
        # Walk body, track return type
        ret_type = DataType.VOID
        for stmt in func.body:
            self._analyze_stmt(stmt)
            if isinstance(stmt, ReturnStmt) and stmt.value is not None:
                rt = self._resolve_type(stmt.value)
                if rt != DataType.UNKNOWN:
                    ret_type = rt
        # Update function return type everywhere
        func.return_type = ret_type
        if func.name in self.functions:
            self.functions[func.name]["return_type"] = ret_type
            self.functions[func.name]["type"] = ret_type
        if func.name in self.symbol_table:
            self.symbol_table[func.name]["type"] = ret_type.value
        self._exit_scope()
        self.current_function = prev

    # ── Statement dispatch ────────────────────────────────────────────

    def _analyze_stmt(self, node):
        if isinstance(node, VarDecl):       self._do_var_decl(node)
        elif isinstance(node, ArrayDecl):   self._do_array_decl(node)
        elif isinstance(node, AssignStmt):  self._do_assign(node)
        elif isinstance(node, ArrayAssign): self._do_arr_assign(node)
        elif isinstance(node, IfStmt):      self._do_if(node)
        elif isinstance(node, WhileStmt):   self._do_while(node)
        elif isinstance(node, ForRangeStmt):self._do_for_range(node)
        elif isinstance(node, ForEachStmt): self._do_for_each(node)
        elif isinstance(node, ReturnStmt):  self._do_return(node)
        elif isinstance(node, PrintStmt):   self._do_print(node)
        elif isinstance(node, InputStmt):   self._do_input(node)
        elif isinstance(node, FunctionCall):self._resolve_call(node)
        elif isinstance(node, Var):         self._resolve_type(node)

    def _do_var_decl(self, node):
        vt = self._resolve_type(node.value) if node.value else DataType.UNKNOWN
        if node.data_type == DataType.UNKNOWN:
            node.data_type = vt
        self._declare(node.name, {"kind": "var", "type": node.data_type}, node.line)

    def _do_array_decl(self, node):
        if node.elements:
            et = self._resolve_type(node.elements[0])
            for e in node.elements[1:]:
                et = self._promote(et, self._resolve_type(e))
            if node.data_type == DataType.UNKNOWN:
                node.data_type = et
        self._declare(node.name, {"kind": "array", "type": node.data_type, "size": node.size}, node.line)

    def _do_assign(self, node):
        sym = self._lookup(node.name)
        if sym is None:
            self.errors.append(CompilerError(Phase.SEMANTIC,
                f"Undeclared variable '{node.name}'", node.line)); return
        vt = self._resolve_type(node.value)
        # Silent INT→FLOAT promotion on the variable
        if sym["type"] == DataType.INT and vt == DataType.FLOAT:
            sym["type"] = DataType.FLOAT
        elif sym["type"] not in (DataType.UNKNOWN, vt) and vt != DataType.UNKNOWN:
            if not (vt == DataType.INT and sym["type"] == DataType.FLOAT):
                self.errors.append(CompilerError(Phase.SEMANTIC,
                    f"Type mismatch: cannot assign {vt.value} to {sym['type'].value} variable '{node.name}'",
                    node.line))

    def _do_arr_assign(self, node):
        sym = self._lookup(node.name)
        if sym is None:
            self.errors.append(CompilerError(Phase.SEMANTIC,
                f"Undeclared array '{node.name}'", node.line)); return
        if sym["kind"] != "array":
            self.errors.append(CompilerError(Phase.SEMANTIC,
                f"'{node.name}' is not an array", node.line)); return
        it = self._resolve_type(node.index)
        if it not in (DataType.INT, DataType.UNKNOWN):
            self.errors.append(CompilerError(Phase.SEMANTIC,
                f"Array index must be int, got {it.value}", node.line))
        self._resolve_type(node.value)

    def _do_if(self, node):
        self._resolve_type(node.condition)
        self._enter_scope()
        for s in node.then_body: self._analyze_stmt(s)
        self._exit_scope()
        if node.else_body:
            self._enter_scope()
            for s in node.else_body: self._analyze_stmt(s)
            self._exit_scope()

    def _do_while(self, node):
        self._resolve_type(node.condition)
        self._enter_scope()
        for s in node.body: self._analyze_stmt(s)
        self._exit_scope()

    def _do_for_range(self, node):
        for expr in (node.start, node.stop, node.step):
            if expr: self._resolve_type(expr)
        self._enter_scope()
        self._declare(node.var, {"kind": "var", "type": DataType.INT}, node.line)
        for s in node.body: self._analyze_stmt(s)
        self._exit_scope()

    def _do_for_each(self, node):
        sym = self._lookup(node.array_name)
        if sym is None:
            self.errors.append(CompilerError(Phase.SEMANTIC,
                f"Undeclared array '{node.array_name}'", node.line))
            et = DataType.UNKNOWN
        elif sym["kind"] != "array":
            self.errors.append(CompilerError(Phase.SEMANTIC,
                f"For-each only supported over declared arrays, '{node.array_name}' is not an array",
                node.line))
            et = DataType.UNKNOWN
        else:
            et = sym["type"]
        self._enter_scope()
        self._declare(node.var, {"kind": "var", "type": et}, node.line)
        for s in node.body: self._analyze_stmt(s)
        self._exit_scope()

    def _do_return(self, node):
        if self.current_function is None:
            self.errors.append(CompilerError(Phase.SEMANTIC,
                "Return statement outside of function", node.line))
            return
        if node.value is not None:
            self._resolve_type(node.value)

    def _do_print(self, node):
        for v in node.values:
            vt = self._resolve_type(v)
            if vt == DataType.VOID:
                self.errors.append(CompilerError(Phase.SEMANTIC,
                    "Cannot print void expression", node.line))

    def _do_input(self, node):
        if hasattr(node.target, "name"):
            target_name = node.target.name
            if type(node.target).__name__ == "ArrayAccess":
                self._resolve_type(node.target.index)
        else:
            target_name = str(node.target)
            
        sym = self._lookup(target_name)
        if sym is None:
            self._declare(target_name, {"kind": "var", "type": node.data_type}, node.line)
        else:
            if node.data_type == DataType.UNKNOWN:
                node.data_type = sym["type"]

    # ── Expression type resolution ────────────────────────────────────

    def _resolve_type(self, node) -> DataType:
        """Recursively determine the DataType of an expression node."""
        if node is None:             return DataType.UNKNOWN
        if isinstance(node, Literal):return node.data_type
        if isinstance(node, Var):    return self._resolve_var(node)
        if isinstance(node, ArrayAccess): return self._resolve_arr_acc(node)
        if isinstance(node, FunctionCall):return self._resolve_call(node)
        if isinstance(node, BinaryOp):    return self._resolve_binop(node)
        if isinstance(node, UnaryOp):
            ot = self._resolve_type(node.operand)
            return DataType.BOOL if node.op == "not" else ot
        return DataType.UNKNOWN

    def _resolve_var(self, node) -> DataType:
        sym = self._lookup(node.name)
        if sym is None:
            self.errors.append(CompilerError(Phase.SEMANTIC,
                f"Undeclared variable '{node.name}'", node.line))
            return DataType.UNKNOWN
        return sym["type"]

    def _resolve_arr_acc(self, node) -> DataType:
        sym = self._lookup(node.name)
        if sym is None:
            self.errors.append(CompilerError(Phase.SEMANTIC,
                f"Undeclared array '{node.name}'", node.line))
            return DataType.UNKNOWN
        if sym["kind"] != "array":
            self.errors.append(CompilerError(Phase.SEMANTIC,
                f"'{node.name}' is not an array", node.line))
            return DataType.UNKNOWN
        it = self._resolve_type(node.index)
        if it not in (DataType.INT, DataType.UNKNOWN):
            self.errors.append(CompilerError(Phase.SEMANTIC,
                f"Array index must be int, got {it.value}", node.line))
        return sym["type"]

    def _resolve_call(self, node) -> DataType:
        fi = self.functions.get(node.name)
        if fi is None:
            self.errors.append(CompilerError(Phase.SEMANTIC,
                f"Undeclared function '{node.name}'", node.line))
            return DataType.UNKNOWN
        if len(node.args) != len(fi["params"]):
            self.errors.append(CompilerError(Phase.SEMANTIC,
                f"Function '{node.name}' expects {len(fi['params'])} args, got {len(node.args)}",
                node.line))
            return fi.get("return_type", DataType.UNKNOWN)
        # Resolve arg types; infer param types if UNKNOWN
        for i, arg in enumerate(node.args):
            at = self._resolve_type(arg)
            if i < len(fi["params"]):
                pn, pt = fi["params"][i]
                if pt == DataType.UNKNOWN and at != DataType.UNKNOWN:
                    fi["params"][i] = (pn, at)
        # On-demand body analysis to determine return type
        if node.name not in self._analyzed and "decl" in fi:
            self._analyze_func_body(fi["decl"])
        return fi.get("return_type", DataType.UNKNOWN)

    def _resolve_binop(self, node) -> DataType:
        lt = self._resolve_type(node.left)
        rt = self._resolve_type(node.right)
        if DataType.STR in (lt, rt):
            self.errors.append(CompilerError(Phase.SEMANTIC,
                "String operations are not supported", getattr(node, 'line', 0)))
            return DataType.STR
        if node.op in ("==", "!=", "<", ">", "<=", ">=", "and", "or"):
            return DataType.BOOL
        return self._promote(lt, rt)

    # ── Type promotion ────────────────────────────────────────────────

    def _promote(self, a, b):
        """INT+INT→INT, INT+FLOAT→FLOAT, FLOAT+FLOAT→FLOAT."""
        if a == DataType.UNKNOWN: return b
        if b == DataType.UNKNOWN: return a
        if DataType.FLOAT in (a, b): return DataType.FLOAT
        if a == DataType.INT and b == DataType.INT: return DataType.INT
        if {a, b} <= {DataType.INT, DataType.BOOL}: return DataType.INT
        return a
