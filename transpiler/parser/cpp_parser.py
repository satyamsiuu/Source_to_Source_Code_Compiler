"""
parser/cpp_parser.py — Recursive descent parser for C++ source.
Phase 3 of the compiler pipeline.

EXTENDS CParser — does NOT copy-paste C parser code.
Only overrides:
    - _parse_statement() → detects cout/cin, delegates rest to parent
    - _parse_cout() → cout << expr << expr << endl; → PrintStmt
    - _parse_cin() → cin >> name; → InputStmt
    - _parse_program() → handles 'using namespace std;' by skipping NAME tokens

Design: C++ is largely a superset of C. All parsing logic for if/while/for/
functions/expressions is inherited unchanged from CParser.
"""

try:
    from transpiler.parser.c_parser import CParser
    from transpiler.errors import CompilerError, Phase
    from transpiler.lexer.tokens import TokenType
    from transpiler.ast_nodes import (
        DataType, PrintStmt, InputStmt, Literal, Var
    )
except ModuleNotFoundError:
    from parser.c_parser import CParser
    from errors import CompilerError, Phase
    from lexer.tokens import TokenType
    from ast_nodes import (
        DataType, PrintStmt, InputStmt, Literal, Var
    )


class CppParser(CParser):
    """Recursive descent parser for C++ subset. Inherits from CParser.

    Only adds: cout << ... → PrintStmt, cin >> ... → InputStmt,
    and skips 'using namespace std;' boilerplate.
    """

    def _parse_program(self):
        """Override to handle 'using namespace std;' which appears as NAME tokens."""
        try:
            from transpiler.ast_nodes import Program, FunctionDecl
        except ModuleNotFoundError:
            from ast_nodes import Program, FunctionDecl
        functions, globals_ = [], []
        while self._current().type != TokenType.EOF:
            if self._current().type == TokenType.INCLUDE:
                self._advance()
                continue
            # Skip 'using namespace std;' — three NAME tokens + SEMICOLON
            if (self._current().type == TokenType.NAME
                    and self._current().value == "using"):
                while self._current().type not in (TokenType.SEMICOLON, TokenType.EOF):
                    self._advance()
                self._match(TokenType.SEMICOLON)
                continue
            if self._is_type_keyword():
                result = self._parse_typed_decl_or_func()
                if isinstance(result, FunctionDecl):
                    functions.append(result)
                elif result:
                    globals_.append(result)
            else:
                stmt = self._parse_statement()
                if stmt:
                    globals_.append(stmt)
        return Program(functions=functions, globals=globals_)

    def _parse_statement(self):
        """Override: detect cout/cin, delegate everything else to CParser."""
        cur = self._current()
        if cur.type == TokenType.COUT:
            return self._parse_cout()
        if cur.type == TokenType.CIN:
            return self._parse_cin()
        # All other statements handled by parent CParser
        return super()._parse_statement()

    def _parse_cout(self) -> PrintStmt:
        """cout << expr << " " << expr << endl; → PrintStmt(values=[...])

        The << operator is tokenized as two LT tokens.
        'endl' is a NAME token that we detect and skip (we always add newline).
        """
        line = self._advance().line  # consume COUT
        values = []
        while True:
            # Expect << (two LT tokens)
            if self._current().type != TokenType.LT:
                break
            self._advance()  # first <
            if self._current().type != TokenType.LT:
                break
            self._advance()  # second <
            # Check for 'endl' — skip it, we handle newlines in generation
            if self._current().type == TokenType.NAME and self._current().value == "endl":
                self._advance()
                continue
            # Check for separator string " " — skip these too
            if (self._current().type == TokenType.STRING
                    and self._current().value.strip("\"'") == " "):
                self._advance()
                continue
            # Parse expression — use _parse_addition to stop before '<' tokens
            # (since << is tokenized as LT LT, _parse_expression would consume them)
            values.append(self._parse_addition())
        self._expect(TokenType.SEMICOLON)
        return PrintStmt(values=values, line=line)

    def _parse_cin(self) -> InputStmt:
        """cin >> name; → InputStmt(target=name, data_type=UNKNOWN)

        The >> operator is tokenized as two GT tokens.
        Type will be resolved by the semantic analyzer from prior declaration.
        """
        line = self._advance().line  # consume CIN
        # Expect >> (two GT tokens)
        self._expect(TokenType.GT)
        self._expect(TokenType.GT)
        target = self._expect(TokenType.NAME).value
        self._expect(TokenType.SEMICOLON)
        return InputStmt(target=target, data_type=DataType.UNKNOWN, line=line)
