# AI Quiz Generator

An intelligent, full-stack adaptive learning platform that transforms uploaded study materials and PDFs into source-grounded Multiple-Choice Questions (MCQs), interactive flashcards, atomic performance diagnostics, and closed-loop adaptive study remediation powered by **Google Gemini** and **RAG (Retrieval-Augmented Generation)**.

---

## 1. Project Overview

The **AI Quiz Generator** converts uploaded study notes, textbooks, and lecture slide PDFs into:
- **Multiple-Choice Questions (MCQs)** with calibrated difficulties (Easy, Medium, Hard).
- **Interactive Study Flashcards** for rapid active recall.
- **Detailed Explanations** and exact page citations for every question.
- **Atomic Performance Analysis** with granular score and accuracy tracking.
- **Weak-Topic Detection** using configurable mastery rules.
- **Targeted Adaptive Quizzes** that focus specifically on detected weak areas.
- **"Teach Me This" Micro-Tutor** generating on-demand concept reviews and interactive recall checks.
- **Cumulative Knowledge Map** visualizing mastery progress across multiple attempts.
- **Personalized Study Plans** providing sequenced action roadmaps with time estimates.

---

## 2. Problem Statement

Students spend hours passively re-reading lecture slides and textbook chapters, leading to low retention and poor exam outcomes. Manually authoring practice questions and flashcards is tedious, while generic LLMs often hallucinate facts, lack source page citations, and have no memory of past performance gaps.

The **AI Quiz Generator** automates the entire active recall lifecycle: extracting text with page coordinate tracking, semantically indexing chunks, enforcing an AI Quality Guard against hallucinations, identifying knowledge weaknesses, and generating tailored remediation loops.

---

## 3. Key Features

- **Strict Source Grounding & AI Quality Guard**: Validates that all questions have exactly 4 distinct plausible options, unambiguous correct answers, and lexical grounding in the source material.
- **Variable Question Counts (10, 20, 30, 50)**: Clean pill selector allowing students to choose their quiz length.
- **Question Batching**: Generates large question sets in sequential batches of 10 to avoid token limits, preserve distractor quality, and distribute questions across document topics.
- **Cross-Batch Deduplication**: Tracks normalized question signatures to guarantee zero duplicate questions across batches.
- **In-Page Adaptive Loading Modal**: Displays real-time focus topics, difficulty badges, and animated status when generating targeted quizzes (zero jarring browser alerts).
- **"Teach Me This" Micro-Tutor**: Instant mini-lesson modal for any missed question featuring core concepts, key ideas, source examples, and an on-the-spot interactive quick check.
- **Rule-Based Weakness Detection**: Automatically classifies topics into Strong ($\ge 75\%$), Medium ($50\% - 74\%$), and Weak ($< 50\%$).
- **Cumulative Knowledge Map**: Aggregates accuracy across multiple quiz sessions with color-coded visual progress indicators.
- **Personalized Study Roadmap**: Synthesizes cumulative student performance into a 3-step prioritized study plan with estimated time investments.

---

## 4. Architecture

```
User / Browser (Vanilla HTML/CSS/JS)
       │
       ▼
FastAPI Backend (backend/main.py)
       │
       ▼
PDF Processing & Text Extraction (backend/pdf_processor.py)
       │
       ▼
ChromaDB Vector Store + Offline Embeddings (backend/rag.py)
       │
       ▼
Google Gemini API via google-genai (backend/gemini_service.py)
       │
       ▼
AI Quality Guard Validation Gate (backend/quality_guard.py)
       │
       ▼
Quiz Persistence & Delivery (SQLite Database)
       │
       ▼
User Quiz Attempt & Submission
       │
       ▼
Atomic Grading & Performance Analysis (backend/performance.py)
       │
       ▼
Configurable Weak-Topic Detection Engine
       │
       ▼
Targeted Adaptive Quiz / "Teach Me This" Remediation
```

---

## 5. Tech Stack

- **Backend Framework**: Python 3.12, FastAPI, Uvicorn
- **Frontend**: Vanilla JavaScript (ES6+), HTML5, CSS3 (No node build tools required)
- **PDF Extraction**: `pypdf` with page-by-page tracking and text cleaning
- **Vector Database**: `chromadb` (persistent collection storage)
- **Embeddings**: `sentence-transformers` (`all-MiniLM-L6-v2` running locally offline)
- **Large Language Model**: Google Gemini API via the official `google-genai` SDK
- **Relational Database**: SQLite 3 (embedded relational storage)

---

## 6. RAG (Retrieval-Augmented Generation) Flow

```
1. PDF Upload ────► 2. Text Extraction & Page Tracking
                            │
                            ▼
3. Paragraph Semantic Chunking (250 words / 40-word overlap)
                            │
                            ▼
4. Local Embeddings Generation (all-MiniLM-L6-v2)
                            │
                            ▼
5. Persistent Storage in ChromaDB Collection
                            │
                            ▼
6. Semantic Vector Similarity Query (Cosine Distance)
                            │
                            ▼
7. Grounded Chunk Injection into Gemini University Examiner Prompt
```

---

## 7. Adaptive Learning Flow

```
1. Student Completes Quiz Attempt
            │
            ▼
2. Atomic Server-Side Grading & SQLite Persistence
            │
            ▼
3. Rule-Based Mastery Evaluation:
   - Strong: ≥ 75%
   - Medium: 50% - 74%
   - Weak: < 50%
            │
            ▼
4. Calibrated Difficulty Selection:
   - Score < 50% ──► Easy (Foundational Review)
   - Score 50% - 80% ──► Medium (Application)
   - Score > 80% ──► Hard (Deep Recall & Edge Cases)
            │
            ▼
5. In-Page Loading Modal Displays Assessed Focus Topics
            │
            ▼
6. ChromaDB Retrieves Semantic Chunks for Weak Topics
            │
            ▼
7. Targeted Remediation Quiz Delivered to Student
```

---

## 8. Question Batching

To avoid token limits, degraded distractor quality, or truncated JSON responses when generating large quizzes:

$$\text{10 questions} = 1 \text{ batch of 10}$$
$$\text{20 questions} = 2 \text{ batches of 10}$$
$$\text{30 questions} = 3 \text{ batches of 10}$$
$$\text{50 questions} = 5 \text{ batches of 10}$$

- **Configurable Constant**: Controlled via `BATCH_SIZE = 10` in `backend/quiz_generator.py`.
- **Topic Distribution**: Pages from the document are partitioned across batches so questions cover different sections of the document instead of clustering on Page 1.
- **Cross-Batch Deduplication**: A cumulative `seen_questions` registry is passed across batches so duplicate questions are discarded by the AI Quality Guard.

---

## 9. Project Structure

```
AI Quiz Generator/
├── backend/
│   ├── main.py                  # FastAPI server & REST API endpoints
│   ├── database.py              # SQLite connection pool & schema initialization
│   ├── gemini_service.py        # Google GenAI SDK wrapper with multi-model fallback
│   ├── pdf_processor.py         # Magic byte validation (%PDF-) & page extraction
│   ├── rag.py                   # Semantic chunking & ChromaDB vector store
│   ├── quiz_generator.py        # Multi-batch question generation & prompt engineering
│   ├── quality_guard.py         # Structural & lexical grounding validation gate
│   ├── performance.py           # Atomic scoring, weak-topic rules, knowledge map
│   ├── teach_me.py              # "Teach Me This" micro-tutor engine
│   ├── study_plan.py            # Personalized 3-step study roadmap synthesizer
│   ├── create_sample_pdf.py     # Helper generating test academic PDF
│   ├── test_batch_generation.py # Batch generation & deduplication test suite
│   ├── test_security_audit.py   # Security & boundary validation test suite
│   └── test_e2e_flow.py         # End-to-end user lifecycle pipeline test
├── frontend/
│   ├── index.html               # Single-page user interface & modal structures
│   ├── style.css                # Responsive styles, pill selectors, and 3D cards
│   └── script.js                # State management, keyboard nav & API calls
├── data/
│   ├── uploads/                 # Uploaded PDFs (gitignored, contains .gitkeep)
│   └── vector_db/               # ChromaDB storage (gitignored, contains .gitkeep)
├── DEMO_WALKTHROUGH.md          # 2.5-minute presentation script & interview defense
├── requirements.txt             # Locked Python dependencies
├── .env.example                 # Template for environment variables
├── .gitignore                   # Git exclusion rules
└── README.md                    # Project documentation
```

---

## 10. Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-username/ai-quiz-generator.git
cd ai-quiz-generator

# 2. Create and activate a Python virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install required dependencies
pip install -r requirements.txt
```

---

## 11. Environment Setup

Copy the example environment file and add your Google Gemini API key:

```bash
cp .env.example .env
```

Edit `.env`:
```env
# Google Gemini API Key (Get a free key at: https://aistudio.google.com/)
GEMINI_API_KEY=your_gemini_api_key_here

# Server Configuration
HOST=127.0.0.1
PORT=8000
```

> **Security Note**: Never commit `.env` to version control. It is explicitly listed in `.gitignore`.

---

## 12. Run the Application

Start the FastAPI application with Uvicorn:

```bash
uvicorn backend.main:app --reload --port 8000
```

Open your browser at **[http://127.0.0.1:8000](http://127.0.0.1:8000)**.

---

## 13. Usage

1. **Upload Study Material**: Drag and drop a lecture or textbook PDF (up to 10MB).
2. **Select Quiz Settings**: Choose the number of questions (`10`, `20`, `30`, or `50`) and initial difficulty.
3. **Generate Quiz**: The system validates the PDF header, extracts pages, indexes vector embeddings, and generates grounded MCQs.
4. **Attempt Questions**: Answer questions using keyboard shortcuts (`1-4`, `A-D`, arrow keys) or mouse clicks.
5. **View Diagnostics**: Submit the quiz to view your score, accuracy, and topic breakdown.
6. **"Teach Me This"**: Click "Teach Me This" on any missed question for an interactive mini-lesson and active recall check.
7. **Generate Targeted Next Quiz**: Click "Generate Targeted Next Quiz" to view the in-page adaptive modal and practice weak topics.
8. **Personalized Study Plan**: Click "Personalized Study Plan" to review a 3-step prioritized study roadmap.
9. **Practice Flashcards**: Flip 3D flashcards for quick revision.

---

## 14. Security

- **API Key Protection**: `GEMINI_API_KEY` is loaded strictly server-side and never returned in API payloads or sent to the browser.
- **Git Isolation**: `.env`, `.env.*`, and sensitive files are excluded via `.gitignore`.
- **PDF Magic Byte Validation**: Verifies `%PDF-` header bytes before reading to reject spoofed files.
- **Path Traversal Defense**: Uploaded filenames are sanitized with `os.path.basename` and regex scrubbing to prevent directory traversal.
- **Schema Validation**: All API inputs are strictly validated with Pydantic boundaries.
- **Data Exclusion**: Uploaded student documents and local databases are excluded from Git commits.

---

## 15. Future Improvements

- **User Authentication**: Multi-tenant user accounts with JWT authentication.
- **Cloud Database**: Migration from SQLite to PostgreSQL / Supabase for distributed persistence.
- **Cloud Object Storage**: S3 / Google Cloud Storage for uploaded documents.
- **Asynchronous Task Workers**: Celery / Redis queue for heavy background document processing.
- **Additional File Formats**: Ingestion support for DOCX, PPTX, and EPUB files.
- **Export Formats**: Anki deck (.apkg) and PDF quiz export options.
