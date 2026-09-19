"""
Performance Analytics & Weak Topic Detection Module for AI Quiz Generator.
Evaluates student answers, records attempts atomically in SQLite,
computes topic & difficulty performance, and detects weak topics using configurable thresholds.
"""
import uuid
from typing import List, Dict, Any, Tuple
from backend.database import get_db

# Configurable Mastery Thresholds (easy to tune or interview-explain)
STRONG_THRESHOLD = 75.0   # >= 75% indicates Mastery
MEDIUM_THRESHOLD = 50.0   # 50% - 74.9% indicates Needs Reinforcement
                          # < 50% indicates Critical Weakness

class QuizGradingError(Exception):
    """Custom exception for quiz grading errors."""
    pass

def classify_topic_mastery(accuracy: float) -> Tuple[str, str]:
    """
    Classifies mastery level and emoji badge based on accuracy percentage.
    Returns: (status_label, badge_icon)
    """
    if accuracy >= STRONG_THRESHOLD:
        return "Strong", "🟢"
    elif accuracy >= MEDIUM_THRESHOLD:
        return "Medium", "🟡"
    else:
        return "Weak", "🔴"

def detect_weak_topics(topic_breakdown: Dict[str, Dict[str, Any]]) -> List[str]:
    """
    Analyzes topic breakdown and returns prioritized list of weak topics
    sorted by lowest accuracy and highest error count.
    """
    weak_candidates = []
    medium_candidates = []

    for topic, stats in topic_breakdown.items():
        acc = stats["accuracy"]
        errors = stats["total"] - stats["correct"]
        if acc < MEDIUM_THRESHOLD:
            weak_candidates.append((topic, acc, errors))
        elif acc < STRONG_THRESHOLD:
            medium_candidates.append((topic, acc, errors))

    # Sort weak candidates by lowest accuracy, then highest errors
    weak_candidates.sort(key=lambda x: (x[1], -x[2]))
    medium_candidates.sort(key=lambda x: (x[1], -x[2]))

    # Prioritize critical weak topics; if none, suggest medium topics
    if weak_candidates:
        return [item[0] for item in weak_candidates]
    elif medium_candidates:
        return [item[0] for item in medium_candidates]
    return []

def determine_adaptive_difficulty(accuracy: float) -> str:
    """
    Recommends next quiz difficulty based on student performance:
    - High accuracy (>= 75%): Increase difficulty to 'hard'
    - Medium accuracy (50% - 74%): Maintain difficulty at 'medium'
    - Low accuracy (< 50%): Reduce difficulty to 'easy' + provide more foundational practice
    """
    if accuracy >= STRONG_THRESHOLD:
        return "hard"
    elif accuracy >= MEDIUM_THRESHOLD:
        return "medium"
    else:
        return "easy"

def grade_and_record_attempt(
    quiz_id: str,
    user_answers: List[Dict[str, str]]
) -> Dict[str, Any]:
    """
    Grades user answers against stored quiz questions, persists attempt and answers
    into SQLite, and computes granular topic and difficulty analytics.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # 1. Fetch quiz and all questions
        quiz = cursor.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
        if not quiz:
            raise QuizGradingError(f"Quiz {quiz_id} not found.")

        rows = cursor.execute(
            "SELECT * FROM questions WHERE quiz_id = ?",
            (quiz_id,)
        ).fetchall()

        if not rows:
            raise QuizGradingError(f"No questions found for quiz {quiz_id}.")

        questions_by_id = {q["id"]: dict(q) for q in rows}
        answers_map = {
            a.get("question_id"): str(a.get("selected_option", "")).upper().strip()
            for a in user_answers
        }

        # 2. Grade each question
        score = 0
        total_questions = len(questions_by_id)
        results: List[Dict[str, Any]] = []

        topic_stats: Dict[str, Dict[str, Any]] = {}
        difficulty_stats: Dict[str, Dict[str, Any]] = {}

        attempt_id = f"att_{uuid.uuid4().hex[:10]}"
        attempt_answers_to_insert = []

        for q_id, q_data in questions_by_id.items():
            user_choice = answers_map.get(q_id, "")
            correct_choice = str(q_data["correct_option"]).upper().strip()
            is_correct = (user_choice == correct_choice)

            if is_correct:
                score += 1

            topic = q_data.get("topic", "General")
            difficulty = q_data.get("difficulty", "medium").lower()

            # Aggregate Topic Stats
            if topic not in topic_stats:
                topic_stats[topic] = {"total": 0, "correct": 0}
            topic_stats[topic]["total"] += 1
            if is_correct:
                topic_stats[topic]["correct"] += 1

            # Aggregate Difficulty Stats
            if difficulty not in difficulty_stats:
                difficulty_stats[difficulty] = {"total": 0, "correct": 0}
            difficulty_stats[difficulty]["total"] += 1
            if is_correct:
                difficulty_stats[difficulty]["correct"] += 1

            ans_id = f"ans_{uuid.uuid4().hex[:10]}"
            attempt_answers_to_insert.append((
                ans_id, attempt_id, q_id, user_choice, 1 if is_correct else 0
            ))

            results.append({
                "question_id": q_id,
                "question": q_data["question_text"],
                "selected_option": user_choice,
                "correct_option": correct_choice,
                "is_correct": is_correct,
                "explanation": q_data["explanation"],
                "topic": topic,
                "difficulty": difficulty,
                "source_reference": q_data.get("source_reference", "")
            })

        # Calculate overall accuracy
        accuracy_pct = round((score / max(total_questions, 1)) * 100, 1)

        # Finalize topic breakdown with status and badges
        topic_breakdown: Dict[str, Dict[str, Any]] = {}
        for t, stats in topic_stats.items():
            pct = round((stats["correct"] / max(stats["total"], 1)) * 100, 1)
            status, badge = classify_topic_mastery(pct)
            topic_breakdown[t] = {
                "total": stats["total"],
                "correct": stats["correct"],
                "accuracy": pct,
                "status": status,
                "badge": badge
            }

        # Finalize difficulty breakdown
        difficulty_breakdown: Dict[str, Dict[str, Any]] = {}
        for d, stats in difficulty_stats.items():
            difficulty_breakdown[d] = {
                "total": stats["total"],
                "correct": stats["correct"],
                "accuracy": round((stats["correct"] / max(stats["total"], 1)) * 100, 1)
            }

        # 3. Detect Weak Topics & Determine Next Adaptive Difficulty
        weak_topics = detect_weak_topics(topic_breakdown)
        recommended_difficulty = determine_adaptive_difficulty(accuracy_pct)

        # 4. Persist Attempt and Answers in SQLite
        cursor.execute("""
            INSERT INTO attempts (id, quiz_id, score, total_questions, accuracy)
            VALUES (?, ?, ?, ?, ?)
        """, (attempt_id, quiz_id, score, total_questions, accuracy_pct))

        cursor.executemany("""
            INSERT INTO attempt_answers (id, attempt_id, question_id, selected_option, is_correct)
            VALUES (?, ?, ?, ?, ?)
        """, attempt_answers_to_insert)

    return {
        "attempt_id": attempt_id,
        "quiz_id": quiz_id,
        "document_id": quiz["document_id"],
        "score": score,
        "total_questions": total_questions,
        "incorrect_count": total_questions - score,
        "accuracy_percentage": accuracy_pct,
        "topic_breakdown": topic_breakdown,
        "difficulty_breakdown": difficulty_breakdown,
        "weak_topics": weak_topics,
        "recommended_next_difficulty": recommended_difficulty,
        "results": results
    }

def get_attempt_weak_topics(attempt_id: str) -> Dict[str, Any]:
    """Retrieves weak topics for any stored attempt ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        attempt = cursor.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
        if not attempt:
            raise QuizGradingError(f"Attempt {attempt_id} not found.")

        rows = cursor.execute("""
            SELECT q.topic, aa.is_correct
            FROM attempt_answers aa
            JOIN questions q ON aa.question_id = q.id
            WHERE aa.attempt_id = ?
        """, (attempt_id,)).fetchall()

        topic_counts: Dict[str, Dict[str, int]] = {}
        for r in rows:
            t = r["topic"]
            if t not in topic_counts:
                topic_counts[t] = {"total": 0, "correct": 0}
            topic_counts[t]["total"] += 1
            if r["is_correct"]:
                topic_counts[t]["correct"] += 1

        breakdown = {}
        for t, s in topic_counts.items():
            acc = round((s["correct"] / s["total"]) * 100, 1)
            status, badge = classify_topic_mastery(acc)
            breakdown[t] = {"total": s["total"], "correct": s["correct"], "accuracy": acc, "status": status, "badge": badge}

        weak = detect_weak_topics(breakdown)
        medium_topics = [t for t, s in breakdown.items() if s["status"] == "Medium"]
        strong_topics = [t for t, s in breakdown.items() if s["status"] == "Strong"]
        return {
            "attempt_id": attempt_id,
            "overall_accuracy": attempt["accuracy"],
            "weak_topics": weak,
            "medium_topics": medium_topics,
            "strong_topics": strong_topics,
            "topic_breakdown": breakdown
        }

def get_cumulative_knowledge_map(document_id: str) -> Dict[str, Any]:
    """
    Computes cumulative knowledge mastery across all attempts for a given document.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        doc = cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not doc:
            raise QuizGradingError(f"Document {document_id} not found.")

        rows = cursor.execute("""
            SELECT q.topic, aa.is_correct
            FROM quizzes qz
            JOIN questions q ON qz.id = q.quiz_id
            JOIN attempt_answers aa ON q.id = aa.question_id
            WHERE qz.document_id = ?
        """, (document_id,)).fetchall()

        if not rows:
            return {
                "document_id": document_id,
                "filename": doc["filename"],
                "total_questions_attempted": 0,
                "overall_mastery": 0.0,
                "strong_topics": [],
                "medium_topics": [],
                "weak_topics": [],
                "topics": []
            }

        topic_stats: Dict[str, Dict[str, int]] = {}
        total_correct = 0
        total_attempted = len(rows)

        for r in rows:
            t = r["topic"]
            if t not in topic_stats:
                topic_stats[t] = {"total": 0, "correct": 0}
            topic_stats[t]["total"] += 1
            if r["is_correct"]:
                topic_stats[t]["correct"] += 1
                total_correct += 1

        overall_mastery = round((total_correct / total_attempted) * 100, 1)

        strong_topics = []
        medium_topics = []
        weak_topics = []
        topic_list = []

        for t, s in topic_stats.items():
            acc = round((s["correct"] / s["total"]) * 100, 1)
            status, badge = classify_topic_mastery(acc)
            topic_data = {
                "topic": t,
                "total": s["total"],
                "correct": s["correct"],
                "accuracy": acc,
                "status": status,
                "badge": badge
            }
            topic_list.append(topic_data)
            if status == "Strong":
                strong_topics.append(t)
            elif status == "Medium":
                medium_topics.append(t)
            else:
                weak_topics.append(t)

        return {
            "document_id": document_id,
            "filename": doc["filename"],
            "total_questions_attempted": total_attempted,
            "overall_mastery": overall_mastery,
            "strong_topics": strong_topics,
            "medium_topics": medium_topics,
            "weak_topics": weak_topics,
            "topics": topic_list
        }
