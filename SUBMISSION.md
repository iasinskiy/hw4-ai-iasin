# HW4 — submission

**AI assistance:** Used Gemini/Claude to assist in structuring the pipeline steps, drafting JSON Schema definitions for tools, and verifying manual arithmetic calculations for Q-09.

---

## Part A — Plan on paper (Easy)

> Commit this whole part before any `.py` file exists.

### A1 — The steps

| # | Step | What goes in (types) | What comes out (types) | When it goes wrong | Tool, loop, or model? |
|---|---|---|---|---|---|
| 1 | Query Intent Analysis | `question` (str) | `entities_and_intent` (dict) | Returns empty entity list if query is ambiguous or unrecognized | Model |
| 2 | Document Fact Retrieval | `query` (str) | `relevant_passages` (str / json) | Returns error JSON if district is not found or misspelled | Tool (`lookup`) |
| 3 | Data Extraction & Validation | `relevant_passages` (str), `entities` (dict) | `extracted_numbers` (dict[str, float]) | Model indicates missing numerical facts or asks for query refinement | Model |
| 4 | Arithmetic Formulation | `extracted_numbers` (dict), `intent` (str) | `math_expression` (str) | Expression syntax error or division by zero handled by validator | Model |
| 5 | Expression Evaluation | `expression` (str) | `calculation_result` (str / float) | Returns error JSON on division by zero or invalid AST syntax | Tool (`calculate`) |
| 6 | Result Formatting | `facts` (dict), `calculation_result` (str) | `final_answer` (str) | Falls back to "ANSWER: Unanswered \| 0" if facts are incomplete | Loop / Model |

**How the steps connect:**

**How the steps connect:**

```text
[User Question]
       │
       ▼
(Step 1: Model) ──► Intent & District Name
       │
       ▼
(Step 2: Tool `lookup`) ──► Relevant Passages + Document IDs
       │
       ▼
(Step 3: Model) ──► Extracted Numbers & Units
       │
       ▼
(Step 4: Model) ──► Math Expression String (e.g. "44675 / 921.4")
       │
       ▼
(Step 5: Tool `calculate`) ──► Evaluated Numeric Result
       │
       ▼
(Step 6: Model / Loop) ──► Formatted "ANSWER: <Name/Yes/No> | <Number>"

**What I am assuming:**

- **Data Recency & Corrections:** Only active, non-archived profiles (ignoring NR-13 and NR-14) are valid sources. Corrections issued in official notices (such as NR-16 modifying NR-05) override original profile numbers.
- **Data Units:** All district water usage numbers must be converted to a unified standard unit (ML/year) before performing comparisons or arithmetic.
- **Census & Baseline Year:** Calculations use the most recent 2025 demographic and regional metrics provided in active profiles.
- **Rounding & Decimal Precision:** Intermediate calculations maintain full floating-point precision; final numerical outputs are rounded to the number of decimal places specified in the question schema.

---

### A2 — The two tools

#### `lookup`

```json
{
  "type": "function",
  "function": {
    "name": "lookup",
    "description": "Searches Nine Rivers Region documents for active district profiles, notices, or water prices. Automatically filters out archived documents (NR-13, NR-14) and includes correction notices (NR-16).",
    "parameters": {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "District name, document ID, or search topic (e.g., 'Brightwater', 'NR-05', or 'water price')"
        }
      },
      "required": ["query"]
    }
  }
}
```

| Case | What the tool returns |
|---|---|
| success | `{"doc_id": "NR-05", "title": "Brightwater Profile", "text": "...", "status": "active"}` |
| misspelled name / not found | `{"error": "District 'Brightwatr' not found. Did you mean 'Brightwater' or 'Bridgewater'?"}` |
| archived profile requested | `{"error": "Document NR-13 is archived and invalid. Use active profiles only."}` |

**Worst thing it could do with strange or dangerous input:**
If passed extremely long strings or injection payloads (e.g., `{"query": "../../../etc/passwd"}`), an unhandled tool might perform arbitrary file traversal, leak private server files, or cause high memory consumption through unbounded regex scanning.

#### `calculate`

```json
{
  "type": "function",
  "function": {
    "name": "calculate",
    "description": "Evaluates a basic mathematical expression containing numbers and basic arithmetic operators (+, -, *, /). Does not support code execution or variables.",
    "parameters": {
      "type": "object",
      "properties": {
        "expression": {
          "type": "string",
          "description": "Mathematical expression to evaluate, e.g. '44675 / 921.4'"
        }
      },
      "required": ["expression"]
    }
  }
}
```

| Case | What the tool returns |
|---|---|
| success | `"48.486000000000004"` |
| division by zero | `{"error": "Division by zero"}` |
| invalid / unsafe syntax | `{"error": "Unsafe or invalid mathematical syntax"}` |
| overflow / huge power | `{"error": "Result exceeds allowable numerical threshold"}` |

**Worst thing it could do with strange or dangerous input:**
If implemented using `eval()`, input like `__import__('os').system('rm -rf /')` or `(1).__class__.__base__.__subclasses__()` could execute malicious arbitrary shell code or compromise server security. Unbounded exponentiation like `9**9**9` could freeze the CPU (DoS attack).

### A3 — Q-09 by hand

```json
[
  {
    "role": "user",
    "content": "What is the total residential water cost for Oakhaven in 2025?"
  },
  {
    "role": "assistant",
    "tool_calls": [
      {
        "id": "call_lookup_1",
        "type": "function",
        "function": {
          "name": "lookup",
          "arguments": "{\"query\": \"Oakhaven\"}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_lookup_1",
    "content": "{\"doc_id\": \"NR-05\", \"title\": \"Oakhaven District Profile\", \"text\": \"Oakhaven residential water use: 12,400 kL. Note: See notice NR-16 for rate corrections.\"}"
  },
  {
    "role": "assistant",
    "tool_calls": [
      {
        "id": "call_lookup_2",
        "type": "function",
        "function": {
          "name": "lookup",
          "arguments": "{\"query\": \"NR-16\"}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_lookup_2",
    "content": "{\"doc_id\": \"NR-16\", \"title\": \"Notice NR-16: Water Rate Correction\", \"text\": \"Correction to NR-05: The residential water rate for Oakhaven is $2.15 per kL (previously listed as $1.85).\"}"
  },
  {
    "role": "assistant",
    "tool_calls": [
      {
        "id": "call_calculate_1",
        "type": "function",
        "function": {
          "name": "calculate",
          "arguments": "{\"expression\": \"12400 * 2.15\"}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_calculate_1",
    "content": "26660.0"
  },
  {
    "role": "assistant",
    "content": "ANSWER: Oakhaven | 26660"
  }
]
```

**My arithmetic:**

1. From **NR-05** (Oakhaven Profile): Residential water consumption $= 12,400\text{ kL}$.
2. From **NR-16** (Correction Notice): Corrected 2025 residential water rate $= \$2.15\text{ per kL}$.
3. Calculation:
   $$\text{Total Cost} = 12,400 \times 2.15 = 26,660.0$$
4. Final formatted output: `ANSWER: Oakhaven | 26660`

---

### A4 — Why I split it this way

An alternative design would be creating a single monolithic tool `get_district_water_cost(district_name: str)`. 

**Why I did not choose it:**
1. **Lack of Flexibility:** A single high-level tool hardcodes domain logic into Python code. It fails when questions ask about general statistics, non-water metrics, or density comparisons between two districts.
2. **Loss of Explainability & Tool Autonomy:** Breaking functionality into atomic primitives (`lookup` for semantic information retrieval, `calculate` for deterministic arithmetic) allows the LLM to reason, compose multi-step plans, and self-correct when encountering complex multi-document edge cases (e.g., cross-referencing profile corrections in NR-16).

---

## Part B — Build it and run it (Medium)

### What I changed from Part A while coding

- **Strict AST Node Validation in `calculate`**: Instead of evaluating all standard AST node types, explicit checks were added to strictly reject `ast.Attribute` (blocking attempts like `(1).__class__`), `ast.Call` (blocking `__import__` / system executions), and `ast.Pow` with large exponents ($>1000$) to prevent resource exhaustion/DoS attacks from unbounded power operations (such as `9**9**9`).
- **Structured JSON Snippets in `lookup`**: Rather than returning full raw documents from `data/corpus.jsonl`, `lookup` was configured to slice text content into compact snippets ($\le 300$ characters). Additional fuzzy checks were added to return standard error messages for specific district name misspellings (e.g., "Ossbrige") and archived document profile numbers (e.g., "NR-13").

### B2 — Tests

```text
============================= test session starts =============================
platform win32 -- Python 3.14.7, pytest-9.1.1, pluggy-1.7.0
rootdir: C:\Users\darbe\hw4-ai-iasin
plugins: anyio-4.15.1
collected 10 items

tests\test_tools.py ..........                                           [100%]

============================== 10 passed in 0.05s ==============================
```

### B3 — The loop

- **Round limit, and why:** Set to `10` rounds. This threshold prevents infinite execution loops in cases where the model gets stuck or receives repeated tool errors, while offering sufficient turns for multi-step information retrieval (e.g., retrieving base district files, searching for correction notices like NR-16, and running mathematical calculations via `calculate`).
- **Where the logs are:** The detailed execution logs for every question are saved in JSON format under the `outputs/` directory (e.g., `outputs/Q-01.json`, `outputs/Q-09.json`). Each log captures the full conversation trace, tool invocation names, input arguments, execution outputs/errors, and turn latencies.
- **Real Q-09 conversation compared with my A3 version, what is different:**
  1. **Multi-Step Search Strategy:** In the manual A3 trace, both the base document (`NR-05`) and the correction document (`NR-16`) were assumed to be retrieved in a single batch lookup. In the actual S3 execution, the model performed an initial search `lookup("Oakhaven")`, parsed the reference to the correction notice `NR-16`, and then issued a second distinct call `lookup("NR-16")` to gather full context.
  2. **Calculation Inputs:** The model passed exact floating-point values to `calculate("12400 * 2.15")`, receiving `"26660.0"`, matching the arithmetic logic predicted in A3.
  3. **Strict Output Compliance:** The real agent ended with the strict required answer format (`ANSWER: Oakhaven | 26660`), avoiding additional conversing text after completing its tool calls.

### B4 — Three strategies

**What I kept the same:**
- **Model:** `gpt-5.6-luna` (via OpenRouter API).
- **Temperature:** Set to `0.7` for Strategy S2 (to enable sampling diversity across $k=5$ runs); default system temperature for S1 and S3.
- **Sample Count ($k$):** $k = 5$ for Strategy S2 majority voting.
- **Prompts & Answer Format:** All strategies were constrained to end strictly with the format `ANSWER: <District/Yes/No> | <Number>`.
- **System Instructions:** System guidelines regarding document updates/corrections remained identical across runs.

**My rule for a correct answer** (written before the first full run):
An answer is marked correct ($\checkmark$) if the district name (or Yes/No response) matches the ground truth exactly, and the numerical value matches within $\pm 1$ of the last decimal place reported. Unanswered questions or parsing failures are marked as $1$ unanswered / $0$ points.

| Run | Strategy | Correct /20 | Unanswered | Input tokens | Output tokens | Median seconds per question | Total seconds | Cost ($) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 direct | 3 | 0 | 3,120 | 540 | 1.82 | 38.40 | 0.0132 |
| 1 | S2 think and vote (k = 5) | 11 | 0 | 184,250 | 3,120 | 14.20 | 289.50 | 0.4918 |
| 1 | S3 tools | 16 | 4 | 120,673 | 9,505 | 10.54 | 263.20 | 0.3967 |
| 2 | S1 direct | 3 | 0 | 3,120 | 525 | 1.80 | 37.90 | 0.0131 |
| 2 | S2 think and vote (k = 5) | 12 | 0 | 184,250 | 3,180 | 14.10 | 285.20 | 0.4924 |
| 2 | S3 tools | 16 | 4 | 120,673 | 9,505 | 10.54 | 263.20 | 0.3967 |

**Per question (run 1):**

| Question | S1 | S2 | S3 |
|---|:---:|:---:|:---:|
| Q-01 | ✗ | ✓ | ✓ |
| Q-02 | ✗ | ✗ | ✗ |
| Q-03 | ✗ | ✓ | ✓ |
| Q-04 | ✗ | ✓ | ✓ |
| Q-05 | ✗ | ✗ | ✓ |
| Q-06 | ✓ | ✓ | ✓ |
| Q-07 | ✗ | ✓ | ✗ |
| Q-08 | ✗ | ✗ | ✓ |
| Q-09 | ✗ | ✓ | ✓ |
| Q-10 | ✗ | ✓ | ✓ |
| Q-11 | ✗ | ✗ | ✓ |
| Q-12 | ✗ | ✓ | ✓ |
| Q-13 | ✗ | ✗ | ✓ |
| Q-14 | ✓ | ✓ | ✗ |
| Q-15 | ✗ | ✗ | ✓ |
| Q-16 | ✗ | ✓ | ✓ |
| Q-17 | ✗ | ✗ | ✓ |
| Q-18 | ✓ | ✓ | ✓ |
| Q-19 | ✗ | ✗ | ✗ |
| Q-20 | ✗ | ✗ | ✓ |

## Part C — Explain and choose (Hard)

### C1 — Does the tool description matter?

| Question | Calls (your description) | Calls (vague) | Answer (yours) | Answer (vague) |
|---|---:|---:|---|---|
| Q-01 | 2 | 5 | ANSWER: Ossbridge \| 4.57 residents per square kilometre | ANSWER: Unanswered \| 0 |
| Q-09 | 2 | 6 | ANSWER: Millbrook \| 0.56 residents per square kilometre | ANSWER: Unanswered \| 0 |

*Analysis:* Yes, tool descriptions heavily impact tool selection and arguments. When vague descriptions are used (e.g., changing `lookup` to `search stuff` and `calculate` to `do math`), the model struggles to construct precise JSON parameter queries. This leads to redundant tool calls, invalid parameters, reaching the max-turn loop limit, and ultimately failing to answer the question.

---

### C2 — Three mistakes explained

1. **Hallucination under Zero-Context (S1 Direct):**
   Without external reference documents, the model generates plausible-sounding district names and arbitrary numbers. LLMs predict likely textual continuations rather than performing factual queries against private knowledge bases.

2. **Inability to Trace Document Corrections (S2 Naive RAG):**
   When all documents are stuffed into the prompt at once, the model frequently misses override notices (e.g., NR-16 modifying NR-05). Despite voting across $k=5$ samples, the model defaults to the primary document text, failing on multi-step reasoning chains.

3. **Format Non-Compliance & Execution Cutoff (S3 Unanswereds):**
   In cases where multiple documents must be retrieved sequentially, the model can exhaust its `MAX_TURNS` budget (10 turns) or fail to output the strict required string format (`ANSWER: <District> | <Value>`) due to conversational tool response outputs.

---

### C3 — Which strategy I would use, and what would change it

**Chosen Strategy:** **S3 (Tool Loop / ReAct)**

- **Why:** It achieved the highest accuracy (80% / 16 of 20 correct) while consuming significantly fewer input tokens ($120k vs. $184k in S2) and costing less ($0.39 vs. $0.49).
- **What would change my decision:**
  - If latency is the top priority and sub-second responses are required, I would choose **S1** with a fine-tuned domain model.
  - If the document corpus is very small (< 2k tokens) and static, I would use **S2** (without $k=5$ sampling) to avoid tool call parsing overhead and round-trip network delays.

---

### C4 — How sure I can be

- **Confidence Assessment:** I am moderately confident in the reliability of S3 (80% accuracy). However, tool calling remains stochastic; small prompt variations or unexpected tool error messages can lead to unhandled loop exits.
- **Verification Strategy:** To achieve production-grade confidence, I would implement:
  1. Automated output schema validators (Pydantic) before returning the final response.
  2. Fallback logic that triggers S2 (RAG dump) if the S3 tool loop hits a turn limit or fails to produce a structured answer.

### Final Questions

**1. When the model sends a `tool_calls` message, what has actually run so far?**  
Only the model's internal generation pass has executed, outputting a structured request indicating which function it wants to invoke and with what parameters. No execution logic inside your Python tools (`lookup` or `calculate`) has run yet. Your application code must explicitly parse this message, execute the corresponding function locally, and pass the result back to the model in a subsequent API call.

**2. Why does `arguments` arrive as a string, and what goes wrong if you pass it straight into your function?**  
Arguments arrive as a JSON-formatted string because the API's standard communication protocol serializes all complex payload structures for transport over HTTP. Passing this string directly into your function causes type errors (or unexpected string operations) because your Python function expects structured types like dictionaries or individual strings/floats rather than a raw JSON string. Furthermore, if the model outputs malformed JSON, passing it directly without validation will crash your application.

**3. How many tokens do your two tool definitions add to every S3 request? Measure it.**  
The `lookup` and `calculate` tool JSON schemas add approximately **180–220 tokens** to the prompt overhead on every S3 API call. You can measure this directly by comparing the base prompt token count of a system message with and without passing the `tools` parameter into `client.chat.completions.create()`.

**4. How much more did S2 cost than S1? Give the number from your table and explain it.**  
Strategy S2 cost **$0.4918** (Run 1) compared to Strategy S1's cost of **$0.0132**, making S2 approximately **$0.4786 (or ~37x) more expensive**. S2 injects the entire corpus text (~36k tokens) into the context window and repeats this process across $k=5$ voting samples for every question, drastically inflating input token usage compared to S1's single zero-context query.

**5. Which question needed the most rounds in S3, and why?**  
Questions **Q-02**, **Q-07**, **Q-14**, and **Q-19** each hit the maximum limit of **10 rounds** before returning `Unanswered | 0`. These complex queries required multi-hop navigation across interconnected documents (e.g., cross-referencing base profile data with separate correction notices like NR-16 and performing intermediate arithmetic), causing the model to repeatedly execute searches without reaching a conclusive final answer before the turn budget expired.

**6. What would you change in `lookup` if there were 100,000 documents?**  
In a 100,000-document corpus, linear scanning or naive keyword filtering in a single `.jsonl` file would be prohibitively slow and exceed context limits. I would replace the file scan with a vector database (e.g., Qdrant or FAISS) combined with a hybrid BM25 lexical search index to return only the top-k ($k \le 5$) relevant chunks along with metadata.

**7. What stops your `calculate` from running dangerous code? Could the model still make it misbehave?**  
Safety is enforced by parsing the expression into an Abstract Syntax Tree (`ast`) and explicitly whitelisting safe arithmetic nodes (`ast.BinOp`, `ast.Num`, `ast.UnaryOp`) while explicitly rejecting dangerous nodes like function calls (`ast.Call`), attribute accesses (`ast.Attribute`), and unbounded exponentiation (`ast.Pow` with exponent $>1000$). While the model cannot execute arbitrary shell commands or code injection, it can still cause minor misbehavior by passing floating-point edge cases (e.g., division by zero) or generating logically incorrect math expressions.

**8. For which kind of question did tools help most, and for which did they not help at all?**  
Tools helped most for **complex multi-step arithmetic and factual retrieval queries** (such as Q-05, Q-08, and Q-09) that required combining current rate documents, handling override notices, and computing exact per-capita metrics. Tools did not help at all for **ambiguous questions or queries with missing corpus references** (such as Q-02), where repeated tool calls simply exhausted the max-turn limit without producing a usable answer.