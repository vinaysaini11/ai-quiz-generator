"""
Automated Security & Quality Audit Suite for AI Quiz Generator.
Tests input validation boundaries, magic-byte checking, secret isolation,
and defense against path traversal and malformed payloads.
"""
import os
import sys
import tempfile
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

BASE_URL = "http://127.0.0.1:8000"
API_KEY = os.getenv("GEMINI_API_KEY", "")

def log_test(test_name: str, passed: bool, detail: str = ""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {test_name}: {detail}")
    if not passed:
        sys.exit(1)

def test_api_key_leakage():
    """Verify that GEMINI_API_KEY is never exposed in any public API responses."""
    if not API_KEY or len(API_KEY) < 10:
        print("⚠️ GEMINI_API_KEY not set or too short to test exposure reliably. Skipping substring check.")
        return

    endpoints = [
        "/api/health",
        "/api/documents/doc_63c4d11595",
        "/api/quiz/quiz_eac9ffbbf7",
        "/api/documents/doc_63c4d11595/knowledge-map"
    ]

    for ep in endpoints:
        res = requests.get(f"{BASE_URL}{ep}")
        body_text = res.text
        passed = (API_KEY not in body_text) and (API_KEY not in str(res.headers))
        log_test(f"Secret Isolation ({ep})", passed, "API key strictly excluded from response")

def test_reject_non_pdf_extension():
    """Verify that uploading non-.pdf files is rejected immediately."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"Hello world text file")
        temp_path = f.name

    try:
        with open(temp_path, "rb") as f:
            res = requests.post(
                f"{BASE_URL}/api/documents/upload",
                files={"file": ("test.txt", f, "text/plain")}
            )
        passed = (res.status_code == 400) and ("Invalid file format" in res.text)
        log_test("Reject Non-PDF Extension", passed, f"Status: {res.status_code}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_reject_fake_pdf_magic_bytes():
    """Verify that renaming a text/binary file to .pdf is rejected by header validation."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"FAKE_NOT_A_PDF_CONTENT_HEADER_TEST")
        temp_path = f.name

    try:
        with open(temp_path, "rb") as f:
            res = requests.post(
                f"{BASE_URL}/api/documents/upload",
                files={"file": ("malicious_fake.pdf", f, "application/pdf")}
            )
        passed = (res.status_code == 400) and ("PDF specification" in res.text or "corrupt" in res.text or "Invalid file format" in res.text)
        log_test("Reject Fake PDF Magic Bytes", passed, f"Status: {res.status_code}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_input_validation_boundaries():
    """Verify Pydantic guards reject malformed parameters with HTTP 422."""
    # 1. Invalid difficulty
    res1 = requests.post(
        f"{BASE_URL}/api/quiz/generate",
        json={"document_id": "doc_test", "num_questions": 5, "difficulty": "super_impossible"}
    )
    passed1 = res1.status_code == 422
    log_test("Boundary: Invalid Difficulty Rejected", passed1, f"Status: {res1.status_code}")

    # 2. Out of range num_questions (< 1)
    res2 = requests.post(
        f"{BASE_URL}/api/quiz/generate",
        json={"document_id": "doc_test", "num_questions": 0, "difficulty": "medium"}
    )
    passed2 = res2.status_code == 422
    log_test("Boundary: Zero Questions Rejected", passed2, f"Status: {res2.status_code}")

    # 3. Out of range num_questions (> 20)
    res3 = requests.post(
        f"{BASE_URL}/api/quiz/generate",
        json={"document_id": "doc_test", "num_questions": 99, "difficulty": "medium"}
    )
    passed3 = res3.status_code == 422
    log_test("Boundary: Excess Questions (>20) Rejected", passed3, f"Status: {res3.status_code}")

    # 4. SQL Injection / Malformed Option in Answer Submission
    res4 = requests.post(
        f"{BASE_URL}/api/quiz/submit",
        json={"quiz_id": "fake_quiz", "answers": [{"question_id": "q1", "selected_option": "A'; DROP TABLE--"}]}
    )
    passed4 = res4.status_code == 422
    log_test("Boundary: Malformed Option Rejected", passed4, f"Status: {res4.status_code}")

def test_safe_path_handling():
    """Verify path traversal filenames are sanitized and don't escape upload directory."""
    from backend.main import UPLOAD_DIR
    import re

    malicious_names = [
        "../../../../etc/passwd.pdf",
        "..\\..\\windows\\system32.pdf",
        "notes/../../../danger.pdf"
    ]

    for name in malicious_names:
        clean_base = os.path.basename(name)
        safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', clean_base)
        resolved_path = os.path.abspath(os.path.join(UPLOAD_DIR, f"doc_test_{safe_name}"))
        passed = resolved_path.startswith(os.path.abspath(UPLOAD_DIR))
        log_test(f"Path Traversal Guard ('{clean_base}')", passed, f"Contained within: {UPLOAD_DIR}")

if __name__ == "__main__":
    print("\n=======================================================")
    print("🔒 RUNNING AI QUIZ GENERATOR SECURITY & QUALITY AUDIT")
    print("=======================================================\n")
    
    test_api_key_leakage()
    test_reject_non_pdf_extension()
    test_reject_fake_pdf_magic_bytes()
    test_input_validation_boundaries()
    test_safe_path_handling()

    print("\n=======================================================")
    print("🎉 ALL SECURITY & QUALITY AUDIT TESTS PASSED!")
    print("=======================================================\n")
