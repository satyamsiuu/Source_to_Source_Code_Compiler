# GEMINI_EXPLANATION.md
# Purpose: every line of every file explained so clearly that someone with basic Python knowledge can understand and explain it in a college viva exam.
# Updated by: Gemini CLI after each phase completes

---

## HOW TO READ THIS FILE
- Looking for a specific file? Ctrl+F the filename
- Preparing for viva? Read the VIVA_ANSWERS section at the bottom
- New to the codebase? Read PROJECT_OVERVIEW first

---

## PROJECT_OVERVIEW
This project is a **source-to-source compiler**, also known as a **transpiler**. It translates code between three programming languages: **Python, C, and C++**. 

Imagine a translator who knows English, French, and Spanish. Instead of translating English directly to Spanish, they first translate the English sentence into a "universal meaning" (like an idea in their head) and then turn that idea into Spanish. This project does the same thing.

### Why each phase exists:
1.  **Preprocessor:** Cleans the code by removing comments. This makes the next steps easier because they don't have to worry about notes the programmer left for themselves.
2.  **Lexer:** Breaks the code into "words" called **Tokens**. Instead of seeing `if x > 0:`, the computer sees `[KEYWORD:if, VARIABLE:x, OPERATOR:>, NUMBER:0, COLON]`.
3.  **Parser:** Organizes the tokens into a "family tree" called an **AST (Abstract Syntax Tree)**. This tree represents the logic and structure of the program (like which code is inside an "if" statement).
4.  **Semantic Analyzer:** Checks if the "meaning" of the code is correct. For example, it checks if you're trying to add a number to a word, or if you're using a variable you never created.
5.  **IR (Intermediate Representation):** Standardizes the tree so it's ready for any target language.
6.  **Codegen (Code Generator):** Turns the standardized tree back into text code in the target language (like C or C++).
7.  **Validator:** Runs the original code and the translated code to make sure they both give the same result.

### How data flows:
Source Code (Text) → Preprocessor → Clean Code → Lexer → Tokens → Parser → AST (Tree) → Semantic Analyzer → Validated AST → IR → Codegen → Target Code (Text).

### What the user sees:
The user sees a web page where they can type code on the left and see it transform through each stage on the right. If there's an error (like a missing colon), the compiler shows exactly where it is and why it's wrong.

---

## FILE: transpiler/errors.py
### What this file does
This file creates the "alarm system" for the compiler. It defines what an error looks like (which line, what message) and how the compiler should stop when it finds one.

### Why this file exists
Without this file, the compiler would crash with confusing Python errors that the user wouldn't understand. This file ensures that every error is explained clearly in a way that helps the programmer fix their code.

### Line by line:

LINE 1-15: [Module Docstring]
  What it does: Explains the design of the error system.
  Why it is written this way: To remind developers that every phase should collect ALL errors before stopping.
  What breaks if you change it: Documentation only; nothing code-wise, but developers might forget the pattern.
  Viva question this could generate: Why do you collect all errors instead of stopping at the first one?
  Answer: It's more user-friendly. Like a teacher marking a whole test instead of stopping at the first wrong answer, it lets the programmer fix everything at once.

LINE 17-18: [Imports]
  What it does: Brings in `dataclass` and `Enum` from Python's standard library.
  Why it is written this way: `dataclass` saves us from writing repetitive code, and `Enum` creates a fixed list of names.
  What breaks if you change it: The classes below won't work.
  Viva question this could generate: What is a dataclass?
  Answer: A tool in Python that automatically writes the "setup" code (the `__init__` method) for a class.

LINE 21-30: [Phase Enum]
  What it does: Lists all the names of the compiler stages (LEXER, PARSER, etc.).
  Why it is written this way: Using an `Enum` prevents typos. You can't accidentally type `"lexr"` because `Phase.LEXER` is checked by Python.
  What breaks if you change it: You might have inconsistent names for phases across different files.
  Viva question this could generate: Why use an Enum instead of just strings?
  Answer: To prevent spelling mistakes and ensure everyone uses the exact same names for the compiler stages.

LINE 33-46: [CompilerError Class]
  What it does: A blueprint for a single error. It stores the phase, the message, the line number, and the column.
  Why it is written this way: It's a `dataclass` so it's very easy to create an error object: `CompilerError(Phase.LEXER, "Oops", 5, 2)`.
  What breaks if you change it: Other phases won't know how to report errors consistently.
  Viva question this could generate: Why is the line number set to `None` by default?
  Answer: Some errors, like "the file is empty," don't happen on a specific line, so we need the option to leave the line number blank.

LINE 48-57: [to_dict method]
  What it does: Converts the error object into a Python dictionary.
  Why it is written this way: The web frontend (the browser) needs the data in a format called JSON. A dictionary is easily converted to JSON.
  What breaks if you change it: The web interface won't be able to show the error messages properly.
  Viva question this could generate: What does `.value` do on the phase?
  Answer: It gets the actual string (like "lexer") instead of the Enum object itself.

LINE 60-84: [CompilerErrorList Class]
  What it does: This is a "package" of errors. It inherits from `Exception`, which means it can be "raised" to stop the program.
  Why it is written this way: It stores a list of errors so we can show them all at once. By extending `Exception`, it naturally stops the compiler pipeline if anything goes wrong.
  What breaks if you change it: The compiler might try to keep running on broken code, causing more crashes.
  Viva question this could generate: Why does this class extend `Exception`?
  Answer: So we can use the `raise` keyword to immediately stop the compiler when we find errors.

---

## FILE: transpiler/ast_nodes.py
### What this file does
This file defines the "universal language" of our compiler. It lists all the different types of code blocks (like "if" statements, "while" loops, or "variable creations") that the computer understands.

### Why this file exists
This is the heart of the transpiler. By defining language-neutral "nodes," we can turn Python code into a tree of these nodes, and then turn that same tree into C code. It's the "bridge" between the languages.

### Line by line:

LINE 1-22: [Module Docstring]
  What it does: Explains that the AST (Abstract Syntax Tree) is language-neutral.
  Why it is written this way: To emphasize that this file is the "Universal Translator" part of the project.
  What breaks if you change it: Documentation only.
  Viva question this could generate: What does "language-neutral" mean here?
  Answer: It means these nodes represent the *idea* of a loop or a variable, regardless of whether it was written in Python or C.

LINE 25-27: [Imports]
  What it does: Imports `dataclass`, `Enum`, and `Optional`.
  Why it is written this way: These are standard Python tools to make our tree nodes clean and safe.
  What breaks if you change it: The code below will fail.

LINE 30-45: [DataType Enum]
  What it does: Lists the types of data the compiler handles: INT (whole numbers), FLOAT (decimals), BOOL (true/false), etc.
  Why it is written this way: It includes `UNKNOWN` for when the compiler sees a variable but hasn't figured out its type yet.
  What breaks if you change it: The compiler won't be able to track what kind of data is being used.
  Viva question this could generate: When is a type `UNKNOWN`?
  Answer: In Python, when we see `x = 5`, we don't know x's type immediately. We assign it `UNKNOWN` and let the Semantic Analyzer fix it later.

LINE 48-57: [ASTNode Base Class]
  What it does: The parent class for every single node in our tree. It stores the line number.
  Why it is written this way: Every node needs a line number for error messages, so we put it in one place (the parent) instead of repeating it 20 times.
  What breaks if you change it: You'd have to manually add `line` to every other class in the file.
  Viva question this could generate: Why use a base class?
  Answer: To ensure consistency. Every node automatically gets the features of the base class, like the line number.

LINE 62-75: [Program Node]
  What it does: The top-most node of our tree. It contains a list of functions and a list of global variables.
  Why it is written this way: C requires code to be in functions, while Python allows code to just "exist" at the top level. We separate them so we can move Python's top-level code into a `main` function for C.
  What breaks if you change it: Translating global code from Python to C would become much harder.
  Viva question this could generate: What are "globals" in this context?
  Answer: Code that is written at the very top of a file, not inside any function.

LINE 78-87: [FunctionDecl Node]
  What it does: Represents a function: its name, its inputs (params), what it returns, and the code inside it (body).
  Why it is written this way: It captures everything needed to define a function in any language.
  What breaks if you change it: The compiler wouldn't be able to handle functions.
  Viva question this could generate: What is the `body`?
  Answer: A list of other AST nodes that represent the statements inside the function.

LINE 107-113: [VarDecl Node]
  What it does: Represents creating a new variable, like `x = 5`.
  Why it is written this way: It separates the *creation* of a variable from just *updating* its value.
  What breaks if you change it: The compiler might confuse creating a variable with using an existing one.
  Viva question this could generate: What's the difference between `VarDecl` and `AssignStmt`?
  Answer: `VarDecl` is for when a variable is born; `AssignStmt` is for when you change the value of an existing variable.

LINE 146-160: [ForRangeStmt Node]
  What it does: Represents a loop that counts, like `for i in range(10)`.
  Why it is written this way: It explicitly stores the start, stop, and step. This is easy to turn into a C `for` loop.
  What breaks if you change it: Standard counting loops would be harder to translate.
  Viva question this could generate: Why have a separate `ForEachStmt`?
  Answer: Because iterating over an array (`for x in arr`) is fundamentally different from counting numbers in C.

LINE 195-207: [PrintStmt Node]
  What it does: Represents a print command.
  Why it is written this way: It stores a *list* of values. This allows `print(x, y, z)` to be represented by a single node.
  What breaks if you change it: You could only print one thing at a time.
  Viva question this could generate: How does this work in C?
  Answer: The C generator looks at the types of all values and builds a single `printf` format string like `%d %f\n`.

LINE 254-270: [Literal Node]
  What it does: Represents a fixed value like `5`, `3.14`, or `"hello"`.
  Why it is written this way: It stores both the value and its type. This is the starting point for all type-checking.
  What breaks if you change it: The compiler won't know that `5` is an integer.
  Viva question this could generate: Why store the type here?
  Answer: So the semantic analyzer knows immediately what type it is without having to guess.

---

## FILE: transpiler/lexer/tokens.py
### What this file does
This file defines the "alphabet" of the compiler. It lists all the possible types of words (Tokens) that can exist in code, like `IF`, `WHILE`, `PLUS`, or `NAME`.

### Why this file exists
Before the compiler can understand a sentence, it needs to recognize the words. This file provides the definitions for those words so the Lexer can tag them correctly.

### Line by line:

LINE 1-22: [Module Docstring]
  What it does: Explains what a token is: a piece of code like `if` or `42`.
  Why it is written this way: To clarify that the lexer's job is to turn a string of letters into a list of these objects.
  What breaks if you change it: Documentation only.
  Viva question this could generate: What is a token?
  Answer: The smallest meaningful unit of source code, like a keyword, a number, or an operator.

LINE 27-99: [TokenType Enum]
  What it does: A giant list of every kind of token the compiler supports.
  Why it is written this way: It groups them by category (Keywords, Literals, Operators, etc.) for readability.
  What breaks if you change it: If you remove a type here, the Lexer and Parser will crash because they won't know it exists.
  Viva question this could generate: Why do you have `INDENT` and `DEDENT`?
  Answer: These are for Python. Since Python uses spaces for blocks, we create "invisible" tokens to tell the parser when a block starts and ends.

LINE 102-125: [Token Class]
  What it does: The actual object that represents a word in your code. It stores the type, the value (the text), and its location.
  Why it is written this way: It uses a `dataclass` for simplicity and includes `line` and `col` so we can point to errors exactly.
  What breaks if you change it: You won't be able to tell the user *where* their error is.
  Viva question this could generate: Why store the `value`?
  Answer: For tokens like `NAME` (variable names) or `NUMBER`, the value tells us which name or number it actually is.

---

## FILE: transpiler/preprocessor/preprocessor.py
### What this file does
This file is the "cleaning crew." It goes through the code and removes all comments (the notes starting with `#` or `//`).

### Why this file exists
Comments are for humans, not computers. If we didn't remove them, the Lexer would get confused trying to understand them as code. By cleaning the code first, everything else becomes simpler.

### Line by line:

LINE 1-17: [Module Docstring]
  What it does: Explains why we strip comments first: to separate concerns.
  Why it is written this way: To justify having a separate phase just for cleaning.
  What breaks if you change it: Documentation only.
  Viva question this could generate: Why not let the Lexer handle comments?
  Answer: It makes the Lexer much more complex. It's cleaner to have one tool (the Preprocessor) do one job (strip comments).

LINE 30-58: [process method]
  What it does: The main function. You give it code and a language, and it returns clean code.
  Why it is written this way: It branches based on whether the language is Python or C/C++ because they use different comment symbols.
  What breaks if you change it: The compiler might try to use Python cleaning rules on C code, which wouldn't work.
  Viva question this could generate: What happens if you give it a language it doesn't know?
  Answer: it raises a `CompilerError` saying the language is unsupported.

LINE 84-110: [_strip_python_line method]
  What it does: Looks at one line of Python code and finds the `#` symbol.
  Why it is written this way: It tracks if we are inside a string (like `"hello # world"`). It only removes the `#` if it's *outside* a string.
  What breaks if you change it: It might delete parts of your text messages if they happen to contain a `#`.
  Viva question this could generate: How do you handle a `#` inside a string?
  Answer: We track the `in_string` state. If we see a quote, we ignore everything until the next matching quote.

LINE 112-192: [_strip_c_comments method]
  What it does: Strips both `//` and `/* ... */` comments from C code.
  Why it is written this way: C block comments can span many lines, so it has to walk through the entire file character by character instead of line by line.
  What breaks if you change it: Multi-line comments might not be completely removed.
  Viva question this could generate: What if a block comment `/*` is never closed?
  Answer: The code detects this and reports an "Unclosed block comment" error with the line number where it started.

---

## FILE: transpiler/lexer/python_lexer.py
### What this file does
This file is the "reader" for Python. it takes a string of Python code and turns it into a list of Tokens (the words).

### Why this file exists
Computers can't "read" text; they need structured data. This file provides that structure by identifying keywords, names, and numbers in Python code.

### Line by line:

LINE 1-18: [Module Docstring]
  What it does: Explains the INDENT/DEDENT algorithm.
  Why it is written this way: Because Python's indentation is the hardest part of lexing, so it's explained clearly here.
  What breaks if you change it: Documentation only.
  Viva question this could generate: How do you handle indentation in Python?
  Answer: We use a stack to keep track of space counts. More spaces = INDENT, fewer spaces = DEDENT.

LINE 45-73: [tokenize method]
  What it does: The main loop. It splits the code into lines and processes them one by one.
  Why it is written this way: It follows a specific order: handle indent → tokenize content → add newline → close everything at the end.
  What breaks if you change it: The order of tokens might get messed up, making the code un-parseable.
  Viva question this could generate: Why add a `NEWLINE` token?
  Answer: In Python, a newline often means a statement has ended, so the parser needs to know where the line ended.

LINE 97-124: [_handle_indent method]
  What it does: Counts leading spaces and compares them to the `indent_stack`.
  Why it is written this way: It detects if the user moved "in" (INDENT) or "out" (DEDENT) of a code block.
  What breaks if you change it: The compiler won't know which code is inside an "if" statement.
  Viva question this could generate: What if someone mixes tabs and spaces?
  Answer: We catch that and report an error immediately because mixed indentation is ambiguous and dangerous in Python.

LINE 154-192: [_tokenize_line method]
  What it does: The "scanner" that looks for keywords, operators, and names on a single line.
  Why it is written this way: It checks for two-character operators (like `==`) *before* single-character ones (like `=`) so it doesn't accidentally split them.
  What breaks if you change it: `==` might be seen as two separate `=` signs, which is a different meaning.
  Viva question this could generate: Why check two-character operators first?
  Answer: To ensure the "longest match" is found. We want `==`, not two `=` tokens.

---

## FILE: transpiler/lexer/c_lexer.py
### What this file does
This file is the "reader" for C code. It identifies C keywords like `int`, `void`, and `printf`.

### Why this file exists
It provides the specific rules for C's syntax, which is different from Python (like using semicolons and braces).

### Line by line:

LINE 1-15: [Module Docstring]
  What it does: Explains that C doesn't care about indentation and uses semicolons.
  Why it is written this way: To contrast it with the Python lexer.
  What breaks if you change it: Documentation only.

LINE 75-125: [tokenize method]
  What it does: Walks through the C code character by character.
  Why it is written this way: C doesn't care about lines, so a single loop through all characters is simpler than splitting by line.
  What breaks if you change it: The lexer might become unnecessarily complex.
  Viva question this could generate: Why skip whitespace?
  Answer: In C, extra spaces or newlines don't change the meaning of the program, so we just ignore them to get to the real tokens.

LINE 142-147: [C-specific: & skip]
  What it does: Skips the `&` symbol.
  Why it is written this way: In our subset of C, `&` only appears in `scanf(&x)`. Our AST doesn't need to know about pointers/addresses, so we just ignore it.
  What breaks if you change it: You'd get an "Unknown character" error for every `scanf`.
  Viva question this could generate: Why do you skip the `&` in C?
  Answer: Because our simplified compiler doesn't support pointers. We just want the variable name `x`.

---

## FILE: transpiler/lexer/cpp_lexer.py
### What this file does
This file is the "reader" for C++. It's very small because it "borrows" almost everything from the C lexer.

### Why this file exists
It follows the DRY (Don't Repeat Yourself) principle. Since C++ is mostly C, we only define the few things that are different, like `cout` and `cin`.

### Line by line:

LINE 25-35: [CPP_KEYWORDS and CPP_TWO_CHAR_OPS]
  What it does: Adds `cout`, `cin`, and `::` to the C dictionaries.
  Why it is written this way: It uses the `**` syntax to copy all C keywords and then just add the new ones.
  What breaks if you change it: You'd have to copy-paste hundreds of lines of code from `c_lexer.py`.
  Viva question this could generate: How does this file relate to `CLexer`?
  Answer: It inherits from it. It's a subclass that just tweaks a few settings.

---

## FILE: transpiler/parser/python_parser.py
### What this file does
This file is the "architect." It takes the list of tokens from the lexer and builds the "family tree" (AST) for Python.

### Why this file exists
A list of words isn't enough; the computer needs to know the structure (e.g., this "print" is *inside* this "if"). The parser determines that structure.

### Line by line:

LINE 1-22: [Imports and Hard Rejects]
  What it does: Imports AST nodes and defines a list of things we *don't* support (like classes).
  Why it is written this way: If a student tries to use a complex feature like `class`, we give them a clear "Not supported" message instead of a random crash.
  What breaks if you change it: Users might get confusing errors when they use unsupported features.
  Viva question this could generate: What are "Hard Rejects"?
  Answer: A list of advanced features we deliberately chose not to support to keep the project focused.

LINE 37-65: [Navigation helpers]
  What it does: Small tools like `_current()`, `_peek()`, and `_advance()`.
  Why it is written this way: These make the rest of the parser code much cleaner. You can just say `_expect(TokenType.IF)` instead of writing complex logic.
  What breaks if you change it: The parser code would become huge and unreadable.

LINE 107-124: [_parse_block method]
  What it does: Parses a block of code (the indented stuff).
  Why it is written this way: It looks for an `INDENT` token, then keeps parsing statements until it sees a `DEDENT` token.
  What breaks if you change it: You wouldn't be able to have code inside `if` statements or functions.
  Viva question this could generate: How do you know when a block ends?
  Answer: When the lexer gives us a `DEDENT` token, meaning the indentation has moved back to the left.

LINE 153-178: [_parse_for method]
  What it does: Parses both `for i in range()` and `for x in arr`.
  Why it is written this way: It peeks ahead to see if the keyword `range` is there. If so, it builds a `ForRangeStmt`. Otherwise, it builds a `ForEachStmt`.
  What breaks if you change it: One of the two types of loops wouldn't work.

LINE 253-315: [Expression Parsing (Precedence)]
  What it does: A chain of functions from `_parse_or` down to `_parse_primary`.
  Why it is written this way: This "Precedence Climbing" ensures that math is done in the right order (multiplication before addition).
  What breaks if you change it: `2 + 3 * 4` might incorrectly give `20` instead of `14`.
  Viva question this could generate: How do you handle operator precedence?
  Answer: We use a chain of functions. Each function handles one level of precedence and calls the next function for the operands.

---

## FILE: transpiler/parser/c_parser.py
### What this file does
This file is the "architect" for C code. It builds the AST from C tokens, using semicolons and braces to find the structure.

### Why this file exists
It translates C's specific rules (like `int x = 5;`) into our universal AST nodes.

### Line by line:

LINE 73-86: [_parse_typed_decl_or_func method]
  What it does: Decides if a line is a variable (`int x;`) or a function (`int main()`).
  Why it is written this way: In C, both start with a type name. The parser peeks ahead for a `(` to see if it's a function.
  What breaks if you change it: The compiler might try to treat a function like a variable.
  Viva question this could generate: How do you distinguish a variable declaration from a function?
  Answer: We look at the token after the name. If it's a `(`, it's a function.

LINE 167-189: [_parse_for method]
  What it does: Parses a C `for` loop: `for(int i=0; i<10; i++)`.
  Why it is written this way: It extracts the start value, the condition, and the update (the `i++`) to fill in our `ForRangeStmt` node.
  What breaks if you change it: `for` loops in C wouldn't be supported.

---

## FILE: transpiler/parser/cpp_parser.py
### What this file does
This file is the "architect" for C++. It inherits from the C parser and adds special rules for `cout` and `cin`.

### Why this file exists
It adds the "C++ flavor" to the C parser without repeating the shared logic.

### Line by line:

LINE 47-66: [Handling 'using namespace std;']
  What it does: Skips this common line in C++ files.
  Why it is written this way: In our simple compiler, we don't need namespaces. We just ignore this line so it doesn't cause an error.
  What breaks if you change it: The compiler would crash on `using` because it wouldn't know what it is.
  Viva question this could generate: Why skip 'using namespace std;'?
  Answer: It's boilerplate that doesn't affect the core logic of the programs we are translating, so skipping it simplifies the compiler.

LINE 81-105: [_parse_cout method]
  What it does: Turns `cout << x << y;` into a `PrintStmt`.
  Why it is written this way: It looks for the `<<` symbols and collects all the variables between them into a list.
  What breaks if you change it: `cout` wouldn't be recognized as a print command.

---

## DECISION_EXPLANATIONS

### Decision: Neutral AST as Intermediate Representation
What we chose: A language-neutral Abstract Syntax Tree (AST).
What we rejected: Three-Address Code (TAC) or LLVM IR.
Why in simple words: A neutral AST keeps the "human" structure of the code (like loops and if-statements). This makes the output code look clean and readable. TAC would flatten everything into assembly-like steps, which makes the translated code very hard to read.
What an examiner might ask: Why not just translate Python text directly to C text?
Answer: Because that would break on anything complex. The AST ensures we understand the *logic* of the program before we try to rewrite it in another language.

### Decision: Recursive Descent Parsing
What we chose: Hand-written recursive descent parsers.
What we rejected: Parser generators like ANTLR or Yacc/Bison.
Why in simple words: Recursive descent is just a set of Python functions that call each other. It's very easy to read and debug. Parser generators create "black box" code that is impossible to explain in a viva.
What an examiner might ask: Is recursive descent efficient?
Answer: Yes, for the languages we are handling, it is very fast (O(n) time complexity) and the most readable way to build a parser.

### Decision: Two-Pass Semantic Analysis (for Python)
What we chose: Scan the code twice.
What we rejected: Single-pass analysis.
Why in simple words: In Python, you can call a function at the top of a file even if it's defined at the bottom. A single-pass scanner would say "I don't know this function yet." By scanning twice, the first pass remembers all function names, and the second pass checks the logic.
What an examiner might ask: Why does C only need one pass?
Answer: Because the C language rules force you to declare a function *before* you use it.

---

## VIVA_ANSWERS

Q: Walk me through what happens when I click Compile.
A: First, the Preprocessor removes comments. Then the Lexer turns the text into Tokens. The Parser takes those tokens and builds a Tree (the AST). The Semantic Analyzer checks that tree for logic errors. Finally, the Codegen turns that validated tree into the target language's code.

Q: What is an AST and why do you need one?
A: An Abstract Syntax Tree is a tree structure that represents the logic of a program. We need it because it strips away the "noise" (like semicolons and spaces) and lets the compiler focus on the actual meaning of the code.

Q: Why does Python need INDENT and DEDENT tokens?
A: Python uses spaces to define blocks of code (like what's inside an 'if'). Since the Parser can't easily count spaces, the Lexer does it first and creates INDENT/DEDENT tokens so the Parser knows exactly where a block starts and ends.

Q: What is semantic analysis and what errors does it catch?
A: It's the "logic check" phase. It catches errors like using a variable that hasn't been created, adding a string to an integer, or giving the wrong number of arguments to a function.

Q: What is your IR and why did you choose it?
A: Our IR is the Language-Neutral AST. We chose it because it preserves the high-level structure of the code, which allows our compiler to produce readable, idiomatic C and C++ code.

Q: How does the validator know if the translation is correct?
A: It runs both the original code and the translated code with the same inputs and compares their outputs. If the outputs match exactly, the translation is considered successful.

Q: Why did you use recursive descent parsing?
A: Because it is the most transparent and explainable way to build a parser. Each function corresponds to a rule in the language's grammar, making it easy to trace exactly how a piece of code was turned into a tree node.

Q: How do you handle print(x, y, z) in C output?
A: The C generator looks at the types of x, y, and z. If x is an int and y is a float, it builds a format string like `"%d %f\n"` and generates a single `printf` call with all the arguments.

Q: What happens when a phase fails?
A: The phase collects all the errors it found, puts them in a `CompilerErrorList`, and raises it. The main pipeline catches this exception, shows the errors to the user, and blocks all subsequent phases from running.

Q: How does scope work in your compiler?
A: We use a "Scope Stack." Each function or block gets its own dictionary of variables. When we look for a variable, we start at the top of the stack (the most local scope) and work our way down to the global scope.

Q: Why three separate lexers instead of one?
A: Because Python and C have very different rules for "words." Python cares about indentation and newlines; C cares about semicolons and braces. Separate lexers keep the logic clean, though they share common code through inheritance.

Q: What is the difference between ForRangeStmt and ForEachStmt?
A: `ForRangeStmt` is for counting (like `for i in range(10)`), which maps to a standard C `for` loop. `ForEachStmt` is for arrays (like `for x in arr`), which requires the generator to create an index variable and loop through the array's size.

Q: How do you handle a variable that changes from an int to a float?
A: This is "silent promotion." If the semantic analyzer sees `x = 5` (int) followed by `x = 5.5`, it updates the variable's type to float in the symbol table so the generator knows to declare it as a `float` in C.

Q: What would you add if you had more time?
A: I would add an optimization phase to make the code faster, support for more complex data structures like `structs` or `classes`, and more helpful error recovery so the parser can keep going after a syntax error.
