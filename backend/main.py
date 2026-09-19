"""
FastAPI Backend Application Entry Point for AI Quiz Generator.
Serves REST API endpoints and static frontend assets.
"""
import os
import uuid
import shutil
from contextlib import asynccontextmanager
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from backend.database import init_db, get_db
from backend.gemini_service import gemini_service
from backend.pdf_processor import extract_text_from_pdf, PDFProcessingError
from backend.rag import rag_engine
from backend.quiz_generator import generate_quiz_from_document, generate_targeted_adaptive_quiz
from backend.performance import grade_and_record_attempt, get_attempt_weak_topics, get_cumulative_knowledge_map, QuizGradingError
from backend.teach_me import teach_concept
from backend.study_plan import generate_study_plan

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database
    init_db()
    yield
    # Shutdown

app = FastAPI(
    title="AI Quiz Generator API",
    description="Adaptive learning system with source-grounded quiz generation and weakness analysis",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

# Mount frontend static files
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/api/health")
async def health_check():
    """Health check endpoint to verify backend status."""
    return {
        "status": "healthy",
        "service": "AI Quiz Generator",
        "version": "1.0.0",
        "gemini_configured": gemini_service.is_configured()
    }

@app.get("/api/gemini/test")
async def test_gemini():
    """Test connection and structured JSON generation from Gemini API."""
    result = gemini_service.test_connection()
    return result

@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Handles PDF upload, validates format & size, extracts text with page numbers,
    and stores document metadata in SQLite.
    """
    # 1. File type validation
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Only text-based PDF documents are supported."
        )

    # 2. Generate unique document ID and safe filename to prevent path traversal
    doc_id = f"doc_{uuid.uuid4().hex[:10]}"
    clean_base = os.path.basename(file.filename or "document.pdf")
    safe_filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', clean_base)
    target_filepath = os.path.join(UPLOAD_DIR, f"{doc_id}_{safe_filename}")

    # 3. Stream write file to disk with 10MB limit enforcement
    max_bytes = 10 * 1024 * 1024
    total_written = 0
    try:
        with open(target_filepath, "wb") as buffer:
            while chunk := await file.read(1024 * 64):
                total_written += len(chunk)
                if total_written > max_bytes:
                    raise HTTPException(
                        status_code=400,
                        detail="File size exceeds the 10MB limit."
                    )
                buffer.write(chunk)
    except HTTPException:
        if os.path.exists(target_filepath):
            os.remove(target_filepath)
        raise
    except Exception as e:
        if os.path.exists(target_filepath):
            os.remove(target_filepath)
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    # 4. Extract text using PyPDF
    try:
        extraction = extract_text_from_pdf(target_filepath)
    except PDFProcessingError as pe:
        if os.path.exists(target_filepath):
            os.remove(target_filepath)
        raise HTTPException(status_code=400, detail=str(pe))
    except Exception as e:
        if os.path.exists(target_filepath):
            os.remove(target_filepath)
        raise HTTPException(status_code=500, detail=f"Text extraction failed: {str(e)}")

    # 5. Persist document metadata in SQLite
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO documents (id, filename, filepath, total_pages) VALUES (?, ?, ?, ?)",
                (doc_id, file.filename, target_filepath, extraction["total_pages"])
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error storing document: {str(e)}")

    # 6. Index into ChromaDB vector database
    try:
        index_result = rag_engine.index_document(doc_id, extraction["pages"])
        total_chunks = index_result.get("total_chunks", len(extraction["pages"]))
    except Exception as e:
        total_chunks = 0
        print(f"⚠️ Warning: Vector indexing failed: {str(e)}")

    return {
        "document_id": doc_id,
        "filename": file.filename,
        "total_pages": extraction["total_pages"],
        "readable_pages": extraction["readable_pages"],
        "total_characters": extraction["total_characters"],
        "total_chunks": total_chunks,
        "message": "Document successfully uploaded, processed, and indexed in vector DB."
    }

@app.get("/api/documents/{document_id}/search")
async def search_document(document_id: str, query: str, top_k: int = 3):
    """Semantic vector search against indexed document chunks in ChromaDB."""
    results = rag_engine.retrieve_relevant_chunks(document_id, query, top_k=top_k)
    return {
        "document_id": document_id,
        "query": query,
        "results_count": len(results),
        "results": results
    }

@app.get("/api/documents/{document_id}/pages")
async def get_document_pages(document_id: str):
    """Returns page-by-page extracted text for an indexed document."""
    with get_db() as conn:
        doc = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    extraction = extract_text_from_pdf(doc["filepath"])
    return {
        "document_id": document_id,
        "filename": doc["filename"],
        "pages": extraction["pages"]
    }

class QuizGenerateRequest(BaseModel):
    document_id: str
    num_questions: int = Field(default=10, ge=1, le=50)
    question_count: Optional[int] = Field(default=None, ge=1, le=50)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    include_flashcards: bool = True

@app.post("/api/quiz/generate")
async def generate_quiz(req: QuizGenerateRequest):
    """
    Generates grounded MCQs and flashcards from an indexed document using Gemini.
    Supports variable question counts (10, 20, 30, 50) using batch generation.
    """
    if not gemini_service.is_configured():
        raise HTTPException(
            status_code=400,
            detail="Gemini API Key is not configured. Please save GEMINI_API_KEY in your .env file."
        )

    try:
        count = req.question_count if req.question_count is not None else req.num_questions
        quiz_data = generate_quiz_from_document(
            document_id=req.document_id,
            num_questions=count,
            difficulty=req.difficulty,
            include_flashcards=req.include_flashcards
        )
        return quiz_data
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        raise HTTPException(status_code=500, detail=str(re))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate quiz: {str(e)}")

@app.get("/api/quiz/{quiz_id}")
async def get_quiz(quiz_id: str):
    """Retrieves quiz details and questions by quiz ID."""
    with get_db() as conn:
        quiz = conn.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")
        questions = conn.execute("SELECT * FROM questions WHERE quiz_id = ?", (quiz_id,)).fetchall()
        
    return {
        "quiz_id": quiz["id"],
        "document_id": quiz["document_id"],
        "difficulty": quiz["difficulty"],
        "questions": [
            {
                "id": q["id"],
                "question": q["question_text"],
                "options": {
                    "A": q["option_a"],
                    "B": q["option_b"],
                    "C": q["option_c"],
                    "D": q["option_d"]
                },
                "topic": q["topic"],
                "difficulty": q["difficulty"],
                "source_reference": q["source_reference"]
            }
            for q in questions
        ]
    }

class AnswerSubmission(BaseModel):
    question_id: str
    selected_option: str = Field(pattern="^[A-D]$")

class QuizSubmitRequest(BaseModel):
    quiz_id: str
    answers: list[AnswerSubmission]

@app.post("/api/quiz/submit")
async def submit_quiz(req: QuizSubmitRequest):
    """
    Submits quiz answers, grades questions, records attempt in SQLite,
    and returns granular score, accuracy, topic breakdown, and explanations.
    """
    try:
        answers_data = [a.model_dump() for a in req.answers]
        result = grade_and_record_attempt(req.quiz_id, answers_data)
        return result
    except QuizGradingError as qe:
        raise HTTPException(status_code=400, detail=str(qe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Grading error: {str(e)}")

@app.get("/api/attempts/{attempt_id}/weak-topics")
async def get_weak_topics(attempt_id: str):
    """Returns detected weak topics and mastery breakdown for an attempt."""
    try:
        return get_attempt_weak_topics(attempt_id)
    except QuizGradingError as qe:
        raise HTTPException(status_code=404, detail=str(qe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class AdaptiveQuizRequest(BaseModel):
    document_id: str
    previous_attempt_id: Optional[str] = None
    target_topics: Optional[list[str]] = None
    target_difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    num_questions: int = Field(default=10, ge=1, le=50)
    question_count: Optional[int] = Field(default=None, ge=1, le=50)

@app.post("/api/quiz/adaptive-generate")
async def generate_adaptive_quiz(req: AdaptiveQuizRequest):
    """
    Generates a targeted, adaptive quiz centered around weak topics and previously missed concepts.
    Supports variable question counts (10, 20, 30, 50) using batch generation.
    """
    if not gemini_service.is_configured():
        raise HTTPException(
            status_code=400,
            detail="Gemini API Key is not configured."
        )
    try:
        count = req.question_count if req.question_count is not None else req.num_questions
        quiz_data = generate_targeted_adaptive_quiz(
            document_id=req.document_id,
            previous_attempt_id=req.previous_attempt_id,
            target_topics=req.target_topics,
            target_difficulty=req.target_difficulty,
            num_questions=count
        )
        return quiz_data
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Adaptive quiz error: {str(e)}")

class TeachMeRequest(BaseModel):
    document_id: str
    question_id: str
    user_answer: Optional[str] = None
    topic: Optional[str] = None

@app.post("/api/quiz/teach-me")
async def teach_me_endpoint(req: TeachMeRequest):
    """
    Generates a personalized, source-grounded explanation and comprehension check
    for an incorrectly answered question.
    """
    if not gemini_service.is_configured():
        raise HTTPException(
            status_code=400,
            detail="Gemini API Key is not configured."
        )
    try:
        lesson = teach_concept(
            document_id=req.document_id,
            question_id=req.question_id,
            user_answer=req.user_answer,
            topic=req.topic
        )
        return lesson
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Teach-me error: {str(e)}")

@app.get("/api/documents/{document_id}/knowledge-map")
async def get_document_knowledge_map(document_id: str):
    """
    Returns cumulative knowledge mastery across all attempts for a given document,
    categorizing topics into Strong (green), Medium (yellow), and Weak (red).
    """
    try:
        km = get_cumulative_knowledge_map(document_id)
        return km
    except QuizGradingError as qe:
        raise HTTPException(status_code=404, detail=str(qe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class StudyPlanRequest(BaseModel):
    attempt_id: Optional[str] = None

@app.post("/api/documents/{document_id}/study-plan")
async def get_study_plan(document_id: str, req: Optional[StudyPlanRequest] = None):
    """
    Generates a personalized, 3-step action roadmap based on assessed weak areas
    and cumulative performance.
    """
    if not gemini_service.is_configured():
        raise HTTPException(
            status_code=400,
            detail="Gemini API Key is not configured."
        )
    try:
        attempt_id = req.attempt_id if req else None
        plan = generate_study_plan(document_id=document_id, attempt_id=attempt_id)
        return plan
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Study plan error: {str(e)}")


@app.get("/")
async def serve_index():
    """Serve the single-page frontend application."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend not found, but API is running."}

# Also serve CSS and JS directly for root index references
@app.get("/style.css")
async def serve_css():
    return FileResponse(os.path.join(FRONTEND_DIR, "style.css"))

@app.get("/script.js")
async def serve_js():
    return FileResponse(os.path.join(FRONTEND_DIR, "script.js"))

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("backend.main:app", host=host, port=port, reload=True)

