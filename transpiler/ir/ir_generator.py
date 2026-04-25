"""
ir/ir_generator.py — Intermediate Representation generator (Phase 5).

Design: Our IR is the AST itself (neutral AST as IR).
- TAC flattens 'return x+y' to 't1=x+y; return t1' — destroys structure.
- LLVM IR requires SSA + LLVM toolchain — can't explain in viva.
- Our AST preserves program structure → generators produce readable output.

Three purposes:
  1. Integrity check: verifies AST is well-formed after semantic analysis.
  2. Serialisation: to_dict() converts AST to JSON for the UI modal.
  3. Checkpoint: divides pipeline — source phases done, target phases next.

Error pattern: collect ALL errors → raise CompilerErrorList once at end.
"""

try:
    from transpiler.errors import CompilerError, CompilerErrorList, Phase
    from transpiler.ast_nodes import (
        DataType, ASTNode, Program, FunctionDecl, Param, VarDecl, ArrayDecl,
        AssignStmt, ArrayAssign, IfStmt, WhileStmt, ForRangeStmt,
        ForEachStmt, ReturnStmt, PrintStmt, InputStmt, FunctionCall,
        BinaryOp, UnaryOp, Var, ArrayAccess, Literal)
except ModuleNotFoundError:
    from errors import CompilerError, CompilerErrorList, Phase
    from ast_nodes import (
        DataType, ASTNode, Program, FunctionDecl, Param, VarDecl, ArrayDecl,
        AssignStmt, ArrayAssign, IfStmt, WhileStmt, ForRangeStmt,
        ForEachStmt, ReturnStmt, PrintStmt, InputStmt, FunctionCall,
        BinaryOp, UnaryOp, Var, ArrayAccess, Literal)


class IRGenerator:
    """Validates AST integrity and provides JSON serialisation for the UI."""

    def generate(self, program: Program) -> Program:
        """Validate AST structural integrity. Returns same Program unchanged.
        Raises CompilerErrorList if any integrity violations found."""
        self.errors = []  # collect all integrity violations
        if not isinstance(program, Program):
            self.errors.append(CompilerError(Phase.IR, "IR input is not a Program node"))
            raise CompilerErrorList(self.errors)
        for func in program.functions:  # validate every function
            self._check_function(func)
        for stmt in program.globals:    # validate every global statement
            self._check_node(stmt)
        if self.errors:                 # raise all collected errors at once
            raise CompilerErrorList(self.errors)
        return program  # unchanged — our IR IS the validated AST

    # ── Node validation ───────────────────────────────────────────────

    def _check_function(self, func):
        """Verify a FunctionDecl is structurally sound."""
        if not isinstance(func, FunctionDecl):
            self.errors.append(CompilerError(
                Phase.IR, f"Expected FunctionDecl, got {type(func).__name__}",
                getattr(func, 'line', None)))
            return
        if not func.name:
            self.errors.append(CompilerError(Phase.IR, "FunctionDecl has empty name", func.line))
        for param in func.params:  # every param must be a Param with a name
            if not isinstance(param, Param):
                self.errors.append(CompilerError(Phase.IR,
                    f"Function '{func.name}' param is {type(param).__name__}, expected Param", func.line))
            elif not param.name:
                self.errors.append(CompilerError(Phase.IR,
                    f"Function '{func.name}' has parameter with empty name", func.line))
        if not isinstance(func.return_type, DataType):  # return type must be valid
            self.errors.append(CompilerError(Phase.IR,
                f"Function '{func.name}' has invalid return type: {func.return_type}", func.line))
        for stmt in func.body:  # recursively check body
            self._check_node(stmt)

    def _check_node(self, node):
        """Recursively validate one AST node. isinstance dispatch like semantic analyzer."""
        if node is None:
            return  # None is valid for optional fields (e.g. ReturnStmt.value)
        if not isinstance(node, ASTNode):
            self.errors.append(CompilerError(Phase.IR, f"Non-AST node in tree: {type(node).__name__}"))
            return
        # Statement dispatch
        if isinstance(node, VarDecl):        self._chk_var_decl(node)
        elif isinstance(node, ArrayDecl):    self._chk_array_decl(node)
        elif isinstance(node, AssignStmt):   self._chk_assign(node)
        elif isinstance(node, ArrayAssign):  self._chk_arr_assign(node)
        elif isinstance(node, IfStmt):       self._chk_if(node)
        elif isinstance(node, WhileStmt):    self._chk_while(node)
        elif isinstance(node, ForRangeStmt): self._chk_for_range(node)
        elif isinstance(node, ForEachStmt):  self._chk_for_each(node)
        elif isinstance(node, ReturnStmt):   self._chk_return(node)
        elif isinstance(node, PrintStmt):    self._chk_print(node)
        elif isinstance(node, InputStmt):    self._chk_input(node)
        elif isinstance(node, FunctionCall): self._chk_call(node)
        # Expression dispatch
        elif isinstance(node, BinaryOp):     self._chk_binop(node)
        elif isinstance(node, UnaryOp):      self._chk_unaryop(node)
        elif isinstance(node, ArrayAccess):  self._chk_arr_access(node)
        elif isinstance(node, (Var, Literal)): pass  # validated by semantic phase
        elif isinstance(node, FunctionDecl): self._check_function(node)

    # ── Individual node checks ────────────────────────────────────────

    def _chk_var_decl(self, n):
        """VarDecl must have a name; value is optional (C allows 'int x;')."""
        if not n.name:
            self.errors.append(CompilerError(Phase.IR, "VarDecl has empty name", n.line))
        if n.value is not None:
            self._check_node(n.value)

    def _chk_array_decl(self, n):
        """ArrayDecl must have name, non-negative size, valid elements."""
        if not n.name:
            self.errors.append(CompilerError(Phase.IR, "ArrayDecl has empty name", n.line))
        if n.size < 0:
            self.errors.append(CompilerError(Phase.IR,
                f"Array '{n.name}' has negative size {n.size}", n.line))
        for elem in n.elements:
            self._check_node(elem)

    def _chk_assign(self, n):
        """AssignStmt must have a target name and a value expression."""
        if not n.name:
            self.errors.append(CompilerError(Phase.IR, "AssignStmt has empty target name", n.line))
        self._check_node(n.value)

    def _chk_arr_assign(self, n):
        """ArrayAssign must have name, index, and value."""
        if not n.name:
            self.errors.append(CompilerError(Phase.IR, "ArrayAssign has empty array name", n.line))
        self._check_node(n.index)
        self._check_node(n.value)

    def _chk_if(self, n):
        """IfStmt must have a condition; then/else bodies are statement lists."""
        if n.condition is None:
            self.errors.append(CompilerError(Phase.IR, "IfStmt has no condition", n.line))
        else:
            self._check_node(n.condition)
        for s in n.then_body: self._check_node(s)
        for s in n.else_body: self._check_node(s)

    def _chk_while(self, n):
        """WhileStmt must have a condition; body is a statement list."""
        if n.condition is None:
            self.errors.append(CompilerError(Phase.IR, "WhileStmt has no condition", n.line))
        else:
            self._check_node(n.condition)
        for s in n.body: self._check_node(s)

    def _chk_for_range(self, n):
        """ForRangeStmt must have var and stop; start/step are optional."""
        if not n.var:
            self.errors.append(CompilerError(Phase.IR, "ForRangeStmt has empty loop variable", n.line))
        if n.stop is None:  # stop is required (range needs upper bound)
            self.errors.append(CompilerError(Phase.IR, "ForRangeStmt has no stop expression", n.line))
        self._check_node(n.start)
        self._check_node(n.stop)
        self._check_node(n.step)
        for s in n.body: self._check_node(s)

    def _chk_for_each(self, n):
        """ForEachStmt must have a loop variable and an array name."""
        if not n.var:
            self.errors.append(CompilerError(Phase.IR, "ForEachStmt has empty loop variable", n.line))
        if not n.array_name:
            self.errors.append(CompilerError(Phase.IR, "ForEachStmt has empty array name", n.line))
        for s in n.body: self._check_node(s)

    def _chk_return(self, n):
        """ReturnStmt: value is optional (bare return for void functions)."""
        if n.value is not None:
            self._check_node(n.value)

    def _chk_print(self, n):
        """PrintStmt must have at least one value to print."""
        if not n.values:
            self.errors.append(CompilerError(Phase.IR, "PrintStmt has no values", n.line))
        for v in n.values: self._check_node(v)

    def _chk_input(self, n):
        """InputStmt must have a target variable name."""
        if not n.target:
            self.errors.append(CompilerError(Phase.IR, "InputStmt has no target variable", n.line))

    def _chk_call(self, n):
        """FunctionCall must have a name; args validated recursively."""
        if not n.name:
            self.errors.append(CompilerError(Phase.IR, "FunctionCall has empty function name", n.line))
        for arg in n.args: self._check_node(arg)

    def _chk_binop(self, n):
        """BinaryOp must have op and both left + right operands."""
        if not n.op:
            self.errors.append(CompilerError(Phase.IR, "BinaryOp has empty operator", n.line))
        self._check_node(n.left)
        self._check_node(n.right)

    def _chk_unaryop(self, n):
        """UnaryOp must have op and operand."""
        if not n.op:
            self.errors.append(CompilerError(Phase.IR, "UnaryOp has empty operator", n.line))
        self._check_node(n.operand)

    def _chk_arr_access(self, n):
        """ArrayAccess must have array name and index expression."""
        if not n.name:
            self.errors.append(CompilerError(Phase.IR, "ArrayAccess has empty array name", n.line))
        self._check_node(n.index)

    # ── JSON serialisation ────────────────────────────────────────────

    def to_dict(self, program: Program) -> dict:
        """Convert entire AST to JSON-serialisable dict for frontend modal.
        Each node → {"node": "TypeName", ...fields...}."""
        return self._n2d(program)

    def _n2d(self, node):
        """Recursively convert one AST node to dict. Dispatch by isinstance."""
        if node is None:
            return None  # optional fields → null in JSON
        if isinstance(node, Program):
            return {"node": "Program",
                    "functions": [self._n2d(f) for f in node.functions],
                    "globals": [self._n2d(g) for g in node.globals]}
        if isinstance(node, FunctionDecl):
            return {"node": "FunctionDecl", "name": node.name,
                    "params": [self._n2d(p) for p in node.params],
                    "return_type": node.return_type.value,
                    "body": [self._n2d(s) for s in node.body], "line": node.line}
        if isinstance(node, Param):
            return {"node": "Param", "name": node.name,
                    "data_type": node.data_type.value, "line": node.line}
        if isinstance(node, VarDecl):
            return {"node": "VarDecl", "name": node.name,
                    "data_type": node.data_type.value,
                    "value": self._n2d(node.value), "line": node.line}
        if isinstance(node, ArrayDecl):
            return {"node": "ArrayDecl", "name": node.name,
                    "data_type": node.data_type.value, "size": node.size,
                    "elements": [self._n2d(e) for e in node.elements], "line": node.line}
        if isinstance(node, AssignStmt):
            return {"node": "AssignStmt", "name": node.name,
                    "value": self._n2d(node.value), "line": node.line}
        if isinstance(node, ArrayAssign):
            return {"node": "ArrayAssign", "name": node.name,
                    "index": self._n2d(node.index),
                    "value": self._n2d(node.value), "line": node.line}
        if isinstance(node, IfStmt):
            return {"node": "IfStmt", "condition": self._n2d(node.condition),
                    "then_body": [self._n2d(s) for s in node.then_body],
                    "else_body": [self._n2d(s) for s in node.else_body], "line": node.line}
        if isinstance(node, WhileStmt):
            return {"node": "WhileStmt", "condition": self._n2d(node.condition),
                    "body": [self._n2d(s) for s in node.body], "line": node.line}
        if isinstance(node, ForRangeStmt):
            return {"node": "ForRangeStmt", "var": node.var,
                    "start": self._n2d(node.start), "stop": self._n2d(node.stop),
                    "step": self._n2d(node.step),
                    "body": [self._n2d(s) for s in node.body], "line": node.line}
        if isinstance(node, ForEachStmt):
            return {"node": "ForEachStmt", "var": node.var,
                    "array_name": node.array_name,
                    "body": [self._n2d(s) for s in node.body], "line": node.line}
        if isinstance(node, ReturnStmt):
            return {"node": "ReturnStmt", "value": self._n2d(node.value), "line": node.line}
        if isinstance(node, PrintStmt):
            return {"node": "PrintStmt",
                    "values": [self._n2d(v) for v in node.values],
                    "separator": node.separator, "line": node.line}
        if isinstance(node, InputStmt):
            return {"node": "InputStmt", "target": node.target,
                    "data_type": node.data_type.value,
                    "prompt": node.prompt, "line": node.line}
        if isinstance(node, FunctionCall):
            return {"node": "FunctionCall", "name": node.name,
                    "args": [self._n2d(a) for a in node.args], "line": node.line}
        if isinstance(node, BinaryOp):
            return {"node": "BinaryOp", "op": node.op,
                    "left": self._n2d(node.left),
                    "right": self._n2d(node.right), "line": node.line}
        if isinstance(node, UnaryOp):
            return {"node": "UnaryOp", "op": node.op,
                    "operand": self._n2d(node.operand), "line": node.line}
        if isinstance(node, Var):
            return {"node": "Var", "name": node.name, "line": node.line}
        if isinstance(node, ArrayAccess):
            return {"node": "ArrayAccess", "name": node.name,
                    "index": self._n2d(node.index), "line": node.line}
        if isinstance(node, Literal):
            return {"node": "Literal", "value": node.value,
                    "data_type": node.data_type.value, "line": node.line}
        # Fallback for unknown node — safety net for debugging
        return {"node": type(node).__name__, "line": getattr(node, 'line', None)}
