## Project Constraints and Limitations

This document outlines the strict technical constraints of the Source-to-Source Code Compiler. The transpiler is designed to handle a logic-heavy subset of Python, C, and C++ and does not support the full breadth of these languages' standard libraries or advanced features.

## 1. Supported Data Types
The transpiler only supports primitive numeric and boolean types that have direct mappings across all three languages.
- **INT**: Standard integer types.
- **FLOAT**: Standard floating-point types.
- **BOOL**: Boolean values (`True`/`False` in Python, `1`/`0` in C).
- **STR**: String literals are supported **only** within `print()` calls and `input()` prompts. Variables cannot be assigned string values, and string manipulation (concatenation, slicing) is not supported.

## 2. Supported Language Constructs
The transpiler is restricted to the following structural elements:
- **Functions**: Global function declarations with parameters and return types. Nested functions are **not** supported.
- **Variables**: Scalar variable declarations and assignments.
- **Arrays**: Fixed-size arrays of primitive types.
- **Control Flow**:
    - `if` / `else` statements.
    - `while` loops.
    - `for i in range(...)` (Numeric range loops).
    - `for x in arr` (Array iteration).
- **I/O Operations**: Basic `print()` for output and `input()` for numeric input.

## 3. Strict Language-Specific Constraints

### Python Constraints
- **No OOP**: Classes, objects, inheritance, and methods are not supported.
- **No Dynamic Structures**: Dictionaries, Sets, and Tuples are not supported. Only fixed-size lists (interpreted as C-style arrays) are allowed.
- **No Standard Library**: You cannot `import` any modules (e.g., `math`, `sys`, `os`).
- **No Comprehensions**: List/Dict comprehensions are not supported.
- **No Exception Handling**: `try`, `except`, `finally`, and `raise` are not supported.
- **No Functional Features**: `lambda`, `map`, `filter`, and `global` keywords are strictly rejected.

### C / C++ Constraints
- **No Pointers**: Manual memory management, pointers (`*`), and references (`&`) are not supported (except internally for `scanf`).
- **No Structs/Unions**: User-defined data structures are not supported.
- **No Templates/Generics**: Code must use explicit types supported by the `DataType` enum.
- **No External Headers**: Beyond the automatically included `stdio.h` (C) and `iostream` (C++), no other headers can be used.

## 4. Architectural Limitations
- **Fixed-Size Arrays**: Because C requires array sizes at compile time, Python lists must have a detectable fixed size (e.g., `arr = [0] * 5` or `arr = [1, 2, 3]`). Dynamic `append()` or `pop()` operations are not supported.
- **Standard Library Functions**: Only built-in primitives are transpiled. Calling functions like `len()`, `max()`, or `abs()` will fail unless they are manually implemented within the source code.
- **Type Consistency**: The Semantic Analyzer enforces strict type rules. Mixing types in operations (e.g., adding a BOOL to a FLOAT) may be rejected depending on the target language's strictness.
- **Recursion**: Basic recursion is supported, but there are no optimizations for tail-call recursion.

## 5. Rejected Keywords
The following keywords are explicitly rejected by the parser to prevent undefined behavior:
`class`, `import`, `try`, `except`, `lambda`, `global`, `yield`, `with`, `async`, `await`, `struct`, `union`, `template`, `namespace`.
