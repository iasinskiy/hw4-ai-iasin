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

<!-- what changed in your plan, and why. "None" is an answer too. -->

### B2 — Tests

```text
<!-- pytest output -->
```

### B3 — The loop

- Round limit, and why:
- Where the logs are:
- Real Q-09 conversation compared with my A3 version, what is different:

### B4 — Three strategies

**What I kept the same:**

<!-- model, temperature, k, prompts, answer format, anything else -->

**My rule for a correct answer** (written before the first full run):

| Run | Strategy | Correct /20 | Unanswered | Input tokens | Output tokens | Median seconds per question | Total seconds | Cost ($) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 direct | | | | | | | |
| 1 | S2 think and vote (k = ) | | | | | | | |
| 1 | S3 tools | | | | | | | |
| 2 | S1 direct | | | | | | | |
| 2 | S2 think and vote (k = ) | | | | | | | |
| 2 | S3 tools | | | | | | | |

**Per question (run 1):**

| Question | S1 | S2 | S3 |
|---|:---:|:---:|:---:|
| Q-01 | | | |
| Q-02 | | | |
| Q-03 | | | |
| Q-04 | | | |
| Q-05 | | | |
| Q-06 | | | |
| Q-07 | | | |
| Q-08 | | | |
| Q-09 | | | |
| Q-10 | | | |
| Q-11 | | | |
| Q-12 | | | |
| Q-13 | | | |
| Q-14 | | | |
| Q-15 | | | |
| Q-16 | | | |
| Q-17 | | | |
| Q-18 | | | |
| Q-19 | | | |
| Q-20 | | | |

---

## Part C — Explain and choose (Hard)

### C1 — Does the tool description matter?

| Question | Calls (your description) | Calls (vague) | Answer (yours) | Answer (vague) |
|---|---:|---:|---|---|
| | | | | |

### C2 — Three mistakes explained

### C3 — Which strategy I would use, and what would change it

### C4 — How sure I can be

### Final questions

1.
2.
3.
4.
5.
6.
7.
8.
