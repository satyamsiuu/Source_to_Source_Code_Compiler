"""
lexer/python_lexer.py — Tokenizes Python source code.
Phase 2 of the compiler pipeline.

Key feature: INDENT/DEDENT generation using an indent stack.
Python uses whitespace for blocks — the lexer converts indentation changes
into INDENT and DEDENT tokens so the parser can treat them like { and }.

Algorithm (from CLAUDE.md):
    indent_stack = [0]
    for each non-blank line:
        indent = count leading spaces
        if tab in leading chars → error: mixed tabs/spaces
        if indent > stack[-1]   → push indent, emit INDENT
        elif indent < stack[-1] →
            while stack[-1] > indent: pop, emit DEDENT
            if stack[-1] != indent → error: bad dedent
        tokenize rest of line
        emit NEWLINE
    at EOF: emit DEDENT for each remaining level > 0
"""

try:
    from transpiler.errors import CompilerError, CompilerErrorList, Phase
    from transpiler.lexer.tokens import Token, TokenType
except ModuleNotFoundError:
    from errors import CompilerError, CompilerErrorList, Phase
    from lexer.tokens import Token, TokenType


# Mapping of Python keywords to their token types
PYTHON_KEYWORDS = {
    "if": TokenType.IF, "else": TokenType.ELSE, "while": TokenType.WHILE,
    "for": TokenType.FOR, "def": TokenType.DEF, "return": TokenType.RETURN,
    "print": TokenType.PRINT, "input": TokenType.INPUT,
    "True": TokenType.TRUE, "False": TokenType.FALSE,
    "int": TokenType.INT_KW, "float": TokenType.FLOAT_KW,
    "bool": TokenType.BOOL_KW, "array": TokenType.ARRAY,
    "in": TokenType.IN, "range": TokenType.RANGE,
    "and": TokenType.AND, "or": TokenType.OR, "not": TokenType.NOT,
}

# Two-character operators must be checked BEFORE single-character operators
TWO_CHAR_OPS = {
    "==": TokenType.EQ, "!=": TokenType.NEQ,
    "<=": TokenType.LEQ, ">=": TokenType.GEQ,
}

# Single-character operators and delimiters
ONE_CHAR_OPS = {
    "+": TokenType.PLUS, "-": TokenType.MINUS,
    "*": TokenType.STAR, "/": TokenType.SLASH,
    "<": TokenType.LT, ">": TokenType.GT, "=": TokenType.ASSIGN,
    "(": TokenType.LPAREN, ")": TokenType.RPAREN,
    "[": TokenType.LBRACKET, "]": TokenType.RBRACKET,
    ",": TokenType.COMMA, ":": TokenType.COLON,
}


class PythonLexer:
    """Tokenizes Python source code into a list of Token objects.

    Usage:
        lexer = PythonLexer()
        tokens = lexer.tokenize("if x > 0:\\n    return x\\n")
    """

    def tokenize(self, source: str) -> list:
        """Main entry point: convert source string to list of Tokens.

        The algorithm processes line by line because Python's semantics
        are line-oriented (indentation matters per line).
        """
        self.tokens = []            # accumulates output tokens
        self.errors = []            # accumulates errors (collect-then-raise)
        self.indent_stack = [0]     # stack of indentation levels, starts at column 0
        self.line_num = 0           # current line number (1-based, set in loop)

        lines = source.split("\n")  # split into individual lines

        for i, line in enumerate(lines):
            self.line_num = i + 1   # 1-based line numbering

            # Skip completely blank lines (they don't affect indentation)
            if line.strip() == "":
                continue

            # Step 1: Handle indentation (emit INDENT or DEDENT tokens)
            self._handle_indent(line)

            # Step 2: Tokenize the content of the line (after leading whitespace)
            self._tokenize_line(line)

            # Step 3: Emit NEWLINE token at end of each non-blank line
            self.tokens.append(Token(TokenType.NEWLINE, "\\n", self.line_num, len(line) + 1))

        # Step 4: At EOF, close all open indentation levels
        self._close_indents()

        # Step 5: Emit EOF token
        self.tokens.append(Token(TokenType.EOF, "", self.line_num, 0))

        # If any errors were collected, raise them all
        if self.errors:
            raise CompilerErrorList(self.errors)

        return self.tokens

    def _handle_indent(self, line: str):
        """Process the indentation of a line, emitting INDENT/DEDENT tokens.

        This implements the indent_stack algorithm that makes Python's
        whitespace-based blocks work with a standard parser.
        """
        # Count leading spaces
        indent = 0
        for ch in line:
            if ch == " ":
                indent += 1
            elif ch == "\t":
                # Mixed tabs and spaces → error (Python also rejects this)
                self.errors.append(CompilerError(
                    Phase.LEXER,
                    "Mixed tabs and spaces in indentation. Use spaces only.",
                    self.line_num, indent + 1
                ))
                return  # can't determine indent level with mixed whitespace
            else:
                break  # first non-whitespace character

        current_indent = self.indent_stack[-1]  # top of stack = current level

        if indent > current_indent:
            # Indentation increased → new block started
            self.indent_stack.append(indent)
            self.tokens.append(Token(TokenType.INDENT, "<INDENT>", self.line_num, 1))

        elif indent < current_indent:
            # Indentation decreased → one or more blocks ended
            while self.indent_stack[-1] > indent:
                self.indent_stack.pop()
                self.tokens.append(Token(TokenType.DEDENT, "<DEDENT>", self.line_num, 1))

            # After all pops, the top of stack must exactly match the new indent
            if self.indent_stack[-1] != indent:
                self.errors.append(CompilerError(
                    Phase.LEXER,
                    f"Inconsistent dedent. Expected {self.indent_stack[-1]} spaces, got {indent}.",
                    self.line_num, indent + 1
                ))
        # else: indent == current_indent → same level, no tokens needed

    def _close_indents(self):
        """At EOF, emit DEDENT for each remaining open indentation level.

        If the source ends with indented code (e.g., inside a function body),
        we need to close those blocks. Without this, the parser would think
        the last block never ended.
        """
        while len(self.indent_stack) > 1:  # > 1 because [0] is the base level
            self.indent_stack.pop()
            self.tokens.append(Token(TokenType.DEDENT, "<DEDENT>", self.line_num, 0))

    def _tokenize_line(self, line: str):
        """Tokenize a single line of Python source (after indentation is handled).

        Walks character by character through the line content, building tokens.
        """
        col = 0
        # Skip leading whitespace (already handled by _handle_indent)
        while col < len(line) and line[col] in (" ", "\t"):
            col += 1

        while col < len(line):
            ch = line[col]

            # Skip spaces between tokens
            if ch == " ":
                col += 1
                continue

            # ── String literals ───────────────────────────────────────
            if ch in ('"', "'"):
                col = self._read_string(line, col)
                continue

            # ── Numbers (integer or float) ────────────────────────────
            if ch.isdigit():
                col = self._read_number(line, col)
                continue

            # ── Two-character operators (must check before single-char) ─
            if col + 1 < len(line):
                two = line[col:col + 2]
                if two in TWO_CHAR_OPS:
                    self.tokens.append(Token(TWO_CHAR_OPS[two], two, self.line_num, col + 1))
                    col += 2
                    continue

            # ── Single-character operators and delimiters ─────────────
            if ch in ONE_CHAR_OPS:
                self.tokens.append(Token(ONE_CHAR_OPS[ch], ch, self.line_num, col + 1))
                col += 1
                continue

            # ── Identifiers and keywords ──────────────────────────────
            if ch.isalpha() or ch == "_":
                col = self._read_identifier(line, col)
                continue

            # ── Unknown character → error ─────────────────────────────
            self.errors.append(CompilerError(
                Phase.LEXER,
                f"Unexpected character: '{ch}'",
                self.line_num, col + 1
            ))
            col += 1

    def _read_string(self, line: str, start: int) -> int:
        """Read a string literal starting at position 'start'.

        Handles escape sequences (\\n, \\", etc).
        Returns the position after the closing quote.
        """
        quote = line[start]  # ' or "
        col = start + 1      # skip opening quote
        value = quote         # accumulate the full string including quotes

        while col < len(line):
            ch = line[col]
            value += ch

            if ch == "\\" and col + 1 < len(line):
                # Escape sequence — include the next character literally
                value += line[col + 1]
                col += 2
                continue

            if ch == quote:
                # Found closing quote — emit token and return
                self.tokens.append(Token(TokenType.STRING, value, self.line_num, start + 1))
                return col + 1

            col += 1

        # Reached end of line without closing quote
        self.errors.append(CompilerError(
            Phase.LEXER,
            f"Unterminated string literal",
            self.line_num, start + 1
        ))
        return col

    def _read_number(self, line: str, start: int) -> int:
        """Read an integer or float literal starting at position 'start'.

        Handles: 42, 3.14 (but not 3.14.15 — only one dot allowed).
        Returns position after the last digit.
        """
        col = start
        has_dot = False

        while col < len(line) and (line[col].isdigit() or line[col] == "."):
            if line[col] == ".":
                if has_dot:
                    break  # second dot → stop (e.g., 3.14.15 stops at second dot)
                has_dot = True
            col += 1

        value = line[start:col]
        self.tokens.append(Token(TokenType.NUMBER, value, self.line_num, start + 1))
        return col

    def _read_identifier(self, line: str, start: int) -> int:
        """Read an identifier or keyword starting at position 'start'.

        Identifiers: [a-zA-Z_][a-zA-Z0-9_]*
        If the identifier matches a keyword, emit that keyword token instead.
        """
        col = start

        while col < len(line) and (line[col].isalnum() or line[col] == "_"):
            col += 1

        word = line[start:col]

        # Check if this identifier is actually a keyword
        if word in PYTHON_KEYWORDS:
            token_type = PYTHON_KEYWORDS[word]
        else:
            token_type = TokenType.NAME

        self.tokens.append(Token(token_type, word, self.line_num, start + 1))
        return col
