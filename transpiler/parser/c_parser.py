"""
parser/c_parser.py — Recursive descent parser for C source.
Converts C token stream into language-neutral AST. Uses { } blocks, semicolons.
Designed for inheritance: CppParser overrides only cout/cin handling.
"""
try:
    from transpiler.errors import CompilerError, CompilerErrorList, Phase
    from transpiler.lexer.tokens import Token, TokenType
    from transpiler.ast_nodes import (
        DataType, Program, FunctionDecl, Param, VarDecl, ArrayDecl,
        AssignStmt, ArrayAssign, IfStmt, WhileStmt, ForRangeStmt,
        ForEachStmt, ReturnStmt, PrintStmt, InputStmt, FunctionCall,
        BinaryOp, UnaryOp, Var, ArrayAccess, Literal)
except ModuleNotFoundError:
    from errors import CompilerError, CompilerErrorList, Phase
    from lexer.tokens import Token, TokenType
    from ast_nodes import (
        DataType, Program, FunctionDecl, Param, VarDecl, ArrayDecl,
        AssignStmt, ArrayAssign, IfStmt, WhileStmt, ForRangeStmt,
        ForEachStmt, ReturnStmt, PrintStmt, InputStmt, FunctionCall,
        BinaryOp, UnaryOp, Var, ArrayAccess, Literal)

TYPE_MAP = {
    TokenType.INT_KW: DataType.INT, TokenType.FLOAT_KW: DataType.FLOAT,
    TokenType.BOOL_KW: DataType.BOOL, TokenType.VOID: DataType.VOID,
}


class CParser:
    """Recursive descent parser for C subset. CppParser extends this."""

    def parse(self, tokens: list) -> Program:
        self.tokens, self.pos, self.errors = tokens, 0, []
        program = self._parse_program()
        if self.errors:
            raise CompilerErrorList(self.errors)
        return program

    # ── Token Navigation ──────────────────────────────────────────────

    def _current(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else self.tokens[-1]

    def _peek(self, offset=1):
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else self.tokens[-1]

    def _advance(self):
        tok = self._current()
        if self.pos < len(self.tokens) - 1: self.pos += 1
        return tok

    def _expect(self, ttype):
        cur = self._current()
        if cur.type != ttype:
            self.errors.append(CompilerError(Phase.PARSER,
                f"Expected {ttype.name}, got {cur.type.name} ('{cur.value}')", cur.line, cur.col))
            return cur
        return self._advance()

    def _match(self, *types):
        if self._current().type in types: return self._advance()
        return None

    def _is_type_keyword(self):
        return self._current().type in TYPE_MAP

    # ── Program Structure ─────────────────────────────────────────────

    def _parse_program(self):
        functions, globals_ = [], []
        while self._current().type != TokenType.EOF:
            if self._current().type == TokenType.INCLUDE:
                self._advance(); continue
            if self._is_type_keyword():
                result = self._parse_typed_decl_or_func()
                if isinstance(result, FunctionDecl):
                    functions.append(result)
                elif isinstance(result, list):
                    # Multi-var declarations return a list
                    globals_.extend(result)
                elif result:
                    globals_.append(result)
            else:
                stmt = self._parse_statement()
                if stmt: globals_.append(stmt)
        return Program(functions=functions, globals=globals_)

    def _parse_typed_decl_or_func(self):
        """Distinguish function_def from var_decl by peeking past name.
        Handles comma-separated declarations: int a, b, c;"""
        dtype = self._parse_type()
        # Accept MAIN keyword as a valid function/var name
        if self._current().type == TokenType.MAIN:
            name_tok = self._advance()
        else:
            name_tok = self._expect(TokenType.NAME)
        name, line = name_tok.value, name_tok.line
        if self._current().type == TokenType.LPAREN:
            return self._parse_function_def(dtype, name, line)
        if self._current().type == TokenType.LBRACKET:
            return self._parse_array_decl(dtype, name, line)
        # Parse first variable (may have initializer)
        value = None
        if self._match(TokenType.ASSIGN): value = self._parse_expression()
        decls = [VarDecl(name=name, data_type=dtype, value=value, line=line)]
        # Handle comma-separated: int a, b, c = 5;
        while self._match(TokenType.COMMA):
            next_tok = self._expect(TokenType.NAME)
            v = None
            if self._match(TokenType.ASSIGN): v = self._parse_expression()
            decls.append(VarDecl(name=next_tok.value, data_type=dtype, value=v, line=next_tok.line))
        self._expect(TokenType.SEMICOLON)
        return decls  # returns a list

    def _parse_function_def(self, return_type, name, line):
        self._expect(TokenType.LPAREN)
        params = self._parse_typed_params()
        self._expect(TokenType.RPAREN)
        body = self._parse_block()
        return FunctionDecl(name=name, params=params, return_type=return_type,
                            body=body, line=line)

    def _parse_typed_params(self):
        params = []
        if self._current().type == TokenType.RPAREN: return params
        dtype = self._parse_type()
        tok = self._expect(TokenType.NAME)
        params.append(Param(name=tok.value, data_type=dtype, line=tok.line))
        while self._match(TokenType.COMMA):
            dtype = self._parse_type()
            tok = self._expect(TokenType.NAME)
            params.append(Param(name=tok.value, data_type=dtype, line=tok.line))
        return params

    def _parse_type(self):
        cur = self._current()
        if cur.type in TYPE_MAP:
            self._advance(); return TYPE_MAP[cur.type]
        self.errors.append(CompilerError(Phase.PARSER,
            f"Expected type keyword, got {cur.type.name}", cur.line, cur.col))
        return DataType.UNKNOWN

    def _parse_block(self):
        self._expect(TokenType.LBRACE)
        stmts = []
        while self._current().type not in (TokenType.RBRACE, TokenType.EOF):
            if self._is_type_keyword():
                result = self._parse_local_typed_decl()
                # _parse_local_typed_decl now returns a list
                if isinstance(result, list):
                    stmts.extend(result)
                elif result:
                    stmts.append(result)
            else:
                stmt = self._parse_statement()
                # scanf can return a list of InputStmts
                if isinstance(stmt, list):
                    stmts.extend(stmt)
                elif stmt:
                    stmts.append(stmt)
        self._expect(TokenType.RBRACE)
        return stmts

    def _parse_block_or_single(self):
        """Parse either a { ... } block or a single statement.
        C allows braceless bodies: for(...) stmt; / if(...) stmt; / while(...) stmt;
        """
        if self._current().type == TokenType.LBRACE:
            return self._parse_block()
        # Single statement — parse one statement and wrap in a list
        if self._is_type_keyword():
            result = self._parse_local_typed_decl()
            return [result] if result else []
        stmt = self._parse_statement()
        return [stmt] if stmt else []

    def _parse_local_typed_decl(self):
        """Parse local typed declaration, handling comma-separated vars/arrays.
        e.g. int n, m, arr[n];
        Returns a list of VarDecl or ArrayDecl nodes."""
        dtype = self._parse_type()
        decls = []
        
        while True:
            name_tok = self._expect(TokenType.NAME)
            name, line = name_tok.value, name_tok.line
            
            if self._current().type == TokenType.LBRACKET:
                # It's an array: arr[n] or arr[] = {...}
                self._advance()
                if self._current().type == TokenType.RBRACKET:
                    # int arr[] = {1, 2}
                    self._advance()
                    self._expect(TokenType.ASSIGN)
                    self._expect(TokenType.LBRACE)
                    elements = self._parse_args()
                    self._expect(TokenType.RBRACE)
                    decls.append(ArrayDecl(name=name, data_type=dtype, size=len(elements), elements=elements, line=line))
                else:
                    # int arr[n]
                    size_expr = self._parse_expression()
                    # Store either exact int if Literal, or keeping it as ASTNode
                    if hasattr(size_expr, "value") and type(size_expr.value) is int:
                        size = size_expr.value
                    elif hasattr(size_expr, "name"):
                        size = size_expr.name
                    else:
                        size = size_expr
                    self._expect(TokenType.RBRACKET)
                    elements = []
                    if self._match(TokenType.ASSIGN):
                        self._expect(TokenType.LBRACE)
                        elements = self._parse_args()
                        self._expect(TokenType.RBRACE)
                    decls.append(ArrayDecl(name=name, data_type=dtype, size=size, elements=elements, line=line))
            else:
                # normal var
                value = None
                if self._match(TokenType.ASSIGN):
                    value = self._parse_expression()
                decls.append(VarDecl(name=name, data_type=dtype, value=value, line=line))
            
            if not self._match(TokenType.COMMA):
                break
                
        self._expect(TokenType.SEMICOLON)
        return decls

    # ── Statements ────────────────────────────────────────────────────

    def _parse_statement(self):
        cur = self._current()
        if cur.type == TokenType.IF:      return self._parse_if()
        if cur.type == TokenType.WHILE:   return self._parse_while()
        if cur.type == TokenType.FOR:     return self._parse_for()
        if cur.type == TokenType.RETURN:  return self._parse_return()
        if cur.type == TokenType.PRINTF:  return self._parse_printf()
        if cur.type == TokenType.SCANF:   return self._parse_scanf()
        if cur.type == TokenType.NAME:    return self._parse_name_stmt()
        self.errors.append(CompilerError(Phase.PARSER,
            f"Unexpected token: {cur.type.name} ('{cur.value}')", cur.line, cur.col))
        self._advance()
        return None

    def _parse_if(self):
        line = self._advance().line
        self._expect(TokenType.LPAREN)
        condition = self._parse_expression()
        self._expect(TokenType.RPAREN)
        then_body = self._parse_block_or_single()
        else_body = []
        if self._match(TokenType.ELSE): else_body = self._parse_block_or_single()
        return IfStmt(condition=condition, then_body=then_body, else_body=else_body, line=line)

    def _parse_while(self):
        line = self._advance().line
        self._expect(TokenType.LPAREN)
        condition = self._parse_expression()
        self._expect(TokenType.RPAREN)
        return WhileStmt(condition=condition, body=self._parse_block_or_single(), line=line)

    def _parse_for(self):
        """Parse C for-loop: for(int i=0; i<n; i++) or for(i=1; i<=10; i++)
        The type keyword is optional — variable may be declared outside the loop."""
        line = self._advance().line
        self._expect(TokenType.LPAREN)
        # Type keyword is optional: for(int i=0;...) vs for(i=1;...)
        if self._is_type_keyword():
            self._parse_type()  # consume type but we don't use it in ForRangeStmt
        var_tok = self._expect(TokenType.NAME)
        self._expect(TokenType.ASSIGN)
        start = self._parse_expression()
        self._expect(TokenType.SEMICOLON)
        cond = self._parse_expression()
        # Extract stop value from condition: i < n → stop=n, i <= n → stop=n+1
        if isinstance(cond, BinaryOp):
            stop = cond.right
            # For <=, the range must be inclusive: i<=10 → range(1, 11)
            if cond.op in ("<=", ">="):
                stop = BinaryOp(op="+", left=stop,
                    right=Literal(value=1, data_type=DataType.INT, line=line), line=line)
        else:
            stop = cond
        self._expect(TokenType.SEMICOLON)
        step = self._parse_for_update()
        self._expect(TokenType.RPAREN)
        body = self._parse_block_or_single()
        return ForRangeStmt(var=var_tok.value, start=start, stop=stop,
                            step=step, body=body, line=line)

    def _parse_for_update(self):
        """Parse C for-loop update: i++, i+=1, i=i+1."""
        self._expect(TokenType.NAME)
        # i++ or i--
        if self._current().type == TokenType.PLUS and self._peek().type == TokenType.PLUS:
            self._advance(); self._advance()
            return Literal(value=1, data_type=DataType.INT)
        if self._current().type == TokenType.MINUS and self._peek().type == TokenType.MINUS:
            self._advance(); self._advance()
            return UnaryOp(op="-", operand=Literal(value=1, data_type=DataType.INT))
        # i += expr or i -= expr
        if self._current().type == TokenType.PLUS and self._peek().type == TokenType.ASSIGN:
            self._advance(); self._advance()
            return self._parse_expression()
        if self._current().type == TokenType.MINUS and self._peek().type == TokenType.ASSIGN:
            self._advance(); self._advance()
            return UnaryOp(op="-", operand=self._parse_expression())
        # i = i + expr
        if self._current().type == TokenType.ASSIGN:
            self._advance()
            expr = self._parse_expression()
            if isinstance(expr, BinaryOp) and expr.op == "+": return expr.right
            if isinstance(expr, BinaryOp) and expr.op == "-":
                return UnaryOp(op="-", operand=expr.right)
            return expr
        return Literal(value=1, data_type=DataType.INT)

    def _parse_return(self):
        line = self._advance().line
        value = None
        if self._current().type != TokenType.SEMICOLON: value = self._parse_expression()
        self._expect(TokenType.SEMICOLON)
        return ReturnStmt(value=value, line=line)

    def _parse_printf(self):
        """Parse printf with full format string support.
        printf("%d x %d = %d\\n", n, i, n*i) -> interleaved literals + expressions.
        """
        line = self._advance().line
        self._expect(TokenType.LPAREN)
        fmt_tok = self._expect(TokenType.STRING)
        # Collect argument expressions after the format string
        args = []
        while self._match(TokenType.COMMA):
            args.append(self._parse_expression())
        self._expect(TokenType.RPAREN); self._expect(TokenType.SEMICOLON)

        fmt = fmt_tok.value.strip('"')

        # If no args, it's a plain string print: printf("hello\n")
        if not args:
            text = fmt.replace("\\n", "")
            if text:
                return PrintStmt(values=[Literal(value=text, data_type=DataType.STR, line=line)], line=line)
            return PrintStmt(values=[], line=line)

        # Parse format string: split on %d, %f, %s etc.
        # Interleave literal text segments with argument expressions
        values = []
        arg_idx = 0
        i = 0
        segment = ""

        while i < len(fmt):
            if fmt[i] == '%' and i + 1 < len(fmt) and fmt[i+1] in ('d', 'f', 's', 'c', 'i', 'u'):
                if segment:
                    values.append(Literal(value=segment, data_type=DataType.STR, line=line))
                    segment = ""
                if arg_idx < len(args):
                    values.append(args[arg_idx])
                    arg_idx += 1
                i += 2
            elif fmt[i] == '%' and i + 2 < len(fmt) and fmt[i+1] == 'l' and fmt[i+2] in ('d', 'f'):
                if segment:
                    values.append(Literal(value=segment, data_type=DataType.STR, line=line))
                    segment = ""
                if arg_idx < len(args):
                    values.append(args[arg_idx])
                    arg_idx += 1
                i += 3
            elif fmt[i:i+2] == '\\n':
                i += 2
            elif fmt[i:i+2] == '\\t':
                segment += "\t"
                i += 2
            else:
                segment += fmt[i]
                i += 1

        if segment:
            values.append(Literal(value=segment, data_type=DataType.STR, line=line))

        return PrintStmt(values=values, separator="", line=line)

    def _parse_scanf(self):
        """Parse scanf with multiple variables: scanf("%d%d", &n, &m);
        Each variable becomes a separate InputStmt."""
        line = self._advance().line
        self._expect(TokenType.LPAREN)
        fmt = self._expect(TokenType.STRING).value.strip('"')
        targets = []
        while self._match(TokenType.COMMA):
            # Lexer skips & usually. Just parse expression (Var or ArrayAccess)
            expr = self._parse_expression()
            targets.append(expr)
        self._expect(TokenType.RPAREN); self._expect(TokenType.SEMICOLON)
        # Determine types from format specifiers
        specs = []
        i = 0
        while i < len(fmt):
            if fmt[i] == '%' and i + 1 < len(fmt):
                spec = fmt[i+1]
                if spec == 'f': specs.append(DataType.FLOAT)
                elif spec == 's': specs.append(DataType.STR)
                else: specs.append(DataType.INT)
                i += 2
            else:
                i += 1
        # Create one InputStmt per variable
        stmts = []
        for idx, target in enumerate(targets):
            dtype = specs[idx] if idx < len(specs) else DataType.INT
            stmts.append(InputStmt(target=target, data_type=dtype, line=line))
        # Return single stmt or list
        if len(stmts) == 1:
            return stmts[0]
        return stmts

    def _parse_name_stmt(self):
        name_tok = self._advance()
        name, line = name_tok.value, name_tok.line
        if self._current().type == TokenType.LBRACKET:
            self._advance()
            index = self._parse_expression()
            self._expect(TokenType.RBRACKET); self._expect(TokenType.ASSIGN)
            value = self._parse_expression()
            self._expect(TokenType.SEMICOLON)
            return ArrayAssign(name=name, index=index, value=value, line=line)
        if self._current().type == TokenType.ASSIGN:
            self._advance()
            value = self._parse_expression()
            self._expect(TokenType.SEMICOLON)
            return AssignStmt(name=name, value=value, line=line)
        if self._current().type == TokenType.LPAREN:
            self._advance()
            args = self._parse_args()
            self._expect(TokenType.RPAREN); self._expect(TokenType.SEMICOLON)
            return FunctionCall(name=name, args=args, line=line)
        self._expect(TokenType.SEMICOLON)
        return Var(name=name, line=line)

    # ── Expressions (same precedence chain as PythonParser) ───────────

    def _parse_expression(self): return self._parse_or()

    def _parse_or(self):
        left = self._parse_and()
        while self._current().type == TokenType.OR:
            op = self._advance()
            left = BinaryOp(op="||", left=left, right=self._parse_and(), line=op.line)
        return left

    def _parse_and(self):
        left = self._parse_not()
        while self._current().type == TokenType.AND:
            op = self._advance()
            left = BinaryOp(op="&&", left=left, right=self._parse_not(), line=op.line)
        return left

    def _parse_not(self):
        if self._current().type == TokenType.NOT:
            op = self._advance()
            return UnaryOp(op="!", operand=self._parse_not(), line=op.line)
        return self._parse_comparison()

    def _parse_comparison(self):
        left = self._parse_addition()
        cmp = (TokenType.EQ, TokenType.NEQ, TokenType.LT, TokenType.GT, TokenType.LEQ, TokenType.GEQ)
        while self._current().type in cmp:
            op = self._advance()
            left = BinaryOp(op=op.value, left=left, right=self._parse_addition(), line=op.line)
        return left

    def _parse_addition(self):
        left = self._parse_multiplication()
        while self._current().type in (TokenType.PLUS, TokenType.MINUS):
            op = self._advance()
            left = BinaryOp(op=op.value, left=left, right=self._parse_multiplication(), line=op.line)
        return left

    def _parse_multiplication(self):
        left = self._parse_unary()
        while self._current().type in (TokenType.STAR, TokenType.SLASH, TokenType.MODULO):
            op = self._advance()
            left = BinaryOp(op=op.value, left=left, right=self._parse_unary(), line=op.line)
        return left

    def _parse_unary(self):
        if self._current().type == TokenType.MINUS:
            op = self._advance()
            return UnaryOp(op="-", operand=self._parse_unary(), line=op.line)
        return self._parse_primary()

    def _parse_primary(self):
        cur = self._current()
        if cur.type == TokenType.NUMBER:
            self._advance()
            if "." in cur.value:
                return Literal(value=float(cur.value), data_type=DataType.FLOAT, line=cur.line)
            return Literal(value=int(cur.value), data_type=DataType.INT, line=cur.line)
        if cur.type == TokenType.STRING:
            self._advance()
            return Literal(value=cur.value.strip('"\''), data_type=DataType.STR, line=cur.line)
        if cur.type == TokenType.TRUE:
            self._advance(); return Literal(value=True, data_type=DataType.BOOL, line=cur.line)
        if cur.type == TokenType.FALSE:
            self._advance(); return Literal(value=False, data_type=DataType.BOOL, line=cur.line)
        if cur.type == TokenType.NAME:
            name_tok = self._advance()
            if self._current().type == TokenType.LPAREN:
                self._advance()
                args = self._parse_args()
                self._expect(TokenType.RPAREN)
                return FunctionCall(name=name_tok.value, args=args, line=name_tok.line)
            if self._current().type == TokenType.LBRACKET:
                self._advance()
                index = self._parse_expression()
                self._expect(TokenType.RBRACKET)
                return ArrayAccess(name=name_tok.value, index=index, line=name_tok.line)
            return Var(name=name_tok.value, line=name_tok.line)
        if cur.type == TokenType.LPAREN:
            self._advance()
            expr = self._parse_expression()
            self._expect(TokenType.RPAREN)
            return expr
        self.errors.append(CompilerError(Phase.PARSER,
            f"Unexpected token in expression: {cur.type.name} ('{cur.value}')", cur.line, cur.col))
        self._advance()
        return Literal(value=0, data_type=DataType.INT, line=cur.line)

    def _parse_args(self):
        args = []
        if self._current().type in (TokenType.RPAREN, TokenType.RBRACE): return args
        args.append(self._parse_expression())
        while self._match(TokenType.COMMA): args.append(self._parse_expression())
        return args
