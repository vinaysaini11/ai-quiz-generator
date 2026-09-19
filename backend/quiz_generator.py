"""
Quiz Generator Module for AI Quiz Generator.
Constructs structured, source-grounded prompts for Google Gemini,
generates MCQs and Flashcards with source citations, and persists them into SQLite.
"""
import uuid
from typing import Dict, Any, List, Optional
from backend.database import get_db
from backend.gemini_service import gemini_service
from backend.pdf_processor import extract_text_from_pdf
from backend.rag import rag_engine
from backend.quality_guard import filter_and_guard_questions

SYSTEM_INSTRUCTION = """You are an expert university examiner and technical assessment designer.
Your mission is to generate high-quality, rigorous Multiple-Choice Questions (MCQs) and study flashcards
derived EXCLUSIVELY from the provided study material.

MANDATORY RULES:
1. Grounding: All questions, answers, and explanations MUST be directly supported by the source text. Do NOT invent facts or cite external knowledge not present in the text.
2. Source References: Every question and flashcard MUST cite the exact page number where the concept appears (e.g. "Page 2" or "Page 3").
3. Multiple Choice Rules:
   - Exactly 4 options: A, B, C, D.
   - Exactly ONE unambiguously correct answer.
   - Distractors (incorrect choices) must be plausible and technically relevant to the topic, not obvious nonsense.
4. Difficulty Calibration:
   - "easy": Direct definitions, core terminology, and basic concept identification.
   - "medium": Conceptual understanding, mechanics, comparisons, and cause-effect relationships.
   - "hard": Edge cases, trade-off analysis, algorithm outcomes, and anomaly behaviors (e.g. Belady's Anomaly, Convoy Effect).
5. Topic Identification: Group questions into distinct, concise topic categories (e.g. "Process Scheduling", "Virtual Memory", "Deadlocks", "File Systems").
6. Flashcards:
   - Front: Prompt, term, or thought-provoking recall question.
   - Back: Accurate, concise definition or explanation grounded in the text with source page.

OUTPUT FORMAT: Return strictly valid JSON with no markdown fences, matching this exact schema:
{
  "questions": [
    {
      "question": "What is...",
      "options": {
        "A": "Option A text",
        "B": "Option B text",
        "C": "Option C text",
        "D": "Option D text"
      },
      "correct_answer": "A",
      "explanation": "Detailed explanation grounded in the source text...",
      "topic": "Topic Name",
      "difficulty": "medium",
      "source_reference": "Page 2"
    }
  ],
  "flashcards": [
    {
      "front": "Concept or Question",
      "back": "Grounded answer explanation",
      "topic": "Topic Name",
      "source_reference": "Page 2"
    }
  ]
}
"""

BATCH_SIZE = 10

def calculate_batches(total_count: int, batch_size: int = BATCH_SIZE) -> List[int]:
    """
    Calculates a list of batch sizes for a requested total question count.
    Example:
        50 -> [10, 10, 10, 10, 10]
        30 -> [10, 10, 10]
        20 -> [10, 10]
        10 -> [10]
        25 -> [10, 10, 5]
    """
    if total_count <= 0:
        return [batch_size]
    batches = []
    remaining = total_count
    while remaining > 0:
        take = min(batch_size, remaining)
        batches.append(take)
        remaining -= take
    return batches

def generate_quiz_from_document(
    document_id: str,
    num_questions: int = 10,
    difficulty: str = "medium",
    include_flashcards: bool = True
) -> Dict[str, Any]:
    """
    Generates a grounded quiz and flashcard deck from an indexed document using Gemini.
    Implements batch generation (BATCH_SIZE = 10) to safely scale to 10, 20, 30, or 50 questions
    with topic distribution across document sections and cross-batch deduplication.
    """
    # 1. Fetch document from SQLite
    with get_db() as conn:
        doc = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if not doc:
        raise ValueError(f"Document {document_id} not found in database.")

    filepath = doc["filepath"]
    filename = doc["filename"]

    # 2. Extract page-level context
    extraction = extract_text_from_pdf(filepath)
    pages = extraction["pages"]
    total_pages = len(pages)
    if total_pages == 0:
        raise ValueError("The uploaded document has 0 extractable pages.")

    batches = calculate_batches(num_questions, BATCH_SIZE)
    total_batches = len(batches)

    all_guarded_questions: List[Dict[str, Any]] = []
    all_flashcards: List[Dict[str, Any]] = []
    seen_questions: set = set()
    aggregated_quality_report = {
        "total_evaluated": 0,
        "passed": 0,
        "failed": 0,
        "issues": []
    }

    # 3. Generate each batch with topic distribution across pages
    for b_idx, batch_count in enumerate(batches):
        # Distribute document pages across batches to prevent all questions from a single section
        if total_pages > 1 and total_batches > 1:
            start_p = (b_idx * total_pages) // total_batches
            end_p = ((b_idx + 1) * total_pages) // total_batches
            if end_p <= start_p:
                end_p = min(total_pages, start_p + 1)
            batch_pages = pages[start_p:end_p]
        else:
            batch_pages = pages

        batch_context_blocks = []
        for page in batch_pages:
            batch_context_blocks.append(
                f"=== [SOURCE DOCUMENT: {filename} | PAGE {page['page_number']}] ===\n{page['text']}\n"
            )
        batch_context = "\n".join(batch_context_blocks)
        page_focus_str = f"Pages {batch_pages[0]['page_number']} to {batch_pages[-1]['page_number']}"

        flashcards_instruction = ""
        if b_idx == 0 and include_flashcards:
            flashcards_instruction = f" and {min(batch_count, 6)} flashcards"

        prompt = f"""STUDY MATERIAL CONTENT (SECTION FOCUS: {page_focus_str}):
{batch_context}

INSTRUCTIONS:
Generate exactly {batch_count} Multiple-Choice Questions (MCQs){flashcards_instruction} from the study material above.
Target Difficulty: {difficulty.upper()}
Batch Progress: Batch {b_idx + 1} of {total_batches}.

Remember:
- Every question must include topic, difficulty, detailed explanation, and exact page number in 'source_reference'.
- Ground all questions strictly in this section of the text.
- Return strictly valid JSON adhering to the specified schema.
"""
        raw_questions = []
        raw_flashcards = []

        # Batch call with single retry resilience
        for attempt in range(2):
            try:
                ai_response = gemini_service.generate_json(
                    prompt=prompt,
                    system_instruction=SYSTEM_INSTRUCTION
                )
                raw_questions = ai_response.get("questions", [])
                if b_idx == 0 and include_flashcards:
                    raw_flashcards = ai_response.get("flashcards", [])
                if raw_questions:
                    break
            except Exception as e:
                if attempt == 1 and not raw_questions:
                    raise RuntimeError(f"Batch {b_idx + 1} generation failed: {str(e)}")

        if not raw_questions:
            continue

        # AI Quality Guard with cross-batch deduplication
        guarded, q_rep = filter_and_guard_questions(
            raw_questions,
            extraction["full_text"],
            seen_questions=seen_questions
        )
        aggregated_quality_report["total_evaluated"] += q_rep["total_evaluated"]
        aggregated_quality_report["passed"] += q_rep["passed"]
        aggregated_quality_report["failed"] += q_rep["failed"]
        aggregated_quality_report["issues"].extend(q_rep["issues"])

        if not guarded and raw_questions:
            guarded = raw_questions[:batch_count]

        all_guarded_questions.extend(guarded)
        if raw_flashcards and not all_flashcards:
            all_flashcards.extend(raw_flashcards)

    if not all_guarded_questions:
        raise ValueError("Could not generate valid questions from the provided document.")

    # Trim to requested count
    final_questions = all_guarded_questions[:num_questions]

    # 4. Persist Quiz and Questions in SQLite
    quiz_id = f"quiz_{uuid.uuid4().hex[:10]}"

    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO quizzes (id, document_id, difficulty, quiz_type) VALUES (?, ?, ?, ?)",
            (quiz_id, document_id, difficulty, "standard")
        )

        formatted_questions: List[Dict[str, Any]] = []
        for q in final_questions:
            q_id = f"q_{uuid.uuid4().hex[:10]}"
            opts = q.get("options", {})
            correct_opt = str(q.get("correct_answer", "A")).upper().strip()
            if correct_opt not in ["A", "B", "C", "D"]:
                correct_opt = "A"

            opt_a = opts.get("A", "Option A")
            opt_b = opts.get("B", "Option B")
            opt_c = opts.get("C", "Option C")
            opt_d = opts.get("D", "Option D")
            explanation = q.get("explanation", "See study notes.")
            topic = q.get("topic", "General")
            q_diff = q.get("difficulty", difficulty).lower()
            source_ref = q.get("source_reference", f"Page {pages[0]['page_number']}")

            cursor.execute("""
                INSERT INTO questions (
                    id, quiz_id, question_text, option_a, option_b, option_c, option_d,
                    correct_option, explanation, topic, difficulty, source_reference
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                q_id, quiz_id, q.get("question", "Untitled Question"),
                opt_a, opt_b, opt_c, opt_d, correct_opt,
                explanation, topic, q_diff, source_ref
            ))

            formatted_questions.append({
                "id": q_id,
                "question": q.get("question", ""),
                "options": {"A": opt_a, "B": opt_b, "C": opt_c, "D": opt_d},
                "topic": topic,
                "difficulty": q_diff,
                "source_reference": source_ref
            })

        # Save Flashcards
        formatted_flashcards: List[Dict[str, Any]] = []
        for fc in all_flashcards:
            fc_id = f"fc_{uuid.uuid4().hex[:10]}"
            front = fc.get("front", "")
            back = fc.get("back", "")
            fc_topic = fc.get("topic", "General")
            fc_source = fc.get("source_reference", f"Page {pages[0]['page_number']}")

            cursor.execute("""
                INSERT INTO flashcards (id, document_id, front, back, topic, source_reference)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (fc_id, document_id, front, back, fc_topic, fc_source))

            formatted_flashcards.append({
                "id": fc_id,
                "front": front,
                "back": back,
                "topic": fc_topic,
                "source_reference": fc_source
            })

    total_eval = aggregated_quality_report["total_evaluated"]
    pass_cnt = aggregated_quality_report["passed"]
    aggregated_quality_report["pass_rate"] = f"{(pass_cnt / max(total_eval, 1)) * 100:.1f}%"

    return {
        "quiz_id": quiz_id,
        "document_id": document_id,
        "difficulty": difficulty,
        "requested_count": num_questions,
        "questions_count": len(formatted_questions),
        "questions": formatted_questions,
        "flashcards_count": len(formatted_flashcards),
        "flashcards": formatted_flashcards,
        "quality_report": aggregated_quality_report
    }

def generate_targeted_adaptive_quiz(
    document_id: str,
    previous_attempt_id: Optional[str] = None,
    target_topics: Optional[List[str]] = None,
    target_difficulty: str = "medium",
    num_questions: int = 10
) -> Dict[str, Any]:
    """
    Generates a targeted, adaptive quiz focused on detected weak topics and
    previously incorrect concepts, with adjusted difficulty and batching support.
    """
    with get_db() as conn:
        doc = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not doc:
            raise ValueError(f"Document {document_id} not found.")

        # 1. Analyze previous attempt for incorrect concepts
        missed_concepts = []
        if previous_attempt_id:
            wrong_answers = conn.execute("""
                SELECT q.question_text, q.topic, q.explanation
                FROM attempt_answers aa
                JOIN questions q ON aa.question_id = q.id
                WHERE aa.attempt_id = ? AND aa.is_correct = 0
            """, (previous_attempt_id,)).fetchall()
            for wa in wrong_answers:
                missed_concepts.append(f"Topic: {wa['topic']} | Missed Question: {wa['question_text']}")

    # 2. Determine target topics
    topics_to_target = target_topics or []
    if not topics_to_target and missed_concepts:
        topics_to_target = list(set([mc.split("|")[0].replace("Topic:", "").strip() for mc in missed_concepts]))
    
    if not topics_to_target:
        topics_to_target = ["Core Foundations"]

    batches = calculate_batches(num_questions, BATCH_SIZE)
    total_batches = len(batches)

    all_guarded_questions: List[Dict[str, Any]] = []
    seen_questions: set = set()
    aggregated_quality_report = {
        "total_evaluated": 0,
        "passed": 0,
        "failed": 0,
        "issues": []
    }

    missed_context_str = ""
    if missed_concepts:
        missed_context_str = "PREVIOUSLY MISSED CONCEPTS TO TARGET AND REINFORCE:\n" + "\n".join(f"- {mc}" for mc in missed_concepts) + "\n\n"

    # 3. Process each batch
    for b_idx, batch_count in enumerate(batches):
        # Distribute focus topics across batches
        if len(topics_to_target) > 1:
            batch_topic = topics_to_target[b_idx % len(topics_to_target)]
            focus_topics = [batch_topic]
        else:
            focus_topics = topics_to_target

        retrieved_chunks = []
        seen_texts = set()
        for topic in focus_topics:
            chunks = rag_engine.retrieve_relevant_chunks(document_id, query=topic, top_k=3)
            for c in chunks:
                if c["text"] not in seen_texts:
                    seen_texts.add(c["text"])
                    retrieved_chunks.append(f"=== [Page {c['page_number']} - Focus: {topic}] ===\n{c['text']}")

        if not retrieved_chunks:
            all_chunks = rag_engine.get_all_chunks(document_id)
            for c in all_chunks[:3]:
                retrieved_chunks.append(f"=== [Page {c['page_number']}] ===\n{c['text']}")

        context_str = "\n\n".join(retrieved_chunks)

        adaptive_prompt = f"""RELEVANT STUDY MATERIAL EXCERPTS:
{context_str}

{missed_context_str}TARGET LEARNING GOALS:
- Primary Focus Topics: {', '.join(focus_topics)}
- Calibrated Difficulty Level: {target_difficulty.upper()}
- Number of Questions Required: {batch_count}
[Batch {b_idx + 1} of {total_batches}]

INSTRUCTIONS:
Generate a targeted remediation quiz containing {batch_count} Multiple-Choice Questions (MCQs) and 2 flashcards.
The questions MUST focus on the student's weak topics and reinforce the concepts they previously struggled with.
Match the target difficulty of {target_difficulty.upper()}.
Return strictly valid JSON matching the specified schema.
"""
        raw_questions = []
        for attempt in range(2):
            try:
                ai_response = gemini_service.generate_json(
                    prompt=adaptive_prompt,
                    system_instruction=SYSTEM_INSTRUCTION
                )
                raw_questions = ai_response.get("questions", [])
                if raw_questions:
                    break
            except Exception as e:
                if attempt == 1 and not raw_questions:
                    raise RuntimeError(f"Adaptive batch {b_idx + 1} generation failed: {str(e)}")

        if not raw_questions:
            continue

        guarded, q_rep = filter_and_guard_questions(
            raw_questions,
            context_str,
            seen_questions=seen_questions
        )
        aggregated_quality_report["total_evaluated"] += q_rep["total_evaluated"]
        aggregated_quality_report["passed"] += q_rep["passed"]
        aggregated_quality_report["failed"] += q_rep["failed"]
        aggregated_quality_report["issues"].extend(q_rep["issues"])

        if not guarded and raw_questions:
            guarded = raw_questions[:batch_count]

        all_guarded_questions.extend(guarded)

    if not all_guarded_questions:
        raise ValueError("Could not generate valid targeted questions for the requested topics.")

    final_questions = all_guarded_questions[:num_questions]

    # 4. Persist Targeted Quiz in SQLite
    quiz_id = f"quiz_{uuid.uuid4().hex[:10]}"

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO quizzes (id, document_id, difficulty, quiz_type) VALUES (?, ?, ?, ?)",
            (quiz_id, document_id, target_difficulty, "targeted")
        )

        formatted_questions = []
        for q in final_questions:
            q_id = f"q_{uuid.uuid4().hex[:10]}"
            opts = q.get("options", {})
            correct_opt = str(q.get("correct_answer", "A")).upper().strip()
            if correct_opt not in ["A", "B", "C", "D"]:
                correct_opt = "A"

            opt_a = opts.get("A", "Option A")
            opt_b = opts.get("B", "Option B")
            opt_c = opts.get("C", "Option C")
            opt_d = opts.get("D", "Option D")
            explanation = q.get("explanation", "See study notes.")
            topic = q.get("topic", topics_to_target[0])
            q_diff = target_difficulty.lower()
            source_ref = q.get("source_reference", "Study Material")

            cursor.execute("""
                INSERT INTO questions (
                    id, quiz_id, question_text, option_a, option_b, option_c, option_d,
                    correct_option, explanation, topic, difficulty, source_reference
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                q_id, quiz_id, q.get("question", "Untitled Question"),
                opt_a, opt_b, opt_c, opt_d, correct_opt,
                explanation, topic, q_diff, source_ref
            ))

            formatted_questions.append({
                "id": q_id,
                "question": q.get("question", ""),
                "options": {"A": opt_a, "B": opt_b, "C": opt_c, "D": opt_d},
                "topic": topic,
                "difficulty": q_diff,
                "source_reference": source_ref
            })

    total_eval = aggregated_quality_report["total_evaluated"]
    pass_cnt = aggregated_quality_report["passed"]
    aggregated_quality_report["pass_rate"] = f"{(pass_cnt / max(total_eval, 1)) * 100:.1f}%"

    return {
        "quiz_id": quiz_id,
        "document_id": document_id,
        "quiz_type": "targeted",
        "difficulty": target_difficulty,
        "target_topics": topics_to_target,
        "requested_count": num_questions,
        "questions_count": len(formatted_questions),
        "questions": formatted_questions,
        "quality_report": aggregated_quality_report
    }


