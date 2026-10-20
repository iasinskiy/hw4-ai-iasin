import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List
from strategies import run_strategy_s1, run_strategy_s2, run_strategy_s3

# Тарифы модели gpt-5.6-luna (условные или стандартные для сметы)
COST_PER_1K_INPUT = 0.0025
COST_PER_1K_OUTPUT = 0.0100


def compute_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens / 1000.0) * COST_PER_1K_INPUT + (
        output_tokens / 1000.0
    ) * COST_PER_1K_OUTPUT


def run_experiment(questions: List[Dict[str, Any]], strategy: str):
    results = []
    total_input = 0
    total_output = 0
    total_time = 0.0
    times = []

    print(f"\n--- Running Strategy: {strategy.upper()} on {len(questions)} questions ---")

    for idx, q in enumerate(questions, 1):
        q_id = q.get("id", f"Q-{idx:02d}")
        q_text = q.get("question")

        if strategy == "s1":
            ans, meta = run_strategy_s1(q_text)
        elif strategy == "s2":
            ans, meta = run_strategy_s2(q_text, k=5)
        elif strategy == "s3":
            ans, meta = run_strategy_s3(q_text, q_id=q_id)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

        elapsed = meta["elapsed_seconds"]
        inp = meta["input_tokens"]
        outp = meta["output_tokens"]

        total_input += inp
        total_output += outp
        total_time += elapsed
        times.append(elapsed)

        print(
            f"[{q_id}] Time: {elapsed:.2f}s | In: {inp} | Out: {outp}\n  Result: {ans}"
        )

        results.append(
            {
                "id": q_id,
                "answer": ans,
                "time": elapsed,
                "input_tokens": inp,
                "output_tokens": outp,
            }
        )

    times.sort()
    median_time = times[len(times) // 2] if times else 0.0
    cost = compute_cost(total_input, total_output)

    print("\n" + "=" * 50)
    print(f"Summary for {strategy.upper()}:")
    print(f"Total Input Tokens:  {total_input}")
    print(f"Total Output Tokens: {total_output}")
    print(f"Median Time / Q:     {median_time:.2f}s")
    print(f"Total Time:          {total_time:.2f}s")
    print(f"Estimated Cost:      ${cost:.4f}")
    print("=" * 50 + "\n")

    return {
        "strategy": strategy,
        "results": results,
        "total_input": total_input,
        "total_output": total_output,
        "median_time": median_time,
        "total_time": total_time,
        "cost": cost,
    }


def main():
    questions_file = "data/questions.json"
    if not Path(questions_file).exists():
        questions_file = "questions.json"

    if not Path(questions_file).exists():
        print(f"Error: {questions_file} not found.")
        sys.exit(1)

    with open(questions_file, "r", encoding="utf-8") as f:
        questions = json.load(f)

    if len(sys.argv) > 1:
        strategy = sys.argv[1].lower()
        run_experiment(questions, strategy)
    else:
        print("Usage: python run.py <s1|s2|s3>")


if __name__ == "__main__":
    main()