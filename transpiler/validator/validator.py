"""
validator/validator.py — Dynamic validation: run source + target, compare output.
Phase 7 of the compiler pipeline.

Validates that the generated target code produces the SAME output as the
source code. Both are executed via subprocess for isolation.

Design:
  - run_python(code, inputs) → subprocess python3 -c "code"
  - run_c(code, inputs) → gcc compile to temp file, execute, cleanup
  - run_cpp(code, inputs) → g++ compile to temp file, execute, cleanup
  - compare(a, b) → try float parse with tolerance 1e-6, else exact match
  - has_input(program) → recursively checks AST for any InputStmt node

Error pattern: collect ALL errors → raise CompilerErrorList once at end.
Note: CompilerError is a dataclass, NOT an Exception. Only CompilerErrorList
can be raised. Errors are appended to self.errors list.
"""
import subprocess
import tempfile
import os

try:
    from transpiler.errors import CompilerError, CompilerErrorList, Phase
    from transpiler.ast_nodes import (
        Program, FunctionDecl, InputStmt, IfStmt, WhileStmt,
        ForRangeStmt, ForEachStmt)
except ModuleNotFoundError:
    from errors import CompilerError, CompilerErrorList, Phase
    from ast_nodes import (
        Program, FunctionDecl, InputStmt, IfStmt, WhileStmt,
        ForRangeStmt, ForEachStmt)

# Timeout for subprocess execution (seconds)
EXEC_TIMEOUT = 10
COMPILE_TIMEOUT = 15


class Validator:
    """Runs source and target code, compares output to verify translation."""

    def validate(self, src_code: str, src_lang: str,
                 tgt_code: str, tgt_lang: str,
                 test_inputs: list = None) -> dict:
        """Execute source and target code, compare stdout.

        Returns: {passed: bool, source_out: str, target_out: str, diff: str}
        """
        self.errors = []
        inputs_str = "\n".join(test_inputs) + "\n" if test_inputs else ""

        # Run source code
        source_out = self._run_code(src_code, src_lang, inputs_str, "source")
        # Run target code
        target_out = self._run_code(tgt_code, tgt_lang, inputs_str, "target")

        if self.errors:
            raise CompilerErrorList(self.errors)

        # Compare outputs
        passed = self._compare(source_out, target_out)
        diff = self._generate_diff(source_out, target_out) if not passed else ""

        return {
            "passed": passed,
            "source_out": source_out,
            "target_out": target_out,
            "diff": diff,
        }

    # ── Code execution dispatch ───────────────────────────────────────

    def _run_code(self, code: str, lang: str, inputs: str, label: str) -> str:
        """Dispatch to the correct runner based on language."""
        runners = {"python": self._run_python, "c": self._run_c, "cpp": self._run_cpp}
        runner = runners.get(lang)
        if runner is None:
            self.errors.append(CompilerError(Phase.VALIDATOR,
                f"Unknown language for {label}: '{lang}'"))
            return ""
        return runner(code, inputs, label)

    def _run_python(self, code: str, inputs: str, label: str) -> str:
        """Execute Python code via subprocess."""
        import sys
        try:
            result = subprocess.run(
                [sys.executable, "-c", code],
                input=inputs, capture_output=True, text=True,
                timeout=EXEC_TIMEOUT)
            if result.returncode != 0:
                err_msg = result.stderr.strip().split("\n")[-1] if result.stderr else "unknown error"
                self.errors.append(CompilerError(Phase.VALIDATOR,
                    f"Python {label} execution failed: {err_msg}"))
                return ""
            return result.stdout
        except subprocess.TimeoutExpired:
            self.errors.append(CompilerError(Phase.VALIDATOR,
                f"Python {label} execution timed out after {EXEC_TIMEOUT}s"))
            return ""
        except FileNotFoundError:
            self.errors.append(CompilerError(Phase.VALIDATOR,
                "Python interpreter not found — cannot validate Python code"))
            return ""

    def _run_c(self, code: str, inputs: str, label: str) -> str:
        """Compile C code with gcc, execute, cleanup temp files."""
        src_path = None
        exe_path = None
        try:
            # Write source to temp file
            with tempfile.NamedTemporaryFile(
                    suffix=".c", mode="w", delete=False) as f:
                f.write(code)
                src_path = f.name
            exe_path = src_path.replace(".c", "")

            # Compile with gcc
            comp = subprocess.run(
                ["gcc", src_path, "-o", exe_path, "-lm"],
                capture_output=True, text=True, timeout=COMPILE_TIMEOUT)
            if comp.returncode != 0:
                err_msg = comp.stderr.strip().split("\n")[0] if comp.stderr else "compilation failed"
                self.errors.append(CompilerError(Phase.VALIDATOR,
                    f"C {label} compilation failed: {err_msg}"))
                return ""

            # Execute
            result = subprocess.run(
                [os.path.abspath(exe_path)], input=inputs, capture_output=True,
                text=True, timeout=EXEC_TIMEOUT)
            if result.returncode != 0:
                err_msg = result.stderr.strip() if result.stderr else "runtime error"
                self.errors.append(CompilerError(Phase.VALIDATOR,
                    f"C {label} execution failed: {err_msg}"))
                return ""
            return result.stdout

        except subprocess.TimeoutExpired:
            self.errors.append(CompilerError(Phase.VALIDATOR,
                f"C {label} compilation/execution timed out"))
            return ""
        except FileNotFoundError:
            self.errors.append(CompilerError(Phase.VALIDATOR,
                "gcc not found — cannot validate C code"))
            return ""
        finally:
            if src_path and os.path.exists(src_path): os.unlink(src_path)
            if exe_path and os.path.exists(exe_path): os.unlink(exe_path)

    def _run_cpp(self, code: str, inputs: str, label: str) -> str:
        """Compile C++ code with g++, execute, cleanup temp files."""
        src_path = None
        exe_path = None
        try:
            with tempfile.NamedTemporaryFile(
                    suffix=".cpp", mode="w", delete=False) as f:
                f.write(code)
                src_path = f.name
            exe_path = src_path.replace(".cpp", "")

            comp = subprocess.run(
                ["g++", src_path, "-o", exe_path],
                capture_output=True, text=True, timeout=COMPILE_TIMEOUT)
            if comp.returncode != 0:
                err_msg = comp.stderr.strip().split("\n")[0] if comp.stderr else "compilation failed"
                self.errors.append(CompilerError(Phase.VALIDATOR,
                    f"C++ {label} compilation failed: {err_msg}"))
                return ""

            result = subprocess.run(
                [os.path.abspath(exe_path)], input=inputs, capture_output=True,
                text=True, timeout=EXEC_TIMEOUT)
            if result.returncode != 0:
                err_msg = result.stderr.strip() if result.stderr else "runtime error"
                self.errors.append(CompilerError(Phase.VALIDATOR,
                    f"C++ {label} execution failed: {err_msg}"))
                return ""
            return result.stdout

        except subprocess.TimeoutExpired:
            self.errors.append(CompilerError(Phase.VALIDATOR,
                "C++ compilation/execution timed out"))
            return ""
        except FileNotFoundError:
            self.errors.append(CompilerError(Phase.VALIDATOR,
                "g++ not found — cannot validate C++ code"))
            return ""
        finally:
            if src_path and os.path.exists(src_path): os.unlink(src_path)
            if exe_path and os.path.exists(exe_path): os.unlink(exe_path)

    # ── Output comparison ─────────────────────────────────────────────

    def _compare(self, source_out: str, target_out: str) -> bool:
        """Compare two outputs. Float-tolerant, then exact match fallback."""
        s_lines = [l.rstrip() for l in source_out.strip().split("\n")]
        t_lines = [l.rstrip() for l in target_out.strip().split("\n")]
        if len(s_lines) != len(t_lines):
            return False
        for s_line, t_line in zip(s_lines, t_lines):
            if s_line == t_line:
                continue
            if not self._float_compare(s_line, t_line):
                return False
        return True

    def _float_compare(self, a: str, b: str) -> bool:
        """Try to parse both as floats and compare with tolerance 1e-6."""
        try:
            return abs(float(a) - float(b)) < 1e-6
        except ValueError:
            return False

    def _generate_diff(self, source_out: str, target_out: str) -> str:
        """Generate human-readable diff for the UI."""
        s_lines = source_out.strip().split("\n")
        t_lines = target_out.strip().split("\n")
        diff_lines = []
        for i in range(max(len(s_lines), len(t_lines))):
            sl = s_lines[i] if i < len(s_lines) else "<missing>"
            tl = t_lines[i] if i < len(t_lines) else "<missing>"
            if sl.rstrip() != tl.rstrip():
                diff_lines.append(f"Line {i+1}: source='{sl}' target='{tl}'")
        return "\n".join(diff_lines)

    # ── IR inspection ─────────────────────────────────────────────────

    @staticmethod
    def has_input(program: Program) -> bool:
        """Check if AST contains any InputStmt (user needs test inputs)."""
        def _walk(nodes):
            for node in nodes:
                if isinstance(node, InputStmt):
                    return True
                if isinstance(node, FunctionDecl):
                    if _walk(node.body): return True
                elif isinstance(node, IfStmt):
                    if _walk(node.then_body) or _walk(node.else_body): return True
                elif isinstance(node, WhileStmt):
                    if _walk(node.body): return True
                elif isinstance(node, (ForRangeStmt, ForEachStmt)):
                    if _walk(node.body): return True
            return False
        return _walk(program.functions) or _walk(program.globals)
