"""
codegen/c_generator.py — Generates C source from language-neutral AST.
Phase 6 of the compiler pipeline.

Key difference from Python generator:
- Explicit types everywhere (int x = 5;)
- Semicolons terminate statements
- Blocks use { } not indentation
- printf() with dynamic format strings for PrintStmt
- scanf() for InputStmt
- Global statements wrapped in main()
- #include <stdio.h> prepended automatically

Designed for inheritance: CppGenerator overrides only preamble + I/O methods.
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

# Map DataType → C type keyword
TYPE_STR = {
    DataType.INT: "int", DataType.FLOAT: "float",
    DataType.BOOL: "int", DataType.VOID: "void",
    DataType.STR: "char*", DataType.UNKNOWN: "int",
}
# Map DataType → printf/scanf format specifier
FMT_SPEC = {
    DataType.INT: "%d", DataType.FLOAT: "%f",
    DataType.BOOL: "%d", DataType.STR: "%s",
}


class CGenerator:
    """Generates C source code from the language-neutral AST.
    CppGenerator extends this — overrides preamble, PrintStmt, InputStmt."""

    def generate(self, program: Program) -> str:
        self.errors = []
        self.indent_level = 0
        self.lines = []
        self.symbol_table = {}  # tracks array sizes + types for ForEachStmt
        self._emit_preamble()
        # Emit all non-main functions
        for func in program.functions:
            if func.name != "main":
                self._gen_function(func)
                self.lines.append("")
        # Wrap globals in main() if there are any
        has_main = any(f.name == "main" for f in program.functions)
        if program.globals and not has_main:
            self._emit("int main() {")
            self.indent_level += 1
            for stmt in program.globals:
                self._gen_stmt(stmt)
            self._emit("return 0;")
            self.indent_level -= 1
            self._emit("}")
        elif has_main:
            main_func = [f for f in program.functions if f.name == "main"][0]
            self._gen_function(main_func)
        if self.errors:
            raise CompilerErrorList(self.errors)
        return "\n".join(self.lines) + "\n"

    # ── Preamble (overridden by CppGenerator) ──────────────────────────

    def _emit_preamble(self):
        """Emit #include directives. Override in CppGenerator."""
        self._emit_raw("#include <stdio.h>")
        self.lines.append("")

    # ── Helpers ────────────────────────────────────────────────────────

    def _indent(self) -> str:
        return "    " * self.indent_level

    def _emit(self, line: str):
        self.lines.append(self._indent() + line)

    def _emit_raw(self, line: str):
        """Emit line without indentation (for preprocessor directives)."""
        self.lines.append(line)

    def _type_str(self, dt: DataType) -> str:
        """Map DataType enum to C type string."""
        return TYPE_STR.get(dt, "int")

    def _expr(self, node) -> str:
        """Convert expression AST node to C expression string."""
        if node is None: return "0"
        if isinstance(node, Literal):     return self._gen_literal(node)
        if isinstance(node, Var):         return node.name
        if isinstance(node, BinaryOp):
            left, right = self._expr(node.left), self._expr(node.right)
            op = node.op
            if op == "and": op = "&&"
            elif op == "or": op = "||"
            return f"({left} {op} {right})"
        if isinstance(node, UnaryOp):
            op = "!" if node.op in ("not", "!") else node.op
            return f"({op}{self._expr(node.operand)})"
        if isinstance(node, FunctionCall):
            args = ", ".join(self._expr(a) for a in node.args)
            return f"{node.name}({args})"
        if isinstance(node, ArrayAccess):
            return f"{node.name}[{self._expr(node.index)}]"
        self.errors.append(CompilerError(Phase.CODEGEN,
            f"Unknown expression node: {type(node).__name__}", getattr(node, 'line', 0)))
        return "0"

    def _gen_literal(self, node: Literal) -> str:
        if node.data_type == DataType.STR:  return f'"{node.value}"'
        if node.data_type == DataType.BOOL: return "1" if node.value else "0"
        if node.data_type == DataType.FLOAT:
            s = str(node.value)
            return s if "." in s else s + ".0"
        return str(node.value)

    # ── Statement generation ──────────────────────────────────────────

    def _gen_stmt(self, node):
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
        elif isinstance(node, FunctionCall):
            self._emit(f"{self._expr(node)};")
        else:
            self.errors.append(CompilerError(Phase.CODEGEN,
                f"Unknown statement: {type(node).__name__}", getattr(node, 'line', 0)))

    def _gen_function(self, func: FunctionDecl):
        """type name(type p1, type p2) { body }"""
        ret = self._type_str(func.return_type)
        params = ", ".join(f"{self._type_str(p.data_type)} {p.name}" for p in func.params)
        self._emit(f"{ret} {func.name}({params}) {{")
        self.indent_level += 1
        for stmt in func.body:
            self._gen_stmt(stmt)
        # Auto-add return 0 for main if last stmt isn't return
        if func.name == "main" and (not func.body or not isinstance(func.body[-1], ReturnStmt)):
            self._emit("return 0;")
        self.indent_level -= 1
        self._emit("}")

    def _gen_var_decl(self, node: VarDecl):
        t = self._type_str(node.data_type)
        if node.value is not None:
            self._emit(f"{t} {node.name} = {self._expr(node.value)};")
        else:
            self._emit(f"{t} {node.name};")

    def _gen_array_decl(self, node: ArrayDecl):
        self.symbol_table[node.name] = {"size": node.size, "type": node.data_type}
        t = self._type_str(node.data_type)
        if node.elements:
            elems = ", ".join(self._expr(e) for e in node.elements)
            self._emit(f"{t} {node.name}[] = {{{elems}}};")
        else:
            self._emit(f"{t} {node.name}[{node.size}];")

    def _gen_assign(self, node: AssignStmt):
        self._emit(f"{node.name} = {self._expr(node.value)};")

    def _gen_arr_assign(self, node: ArrayAssign):
        self._emit(f"{node.name}[{self._expr(node.index)}] = {self._expr(node.value)};")

    def _gen_if(self, node: IfStmt):
        self._emit(f"if ({self._expr(node.condition)}) {{")
        self.indent_level += 1
        for s in node.then_body: self._gen_stmt(s)
        self.indent_level -= 1
        if node.else_body:
            self._emit("} else {")
            self.indent_level += 1
            for s in node.else_body: self._gen_stmt(s)
            self.indent_level -= 1
        self._emit("}")

    def _gen_while(self, node: WhileStmt):
        self._emit(f"while ({self._expr(node.condition)}) {{")
        self.indent_level += 1
        for s in node.body: self._gen_stmt(s)
        self.indent_level -= 1
        self._emit("}")

    def _gen_for_range(self, node: ForRangeStmt):
        """for (int i = start; i < stop; i += step) { body }"""
        var = node.var
        start = self._expr(node.start) if node.start else "0"
        stop = self._expr(node.stop)
        step = self._expr(node.step) if node.step else "1"
        self._emit(f"for (int {var} = {start}; {var} < {stop}; {var} += {step}) {{")
        self.indent_level += 1
        for s in node.body: self._gen_stmt(s)
        self.indent_level -= 1
        self._emit("}")

    def _gen_for_each(self, node: ForEachStmt):
        """for (int _i=0; _i<arr_size; _i++) { type x = arr[_i]; body }"""
        info = self.symbol_table.get(node.array_name, {})
        size = info.get("size", 0)
        elem_type = self._type_str(info.get("type", DataType.INT))
        self._emit(f"for (int _i = 0; _i < {size}; _i++) {{")
        self.indent_level += 1
        self._emit(f"{elem_type} {node.var} = {node.array_name}[_i];")
        for s in node.body: self._gen_stmt(s)
        self.indent_level -= 1
        self._emit("}")

    def _gen_return(self, node: ReturnStmt):
        if node.value is not None:
            self._emit(f"return {self._expr(node.value)};")
        else:
            self._emit("return;")

    def _gen_print(self, node: PrintStmt):
        """printf(format_string, args...) with dynamic format string."""
        fmt_parts, args = [], []
        for v in node.values:
            dt = self._infer_type(v)
            fmt_parts.append(FMT_SPEC.get(dt, "%d"))
            args.append(self._expr(v))
        fmt = " ".join(fmt_parts) + "\\n"
        if args:
            arg_str = ", ".join(args)
            self._emit(f'printf("{fmt}", {arg_str});')
        else:
            self._emit(f'printf("{fmt}");')

    def _gen_input(self, node: InputStmt):
        """scanf(format, &target)"""
        fmt = FMT_SPEC.get(node.data_type, "%d")
        if node.prompt:
            self._emit(f'printf("{node.prompt}");')
        self._emit(f'scanf("{fmt}", &{node.target});')

    def _infer_type(self, node) -> DataType:
        """Best-effort type inference for printf format string generation."""
        if isinstance(node, Literal): return node.data_type
        if isinstance(node, Var):
            # Check symbol table from semantic analysis (stored in node or lookup)
            return DataType.INT  # fallback
        if isinstance(node, BinaryOp):
            if node.op in ("==", "!=", "<", ">", "<=", ">=", "and", "or"):
                return DataType.BOOL
            lt = self._infer_type(node.left)
            rt = self._infer_type(node.right)
            if DataType.FLOAT in (lt, rt): return DataType.FLOAT
            return DataType.INT
        if isinstance(node, FunctionCall): return DataType.INT  # fallback
        if isinstance(node, ArrayAccess): return DataType.INT   # fallback
        if isinstance(node, UnaryOp): return self._infer_type(node.operand)
        return DataType.INT
