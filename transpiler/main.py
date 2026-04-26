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

# Initialise Flask app with explicit frontend folder
app = Flask(__name__, static_folder='frontend', static_url_path='')

@app.route('/')
def index():
    """Serve the single-page UI."""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/compile', methods=['POST'])
def compile_source():
    """Execute Phases 1-5: Preprocessor to IR."""
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
        prep = Preprocessor()
        res = prep.process(source, lang)
        results["preprocessor"] = {"status": "pass", "comments": res["comments"]}
        clean_source = res["clean_source"]
    except CompilerErrorList as e:
        results["preprocessor"] = {"status": "error", "errors": [err.to_dict() for err in e.errors]}
        blocked = True
    
    # 2. Lexer
    if not blocked:
        try:
            lexer = PythonLexer() if lang == "python" else (CppLexer() if lang == "cpp" else CLexer())
            tokens = lexer.tokenize(clean_source)
            results["lexer"] = {"status": "pass", "tokens": [t.to_dict() for t in tokens]}
        except CompilerErrorList as e:
            results["lexer"] = {"status": "error", "errors": [err.to_dict() for err in e.errors]}
            blocked = True
    else:
        results["lexer"]["status"] = "blocked"

    # 3. Parser
    if not blocked:
        try:
            parser = PythonParser() if lang == "python" else (CppParser() if lang == "cpp" else CParser())
            program = parser.parse(tokens)
            # The parser returns the Program object
            results["parser"] = {"status": "pass", "ast_text": str(program)} 
        except CompilerErrorList as e:
            results["parser"] = {"status": "error", "errors": [err.to_dict() for err in e.errors]}
            blocked = True
    else:
        results["parser"]["status"] = "blocked"

    # 4. Semantic Analyzer
    if not blocked:
        try:
            analyzer = SemanticAnalyzer()
            program, symbol_table = analyzer.analyze(program, lang)
            results["semantic"] = {"status": "pass", "symbol_table": symbol_table}
        except CompilerErrorList as e:
            results["semantic"] = {"status": "error", "errors": [err.to_dict() for err in e.errors]}
            blocked = True
    else:
        results["semantic"]["status"] = "blocked"

    # 5. IR Generator
    if not blocked:
        try:
            irg = IRGenerator()
            program = irg.generate(program)
            results["ir"] = {"status": "pass", "ir_dict": irg.to_dict(program)}
        except CompilerErrorList as e:
            results["ir"] = {"status": "error", "errors": [err.to_dict() for err in e.errors]}
            blocked = True
    else:
        results["ir"]["status"] = "blocked"

    return jsonify(results)

@app.route('/generate', methods=['POST'])
def generate_code():
    """Execute Phase 6: Code Generation."""
    data = request.json
    # In a real system, we'd reconstruct the Program from ir_dict.
    # For this demo, we re-run the pipeline to get the Program object.
    # This ensures consistency and simplifies the API.
    source = data.get('source', '')
    src_lang = data.get('src_lang', 'python').lower()
    tgt_lang = data.get('tgt_lang', 'c').lower()
    
    try:
        # Re-run pipeline to get validated Program object
        prep = Preprocessor()
        clean = prep.process(source, src_lang)["clean_source"]
        
        lexer = PythonLexer() if src_lang == "python" else (CppLexer() if src_lang == "cpp" else CLexer())
        tokens = lexer.tokenize(clean)
        
        parser = PythonParser() if src_lang == "python" else (CppParser() if src_lang == "cpp" else CParser())
        program = parser.parse(tokens)
        
        analyzer = SemanticAnalyzer()
        program, _ = analyzer.analyze(program, src_lang)
        
        # Now generate for target
        gen = PythonGenerator() if tgt_lang == "python" else (CppGenerator() if tgt_lang == "cpp" else CGenerator())
        code = gen.generate(program)
        
        return jsonify({"status": "pass", "code": code})
    except Exception as e:
        # Unexpected error in re-run
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/validate', methods=['POST'])
def validate_translation():
    """Execute Phase 7: Validation."""
    data = request.json
    src_code = data.get('src_code', '')
    src_lang = data.get('src_lang', 'python').lower()
    tgt_code = data.get('tgt_code', '')
    tgt_lang = data.get('tgt_lang', 'c').lower()
    inputs = data.get('inputs', [])
    
    try:
        val = Validator()
        res = val.validate(src_code, src_lang, tgt_code, tgt_lang, inputs)
        return jsonify({"status": "pass", "result": res})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # Add project root to path for imports
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    app.run(debug=True, port=5000)
