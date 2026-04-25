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
                if isinstance(result, FunctionDecl): functions.append(result)
                elif result: globals_.append(result)
            else:
                stmt = self._parse_statement()
                if stmt: globals_.append(stmt)
        return Program(functions=functions, globals=globals_)

    def _parse_typed_decl_or_func(self):
        """Distinguish function_def from var_decl by peeking past name."""
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
        value = None
        if self._match(TokenType.ASSIGN): value = self._parse_expression()
        self._expect(TokenType.SEMICOLON)
        return VarDecl(name=name, data_type=dtype, value=value, line=line)

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
                if result: stmts.append(result)
            else:
                stmt = self._parse_statement()
                if stmt: stmts.append(stmt)
        self._expect(TokenType.RBRACE)
        return stmts

    def _parse_local_typed_decl(self):
        dtype = self._parse_type()
        name_tok = self._expect(TokenType.NAME)
        name, line = name_tok.value, name_tok.line
        if self._current().type == TokenType.LBRACKET:
            return self._parse_array_decl(dtype, name, line)
        value = None
        if self._match(TokenType.ASSIGN): value = self._parse_expression()
        self._expect(TokenType.SEMICOLON)
        return VarDecl(name=name, data_type=dtype, value=value, line=line)

    def _parse_array_decl(self, dtype, name, line):
        self._expect(TokenType.LBRACKET)
        if self._current().type == TokenType.NUMBER:
            size = int(self._advance().value)
            self._expect(TokenType.RBRACKET)
            elements = []
            if self._match(TokenType.ASSIGN):
                self._expect(TokenType.LBRACE)
                elements = self._parse_args()
                self._expect(TokenType.RBRACE)
            self._expect(TokenType.SEMICOLON)
            return ArrayDecl(name=name, data_type=dtype, size=size, elements=elements, line=line)
        self._expect(TokenType.RBRACKET); self._expect(TokenType.ASSIGN)
        self._expect(TokenType.LBRACE)
        elements = self._parse_args()
        self._expect(TokenType.RBRACE); self._expect(TokenType.SEMICOLON)
        return ArrayDecl(name=name, data_type=dtype, size=len(elements),
                         elements=elements, line=line)

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
        then_body = self._parse_block()
        else_body = []
        if self._match(TokenType.ELSE): else_body = self._parse_block()
        return IfStmt(condition=condition, then_body=then_body, else_body=else_body, line=line)

    def _parse_while(self):
        line = self._advance().line
        self._expect(TokenType.LPAREN)
        condition = self._parse_expression()
        self._expect(TokenType.RPAREN)
        return WhileStmt(condition=condition, body=self._parse_block(), line=line)

    def _parse_for(self):
        line = self._advance().line
        self._expect(TokenType.LPAREN)
        dtype = self._parse_type()
        var_tok = self._expect(TokenType.NAME)
        self._expect(TokenType.ASSIGN)
        start = self._parse_expression()
        self._expect(TokenType.SEMICOLON)
        cond = self._parse_expression()
        stop = cond.right if isinstance(cond, BinaryOp) else cond
        self._expect(TokenType.SEMICOLON)
        step = self._parse_for_update()
        self._expect(TokenType.RPAREN)
        body = self._parse_block()
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
        line = self._advance().line
        self._expect(TokenType.LPAREN)
        fmt_tok = self._expect(TokenType.STRING)
        values = []
        while self._match(TokenType.COMMA): values.append(self._parse_expression())
        self._expect(TokenType.RPAREN); self._expect(TokenType.SEMICOLON)
        if not values and fmt_tok.type == TokenType.STRING:
            text = fmt_tok.value.strip('"').replace("\\n", "")
            if text: values = [Literal(value=text, data_type=DataType.STR, line=line)]
        return PrintStmt(values=values, line=line)

    def _parse_scanf(self):
        line = self._advance().line
        self._expect(TokenType.LPAREN)
        fmt = self._expect(TokenType.STRING).value.strip('"')
        self._expect(TokenType.COMMA)
        target = self._expect(TokenType.NAME).value
        self._expect(TokenType.RPAREN); self._expect(TokenType.SEMICOLON)
        dtype = DataType.FLOAT if "%f" in fmt else (DataType.STR if "%s" in fmt else DataType.INT)
        return InputStmt(target=target, data_type=dtype, line=line)

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
        while self._current().type in (TokenType.STAR, TokenType.SLASH):
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
