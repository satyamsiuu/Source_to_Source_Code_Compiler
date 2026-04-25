"""
lexer/cpp_lexer.py — Tokenizes C++ source code.
Phase 2 of the compiler pipeline.

EXTENDS CLexer — does NOT copy-paste C lexer code.
Only adds C++-specific tokens:
    cout  → COUT token (for cout << x outputS)
    cin   → CIN token  (for cin >> x input)
    ::    → SCOPE token (scope resolution, e.g. std::cout)
    >>    → handled in parser (CIN context)
    <<    → handled in parser (COUT context)

Design: Override get_keywords() and get_two_char_ops() to extend the parent's
token maps. The tokenize() loop and all helper methods are inherited unchanged.
"""

try:
    from transpiler.lexer.c_lexer import CLexer, C_KEYWORDS, C_TWO_CHAR_OPS, C_ONE_CHAR_OPS
    from transpiler.lexer.tokens import TokenType
except ModuleNotFoundError:
    from lexer.c_lexer import CLexer, C_KEYWORDS, C_TWO_CHAR_OPS, C_ONE_CHAR_OPS
    from lexer.tokens import TokenType


# C++ adds cout, cin, and 'using' / 'namespace' (which we skip over)
CPP_KEYWORDS = {
    **C_KEYWORDS,          # inherit all C keywords
    "cout": TokenType.COUT,
    "cin": TokenType.CIN,
}

# C++ adds :: (scope resolution operator, e.g. std::cout)
CPP_TWO_CHAR_OPS = {
    **C_TWO_CHAR_OPS,      # inherit all C two-char operators
    "::": TokenType.SCOPE,
}


class CppLexer(CLexer):
    """Tokenizes C++ source code. Inherits from CLexer.

    Only overrides:
    - get_keywords() → adds cout, cin
    - get_two_char_ops() → adds ::

    Everything else (tokenize loop, string/number/identifier reading,
    error handling) is inherited from CLexer unchanged.

    Usage:
        lexer = CppLexer()
        tokens = lexer.tokenize('#include <iostream>\\nusing namespace std;\\nint main() { cout << 42; }')
    """

    def get_keywords(self) -> dict:
        """Return C keywords + C++ additions (cout, cin)."""
        return CPP_KEYWORDS

    def get_two_char_ops(self) -> dict:
        """Return C two-char ops + :: scope resolution."""
        return CPP_TWO_CHAR_OPS

    # get_one_char_ops() is inherited unchanged — C++ uses same single-char ops
    # tokenize() is inherited — no override needed
    # All _read_* methods are inherited — no override needed
