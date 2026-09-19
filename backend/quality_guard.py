"""
AI Quality Guard Module for AI Quiz Generator.
Performs programmatic validation on generated questions before persistence:
- 4 distinct options check (detects duplicate/degenerate choices)
- Single valid answer check
- Question clarity and minimum length
- Lexical source grounding check (anchored to source document text)
- Duplicate question detection
"""
import re
from typing import List, Dict, Any, Tuple, Optional

class QualityGuardReport:
    def __init__(self):
        self.total_evaluated = 0
        self.passed_count = 0
        self.failed_count = 0
        self.issues: List[Dict[str, Any]] = []

    def add_issue(self, question_idx: int, question_text: str, reason: str):
        self.failed_count += 1
        self.issues.append({
            "index": question_idx,
            "question": question_text[:60] + "..." if len(question_text) > 60 else question_text,
            "reason": reason
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_evaluated": self.total_evaluated,
            "passed": self.passed_count,
            "failed": self.failed_count,
            "pass_rate": f"{(self.passed_count / max(self.total_evaluated, 1)) * 100:.1f}%",
            "issues": self.issues
        }

def validate_question(
    q: Dict[str, Any],
    source_text_lower: str,
    seen_question_texts: set
) -> Tuple[bool, str]:
    """
    Validates a single question against quality and grounding invariants.
    Returns: (is_valid: bool, failure_reason: str)
    """
    # 1. Question text validation
    q_text = str(q.get("question", "")).strip()
    if not q_text or len(q_text) < 15:
        return False, "Question text is too short or empty."

    # Deduplication check
    normalized_q = re.sub(r"[^a-z0-9]", "", q_text.lower())
    if normalized_q in seen_question_texts:
        return False, "Duplicate question detected in the generated batch."

    # 2. Options validation
    options = q.get("options", {})
    if not isinstance(options, dict):
        return False, "Options must be a key-value dictionary."

    required_keys = {"A", "B", "C", "D"}
    if set(options.keys()) != required_keys:
        return False, f"Options must contain exactly keys A, B, C, D. Got: {list(options.keys())}"

    # Check for non-empty and distinct option texts
    option_texts = [str(opt).strip().lower() for opt in options.values()]
    for opt_txt in option_texts:
        if not opt_txt:
            return False, "Empty option text found."

    if len(set(option_texts)) < 4:
        return False, "Duplicate options found (all 4 options must be distinct)."

    # 3. Correct answer validation
    correct_ans = str(q.get("correct_answer", "")).upper().strip()
    if correct_ans not in required_keys:
        return False, f"Correct answer '{correct_ans}' is invalid; must be one of A, B, C, D."

    # 4. Explanation check
    explanation = str(q.get("explanation", "")).strip()
    if not explanation or len(explanation) < 10:
        return False, "Explanation is missing or too brief."

    # 5. Grounding check against source text
    # Extract significant alphanumeric keywords from question and correct option
    words = re.findall(r"\b[a-zA-Z]{4,}\b", q_text.lower())
    correct_opt_text = options[correct_ans].lower()
    words.extend(re.findall(r"\b[a-zA-Z]{4,}\b", correct_opt_text))

    if words and source_text_lower:
        matched_words = [w for w in set(words) if w in source_text_lower]
        # At least 2 significant words must exist in source text
        if len(matched_words) < min(2, len(set(words))):
            return False, "Question contains terms not grounded in the uploaded study material."

    return True, "Valid"

def filter_and_guard_questions(
    questions: List[Dict[str, Any]],
    source_text: str,
    seen_questions: Optional[set] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Evaluates a batch of generated questions through the AI Quality Guard.
    Discards invalid or hallucinated questions and returns valid questions + report.
    Accepts an optional seen_questions set to enforce deduplication across multiple batches.
    """
    report = QualityGuardReport()
    report.total_evaluated = len(questions)

    valid_questions: List[Dict[str, Any]] = []
    if seen_questions is None:
        seen_questions = set()
    source_lower = source_text.lower() if source_text else ""

    for idx, q in enumerate(questions):
        is_valid, reason = validate_question(q, source_lower, seen_questions)
        if is_valid:
            normalized_q = re.sub(r"[^a-z0-9]", "", str(q.get("question", "")).lower())
            seen_questions.add(normalized_q)
            valid_questions.append(q)
            report.passed_count += 1
        else:
            report.add_issue(idx + 1, str(q.get("question", "")), reason)

    return valid_questions, report.to_dict()

