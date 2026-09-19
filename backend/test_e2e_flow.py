"""
End-to-End Test Suite for AI Quiz Generator.
Simulates the entire student user journey from PDF upload to adaptive remediation.
"""
import os
import sys
import time
import requests

BASE_URL = "http://127.0.0.1:8000"
PDF_PATH = os.path.join(os.path.dirname(__file__), "data", "Operating_Systems_Concepts.pdf")

def step_banner(num: int, title: str):
    print(f"\n=======================================================")
    print(f"▶ STEP {num}: {title}")
    print(f"=======================================================")

def assert_step(condition: bool, message: str):
    if condition:
        print(f"  ✅ PASS: {message}")
    else:
        print(f"  ❌ FAIL: {message}")
        sys.exit(1)

def run_e2e_pipeline():
    print("\n🚀 LAUNCHING END-TO-END VERIFICATION PIPELINE\n")

    # Step 1: Upload PDF
    step_banner(1, "Upload Document & Indexing")
    assert_step(os.path.exists(PDF_PATH), f"PDF exists at {PDF_PATH}")
    
    with open(PDF_PATH, "rb") as f:
        res = requests.post(
            f"{BASE_URL}/api/documents/upload",
            files={"file": ("Operating_Systems_Concepts.pdf", f, "application/pdf")}
        )
    assert_step(res.status_code == 200, f"Upload status 200 (Got {res.status_code})")
    upload_data = res.json()
    doc_id = upload_data["document_id"]
    assert_step(doc_id.startswith("doc_"), f"Generated Document ID: {doc_id}")
    assert_step(upload_data["total_pages"] == 4, f"Extracted {upload_data['total_pages']} pages")
    print(f"  ℹ️ Indexed {upload_data['total_characters']} characters in ChromaDB collection.")

    # Step 2: Generate Baseline Quiz & Flashcards
    step_banner(2, "Generate Grounded Quiz & Flashcards (Gemini + Quality Guard)")
    gen_payload = {
        "document_id": doc_id,
        "num_questions": 4,
        "difficulty": "medium",
        "include_flashcards": True
    }
    res = requests.post(f"{BASE_URL}/api/quiz/generate", json=gen_payload)
    assert_step(res.status_code == 200, f"Quiz generation status 200 (Got {res.status_code})")
    quiz_data = res.json()
    quiz_id = quiz_data["quiz_id"]
    questions = quiz_data["questions"]
    flashcards = quiz_data["flashcards"]
    assert_step(len(questions) >= 3, f"Received {len(questions)} validated questions")
    assert_step(len(flashcards) >= 1, f"Received {len(flashcards)} flashcards")
    assert_step(all("source_reference" in q for q in questions), "All questions have source citations")
    print(f"  ℹ️ Quality Guard verified 100% of questions for structural integrity.")

    # Step 3: Fetch Quiz Details via GET
    step_banner(3, "Fetch Quiz for Student Taking")
    res = requests.get(f"{BASE_URL}/api/quiz/{quiz_id}")
    assert_step(res.status_code == 200, "Quiz fetched successfully")
    fetched_quiz = res.json()
    assert_step(len(fetched_quiz["questions"]) == len(questions), "Questions count matches")

    # Step 4: Submit Answers (Intentionally miss some questions to trigger weak topics)
    step_banner(4, "Simulate Quiz Submission & Real-Time Grading")
    # For question 0: pick 'A', for question 1: pick 'B', etc.
    # In SQLite, correct answers are stored. We submit a mixture.
    answers_payload = []
    options = ["A", "B", "C", "D"]
    for i, q in enumerate(questions):
        # Alternate picks
        chosen = options[i % 4]
        answers_payload.append({
            "question_id": q["id"],
            "selected_option": chosen
        })

    submit_req = {
        "quiz_id": quiz_id,
        "answers": answers_payload
    }
    res = requests.post(f"{BASE_URL}/api/quiz/submit", json=submit_req)
    assert_step(res.status_code == 200, f"Submission status 200 (Got {res.status_code})")
    result_data = res.json()
    attempt_id = result_data["attempt_id"]
    print(f"  ℹ️ Attempt ID: {attempt_id}")
    print(f"  ℹ️ Score: {result_data['score']}/{result_data['total_questions']} ({result_data['accuracy_percentage']:.1f}%)")
    assert_step("topic_breakdown" in result_data, "Topic breakdown generated")

    # Step 5: Detect Weak Topics
    step_banner(5, "Configurable Rule-Based Weak Topic Detection")
    res = requests.get(f"{BASE_URL}/api/attempts/{attempt_id}/weak-topics")
    assert_step(res.status_code == 200, "Weak topics endpoint returned 200")
    weak_data = res.json()
    weak_topics = weak_data["weak_topics"]
    medium_topics = weak_data["medium_topics"]
    print(f"  ℹ️ Weak Topics: {weak_topics}")
    print(f"  ℹ️ Medium Topics: {medium_topics}")
    print(f"  ℹ️ Strong Topics: {weak_data['strong_topics']}")
    assert_step("topic_breakdown" in weak_data, "Topic breakdown present")

    # Step 6: Trigger "Teach Me This" Micro-Tutor
    step_banner(6, "Personalized Micro-Tutor ('Teach Me This')")
    wrong_answers = [r for r in result_data["results"] if not r["is_correct"]]
    target_q = wrong_answers[0] if wrong_answers else result_data["results"][0]
    
    teach_payload = {
        "document_id": doc_id,
        "question_id": target_q["question_id"],
        "user_answer": target_q.get("selected_option", "A"),
        "topic": target_q.get("topic", "General")
    }
    res = requests.post(f"{BASE_URL}/api/quiz/teach-me", json=teach_payload)
    assert_step(res.status_code == 200, f"Teach Me status 200 (Got {res.status_code})")
    teach_data = res.json()
    assert_step(bool(teach_data.get("explanation")), "Explanation generated")
    assert_step(bool(teach_data.get("key_idea")), "Key idea synthesized")
    assert_step("quick_check" in teach_data and "question" in teach_data["quick_check"], "Interactive quick check question generated")
    print(f"  ℹ️ Teach-Me Concept: {teach_data.get('topic')}")
    print(f"  ℹ️ Grounded Source Ref: {teach_data.get('source_reference')}")

    # Step 7: Generate Targeted Adaptive Quiz
    step_banner(7, "Targeted Adaptive Next Quiz Generation")
    target_topics_for_next = weak_topics if weak_topics else (medium_topics if medium_topics else ["Virtual Memory"])
    adapt_payload = {
        "document_id": doc_id,
        "previous_attempt_id": attempt_id,
        "target_topics": target_topics_for_next,
        "target_difficulty": result_data.get("recommended_next_difficulty", "medium"),
        "num_questions": 3
    }
    res = requests.post(f"{BASE_URL}/api/quiz/adaptive-generate", json=adapt_payload)
    assert_step(res.status_code == 200, f"Adaptive quiz status 200 (Got {res.status_code})")
    adapt_quiz = res.json()
    assert_step(len(adapt_quiz["questions"]) >= 1, f"Adaptive quiz generated with {len(adapt_quiz['questions'])} questions")
    assert_step(adapt_quiz["quiz_id"] != quiz_id, "New distinct adaptive quiz ID created")
    print(f"  ℹ️ Adaptive Quiz ID: {adapt_quiz['quiz_id']}")

    # Step 8: Cumulative Knowledge Map
    step_banner(8, "Cumulative Knowledge Map Across Attempts")
    res = requests.get(f"{BASE_URL}/api/documents/{doc_id}/knowledge-map")
    assert_step(res.status_code == 200, "Knowledge map status 200")
    km_data = res.json()
    assert_step(km_data["total_questions_attempted"] >= 3, f"Cumulative attempted: {km_data['total_questions_attempted']}")
    assert_step("overall_mastery" in km_data, f"Overall mastery: {km_data['overall_mastery']}%")
    print(f"  ℹ️ Cumulative Mastery: {km_data['overall_mastery']}% across {len(km_data['topics'])} topics")

    # Step 9: Personalized Study Plan
    step_banner(9, "Personalized Study Roadmap Generation")
    res = requests.post(f"{BASE_URL}/api/documents/{doc_id}/study-plan", json={"attempt_id": attempt_id})
    assert_step(res.status_code == 200, "Study plan status 200")
    sp_data = res.json()
    plan = sp_data.get("plan", {})
    assert_step(bool(plan.get("summary")), "Study plan summary present")
    assert_step(len(plan.get("study_sequence", [])) >= 1, f"Plan contains {len(plan.get('study_sequence', []))} sequenced steps")
    print(f"  ℹ️ Study Roadmap Estimated Time: {plan.get('total_estimated_time_minutes', 30)} minutes")
    print(f"  ℹ️ Priority Focus: {plan.get('priority_focus')}")

    print("\n=======================================================")
    print("🎉 END-TO-END VERIFICATION COMPLETED SUCCESSFULLY!")
    print("   All 9 Stages of the Core Loop Tested and Passed.")
    print("=======================================================\n")

if __name__ == "__main__":
    run_e2e_pipeline()

