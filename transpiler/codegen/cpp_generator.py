"""
codegen/cpp_generator.py — Generates C++ source from language-neutral AST.
Phase 6 of the compiler pipeline.

EXTENDS CGenerator — does NOT copy-paste C generator code.
Only overrides:
  - _emit_preamble() → #include <iostream> + using namespace std;
  - _gen_print() → cout << v1 << " " << v2 << endl;
  - _gen_input() → cin >> target;

Everything else (function defs, var decls, for loops, expressions,
assignments, blocks) is inherited unchanged from CGenerator.
"""
try:
    from transpiler.codegen.c_generator import CGenerator, FMT_SPEC, TYPE_STR
    from transpiler.errors import CompilerError, Phase
    from transpiler.ast_nodes import DataType, PrintStmt, InputStmt, Literal
except ModuleNotFoundError:
    from codegen.c_generator import CGenerator, FMT_SPEC, TYPE_STR
    from errors import CompilerError, Phase
    from ast_nodes import DataType, PrintStmt, InputStmt, Literal


class CppGenerator(CGenerator):
    """Generates C++ source code. Inherits from CGenerator.

    Only overrides: preamble (#include <iostream>), PrintStmt (cout <<),
    and InputStmt (cin >>). All other generation inherited unchanged.
    """

    def _emit_preamble(self):
        """Override: emit C++ includes instead of C includes."""
        self._emit_raw("#include <iostream>")
        self._emit_raw("using namespace std;")
        self.lines.append("")

    def _gen_print(self, node: PrintStmt):
        """cout << v1 << " x " << v2 << endl;
        Handles interleaved Literal(STR) for format strings."""
        if not node.values:
            self._emit("cout << endl;")
            return
        parts = []
        for i, v in enumerate(node.values):
            if isinstance(v, Literal) and v.data_type == DataType.STR:
                parts.append(f'<< "{v.value}"')
            else:
                parts.append(f"<< {self._expr(v)}")
            # Add separator between values only when separator is not empty
            if node.separator and i < len(node.values) - 1:
                parts.append(f'<< "{node.separator}"')
        parts.append("<< endl")
        self._emit(f"cout {' '.join(parts)};")

    def _gen_input(self, node: InputStmt):
        """cout << prompt; cin >> target;"""
        if node.prompt:
            self._emit(f'cout << "{node.prompt}";')
        tgt = self._expr(node.target) if hasattr(node.target, "line") else node.target
        # Auto-declare simple vars if unseen
        if isinstance(tgt, str) and "[" not in tgt and tgt not in self._declared:
            self._declared.add(tgt)
            self._var_types[tgt] = node.data_type
            self._emit(f"{self._type_str(node.data_type)} {tgt};")
            
        self._emit(f"cin >> {tgt};")
