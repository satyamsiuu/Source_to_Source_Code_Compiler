"""
codegen/python_generator.py — Generates Python source from language-neutral AST.
Phase 6 of the compiler pipeline.

Walks AST recursively, emitting Python-idiomatic code.
Indentation via indent_level counter: each block increments by 1.
No type annotations in output (Python is dynamically typed).
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


class PythonGenerator:
    """Generates Python source code from the language-neutral AST."""

    def generate(self, program: Program) -> str:
        """Entry point: convert entire Program AST to Python source string."""
        self.errors = []
        self.indent_level = 0  # tracks current nesting depth
        self.lines = []        # accumulates output lines
        self.symbol_table = {} # tracks array sizes for ForEachStmt
        self._declared = set() # tracks already-declared vars (for VarDecl vs AssignStmt)
        self._var_types = {}   # tracks var name → DataType for division inference
        # Emit non-main functions first
        for func in program.functions:
            if func.name == "main":
                continue  # main body handled below as globals
            self._gen_function(func)
            self.lines.append("")  # blank line between top-level constructs
        # Global statements
        for stmt in program.globals:
            self._gen_stmt(stmt)
        # Unwrap main() body as top-level statements (C→Python fix)
        main_funcs = [f for f in program.functions if f.name == "main"]
        if main_funcs:
            for stmt in main_funcs[0].body:
                # Skip 'return 0' — C idiom, not needed in Python
                if isinstance(stmt, ReturnStmt) and isinstance(getattr(stmt, 'value', None), Literal):
                    if stmt.value.value == 0:
                        continue
                self._gen_stmt(stmt)
        if self.errors:
            raise CompilerErrorList(self.errors)
        return "\n".join(self.lines) + "\n"

    # ── Helpers ────────────────────────────────────────────────────────

    def _indent(self) -> str:
        """Return current indentation string (4 spaces per level)."""
        return "    " * self.indent_level

    def _emit(self, line: str):
        """Add one line with current indentation."""
        self.lines.append(self._indent() + line)

    def _expr(self, node) -> str:
        """Convert an expression AST node to a Python expression string."""
        if node is None:
            return "None"
        if isinstance(node, Literal):
            return self._gen_literal(node)
        if isinstance(node, Var):
            return node.name
        if isinstance(node, BinaryOp):
            left = self._expr(node.left)
            right = self._expr(node.right)
            # Map C-style operators to Python
            op = node.op
            if op == "&&": op = "and"
            elif op == "||": op = "or"
            elif op == "/":
                # Use // (integer division) only when BOTH operands are int
                lt = self._infer_type(node.left)
                rt = self._infer_type(node.right)
                if DataType.FLOAT not in (lt, rt):
                    op = "//"
            return f"({left} {op} {right})"
        if isinstance(node, UnaryOp):
            op = "not " if node.op in ("not", "!") else node.op
            return f"({op}{self._expr(node.operand)})"
        if isinstance(node, FunctionCall):
            args = ", ".join(self._expr(a) for a in node.args)
            return f"{node.name}({args})"
        if isinstance(node, ArrayAccess):
            return f"{node.name}[{self._expr(node.index)}]"
        self.errors.append(CompilerError(Phase.CODEGEN,
            f"Unknown expression node: {type(node).__name__}", getattr(node, 'line', 0)))
        return "???"

    def _infer_type(self, node) -> DataType:
        """Best-effort type inference for division operator selection.
        Returns FLOAT if any operand is float, otherwise INT."""
        if node is None: return DataType.INT
        if isinstance(node, Literal): return node.data_type
        if isinstance(node, Var):
            return self._var_types.get(node.name, DataType.INT)
        if isinstance(node, BinaryOp):
            lt = self._infer_type(node.left)
            rt = self._infer_type(node.right)
            if DataType.FLOAT in (lt, rt): return DataType.FLOAT
            return DataType.INT
        if isinstance(node, ArrayAccess): return DataType.INT
        if isinstance(node, FunctionCall): return DataType.INT
        if isinstance(node, UnaryOp): return self._infer_type(node.operand)
        return DataType.INT

    def _gen_literal(self, node: Literal) -> str:
        """Convert a Literal node to Python source representation."""
        if node.data_type == DataType.STR:
            return f'"{node.value}"'
        if node.data_type == DataType.BOOL:
            return "True" if node.value else "False"
        if node.data_type == DataType.FLOAT:
            s = str(node.value)
            return s if "." in s else s + ".0"  # ensure 5 → 5.0
        return str(node.value)  # INT and fallback

    # ── Statement generation ──────────────────────────────────────────

    def _gen_stmt(self, node):
        """Dispatch to the correct statement generator."""
        if isinstance(node, VarDecl):       self._gen_var_decl(node)
        elif isinstance(node, ArrayDecl):   self._gen_array_decl(node)
        elif isinstance(node, AssignStmt):  self._gen_assign(node)
        elif isinstance(node, ArrayAssign): self._gen_arr_assign(node)
        elif isinstance(node, IfStmt):      self._gen_if(node)
        elif isinstance(node, WhileStmt):   self._gen_while(node)
        elif isinstance(node, ForRangeStmt):self._gen_for_range(node)
        elif isinstance(node, ForEachStmt): self._gen_for_each(node)
        elif isinstance(node, ReturnStmt):  self._gen_return(node)
        elif isinstance(node, PrintStmt):   self._gen_print(node)
        elif isinstance(node, InputStmt):   self._gen_input(node)
        elif isinstance(node, FunctionCall):self._emit(self._expr(node))
        else:
            self.errors.append(CompilerError(Phase.CODEGEN,
                f"Unknown statement node: {type(node).__name__}", getattr(node, 'line', 0)))

    def _gen_function(self, func: FunctionDecl):
        """def name(params):\n    body"""
        params = ", ".join(p.name for p in func.params)
        self._emit(f"def {func.name}({params}):")
        self.indent_level += 1
        if not func.body:
            self._emit("pass")  # empty function needs pass
        for stmt in func.body:
            self._gen_stmt(stmt)
        self.indent_level -= 1

    def _gen_var_decl(self, node: VarDecl):
        # If already declared in this scope, emit assignment instead of redeclaration
        if node.name in self._declared:
            if node.value is not None:
                self._emit(f"{node.name} = {self._expr(node.value)}")
            return
        self._declared.add(node.name)
        self._var_types[node.name] = node.data_type
        if node.value is not None:
            self._emit(f"{node.name} = {self._expr(node.value)}")
        else:
            # Uninitialized: provide default based on type
            defaults = {DataType.INT: "0", DataType.FLOAT: "0.0",
                        DataType.BOOL: "False", DataType.STR: '""'}
            self._emit(f"{node.name} = {defaults.get(node.data_type, '0')}")

    def _gen_array_decl(self, node: ArrayDecl):
        self.symbol_table[node.name] = {"size": node.size, "type": node.data_type}
        if node.elements:
            elems = ", ".join(self._expr(e) for e in node.elements)
            self._emit(f"{node.name} = [{elems}]")
        else:
            # Empty array with known size: [0] * size
            defaults = {DataType.INT: "0", DataType.FLOAT: "0.0",
                        DataType.BOOL: "False"}
            d = defaults.get(node.data_type, "0")
            self._emit(f"{node.name} = [{d}] * {node.size}")

    def _gen_assign(self, node: AssignStmt):
        self._emit(f"{node.name} = {self._expr(node.value)}")

    def _gen_arr_assign(self, node: ArrayAssign):
        self._emit(f"{node.name}[{self._expr(node.index)}] = {self._expr(node.value)}")

    def _gen_if(self, node: IfStmt):
        self._emit(f"if {self._expr(node.condition)}:")
        self.indent_level += 1
        if not node.then_body:
            self._emit("pass")
        for s in node.then_body:
            self._gen_stmt(s)
        self.indent_level -= 1
        if node.else_body:
            self._emit("else:")
            self.indent_level += 1
            for s in node.else_body:
                self._gen_stmt(s)
            self.indent_level -= 1

    def _gen_while(self, node: WhileStmt):
        self._emit(f"while {self._expr(node.condition)}:")
        self.indent_level += 1
        if not node.body:
            self._emit("pass")
        for s in node.body:
            self._gen_stmt(s)
        self.indent_level -= 1

    def _gen_for_range(self, node: ForRangeStmt):
        start = self._expr(node.start) if node.start else "0"
        stop = self._expr(node.stop)
        step = self._expr(node.step) if node.step else "1"
        # Simplify range() call: range(0, n, 1) → range(n)
        if start == "0" and step == "1":
            self._emit(f"for {node.var} in range({stop}):")
        elif step == "1":
            self._emit(f"for {node.var} in range({start}, {stop}):")
        else:
            self._emit(f"for {node.var} in range({start}, {stop}, {step}):")
        self.indent_level += 1
        if not node.body:
            self._emit("pass")
        for s in node.body:
            self._gen_stmt(s)
        self.indent_level -= 1

    def _gen_for_each(self, node: ForEachStmt):
        self._emit(f"for {node.var} in {node.array_name}:")
        self.indent_level += 1
        if not node.body:
            self._emit("pass")
        for s in node.body:
            self._gen_stmt(s)
        self.indent_level -= 1

    def _gen_return(self, node: ReturnStmt):
        if node.value is not None:
            self._emit(f"return {self._expr(node.value)}")
        else:
            self._emit("return")

    def _gen_print(self, node: PrintStmt):
        args = ", ".join(self._expr(v) for v in node.values)
        # When separator is empty, use sep='' to avoid Python's default space
        if node.separator == "" and len(node.values) > 1:
            self._emit(f'print({args}, sep="")')
        else:
            self._emit(f"print({args})")

    def _gen_input(self, node: InputStmt):
        type_map = {DataType.INT: "int", DataType.FLOAT: "float"}
        wrapper = type_map.get(node.data_type, "")
        prompt = f'"{node.prompt}"' if node.prompt else ""
        tgt = self._expr(node.target) if hasattr(node.target, "line") else node.target
        if wrapper:
            self._emit(f"{tgt} = {wrapper}(input({prompt}))")
        else:
            self._emit(f"{tgt} = input({prompt})")
