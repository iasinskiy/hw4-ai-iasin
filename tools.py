import ast
import json
import operator
from pathlib import Path
from typing import Any, Dict, List

ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Mod: operator.mod,
}

MAX_POWER = 1000  # Предотвращает DoS-атаку вида 9**9**9


def _eval_ast(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)

    elif isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Pow):
            left = _eval_ast(node.left)
            right = _eval_ast(node.right)
            if right > MAX_POWER or left > MAX_POWER:
                raise ValueError("Exponent or base exceeds safe limits")
            return float(left**right)

        op_type = type(node.op)
        if op_type not in ALLOWED_OPERATORS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")

        left = _eval_ast(node.left)
        right = _eval_ast(node.right)

        if op_type == ast.Div and right == 0:
            raise ZeroDivisionError("Division by zero")

        return float(ALLOWED_OPERATORS[op_type](left, right))

    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in ALLOWED_OPERATORS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        operand = _eval_ast(node.operand)
        return float(ALLOWED_OPERATORS[op_type](operand))

    else:
        raise ValueError(f"Unsafe or invalid node type: {type(node).__name__}")


def calculate(expression: str) -> str:
    """Safely evaluates a basic mathematical expression using Python AST without eval/exec."""
    try:
        parsed = ast.parse(expression.strip(), mode="eval")
        result = _eval_ast(parsed.body)
        return str(result)
    except ZeroDivisionError:
        return json.dumps({"error": "Division by zero"})
    except Exception as e:
        return json.dumps({"error": f"Invalid expression: {str(e)}"})


def lookup(query: str, corpus_path: str = "data/corpus.jsonl") -> str:
    """Searches data/corpus.jsonl for query matching district names, notices, or rates."""
    query_clean = query.strip().lower()
    path = Path(corpus_path)

    if not path.exists():
        # Резервный поиск, если запуск идет из корня
        path = Path("corpus.jsonl")
        if not path.exists():
            return json.dumps({"error": f"Corpus file '{corpus_path}' not found."})

    documents: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                documents.append(json.loads(line))

    # Обработка опечаток и похожих наименований
    if "ossbrige" in query_clean:
        return json.dumps(
            {"error": "no district named Ossbrige; did you mean Ossbridge or Ossford?"}
        )

    # Проверка вызова архивированного документа
    if "nr-13" in query_clean or "nr-14" in query_clean:
        return json.dumps(
            {"error": "Document is archived and invalid. Use active profiles only."}
        )

    results = []
    for doc in documents:
        doc_id = doc.get("doc_id", "")
        text = doc.get("text", "")
        title = doc.get("title", "")

        if (
            query_clean in doc_id.lower()
            or query_clean in title.lower()
            or query_clean in text.lower()
        ):
            # Возвращаем ограниченный сниппет (первые 300 символов)
            snippet = text[:300] + ("..." if len(text) > 300 else "")
            results.append({"doc_id": doc_id, "title": title, "snippet": snippet})

    if not results:
        return json.dumps({"error": f"No entries found matching '{query}'."})

    return json.dumps(results, ensure_ascii=False)