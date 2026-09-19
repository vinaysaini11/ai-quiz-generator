"""
Teach Me This (Micro-Tutor) Module for AI Quiz Generator.
Provides source-grounded remediation when a student answers incorrectly:
- Intuitive explanation
- Core mental model / key idea
- Document-grounded example
- Interactive quick-check question
"""
from typing import Dict, Any, Optional
from backend.database import get_db
from backend.gemini_service import gemini_service
from backend.rag import rag_engine

TEACH_ME_SYSTEM_INSTRUCTION = """You are a warm, encouraging university professor and master tutor.
A student answered a quiz question incorrectly and requested help understanding the underlying concept.

MANDATORY RULES:
1. Grounding: Your explanation, example, and quick check question MUST be strictly supported by the provided study material. Do NOT invent outside facts.
2. Tone: Clear, accessible, encouraging, and intuitive. Avoid dense jargon without explaining it.
3. Structure:
   - "explanation": 2-3 clear sentences breaking down why the concept works the way it does.
   - "key_idea": Exactly 1 crisp takeaway sentence capturing the core mental model.
   - "example": A realistic, concrete example or scenario directly derived from the source notes.
   - "source_reference": Explicit page citation (e.g. "Page 2").
   - "quick_check": A fresh, single-sentence verification question with 4 options to test immediate recall.

OUTPUT FORMAT: Return strictly valid JSON with no markdown fences, matching this schema:
{
  "concept": "Title of the Concept",
  "explanation": "Clear breakdown...",
  "key_idea": "Core mental model takeaway...",
  "example": "Source example...",
  "source_reference": "Page 2",
  "quick_check": {
    "question": "Quick comprehension check question?",
    "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
    "correct_answer": "Option 1"
  }
}
"""

def teach_concept(
    document_id: str,
    question_id: str,
    user_answer: Optional[str] = None,
    topic: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generates a personalized micro-lesson grounded in source document text
    addressing the student's specific mistake.
    """
    with get_db() as conn:
        q_row = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
        if not q_row:
            raise ValueError(f"Question {question_id} not found.")

    question_text = q_row["question_text"]
    correct_opt = q_row["correct_option"]
    concept_topic = topic or q_row["topic"] or "Core Concept"
    existing_source = q_row["source_reference"] or "Study Material"

    # 1. Retrieve relevant source paragraphs from ChromaDB
    search_query = f"{concept_topic} {question_text}"
    retrieved_chunks = rag_engine.retrieve_relevant_chunks(document_id, query=search_query, top_k=2)

    if not retrieved_chunks:
        # Fallback to all chunks
        retrieved_chunks = rag_engine.get_all_chunks(document_id)[:2]

    context_parts = []
    source_page = existing_source
    for c in retrieved_chunks:
        context_parts.append(f"=== [SOURCE EXCERPT (Page {c['page_number']})] ===\n{c['text']}")
        source_page = f"Page {c['page_number']}"

    context_str = "\n\n".join(context_parts)

    options_dict = {
        "A": q_row["option_a"],
        "B": q_row["option_b"],
        "C": q_row["option_c"],
        "D": q_row["option_d"]
    }
    user_selected_text = options_dict.get(user_answer, user_answer or "None")
    correct_answer_text = options_dict.get(correct_opt, correct_opt)

    # 2. Build prompt
    prompt = f"""RELEVANT STUDY MATERIAL EXCERPT:
{context_str}

STUDENT'S ASSESSMENT CONTEXT:
- Topic: {concept_topic}
- Question Asked: {question_text}
- Student Selected (Incorrect): {user_answer} ({user_selected_text})
- Correct Option: {correct_opt} ({correct_answer_text})
- Reference: {existing_source}

INSTRUCTION:
Teach the student this concept clearly. Address the misunderstanding and explain why {correct_opt} is the correct answer
based on the provided text. Provide a 1-sentence key idea, an example, and an interactive quick check question.
Return strictly valid JSON.
"""

    ai_response = gemini_service.generate_json(
        prompt=prompt,
        system_instruction=TEACH_ME_SYSTEM_INSTRUCTION
    )

    # Attach fallback source reference if omitted
    if "source_reference" not in ai_response or not ai_response["source_reference"]:
        ai_response["source_reference"] = source_page

    return ai_response

