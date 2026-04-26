"""
main.py — Flask web server for the source-to-source compiler.
Phase 8 of the compiler pipeline.

Routes:
  GET  /           → serves the single-page frontend
  POST /compile    → runs Phases 1-5 (preprocessor to IR), returns has_input flag
  POST /generate   → runs Phase 6 (code generation for target language)
  POST /validate   → runs Phase 7 (execute source+target, compare output)
"""
import os
import sys
from flask import Flask, request, jsonify, send_from_directory
from errors import Phase, CompilerError, CompilerErrorList
from preprocessor.preprocessor import Preprocessor
from lexer.python_lexer import PythonLexer
from lexer.c_lexer import CLexer
from lexer.cpp_lexer import CppLexer
from parser.python_parser import PythonParser
from parser.c_parser import CParser
from parser.cpp_parser import CppParser
from semantic.analyzer import SemanticAnalyzer
from ir.ir_generator import IRGenerator
from codegen.python_generator import PythonGenerator
from codegen.c_generator import CGenerator
from codegen.cpp_generator import CppGenerator
from validator.validator import Validator
from visualizer.ast_visualizer import ast_to_tree as _ast_to_tree, get_legend as _get_ast_legend
from ast_nodes import (
    Program, FunctionDecl, Param, VarDecl, ArrayDecl,
    AssignStmt, ArrayAssign, IfStmt, WhileStmt, ForRangeStmt,
    ForEachStmt, ReturnStmt, PrintStmt, InputStmt, FunctionCall,
    BinaryOp, UnaryOp, Var, ArrayAccess, Literal, DataType
)

# Initialise Flask app with explicit frontend folder
app = Flask(__name__, static_folder='frontend', static_url_path='')


def _get_lexer(lang):
    """Return the correct lexer for the given language."""
    return {"python": PythonLexer, "c": CLexer, "cpp": CppLexer}[lang]()


def _get_parser(lang):
    """Return the correct parser for the given language."""
    return {"python": PythonParser, "c": CParser, "cpp": CppParser}[lang]()


def _get_generator(lang):
    """Return the correct code generator for the given language."""
    return {"python": PythonGenerator, "c": CGenerator, "cpp": CppGenerator}[lang]()


def _run_frontend_pipeline(source, lang):
    """Run Phases 1-5 and return the Program object."""
    clean = Preprocessor().process(source, lang)["clean_source"]
    tokens = _get_lexer(lang).tokenize(clean)
    program = _get_parser(lang).parse(tokens)
    program, _ = SemanticAnalyzer().analyze(program, lang)
    program = IRGenerator().generate(program)
    return program




@app.route('/')
def index():
    """Serve the single-page UI."""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/compile', methods=['POST'])
def compile_source():
    """Execute Phases 1-5: Preprocessor to IR.
    Returns phase results + has_input flag + AST tree for visualization."""
    data = request.json
    source = data.get('source', '')
    lang = data.get('lang', 'python').lower()

    results = {
        "preprocessor": {"status": "pending"},
        "lexer":        {"status": "pending"},
        "parser":       {"status": "pending"},
        "semantic":     {"status": "pending"},
        "ir":           {"status": "pending"}
    }

    blocked = False
    program = None
    tokens = None

    # 1. Preprocessor
    try:
        res = Preprocessor().process(source, lang)
        results["preprocessor"] = {"status": "pass", "comments": res["comments"]}
        clean_source = res["clean_source"]
    except CompilerErrorList as e:
        results["preprocessor"] = {"status": "error", "errors": e.to_dict_list()}
        blocked = True

    # 2. Lexer
    if not blocked:
        try:
            tokens = _get_lexer(lang).tokenize(clean_source)
            results["lexer"] = {"status": "pass", "tokens": [t.to_dict() for t in tokens]}
        except CompilerErrorList as e:
            results["lexer"] = {"status": "error", "errors": e.to_dict_list()}
            blocked = True
    else:
        results["lexer"]["status"] = "blocked"

    # 3. Parser
    if not blocked:
        try:
            program = _get_parser(lang).parse(tokens)
            # Return text representation AND tree structure for graphical AST
            import json, dataclasses, enum
            class ASTEncoder(json.JSONEncoder):
                def default(self, o):
                    if isinstance(o, enum.Enum): return o.value
                    if dataclasses.is_dataclass(o) and not isinstance(o, type):
                        return {o.__class__.__name__: dataclasses.asdict(o)}
                    return str(o)
            ast_dict = IRGenerator().to_dict(program)
            results["parser"] = {
                "status": "pass",
                "ast_text": json.dumps(ast_dict, indent=2, cls=ASTEncoder),
                "ast_tree": _ast_to_tree(program),
                "ast_legend": _get_ast_legend()
            }
        except CompilerErrorList as e:
            results["parser"] = {"status": "error", "errors": e.to_dict_list()}
            blocked = True
    else:
        results["parser"]["status"] = "blocked"

    # 4. Semantic Analyzer
    if not blocked:
        try:
            program, symbol_table = SemanticAnalyzer().analyze(program, lang)
            # Build a richer symbol table view for the UI
            semantic_info = {
                "symbol_table": symbol_table,
                "summary": _semantic_summary(symbol_table, program)
            }
            results["semantic"] = {"status": "pass", **semantic_info}
        except CompilerErrorList as e:
            results["semantic"] = {"status": "error", "errors": e.to_dict_list()}
            blocked = True
    else:
        results["semantic"]["status"] = "blocked"

    # 5. IR Generator
    if not blocked:
        try:
            irg = IRGenerator()
            program = irg.generate(program)
            results["ir"] = {
                "status": "pass",
                "ir_dict": irg.to_dict(program),
                "ir_tree": _ast_to_tree(program)  # same tree for IR visualization
            }
            results["has_input"] = Validator.has_input(program)
        except CompilerErrorList as e:
            results["ir"] = {"status": "error", "errors": e.to_dict_list()}
            blocked = True
    else:
        results["ir"]["status"] = "blocked"

    return jsonify(results)


def _semantic_summary(sym_table, program):
    """Generate a human-readable summary of semantic analysis results."""
    funcs = [k for k, v in sym_table.items() if v.get('kind') == 'function']
    vars_ = [k for k, v in sym_table.items() if v.get('kind') == 'var' and '.' not in k]
    local_vars = [k for k, v in sym_table.items() if v.get('kind') == 'var' and '.' in k]

    # Count statement types in the AST
    stmt_counts = {}
    def _count(node):
        name = type(node).__name__
        if name != 'list':
            stmt_counts[name] = stmt_counts.get(name, 0) + 1
        for attr in ['body', 'then_body', 'else_body', 'globals']:
            stmts = getattr(node, attr, None)
            if isinstance(stmts, list):
                for s in stmts:
                    _count(s)
    for f in program.functions:
        _count(f)
    for g in program.globals:
        _count(g)

    return {
        "functions": funcs,
        "global_vars": vars_,
        "local_vars": local_vars,
        "total_symbols": len(sym_table),
        "statement_types": stmt_counts
    }


@app.route('/generate', methods=['POST'])
def generate_code():
    """Execute Phase 6: Code Generation."""
    data = request.json
    source = data.get('source', '')
    src_lang = data.get('src_lang', 'python').lower()
    tgt_lang = data.get('tgt_lang', 'c').lower()

    try:
        program = _run_frontend_pipeline(source, src_lang)
        code = _get_generator(tgt_lang).generate(program)
        return jsonify({"status": "pass", "code": code})
    except CompilerErrorList as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/validate', methods=['POST'])
def validate_translation():
    """Execute Phase 7: Validation."""
    data = request.json
    source = data.get('source', '')
    src_lang = data.get('src_lang', 'python').lower()
    tgt_lang = data.get('tgt_lang', 'c').lower()
    inputs = data.get('inputs', [])

    try:
        program = _run_frontend_pipeline(source, src_lang)
        src_code = _get_generator(src_lang).generate(program)
        tgt_code = _get_generator(tgt_lang).generate(program)

        val = Validator()
        res = val.validate(src_code, src_lang, tgt_code, tgt_lang, inputs if inputs else None)
        return jsonify({
            "status": "pass",
            "result": res,
            "src_code": src_code,
            "tgt_code": tgt_code
        })
    except CompilerErrorList as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    app.run(debug=True, port=5000)
