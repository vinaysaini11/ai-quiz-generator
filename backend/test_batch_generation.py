"""
Automated Test Suite for Variable Question Counts, Batch Generation,
Topic Distribution, Deduplication, and Adaptive Loading Compatibility.
"""
import os
import sys
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from backend.quiz_generator import calculate_batches, BATCH_SIZE
from backend.quality_guard import filter_and_guard_questions

BASE_URL = "http://127.0.0.1:8000"

def log_test(test_name: str, passed: bool, detail: str = ""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {test_name}: {detail}")
    if not passed:
        sys.exit(1)

def test_batch_calculation_logic():
    """Verify calculate_batches handles standard, multiple, and remainder counts."""
    b10 = calculate_batches(10, BATCH_SIZE)
    log_test("Batch Calc 10", b10 == [10], f"Result: {b10}")

    b20 = calculate_batches(20, BATCH_SIZE)
    log_test("Batch Calc 20", b20 == [10, 10], f"Result: {b20}")

    b30 = calculate_batches(30, BATCH_SIZE)
    log_test("Batch Calc 30", b30 == [10, 10, 10], f"Result: {b30}")

    b50 = calculate_batches(50, BATCH_SIZE)
    log_test("Batch Calc 50", b50 == [10, 10, 10, 10, 10], f"Result: {b50}")

    b25 = calculate_batches(25, BATCH_SIZE)
    log_test("Batch Calc 25 (Remainder)", b25 == [10, 10, 5], f"Result: {b25}")

def test_quality_guard_cross_batch_deduplication():
    """Verify Quality Guard catches duplicates across successive batches."""
    sample_q = {
        "question": "What is the primary cause of Belady's Anomaly in page replacement?",
        "options": {
            "A": "FIFO replacement algorithm anomaly",
            "B": "LRU stack property",
            "C": "Optimal replacement algorithm",
            "D": "Clock algorithm"
        },
        "correct_answer": "A",
        "explanation": "FIFO page replacement can exhibit Belady's Anomaly where more frames lead to more faults.",
        "topic": "Virtual Memory",
        "difficulty": "medium",
        "source_reference": "Page 2"
    }

    seen = set()
    # Batch 1: First appearance should pass
    valid1, rep1 = filter_and_guard_questions([sample_q], "fifo page replacement belady anomaly", seen_questions=seen)
    log_test("Batch 1 Unique Question", len(valid1) == 1, "Question passed Quality Guard")

    # Batch 2: Duplicate question should be rejected
    duplicate_q = dict(sample_q)
    duplicate_q["question"] = "What is the primary cause of Belady's Anomaly in page replacement?  "
    valid2, rep2 = filter_and_guard_questions([duplicate_q], "fifo page replacement belady anomaly", seen_questions=seen)
    log_test("Batch 2 Duplicate Rejection", len(valid2) == 0, f"Duplicate successfully caught: {rep2['issues'][0]['reason']}")

def test_live_quiz_generation_counts():
    """Tests live API generation with question counts and field validation."""
    # Retrieve active document ID
    doc_id = "doc_63c4d11595"

    # Test 1: Generate 10 questions (1 batch)
    print("\n--- Testing 10 Questions Generation (1 batch) ---")
    res10 = requests.post(f"{BASE_URL}/api/quiz/generate", json={
        "document_id": doc_id,
        "question_count": 10,
        "difficulty": "medium"
    })
    log_test("API Status (10 questions)", res10.status_code == 200, f"Status: {res10.status_code}")
    data10 = res10.json()
    questions10 = data10.get("questions", [])
    log_test("Exactly 10 Questions Generated", len(questions10) == 10, f"Received {len(questions10)} questions")

    # Verify all question fields
    all_fields_valid = all(
        len(q.get("options", {})) == 4 and
        bool(q.get("topic")) and
        bool(q.get("difficulty")) and
        bool(q.get("source_reference"))
        for q in questions10
    )
    log_test("Question Schema Integrity", all_fields_valid, "All 10 questions contain options, topic, difficulty, source_reference")

    # Test 2: Generate 20 questions (2 batches)
    print("\n--- Testing 20 Questions Generation (2 batches of 10) ---")
    res20 = requests.post(f"{BASE_URL}/api/quiz/generate", json={
        "document_id": doc_id,
        "question_count": 20,
        "difficulty": "medium"
    })
    log_test("API Status (20 questions)", res20.status_code == 200, f"Status: {res20.status_code}")
    data20 = res20.json()
    questions20 = data20.get("questions", [])
    log_test("Exactly 20 Questions Generated", len(questions20) == 20, f"Received {len(questions20)} questions")

    # Check for duplicate questions in 20 questions
    normalized_texts = [q["question"].strip().lower() for q in questions20]
    unique_count = len(set(normalized_texts))
    log_test("Deduplication in 20 Questions", unique_count == 20, f"{unique_count}/20 questions are completely distinct")

def test_adaptive_quiz_with_variable_count():
    """Verify adaptive quiz generation supports question count parameter and returns targeted quiz."""
    print("\n--- Testing Adaptive Quiz with Variable Question Count ---")
    doc_id = "doc_63c4d11595"
    res_adapt = requests.post(f"{BASE_URL}/api/quiz/adaptive-generate", json={
        "document_id": doc_id,
        "target_topics": ["Virtual Memory", "CPU Scheduling"],
        "target_difficulty": "easy",
        "question_count": 10
    })
    log_test("Adaptive API Status (10 questions)", res_adapt.status_code == 200, f"Status: {res_adapt.status_code}")
    adapt_data = res_adapt.json()
    adapt_questions = adapt_data.get("questions", [])
    log_test("Adaptive Questions Generated", len(adapt_questions) == 10, f"Received {len(adapt_questions)} adaptive questions")
    log_test("Adaptive Difficulty Preserved", adapt_data.get("difficulty") == "easy", f"Difficulty: {adapt_data.get('difficulty')}")

if __name__ == "__main__":
    print("\n=======================================================")
    print("🧪 RUNNING BATCH GENERATION & VARIABLE COUNT TEST SUITE")
    print("=======================================================\n")
    test_batch_calculation_logic()
    test_quality_guard_cross_batch_deduplication()
    test_live_quiz_generation_counts()
    test_adaptive_quiz_with_variable_count()
    print("\n=======================================================")
    print("🎉 ALL BATCH & ADAPTIVE TESTS PASSED SUCCESSFULLY!")
    print("=======================================================\n")

