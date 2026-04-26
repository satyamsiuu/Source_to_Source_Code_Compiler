"""
lexer/c_lexer.py — Tokenizes C source code.
Phase 2 of the compiler pipeline.

Key differences from Python lexer:
    - No INDENT/DEDENT (C uses { } for blocks)
    - Semicolons are significant (statement terminators)
    - { and } are block delimiters
    - Type keywords appear in declarations: int, float, void
    - C-specific tokens: printf, scanf, main, #include
    - Whitespace (including newlines) is insignificant between tokens

This lexer is designed to be EXTENDED by CppLexer (not copy-pasted).
CppLexer adds cout, cin, :: and overrides the keyword map.
"""

try:
    from transpiler.errors import CompilerError, CompilerErrorList, Phase
    from transpiler.lexer.tokens import Token, TokenType
except ModuleNotFoundError:
    from errors import CompilerError, CompilerErrorList, Phase
    from lexer.tokens import Token, TokenType


# C keywords → token types (CppLexer extends this dict)
C_KEYWORDS = {
    "if": TokenType.IF, "else": TokenType.ELSE, "while": TokenType.WHILE,
    "for": TokenType.FOR, "return": TokenType.RETURN,
    "printf": TokenType.PRINTF, "scanf": TokenType.SCANF,
    "void": TokenType.VOID, "main": TokenType.MAIN,
    "int": TokenType.INT_KW, "float": TokenType.FLOAT_KW,
    "bool": TokenType.BOOL_KW,
    "true": TokenType.TRUE, "false": TokenType.FALSE,
}

# Two-character operators (checked before single-char)
C_TWO_CHAR_OPS = {
    "==": TokenType.EQ, "!=": TokenType.NEQ,
    "<=": TokenType.LEQ, ">=": TokenType.GEQ,
}

# Single-character operators and delimiters
C_ONE_CHAR_OPS = {
    "+": TokenType.PLUS, "-": TokenType.MINUS,
    "*": TokenType.STAR, "/": TokenType.SLASH, "%": TokenType.MODULO,
    "<": TokenType.LT, ">": TokenType.GT, "=": TokenType.ASSIGN,
    "(": TokenType.LPAREN, ")": TokenType.RPAREN,
    "{": TokenType.LBRACE, "}": TokenType.RBRACE,
    "[": TokenType.LBRACKET, "]": TokenType.RBRACKET,
    ",": TokenType.COMMA, ";": TokenType.SEMICOLON,
    ":": TokenType.COLON,
}


class CLexer:
    """Tokenizes C source code into a list of Token objects.

    Designed for inheritance: CppLexer overrides get_keywords() and
    get_two_char_ops() to add C++-specific tokens without duplicating code.

    Usage:
        lexer = CLexer()
        tokens = lexer.tokenize("int main() { return 0; }")
    """

    def get_keywords(self) -> dict:
        """Returns keyword→TokenType mapping. Override in subclass to add keywords."""
        return C_KEYWORDS

    def get_two_char_ops(self) -> dict:
        """Returns two-char operator→TokenType mapping. Override to add operators."""
        return C_TWO_CHAR_OPS

    def get_one_char_ops(self) -> dict:
        """Returns single-char operator→TokenType mapping. Override to add ops."""
        return C_ONE_CHAR_OPS

    def tokenize(self, source: str) -> list:
        """Main entry point: convert C source string to list of Tokens.

        Unlike the Python lexer, C doesn't care about lines — whitespace
        (including newlines) is just a separator between tokens.
        """
        self.tokens = []
        self.errors = []
        self.source = source
        self.pos = 0              # current character index
        self.line = 1             # current line number (1-based)
        self.col = 1              # current column number (1-based)
        self.keywords = self.get_keywords()
        self.two_char_ops = self.get_two_char_ops()
        self.one_char_ops = self.get_one_char_ops()

        while self.pos < len(self.source):
            ch = self.source[self.pos]

            # ── Skip whitespace (including newlines) ──────────────────
            if ch in (" ", "\t", "\n", "\r"):
                self._advance()
                continue

            # ── Handle #include directive ─────────────────────────────
            if ch == "#":
                self._read_include()
                continue

            # ── String literals ───────────────────────────────────────
            if ch in ('"', "'"):
                self._read_string()
                continue

            # ── Numbers ───────────────────────────────────────────────
            if ch.isdigit():
                self._read_number()
                continue

            # ── Two-character operators ───────────────────────────────
            if self.pos + 1 < len(self.source):
                two = self.source[self.pos:self.pos + 2]
                if two in self.two_char_ops:
                    self.tokens.append(Token(self.two_char_ops[two], two, self.line, self.col))
                    self._advance()
                    self._advance()
                    continue

            # ── Single-character operators and delimiters ─────────────
            if ch in self.one_char_ops:
                self.tokens.append(Token(self.one_char_ops[ch], ch, self.line, self.col))
                self._advance()
                continue

            # ── Identifiers and keywords ──────────────────────────────
            if ch.isalpha() or ch == "_":
                self._read_identifier()
                continue

            # ── C-specific: & (for scanf) ─────────────────────────────
            if ch == "&":
                # We skip '&' — in our subset, it only appears in scanf(&x)
                # The parser will handle variable reference without &
                self._advance()
                continue

            # ── Unknown character → error ─────────────────────────────
            self.errors.append(CompilerError(
                Phase.LEXER,
                f"Unexpected character: '{ch}'",
                self.line, self.col
            ))
            self._advance()

        # Emit EOF token
        self.tokens.append(Token(TokenType.EOF, "", self.line, self.col))

        if self.errors:
            raise CompilerErrorList(self.errors)

        return self.tokens

    def _advance(self):
        """Move to the next character, tracking line and column position."""
        if self.pos < len(self.source):
            if self.source[self.pos] == "\n":
                self.line += 1
                self.col = 1
            else:
                self.col += 1
            self.pos += 1

    def _read_string(self):
        """Read a string literal (handles escape sequences)."""
        quote = self.source[self.pos]
        start_line = self.line
        start_col = self.col
        value = quote
        self._advance()  # skip opening quote

        while self.pos < len(self.source):
            ch = self.source[self.pos]

            if ch == "\\" and self.pos + 1 < len(self.source):
                value += ch + self.source[self.pos + 1]
                self._advance()
                self._advance()
                continue

            value += ch
            if ch == quote:
                self._advance()
                self.tokens.append(Token(TokenType.STRING, value, start_line, start_col))
                return
            self._advance()

        self.errors.append(CompilerError(
            Phase.LEXER, "Unterminated string literal", start_line, start_col
        ))

    def _read_number(self):
        """Read an integer or float literal."""
        start = self.pos
        start_col = self.col
        has_dot = False

        while self.pos < len(self.source) and (self.source[self.pos].isdigit() or self.source[self.pos] == "."):
            if self.source[self.pos] == ".":
                if has_dot:
                    break
                has_dot = True
            self._advance()

        value = self.source[start:self.pos]
        self.tokens.append(Token(TokenType.NUMBER, value, self.line, start_col))

    def _read_identifier(self):
        """Read an identifier or keyword."""
        start = self.pos
        start_col = self.col

        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == "_"):
            self._advance()

        word = self.source[start:self.pos]

        if word in self.keywords:
            self.tokens.append(Token(self.keywords[word], word, self.line, start_col))
        else:
            self.tokens.append(Token(TokenType.NAME, word, self.line, start_col))

    def _read_include(self):
        """Read a #include directive. Emits INCLUDE token + skips the rest of the line.

        In our compiler, #include is recognized but not processed (the preprocessor
        already handles it, and our subset doesn't support multi-file compilation).
        """
        start_col = self.col
        self._advance()  # skip '#'

        # Read the word after '#' (should be 'include')
        while self.pos < len(self.source) and self.source[self.pos] in (" ", "\t"):
            self._advance()

        word_start = self.pos
        while self.pos < len(self.source) and self.source[self.pos].isalpha():
            self._advance()

        word = self.source[word_start:self.pos]
        if word == "include":
            self.tokens.append(Token(TokenType.INCLUDE, "#include", self.line, start_col))
            # Skip the rest of the line (e.g., <stdio.h> or "header.h")
            while self.pos < len(self.source) and self.source[self.pos] != "\n":
                self._advance()
        else:
            self.errors.append(CompilerError(
                Phase.LEXER,
                f"Unknown preprocessor directive: '#{word}'",
                self.line, start_col
            ))
