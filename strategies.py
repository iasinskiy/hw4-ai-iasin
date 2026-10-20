import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Tuple
from dotenv import load_dotenv
from openai import OpenAI
from tools import calculate, lookup

# Автоматически загружаем переменные из файла .env
load_dotenv()

# Считываем ключ (OPENROUTER_API_KEY или OPENAI_API_KEY)
api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")

if not api_key:
    raise ValueError(
        "API Key not found. Please set OPENROUTER_API_KEY or OPENAI_API_KEY in .env file."
    )

client = OpenAI(
    api_key=api_key,
    base_url=base_url,
)

MODEL_NAME = os.getenv("MODEL_NAME", "gpt-5.6-luna")
MAX_TURNS = 10  # Лимит итераций цикла ReAct

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "lookup",
            "description": "Searches Nine Rivers Region documents for active district profiles, notices, or rates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "District name, document ID, or search topic.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Evaluates basic mathematical expressions (+, -, *, /).",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression to evaluate.",
                    }
                },
                "required": ["expression"],
            },
        },
    },
]


def _ensure_outputs_dir():
    Path("outputs").mkdir(exist_ok=True)


def run_strategy_s1(question: str) -> Tuple[str, Dict[str, Any]]:
    """S1: Прямой запрос к модель без дополнительного контекста."""
    prompt = (
        f"{question}\n\n"
        "Provide your answer in the exact format: ANSWER: <District/Yes/No> | <Number>"
    )
    start_time = time.time()
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
    )
    elapsed = time.time() - start_time
    content = response.choices[0].message.content.strip()
    usage = response.usage.model_dump() if response.usage else {}

    meta = {
        "elapsed_seconds": elapsed,
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
    }
    return content, meta


def run_strategy_s2(question: str, k: int = 5) -> Tuple[str, Dict[str, Any]]:
    """S2: Naive RAG с подачей всех документов в промпт и k=5 мажоритарным голосованием."""
    corpus_text = ""
    corpus_path = Path("data/corpus.jsonl")
    if not corpus_path.exists():
        corpus_path = Path("corpus.jsonl")

    if corpus_path.exists():
        with open(corpus_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    doc = json.loads(line)
                    corpus_text += f"\n--- {doc.get('doc_id')} ({doc.get('title')}) ---\n{doc.get('text')}\n"

    prompt = (
        f"Context Documents:\n{corpus_text}\n\n"
        f"Question: {question}\n\n"
        "Provide your answer in the exact format: ANSWER: <District/Yes/No> | <Number>"
    )

    answers = []
    total_input_tokens = 0
    total_output_tokens = 0
    start_time = time.time()

    for _ in range(k):
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        content = response.choices[0].message.content.strip()
        answers.append(content)
        if response.usage:
            total_input_tokens += response.usage.prompt_tokens
            total_output_tokens += response.usage.completion_tokens

    elapsed = time.time() - start_time
    majority_answer = max(set(answers), key=answers.count)

    meta = {
        "elapsed_seconds": elapsed,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "samples": answers,
    }
    return majority_answer, meta


def run_strategy_s3(
    question: str, q_id: str = "Q-00"
) -> Tuple[str, Dict[str, Any]]:
    """S3: Циклический агент с поддержкой вызова инструментов и логированием."""
    _ensure_outputs_dir()
    log_data = {"question_id": q_id, "question": question, "tool_calls": []}

    messages = [
        {
            "role": "system",
            "content": (
                "You are a factual assistant for Nine Rivers Region. "
                "Use the provided tools (`lookup` and `calculate`) to gather evidence and perform calculations. "
                "Notice that some documents are corrections (e.g. NR-16 overrides NR-05). "
                "Always finish with the strict format: ANSWER: <District/Yes/No> | <Number>"
            ),
        },
        {"role": "user", "content": question},
    ]

    start_time = time.time()
    total_input_tokens = 0
    total_output_tokens = 0
    final_answer = "ANSWER: Unanswered | 0"

    for turn in range(MAX_TURNS):
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto",
        )

        if response.usage:
            total_input_tokens += response.usage.prompt_tokens
            total_output_tokens += response.usage.completion_tokens

        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            final_answer = msg.content.strip() if msg.content else final_answer
            break

        for tool_call in msg.tool_calls:
            fn_name = tool_call.function.name
            raw_args = tool_call.function.arguments

            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                result = json.dumps({"error": "Invalid JSON arguments in tool call"})
                args = {}

            tool_start = time.time()
            if fn_name == "lookup":
                result = lookup(args.get("query", ""))
            elif fn_name == "calculate":
                result = calculate(args.get("expression", ""))
            else:
                result = json.dumps({"error": f"Unknown function: {fn_name}"})
            tool_elapsed = time.time() - tool_start

            log_data["tool_calls"].append(
                {
                    "turn": turn + 1,
                    "tool": fn_name,
                    "inputs": args,
                    "result": result,
                    "latency_seconds": round(tool_elapsed, 4),
                }
            )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

    elapsed = time.time() - start_time

    log_data["final_answer"] = final_answer
    log_data["total_seconds"] = round(elapsed, 4)
    with open(f"outputs/{q_id}.json", "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

    meta = {
        "elapsed_seconds": elapsed,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
    }
    return final_answer, meta