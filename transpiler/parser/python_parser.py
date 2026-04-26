"""
parser/python_parser.py — Recursive descent parser for Python source.
Converts token stream into language-neutral AST using INDENT/DEDENT for blocks.
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

# Hard-rejected keywords → clear error messages
HARD_REJECT = {
    "class": "Classes and structs are not supported",
    "import": "Import statements are not supported",
    "try": "Exception handling is not supported",
    "lambda": "Lambda expressions are not supported",
    "global": "The global keyword is not supported",
}


class PythonParser:
    """Recursive descent parser for the Python subset."""

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
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return tok

    def _expect(self, ttype):
        cur = self._current()
        if cur.type != ttype:
            self.errors.append(CompilerError(Phase.PARSER,
                f"Expected {ttype.name}, got {cur.type.name} ('{cur.value}')", cur.line, cur.col))
            return cur
        return self._advance()

    def _match(self, *types):
        if self._current().type in types:
            return self._advance()
        return None

    # ── Program Structure ─────────────────────────────────────────────

    def _parse_program(self):
        functions, globals_ = [], []
        while self._current().type != TokenType.EOF:
            if self._current().type == TokenType.NEWLINE:
                self._advance(); continue
            if self._current().type == TokenType.DEF:
                functions.append(self._parse_function_def())
            else:
                stmt = self._parse_statement()
                if stmt: globals_.append(stmt)
        return Program(functions=functions, globals=globals_)

    def _parse_function_def(self):
        line = self._advance().line  # DEF
        name = self._expect(TokenType.NAME).value
        self._expect(TokenType.LPAREN)
        params = self._parse_params()
        self._expect(TokenType.RPAREN)
        self._expect(TokenType.COLON)
        self._match(TokenType.NEWLINE)
        body = self._parse_block()
        return FunctionDecl(name=name, params=params,
                            return_type=DataType.UNKNOWN, body=body, line=line)

    def _parse_params(self):
        params = []
        if self._current().type == TokenType.RPAREN: return params
        tok = self._expect(TokenType.NAME)
        params.append(Param(name=tok.value, data_type=DataType.UNKNOWN, line=tok.line))
        while self._match(TokenType.COMMA):
            tok = self._expect(TokenType.NAME)
            params.append(Param(name=tok.value, data_type=DataType.UNKNOWN, line=tok.line))
        return params

    def _parse_block(self):
        self._expect(TokenType.INDENT)
        stmts = []
        while self._current().type not in (TokenType.DEDENT, TokenType.EOF):
            if self._current().type == TokenType.NEWLINE:
                self._advance(); continue
            stmt = self._parse_statement()
            if stmt: stmts.append(stmt)
        self._expect(TokenType.DEDENT)
        return stmts

    # ── Statements ────────────────────────────────────────────────────

    def _parse_statement(self):
        cur = self._current()
        # Hard rejection for unsupported keywords
        if cur.type == TokenType.NAME and cur.value in HARD_REJECT:
            self.errors.append(CompilerError(Phase.PARSER, HARD_REJECT[cur.value], cur.line, cur.col))
            while self._current().type not in (TokenType.NEWLINE, TokenType.EOF):
                self._advance()
            return None
        if cur.type == TokenType.IF:      return self._parse_if()
        if cur.type == TokenType.WHILE:   return self._parse_while()
        if cur.type == TokenType.FOR:     return self._parse_for()
        if cur.type == TokenType.RETURN:  return self._parse_return()
        if cur.type == TokenType.PRINT:   return self._parse_print()
        if cur.type == TokenType.NAME:    return self._parse_name_stmt()
        if cur.type == TokenType.DEF:
            self.errors.append(CompilerError(Phase.PARSER,
                "Nested functions are not supported", cur.line, cur.col))
            while self._current().type not in (TokenType.NEWLINE, TokenType.EOF):
                self._advance()
            return None
        self.errors.append(CompilerError(Phase.PARSER,
            f"Unexpected token: {cur.type.name} ('{cur.value}')", cur.line, cur.col))
        self._advance()
        return None

    def _parse_if(self):
        line = self._advance().line
        condition = self._parse_expression()
        self._expect(TokenType.COLON); self._match(TokenType.NEWLINE)
        then_body = self._parse_block()
        else_body = []
        if self._match(TokenType.ELSE):
            self._expect(TokenType.COLON); self._match(TokenType.NEWLINE)
            else_body = self._parse_block()
        return IfStmt(condition=condition, then_body=then_body, else_body=else_body, line=line)

    def _parse_while(self):
        line = self._advance().line
        condition = self._parse_expression()
        self._expect(TokenType.COLON); self._match(TokenType.NEWLINE)
        return WhileStmt(condition=condition, body=self._parse_block(), line=line)

    def _parse_for(self):
        line = self._advance().line  # FOR
        var_tok = self._expect(TokenType.NAME)
        self._expect(TokenType.IN)
        if self._current().type == TokenType.RANGE:
            self._advance()  # RANGE
            self._expect(TokenType.LPAREN)
            args = self._parse_args()
            self._expect(TokenType.RPAREN)
            self._expect(TokenType.COLON); self._match(TokenType.NEWLINE)
            body = self._parse_block()
            zero = Literal(value=0, data_type=DataType.INT, line=line)
            one = Literal(value=1, data_type=DataType.INT, line=line)
            if len(args) == 1:   start, stop, step = zero, args[0], one
            elif len(args) == 2: start, stop, step = args[0], args[1], one
            elif len(args) == 3: start, stop, step = args[0], args[1], args[2]
            else:
                self.errors.append(CompilerError(Phase.PARSER, "range() takes 1-3 args", line))
                start = stop = step = zero
            return ForRangeStmt(var=var_tok.value, start=start, stop=stop,
                                step=step, body=body, line=line)
        # for x in arr
        arr_tok = self._expect(TokenType.NAME)
        self._expect(TokenType.COLON); self._match(TokenType.NEWLINE)
        return ForEachStmt(var=var_tok.value, array_name=arr_tok.value,
                           body=self._parse_block(), line=line)

    def _parse_return(self):
        line = self._advance().line
        value = None
        if self._current().type not in (TokenType.NEWLINE, TokenType.DEDENT, TokenType.EOF):
            value = self._parse_expression()
        self._match(TokenType.NEWLINE)
        return ReturnStmt(value=value, line=line)

    def _parse_print(self):
        line = self._advance().line
        self._expect(TokenType.LPAREN)
        values = self._parse_args()
        self._expect(TokenType.RPAREN)
        self._match(TokenType.NEWLINE)
        return PrintStmt(values=values, line=line)

    def _parse_name_stmt(self):
        """Handle NAME-starting stmts: assignment, array, input, call."""
        name_tok = self._advance()
        name, line = name_tok.value, name_tok.line
        # name[expr] = expr → ArrayAssign
        if self._current().type == TokenType.LBRACKET:
            self._advance()
            index = self._parse_expression()
            self._expect(TokenType.RBRACKET); self._expect(TokenType.ASSIGN)
            if (self._current().type in (TokenType.INT_KW, TokenType.FLOAT_KW)
                    and self._peek().type == TokenType.LPAREN
                    and self._peek(2).type == TokenType.INPUT):
                target_node = ArrayAccess(name=name, index=index, line=line)
                return self._parse_input_stmt(target_node, line)
            value = self._parse_expression()
            self._match(TokenType.NEWLINE)
            return ArrayAssign(name=name, index=index, value=value, line=line)
        # name = ...
        if self._current().type == TokenType.ASSIGN:
            self._advance()
            if self._current().type == TokenType.ARRAY:
                return self._parse_array_decl(name, line)
            if self._current().type == TokenType.LBRACKET:
                return self._parse_array_literal(name, line)
            if (self._current().type in (TokenType.INT_KW, TokenType.FLOAT_KW)
                    and self._peek().type == TokenType.LPAREN
                    and self._peek(2).type == TokenType.INPUT):
                return self._parse_input_stmt(name, line)
            value = self._parse_expression()
            self._match(TokenType.NEWLINE)
            return VarDecl(name=name, value=value, line=line)
        # name(args) → FunctionCall
        if self._current().type == TokenType.LPAREN:
            self._advance()
            args = self._parse_args()
            self._expect(TokenType.RPAREN); self._match(TokenType.NEWLINE)
            return FunctionCall(name=name, args=args, line=line)
        self._match(TokenType.NEWLINE)
        return Var(name=name, line=line)

    def _parse_array_decl(self, name, line):
        """array(type, size) → ArrayDecl"""
        self._advance()  # ARRAY
        self._expect(TokenType.LPAREN)
        dtype = self._parse_type_keyword()
        self._expect(TokenType.COMMA)
        size_tok = self._expect(TokenType.NUMBER)
        size = int(size_tok.value) if size_tok.value.isdigit() else 0
        self._expect(TokenType.RPAREN); self._match(TokenType.NEWLINE)
        return ArrayDecl(name=name, data_type=dtype, size=size, line=line)

    def _parse_array_literal(self, name, line):
        """[expr, ...] → ArrayDecl with elements
           [0] * n     → ArrayDecl with size n"""
        self._advance()  # [
        if self._current().type == TokenType.RBRACKET:
            self._advance()
            self._match(TokenType.NEWLINE)
            return ArrayDecl(name=name, data_type=DataType.UNKNOWN, size=0, line=line)
        
        elements = self._parse_args()
        self._expect(TokenType.RBRACKET)
        
        if self._match(TokenType.STAR):
            size_expr = self._parse_expression()
            self._match(TokenType.NEWLINE)
            size = size_expr.value if hasattr(size_expr, "value") else size_expr.name if hasattr(size_expr, "name") else size_expr
            dtype = elements[0].data_type if elements and hasattr(elements[0], "data_type") else DataType.INT
            return ArrayDecl(name=name, data_type=dtype, size=size, line=line)

        self._match(TokenType.NEWLINE)
        return ArrayDecl(name=name, data_type=DataType.UNKNOWN,
                         size=len(elements), elements=elements, line=line)

    def _parse_input_stmt(self, name, line):
        """int(input("prompt")) → InputStmt"""
        dtype = self._parse_type_keyword()
        self._expect(TokenType.LPAREN); self._expect(TokenType.INPUT)
        self._expect(TokenType.LPAREN)
        prompt = None
        if self._current().type == TokenType.STRING:
            prompt = self._advance().value.strip("\"'")
        self._expect(TokenType.RPAREN); self._expect(TokenType.RPAREN)
        self._match(TokenType.NEWLINE)
        return InputStmt(target=name, data_type=dtype, prompt=prompt, line=line)

    def _parse_type_keyword(self):
        cur = self._current()
        type_map = {TokenType.INT_KW: DataType.INT, TokenType.FLOAT_KW: DataType.FLOAT,
                    TokenType.BOOL_KW: DataType.BOOL}
        if cur.type in type_map:
            self._advance()
            return type_map[cur.type]
        self.errors.append(CompilerError(Phase.PARSER,
            f"Expected type keyword, got {cur.type.name}", cur.line, cur.col))
        return DataType.UNKNOWN

    # ── Expressions (precedence: or < and < not < cmp < add < mul < unary < primary)

    def _parse_expression(self):
        return self._parse_or()

    def _parse_or(self):
        left = self._parse_and()
        while self._current().type == TokenType.OR:
            op = self._advance()
            left = BinaryOp(op="or", left=left, right=self._parse_and(), line=op.line)
        return left

    def _parse_and(self):
        left = self._parse_not()
        while self._current().type == TokenType.AND:
            op = self._advance()
            left = BinaryOp(op="and", left=left, right=self._parse_not(), line=op.line)
        return left

    def _parse_not(self):
        if self._current().type == TokenType.NOT:
            op = self._advance()
            return UnaryOp(op="not", operand=self._parse_not(), line=op.line)
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
            return Literal(value=cur.value.strip("\"'"), data_type=DataType.STR, line=cur.line)
        if cur.type == TokenType.TRUE:
            self._advance()
            return Literal(value=True, data_type=DataType.BOOL, line=cur.line)
        if cur.type == TokenType.FALSE:
            self._advance()
            return Literal(value=False, data_type=DataType.BOOL, line=cur.line)
        if cur.type == TokenType.NAME:
            name_tok = self._advance()
            if self._current().type == TokenType.LPAREN:  # function call
                self._advance()
                args = self._parse_args()
                self._expect(TokenType.RPAREN)
                return FunctionCall(name=name_tok.value, args=args, line=name_tok.line)
            if self._current().type == TokenType.LBRACKET:  # array access
                self._advance()
                index = self._parse_expression()
                self._expect(TokenType.RBRACKET)
                return ArrayAccess(name=name_tok.value, index=index, line=name_tok.line)
            return Var(name=name_tok.value, line=name_tok.line)
        if cur.type == TokenType.LPAREN:  # grouped expression
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
        if self._current().type in (TokenType.RPAREN, TokenType.RBRACKET): return args
        args.append(self._parse_expression())
        while self._match(TokenType.COMMA):
            args.append(self._parse_expression())
        return args
