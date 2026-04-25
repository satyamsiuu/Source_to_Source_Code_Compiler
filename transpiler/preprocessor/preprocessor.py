"""
preprocessor/preprocessor.py — Strip comments from source code before lexing.
Phase 1 of the compiler pipeline.

Why a separate preprocessor?
    If comments weren't stripped first, the lexer would need to distinguish:
    - '#' starting a comment vs '#' inside a string
    - '//' as integer division vs '//' as C comment
    - '/*' inside a string vs '/*' starting a block comment
    Separation of concerns: preprocessor handles ONLY comments.
    The lexer then works on clean, comment-free source code.

Supported comment formats:
    Python:  # single line comment
    C/C++:   // single line comment
    C/C++:   /* multi-line block comment */

Error handling:
    Unclosed /* block comment → CompilerError(Phase.PREPROCESSOR)
    Uses the collect-then-raise pattern from errors.py.
"""

# Import works both as package (from transpiler/) and standalone (inside transpiler/)
try:
    from transpiler.errors import CompilerError, CompilerErrorList, Phase
except ModuleNotFoundError:
    from errors import CompilerError, CompilerErrorList, Phase


class Preprocessor:
    """Strips comments from source code and returns clean source + extracted comments.

    Usage:
        p = Preprocessor()
        result = p.process("x = 1  # comment", "python")
        # result = {"clean_source": "x = 1  ", "comments": ["# comment"]}
    """

    def process(self, source: str, lang: str) -> dict:
        """Main entry point: strip comments from source code.

        Args:
            source — raw source code string
            lang   — "python", "c", or "cpp" (determines comment syntax)

        Returns:
            dict with keys:
                clean_source — source with all comments removed
                comments     — list of extracted comment strings
        """
        errors = []  # collect-then-raise pattern

        if lang == "python":
            clean, comments = self._strip_python_comments(source)
        elif lang in ("c", "cpp"):
            clean, comments, errs = self._strip_c_comments(source)
            errors.extend(errs)  # add any errors (e.g. unclosed block comment)
        else:
            # Unsupported language — raise immediately, no recovery possible
            errors.append(CompilerError(
                Phase.PREPROCESSOR,
                f"Unsupported language: '{lang}'. Expected 'python', 'c', or 'cpp'."
            ))

        # If any errors were collected, raise them all at once
        if errors:
            raise CompilerErrorList(errors)

        return {
            "clean_source": clean,
            "comments": comments,
        }

    def _strip_python_comments(self, source: str) -> tuple:
        """Strip Python # comments, preserving strings.

        Algorithm:
            Process each line character by character.
            Track whether we are inside a string (single or double quoted).
            When we hit '#' outside a string, everything after it is a comment.

        Returns:
            (clean_source: str, comments: list[str])
        """
        clean_lines = []     # accumulates cleaned lines
        comments = []        # accumulates extracted comments

        for line in source.split("\n"):    # process line by line
            clean, comment = self._strip_python_line(line)
            clean_lines.append(clean)
            if comment is not None:
                comments.append(comment)

        # Rejoin with newlines to preserve original line structure
        return "\n".join(clean_lines), comments

    def _strip_python_line(self, line: str) -> tuple:
        """Process a single line: find '#' outside of strings.

        Returns:
            (clean_part: str, comment_or_none)
        """
        in_string = None  # None = not in string, '"' or "'" = which quote started it
        i = 0

        while i < len(line):
            ch = line[i]

            if in_string:
                # Inside a string — only exit when we see the matching quote
                if ch == in_string and (i == 0 or line[i - 1] != "\\"):
                    in_string = None  # end of string
            elif ch in ('"', "'"):
                in_string = ch  # entering a string
            elif ch == "#":
                # Found a comment outside a string
                comment = line[i:].rstrip()     # extract from '#' to end of line
                clean = line[:i]                 # everything before '#'
                return clean, comment

            i += 1

        # No comment found on this line
        return line, None

    def _strip_c_comments(self, source: str) -> tuple:
        """Strip C/C++ comments: // single-line and /* */ multi-line.

        Algorithm:
            Walk through entire source character by character.
            Track state: normal, in_string, in_line_comment, in_block_comment.
            - '//' outside string → skip to end of line
            - '/*' outside string → skip until '*/' found
            - String quotes toggle in_string state (respecting escape chars)

        Returns:
            (clean_source: str, comments: list[str], errors: list[CompilerError])
        """
        clean = []          # characters of clean source (will be joined at end)
        comments = []       # extracted comment strings
        errors = []         # any errors found (unclosed block comments)

        i = 0               # current character index
        length = len(source)
        line_num = 1        # track line number for error messages

        while i < length:
            ch = source[i]

            # ── Check for // single-line comment ──────────────────────────
            if ch == "/" and i + 1 < length and source[i + 1] == "/":
                comment_start = i
                # Find end of line (or end of source)
                end = source.find("\n", i)
                if end == -1:
                    end = length  # comment goes to end of file
                comment_text = source[comment_start:end].rstrip()
                comments.append(comment_text)
                i = end  # skip past the comment, '\n' will be added normally
                continue

            # ── Check for /* block comment ────────────────────────────────
            if ch == "/" and i + 1 < length and source[i + 1] == "*":
                comment_start_line = line_num  # save for error message
                comment_start = i
                i += 2  # skip past '/*'

                # Search for closing '*/'
                found_close = False
                while i < length:
                    if source[i] == "\n":
                        line_num += 1  # track lines inside block comment
                    if source[i] == "*" and i + 1 < length and source[i + 1] == "/":
                        # Found the closing '*/'
                        comment_text = source[comment_start:i + 2]
                        comments.append(comment_text)
                        i += 2  # skip past '*/'
                        found_close = True
                        break
                    i += 1

                if not found_close:
                    # Reached end of file without finding '*/'
                    errors.append(CompilerError(
                        Phase.PREPROCESSOR,
                        "Unclosed block comment '/*' — missing closing '*/'",
                        line=comment_start_line,
                    ))
                continue

            # ── Check for string literals (don't strip inside strings) ────
            if ch in ('"', "'"):
                quote = ch
                clean.append(ch)  # keep the opening quote
                i += 1
                # Walk until matching close quote (handling escapes)
                while i < length and source[i] != quote:
                    if source[i] == "\\" and i + 1 < length:
                        clean.append(source[i])      # keep backslash
                        clean.append(source[i + 1])  # keep escaped char
                        i += 2
                        continue
                    if source[i] == "\n":
                        line_num += 1
                    clean.append(source[i])
                    i += 1
                if i < length:
                    clean.append(source[i])  # keep the closing quote
                    i += 1
                continue

            # ── Normal character — keep it ────────────────────────────────
            if ch == "\n":
                line_num += 1
            clean.append(ch)
            i += 1

        return "".join(clean), comments, errors
