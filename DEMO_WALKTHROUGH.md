# 🏆 AI Quiz Generator — Hackathon Demo Script & Interview Defense

This guide provides the exact 2-to-3 minute live presentation pitch, interactive click-by-click demo sequence, architectural defense, and winning answers for technical judges.

---

## ⏱️ 2.5-Minute Live Presentation Script

### 🎬 Scene 1: The Problem & The Upload (0:00 – 0:30)
* **What to Say**:
  > *"Students spend hours re-reading 50-page lecture slides or textbook chapters with passive, low-retention studying. When they use generic LLMs for practice questions, they get hallucinated answers, no citations, and zero memory of their past weaknesses.*
  > 
  > *Today, we built the **AI Quiz Generator**: an intelligent, source-grounded adaptive learning loop. Let's upload an Operating Systems lecture notes PDF."*
* **What to Do**:
  1. Open `http://127.0.0.1:8000`.
  2. Drag and drop `backend/data/Operating_Systems_Concepts.pdf` into the upload zone.
  3. Select **Medium** difficulty and **5 questions**.
  4. Click **"Generate Grounded Quiz"**.
  5. Point out the real-time processing indicator: *"The backend validates the PDF magic bytes, extracts text with exact page numbers, and indexes semantic chunks in ChromaDB."*

---

### 🎯 Scene 2: Taking the Quiz & The AI Quality Guard (0:30 – 1:00)
* **What to Say**:
  > *"Notice that every question generated is grounded directly from our lecture notes with an exact page citation. But here's the differentiator: before any question reaches the student, our **AI Quality Guard** automatically validates it.*
  > 
  > *It enforces 4 distinct options, ensures the answer pointer matches an option verbatim, verifies that distractors are plausible, and lexically validates grounding against source chunks. No broken questions, no hallucinations."*
* **What to Do**:
  1. Answer Question 1 correctly using keyboard shortcut `1` or clicking **A**.
  2. Intentionally pick an incorrect option on Question 2 (e.g. Belady's Anomaly / Virtual Memory question).
  3. Navigate through the questions using the keyboard arrow keys or `Next →`.
  4. Click **"Submit Quiz ✓"**.

---

### 📊 Scene 3: Performance Analysis & Weak Topic Detection (1:00 – 1:30)
* **What to Say**:
  > *"Immediately upon submission, our atomic scoring engine evaluates the attempt, stores it in SQLite, and applies our configurable rule-based weakness detection engine.*
  > 
  > *Notice the breakdown: CPU Scheduling is green (Strong, 100%), but Virtual Memory is flagged red (Weak, 0%). The system automatically recommends dropping difficulty to Easy on the next iteration to rebuild foundational comprehension."*
* **What to Do**:
  1. Scroll through the **Quiz Performance Analysis** card.
  2. Point to the **Score (80%)**, **Accuracy**, and **Recommended Next Difficulty**.
  3. Highlight the **Knowledge Map & Topic Mastery** progress bars showing 🟢 Strong and 🔴 Weak badges.

---

### 💡 Scene 4: Standout Feature #1 — "Teach Me This" Micro-Tutor (1:30 – 2:00)
* **What to Say**:
  > *"Normally, when a student gets an answer wrong, they get a static explanation that doesn't stick. Let's click **'💡 Teach Me This'** on the question we missed."*
* **What to Do**:
  1. Click **"💡 Teach Me This"** on the missed Belady's Anomaly question.
  2. When the micro-tutor modal opens, show the 4 grounded sections:
     - **Core Concept**: Clear explanation anchored to Page 2.
     - **Key Idea Callout**: The 1-sentence mental model.
     - **Source Example**: Concrete scenario from the textbook.
     - **Interactive Quick Check**: An on-the-spot active recall question.
  3. Click the correct option on the quick check to trigger the instant green confirmation badge: *"✓ Correct! Concept mastered."*
  4. Close the modal.

---

### 🔄 Scene 5: Standout Feature #2 & #3 — Targeted Adaptive Quiz & Study Plan (2:00 – 2:45)
* **What to Say**:
  > *"Now, instead of making the student repeat questions they already know, they click **'🎯 Generate Targeted Next Quiz'**.*
  > 
  > *Our RAG engine semantically queries ChromaDB exclusively for chunks related to their weak topics (Virtual Memory), generating an adaptive quiz tuned specifically to their gaps.*
  > 
  > *And for long-term retention, one click on **'📋 Personalized Study Plan'** synthesizes their cumulative mastery profile into an actionable 3-step study roadmap with estimated time investments."*
* **What to Do**:
  1. Click **"📋 Personalized Study Plan"**.
  2. Show the generated 3-step prioritized roadmap with time estimates (~45 mins) and specific exercises (e.g. tracing page fault strings).
  3. Click **"🎯 Generate Targeted Next Quiz"** or show the **"📇 Practice Flashcards"** 3D flipping deck.

---

## 🛡️ Technical Architecture & Judge Defense

### 1. Why RAG with ChromaDB instead of just passing the whole PDF to Gemini?
* **Cost & Scalability**: Passing a 200-page textbook on every quiz generation consumes hundreds of thousands of input tokens and incurs high latency.
* **Retrieval Precision**: Chunk-level semantic retrieval ensures the LLM focuses only on the most relevant concepts without getting distracted by textbook boilerplate.
* **Offline Embeddings**: We run `all-MiniLM-L6-v2` locally and offline. Embeddings are fast, free, and operate with zero external API calls.

### 2. How do you prevent hallucinations in academic questions?
* **3-Layer Quality Guard**:
  1. **Strict System Instructions**: The LLM is instructed as a rigorous university examiner and given exact candidate context chunks with page numbers.
  2. **Schema & Logic Validation**: The Quality Guard validates that:
     - Exactly 4 non-empty, non-duplicate options exist.
     - The answer pointer (`A`, `B`, `C`, or `D`) matches the text of `correct_answer` verbatim.
     - No generic cop-outs like *"All of the above"* or *"None of the above"*.
  3. **Lexical & Source Cross-Verification**: Questions and explanations must match key entities present in the source chunk.

### 3. How is adaptability calculated?
* **Configurable Rule-Based Thresholds**:
  - `Strong`: Mastery $\ge 75\%$
  - `Medium`: $50\% \le \text{Mastery} < 75\%$
  - `Weak`: $\text{Mastery} < 50\%$
* **Dynamic Next Difficulty Recommendation**:
  - Score $\ge 80\% \implies$ Advance to **Hard**.
  - $50\% \le \text{Score} < 80\% \implies$ Consolidate at **Medium**.
  - Score $< 50\% \implies$ Drop to **Easy** with targeted concept remediation.

### 4. What happens if the Gemini Free Tier is rate-limited or high demand?
* We built an automatic multi-model failover cascade in `backend/gemini_service.py`:
  `gemini-flash-latest` $\to$ `gemini-3.5-flash` $\to$ `gemini-3.6-flash` $\to$ `gemini-3.7-flash`.
* If a model returns HTTP 503 or 429, the service automatically retries across candidate models with exponential backoff.

---

## 🧪 Verification Commands for Judges

Show judges that the entire codebase is verified and covered with automated test suites:

```bash
# 1. Run Security & Input Validation Audit (Secret isolation, PDF magic bytes, path traversal)
./venv/bin/python backend/test_security_audit.py

# 2. Run Full End-to-End Pipeline (Upload, RAG, Quiz, Grading, Weak Topics, Teach-Me, Adaptive, Plan)
./venv/bin/python backend/test_e2e_flow.py
```

Both test suites exit with `code 0` and display comprehensive validation reports.

