"""
lexer/tokens.py — Token type definitions and Token dataclass.
FROZEN after Phase 0 — do not modify.

What is a token?
The lexer reads raw source text character by character and groups characters
into meaningful units called "tokens". For example:
    'if x > 0'  →  [IF, NAME:x, GT, NUMBER:0]

Each token has:
    type  — what KIND of token (keyword, number, operator, etc.)
    value — the actual text fragment from the source
    line  — where in the source code (for error messages)
    col   — column position (for error messages)

Why TokenType as Enum?
    - Typo protection: TokenType.IFF would crash at import time
    - IDE autocomplete: TokenType.<tab> shows all valid types
    - Exhaustiveness: adding a new token requires ONE addition here,
      and if a lexer/parser doesn't handle it, it's visible
"""

from dataclasses import dataclass
from enum import Enum, auto  # auto() assigns incrementing integer values


class TokenType(Enum):
    """Every type of token our lexer can produce.

    Grouped by category for readability. auto() assigns unique integer values —
    the actual numbers don't matter, only the names are used for comparison.
    """

    # ─── Keywords (language constructs) ────────────────────────────────
    IF = auto()         # if
    ELSE = auto()       # else
    WHILE = auto()      # while
    FOR = auto()        # for
    DEF = auto()        # def (Python function declaration)
    RETURN = auto()     # return
    PRINT = auto()      # print
    INPUT = auto()      # input (Python), scanf (C)
    TRUE = auto()       # True / true
    FALSE = auto()      # False / false
    VOID = auto()       # void (C/C++ only)
    IN = auto()         # in (Python for-each: 'for x in arr')
    RANGE = auto()      # range (Python for-range: 'for i in range(n)')
    AND = auto()        # and / && logical AND
    OR = auto()         # or / || logical OR
    NOT = auto()        # not / ! logical NOT

    # ─── Type keywords ─────────────────────────────────────────────────
    INT_KW = auto()     # int (type declaration in C/C++, array(int,5) in Python)
    FLOAT_KW = auto()   # float
    BOOL_KW = auto()    # bool
    ARRAY = auto()      # array (Python syntax: array(int, 5))

    # ─── C/C++ specific keywords ───────────────────────────────────────
    INCLUDE = auto()    # #include
    COUT = auto()       # cout (C++ output)
    CIN = auto()        # cin (C++ input)
    MAIN = auto()       # main (the main function in C/C++)
    PRINTF = auto()     # printf (C output)
    SCANF = auto()      # scanf (C input)

    # ─── Literals (values) ─────────────────────────────────────────────
    NUMBER = auto()     # integer or float literal: 42, 3.14
    STRING = auto()     # string literal: "hello"
    NAME = auto()       # identifier: variable name, function name

    # ─── Operators ─────────────────────────────────────────────────────
    PLUS = auto()       # +
    MINUS = auto()      # -
    STAR = auto()       # *
    SLASH = auto()      # /
    MODULO = auto()     # %
    EQ = auto()         # ==
    NEQ = auto()        # !=
    LT = auto()         # <
    GT = auto()         # >
    LEQ = auto()        # <=
    GEQ = auto()        # >=
    ASSIGN = auto()     # =

    # ─── Delimiters ────────────────────────────────────────────────────
    LPAREN = auto()     # (
    RPAREN = auto()     # )
    LBRACE = auto()     # {
    RBRACE = auto()     # }
    LBRACKET = auto()   # [
    RBRACKET = auto()   # ]
    COMMA = auto()      # ,
    SEMICOLON = auto()  # ;
    COLON = auto()      # :
    SCOPE = auto()      # :: (C++ scope resolution)

    # ─── Python-specific whitespace tokens ─────────────────────────────
    INDENT = auto()     # indentation increased (Python block start)
    DEDENT = auto()     # indentation decreased (Python block end)
    NEWLINE = auto()    # end of a logical line in Python

    # ─── Meta ──────────────────────────────────────────────────────────
    EOF = auto()        # end of file — signals the parser to stop


@dataclass
class Token:
    """A single token produced by the lexer.

    Fields:
        type  — TokenType enum value (what kind of token this is)
        value — the raw text from source code (e.g. 'if', '42', '+')
        line  — 1-based line number in the source file
        col   — 1-based column number in the source file (start of the token)

    Why store line and col?
        Error messages need source location: "Error at line 5, col 12".
        The parser and semantic analyzer don't have access to the raw source —
        they work with tokens. So the lexer must embed position info into each token.
    """
    type: TokenType
    value: str
    line: int
    col: int

    def to_dict(self) -> dict:
        """Serialize for JSON API response. The frontend uses this to render token pills."""
        return {
            "type": self.type.name,   # .name gives 'IF', not 'TokenType.IF'
            "value": self.value,
            "line": self.line,
            "col": self.col,
        }
