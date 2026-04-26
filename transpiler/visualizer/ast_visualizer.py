"""
visualizer/ast_visualizer.py — AST tree visualization helper.

Converts compiler AST nodes into a JSON-serializable tree structure
suitable for rendering as an interactive SVG tree in the frontend.

Each output node has:
    { type: str, label: str, dtype?: str, children: [...] }

Color categories (applied in frontend):
    - Program / Root     → Blue (#3b82f6)
    - Function / Params  → Purple (#8b5cf6)
    - Control Flow       → Green (#10b981)  — if, while, for
    - I/O Statements     → Pink (#ec4899)   — print, input
    - Declarations       → Teal (#14b8a6)   — VarDecl, ArrayDecl
    - Assignments        → Sky (#0ea5e9)    — AssignStmt
    - Return             → Indigo (#6366f1)
    - Expressions        → Orange (#f97316) — BinaryOp, UnaryOp
    - Literals           → Yellow (#eab308)
    - Variables          → Cyan (#22d3ee)
    - Structural         → Slate (#475569)  — body, condition blocks
"""

try:
    from transpiler.ast_nodes import (
        Program, FunctionDecl, Param, VarDecl, ArrayDecl,
        AssignStmt, ArrayAssign, IfStmt, WhileStmt, ForRangeStmt,
        ForEachStmt, ReturnStmt, PrintStmt, InputStmt, FunctionCall,
        BinaryOp, UnaryOp, Var, ArrayAccess, Literal, DataType
    )
except ModuleNotFoundError:
    from ast_nodes import (
        Program, FunctionDecl, Param, VarDecl, ArrayDecl,
        AssignStmt, ArrayAssign, IfStmt, WhileStmt, ForRangeStmt,
        ForEachStmt, ReturnStmt, PrintStmt, InputStmt, FunctionCall,
        BinaryOp, UnaryOp, Var, ArrayAccess, Literal, DataType
    )


# Node color categories for the frontend legend
NODE_CATEGORIES = {
    "Program & Root":    {"color": "#3b82f6", "types": ["Program"]},
    "Functions":         {"color": "#8b5cf6", "types": ["FunctionDecl", "Param", "Params"]},
    "Control Flow":      {"color": "#10b981", "types": ["IfStmt", "WhileStmt", "ForRangeStmt", "ForEachStmt"]},
    "I/O Statements":    {"color": "#ec4899", "types": ["PrintStmt", "InputStmt"]},
    "Declarations":      {"color": "#14b8a6", "types": ["VarDecl", "ArrayDecl"]},
    "Assignments":       {"color": "#0ea5e9", "types": ["AssignStmt", "ArrayAssign"]},
    "Return":            {"color": "#6366f1", "types": ["ReturnStmt"]},
    "Expressions":       {"color": "#f97316", "types": ["BinaryOp", "UnaryOp", "FunctionCall"]},
    "Literals":          {"color": "#eab308", "types": ["Literal"]},
    "Variables":         {"color": "#22d3ee", "types": ["Var", "ArrayAccess"]},
    "Structural":        {"color": "#475569", "types": ["Body", "ThenBlock", "ElseBlock", "Condition"]},
}


def ast_to_tree(node):
    """Convert an AST node into a JSON-serializable tree dictionary.

    Returns: { type: str, label: str, children: list[dict] }
    Returns None for None inputs.
    """
    if node is None:
        return None

    # ── Leaf nodes ─────────────────────────────
    if isinstance(node, Literal):
        val = repr(node.value) if isinstance(node.value, str) else str(node.value)
        return {"type": "Literal", "label": val, "dtype": node.data_type.value, "children": []}

    if isinstance(node, Var):
        return {"type": "Var", "label": node.name, "children": []}

    if isinstance(node, Param):
        return {"type": "Param", "label": f"{node.name}: {node.data_type.value}", "children": []}

    if isinstance(node, InputStmt):
        return {"type": "InputStmt", "label": f"input → {node.target}", "children": []}

    # ── Expression nodes ──────────────────────
    if isinstance(node, BinaryOp):
        return {"type": "BinaryOp", "label": node.op,
                "children": [ast_to_tree(node.left), ast_to_tree(node.right)]}

    if isinstance(node, UnaryOp):
        return {"type": "UnaryOp", "label": node.op,
                "children": [ast_to_tree(node.operand)]}

    if isinstance(node, FunctionCall):
        return {"type": "FunctionCall", "label": f"{node.name}()",
                "children": [ast_to_tree(a) for a in node.args]}

    if isinstance(node, ArrayAccess):
        return {"type": "ArrayAccess", "label": f"{node.name}[]",
                "children": [ast_to_tree(node.index)]}

    # ── Declaration nodes ─────────────────────
    if isinstance(node, VarDecl):
        c = [ast_to_tree(node.value)] if node.value else []
        return {"type": "VarDecl", "label": f"{node.name}: {node.data_type.value}", "children": c}

    if isinstance(node, ArrayDecl):
        c = [ast_to_tree(e) for e in node.elements] if node.elements else []
        return {"type": "ArrayDecl", "label": f"{node.name}[{node.size}]", "children": c}

    # ── Statement nodes ───────────────────────
    if isinstance(node, AssignStmt):
        return {"type": "AssignStmt", "label": f"{node.name} =",
                "children": [ast_to_tree(node.value)]}

    if isinstance(node, ArrayAssign):
        return {"type": "ArrayAssign", "label": f"{node.name}[] =",
                "children": [ast_to_tree(node.index), ast_to_tree(node.value)]}

    if isinstance(node, IfStmt):
        c = [{"type": "Condition", "label": "condition", "children": [ast_to_tree(node.condition)]}]
        c.append({"type": "ThenBlock", "label": "then", "children": [ast_to_tree(s) for s in node.then_body]})
        if node.else_body:
            c.append({"type": "ElseBlock", "label": "else", "children": [ast_to_tree(s) for s in node.else_body]})
        return {"type": "IfStmt", "label": "if", "children": c}

    if isinstance(node, WhileStmt):
        c = [{"type": "Condition", "label": "condition", "children": [ast_to_tree(node.condition)]}]
        c.append({"type": "Body", "label": "body", "children": [ast_to_tree(s) for s in node.body]})
        return {"type": "WhileStmt", "label": "while", "children": c}

    if isinstance(node, ForRangeStmt):
        c = [{"type": "Var", "label": node.var, "children": []}]
        if node.start:
            c.append({"type": "Start", "label": "start", "children": [ast_to_tree(node.start)]})
        c.append({"type": "Stop", "label": "stop", "children": [ast_to_tree(node.stop)]})
        if node.step:
            c.append({"type": "Step", "label": "step", "children": [ast_to_tree(node.step)]})
        c.append({"type": "Body", "label": "body", "children": [ast_to_tree(s) for s in node.body]})
        return {"type": "ForRangeStmt", "label": "for", "children": c}

    if isinstance(node, ForEachStmt):
        c = [{"type": "Body", "label": "body", "children": [ast_to_tree(s) for s in node.body]}]
        return {"type": "ForEachStmt", "label": f"foreach {node.var} in {node.array_name}", "children": c}

    if isinstance(node, ReturnStmt):
        c = [ast_to_tree(node.value)] if node.value else []
        return {"type": "ReturnStmt", "label": "return", "children": c}

    if isinstance(node, PrintStmt):
        return {"type": "PrintStmt", "label": "print",
                "children": [ast_to_tree(v) for v in node.values]}

    # ── Compound nodes ────────────────────────
    if isinstance(node, FunctionDecl):
        params = [ast_to_tree(p) for p in node.params]
        body = [ast_to_tree(s) for s in node.body]
        c = []
        if params:
            c.append({"type": "Params", "label": "params", "children": params})
        c.append({"type": "Body", "label": "body", "children": body})
        rt = node.return_type.value if hasattr(node.return_type, 'value') else str(node.return_type)
        return {"type": "FunctionDecl", "label": f"fn {node.name}() → {rt}", "children": c}

    if isinstance(node, Program):
        c = [ast_to_tree(f) for f in node.functions]
        c += [ast_to_tree(g) for g in node.globals]
        return {"type": "Program", "label": "Program", "children": c}

    # Fallback for unknown node types
    return {"type": type(node).__name__, "label": str(node), "children": []}


def get_legend():
    """Return the color legend for the frontend.
    Returns: list of { category: str, color: str, types: list[str] }
    """
    return [
        {"category": cat, "color": info["color"], "types": info["types"]}
        for cat, info in NODE_CATEGORIES.items()
    ]
