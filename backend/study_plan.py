"""
Personalized Study Plan Generator for AI Quiz Generator.
Synthesizes student weak topics, mastery accuracy, and document context
into an actionable, sequenced learning roadmap.
"""
from typing import Dict, Any, Optional
from backend.database import get_db
from backend.gemini_service import gemini_service
from backend.performance import get_cumulative_knowledge_map

STUDY_PLAN_SYSTEM_INSTRUCTION = """You are an elite academic counselor and learning strategist.
Your task is to generate an actionable, highly motivating Personalized Study Plan tailored specifically
to a student's assessed performance on their uploaded study notes.

MANDATORY RULES:
1. Grounding: Tie every study action to concepts actually discussed in the notes.
2. Prioritization: Always place the student's identified Weak and Medium topics first in the study sequence.
3. Concreteness: Provide concrete instructions (e.g. "Review Page 2 section on FIFO vs LRU", "Test recall with 5 targeted flashcards").
4. Return strictly valid JSON with no markdown fences, matching this exact schema:
{
  "summary": "1-sentence assessment of current knowledge state",
  "priority_focus": ["Weak Topic 1", "Weak Topic 2"],
  "study_sequence": [
    {
      "step": 1,
      "topic": "Topic Name",
      "action": "Specific action to take",
      "estimated_minutes": 10,
      "priority": "High"
    }
  ],
  "practice_recommendation": "Specific quiz and flashcard practice routine",
  "total_estimated_time_minutes": 30
}
"""

def generate_study_plan(
    document_id: str,
    attempt_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generates a structured, actionable study plan based on cumulative document mastery
    or specific attempt results.
    """
    km = get_cumulative_knowledge_map(document_id)
    filename = km.get("filename", "Study Notes")
    weak_topics = km.get("weak_topics", [])
    medium_topics = km.get("medium_topics", [])
    strong_topics = km.get("strong_topics", [])
    mastery = km.get("overall_mastery", 0.0)
    total_attempted = km.get("total_questions_attempted", 0)

    # If an attempt_id is supplied, look up specific missed questions
    missed_snippets = []
    if attempt_id:
        with get_db() as conn:
            rows = conn.execute("""
                SELECT q.question_text, q.topic, q.source_reference
                FROM attempt_answers aa
                JOIN questions q ON aa.question_id = q.id
                WHERE aa.attempt_id = ? AND aa.is_correct = 0
            """, (attempt_id,)).fetchall()
            for r in rows:
                missed_snippets.append(f"- {r['topic']}: Missed '{r['question_text']}' (Ref: {r['source_reference']})")

    missed_text = "\n".join(missed_snippets) if missed_snippets else "None specifically identified."

    prompt = f"""STUDENT PERFORMANCE PROFILE:
- Document: {filename}
- Total Questions Attempted: {total_attempted}
- Overall Cumulative Mastery: {mastery}%
- Identified Weak Topics (Critical): {', '.join(weak_topics) if weak_topics else 'None (<50%)'}
- Medium Topics (Needs Reinforcement): {', '.join(medium_topics) if medium_topics else 'None'}
- Strong Topics (Mastered): {', '.join(strong_topics) if strong_topics else 'None'}

RECENTLY MISSED QUESTIONS:
{missed_text}

INSTRUCTION:
Create a high-impact, personalized 3-step study plan to help this student bridge their gaps
and achieve 100% mastery on this material.
Return strictly valid JSON following the schema.
"""

    ai_response = gemini_service.generate_json(
        prompt=prompt,
        system_instruction=STUDY_PLAN_SYSTEM_INSTRUCTION
    )

    return {
        "document_id": document_id,
        "filename": filename,
        "overall_mastery": mastery,
        "plan": ai_response
    }

