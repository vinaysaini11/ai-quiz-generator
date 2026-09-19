/**
 * AI Quiz Generator - Frontend State & Interaction Handler
 */

// Application State
const state = {
  documentId: null,
  filename: null,
  totalPages: 0,
  quizId: null,
  questions: [],
  currentQuestionIndex: 0,
  userAnswers: {},      // questionId -> 'A' | 'B' | 'C' | 'D'
  flashcards: [],
  currentFlashcardIndex: 0,
  attemptResults: null,
  selectedQuestionCount: 10,
  isGeneratingAdaptiveQuiz: false
};

// DOM Elements
const elements = {
  statusBadge: document.getElementById('system-status-badge'),
  dropzone: document.getElementById('dropzone'),
  pdfInput: document.getElementById('pdf-input'),
  fileInfo: document.getElementById('file-info'),
  fileName: document.getElementById('file-name'),
  fileSize: document.getElementById('file-size'),
  removeFileBtn: document.getElementById('remove-file-btn'),
  questionCountSelector: document.getElementById('question-count-selector'),
  numQuestionsSelect: document.getElementById('num-questions-select'),
  difficultySelect: document.getElementById('difficulty-select'),
  btnUploadGenerate: document.getElementById('btn-upload-generate'),
  uploadSpinner: document.getElementById('upload-spinner'),
  uploadFeedback: document.getElementById('upload-feedback'),
  
  // Sections
  uploadSection: document.getElementById('upload-section'),
  quizSection: document.getElementById('quiz-section'),
  resultsSection: document.getElementById('results-section'),
  flashcardsSection: document.getElementById('flashcards-section'),
  
  // Quiz Elements
  currentQIndex: document.getElementById('current-q-index'),
  totalQCount: document.getElementById('total-q-count'),
  qTopicBadge: document.getElementById('q-topic-badge'),
  qDiffBadge: document.getElementById('q-diff-badge'),
  quizProgressBar: document.getElementById('quiz-progress-bar'),
  questionText: document.getElementById('question-text'),
  optionsContainer: document.getElementById('options-container'),
  btnPrevQuestion: document.getElementById('btn-prev-question'),
  btnNextQuestion: document.getElementById('btn-next-question'),
  btnSubmitQuiz: document.getElementById('btn-submit-quiz'),
  
  // Results Elements
  resScore: document.getElementById('res-score'),
  resAccuracy: document.getElementById('res-accuracy'),
  resNextDiff: document.getElementById('res-next-diff'),
  knowledgeMapContainer: document.getElementById('knowledge-map-container'),
  reviewAnswersList: document.getElementById('review-answers-list'),
  btnStartAdaptiveQuiz: document.getElementById('btn-start-adaptive-quiz'),
  btnGenerateStudyPlan: document.getElementById('btn-generate-study-plan'),
  btnToggleFlashcards: document.getElementById('btn-toggle-flashcards'),
  btnRestart: document.getElementById('btn-restart'),
  studyPlanContainer: document.getElementById('study-plan-container'),
  spTotalTime: document.getElementById('sp-total-time'),
  spSummary: document.getElementById('sp-summary'),
  spSequenceList: document.getElementById('sp-sequence-list'),
  spRecommendation: document.getElementById('sp-recommendation'),
  
  // Flashcards Elements
  activeFlashcard: document.getElementById('active-flashcard'),
  fcTopicFront: document.getElementById('fc-topic-front'),
  fcFrontText: document.getElementById('fc-front-text'),
  fcTopicBack: document.getElementById('fc-topic-back'),
  fcBackText: document.getElementById('fc-back-text'),
  fcSourceTag: document.getElementById('fc-source-tag'),
  btnFcPrev: document.getElementById('btn-fc-prev'),
  btnFcNext: document.getElementById('btn-fc-next'),
  fcCounter: document.getElementById('fc-counter'),
  btnBackToResults: document.getElementById('btn-back-to-results'),
  
  // Modal Elements
  teachMeModal: document.getElementById('teach-me-modal'),
  modalConceptTitle: document.getElementById('modal-concept-title'),
  btnCloseModal: document.getElementById('btn-close-modal'),
  modalLoading: document.getElementById('modal-loading'),
  modalLoadedContent: document.getElementById('modal-loaded-content'),
  teachExplanation: document.getElementById('teach-explanation'),
  teachKeyIdea: document.getElementById('teach-key-idea'),
  teachExample: document.getElementById('teach-example'),
  teachQuickQ: document.getElementById('teach-quick-q'),
  teachQuickOptions: document.getElementById('teach-quick-options'),
  teachQuickFeedback: document.getElementById('teach-quick-feedback'),
  teachSource: document.getElementById('teach-source'),

  // Adaptive Loading Modal Elements
  adaptiveLoadingModal: document.getElementById('adaptive-loading-modal'),
  adaptiveFocusList: document.getElementById('adaptive-focus-list'),
  adaptiveDiffDisplay: document.getElementById('adaptive-diff-display')
};

let selectedFile = null;

// Initialization
document.addEventListener('DOMContentLoaded', () => {
  checkBackendHealth();
  setupEventListeners();
});

// Check System Health
async function checkBackendHealth() {
  try {
    const res = await fetch('/api/health');
    if (res.ok) {
      elements.statusBadge.textContent = 'Backend Online';
      elements.statusBadge.className = 'badge badge-ready';
    } else {
      elements.statusBadge.textContent = 'API Error';
      elements.statusBadge.className = 'badge badge-weak';
    }
  } catch (err) {
    elements.statusBadge.textContent = 'Offline / Connecting...';
    elements.statusBadge.className = 'badge badge-weak';
  }
}

// Event Listeners
function setupEventListeners() {
  // File Drop & Select
  elements.dropzone.addEventListener('click', (e) => {
    if (!e.target.closest('#remove-file-btn')) {
      elements.pdfInput.click();
    }
  });

  elements.dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    elements.dropzone.classList.add('dragover');
  });

  elements.dropzone.addEventListener('dragleave', () => {
    elements.dropzone.classList.remove('dragover');
  });

  elements.dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    elements.dropzone.classList.remove('dragover');
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  elements.pdfInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelected(e.target.files[0]);
    }
  });

  elements.removeFileBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    clearSelectedFile();
  });

  // Question Count Pill Selector
  if (elements.questionCountSelector) {
    const pillButtons = elements.questionCountSelector.querySelectorAll('.pill-btn');
    pillButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        pillButtons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.selectedQuestionCount = parseInt(btn.dataset.count, 10) || 10;
        if (elements.numQuestionsSelect) {
          elements.numQuestionsSelect.value = state.selectedQuestionCount.toString();
        }
      });
    });
  }

  // Upload & Generate
  elements.btnUploadGenerate.addEventListener('click', onUploadAndGenerate);

  // Quiz Navigation
  elements.btnPrevQuestion.addEventListener('click', () => navigateQuestion(-1));
  elements.btnNextQuestion.addEventListener('click', () => navigateQuestion(1));
  elements.btnSubmitQuiz.addEventListener('click', onSubmitQuiz);

  // Flashcards
  elements.activeFlashcard.addEventListener('click', () => {
    elements.activeFlashcard.classList.toggle('flipped');
  });
  elements.btnFcPrev.addEventListener('click', () => navigateFlashcard(-1));
  elements.btnFcNext.addEventListener('click', () => navigateFlashcard(1));
  elements.btnToggleFlashcards.addEventListener('click', showFlashcardsView);
  elements.btnBackToResults.addEventListener('click', () => showSection('resultsSection'));

  // Adaptive Quiz & Restart
  elements.btnRestart.addEventListener('click', restartWorkflow);
  elements.btnStartAdaptiveQuiz.addEventListener('click', onStartAdaptiveQuiz);
  elements.btnGenerateStudyPlan.addEventListener('click', onGenerateStudyPlan);

  // Modal Close
  elements.btnCloseModal.addEventListener('click', closeModal);
  elements.teachMeModal.addEventListener('click', (e) => {
    if (e.target === elements.teachMeModal) closeModal();
  });

  // Keyboard Navigation for Quiz
  document.addEventListener('keydown', (e) => {
    if (elements.quizSection.classList.contains('active') && !elements.teachMeModal.classList.contains('active')) {
      const q = state.questions[state.currentQuestionIndex];
      if (!q) return;

      const key = e.key.toUpperCase();
      if (['A', 'B', 'C', 'D'].includes(key)) {
        state.userAnswers[q.id] = key;
        renderQuestion();
      } else if (['1', '2', '3', '4'].includes(e.key)) {
        const keyMap = { '1': 'A', '2': 'B', '3': 'C', '4': 'D' };
        state.userAnswers[q.id] = keyMap[e.key];
        renderQuestion();
      } else if (e.key === 'ArrowRight' && state.currentQuestionIndex < state.questions.length - 1) {
        navigateQuestion(1);
      } else if (e.key === 'ArrowLeft' && state.currentQuestionIndex > 0) {
        navigateQuestion(-1);
      }
    }
  });
}

function handleFileSelected(file) {
  if (file.type !== 'application/pdf' && !file.name.endsWith('.pdf')) {
    showBanner('Please select a valid PDF file.', 'error');
    return;
  }
  const maxBytes = 10 * 1024 * 1024; // 10MB limit
  if (file.size > maxBytes) {
    showBanner('File size exceeds the 10MB limit.', 'error');
    return;
  }

  selectedFile = file;
  elements.fileName.textContent = file.name;
  elements.fileSize.textContent = `(${(file.size / (1024 * 1024)).toFixed(2)} MB)`;
  elements.fileInfo.classList.remove('hidden');
  elements.btnUploadGenerate.disabled = false;
  hideBanner();
}

function clearSelectedFile() {
  selectedFile = null;
  elements.pdfInput.value = '';
  elements.fileInfo.classList.add('hidden');
  elements.btnUploadGenerate.disabled = true;
  hideBanner();
}

function showBanner(msg, type = 'info') {
  elements.uploadFeedback.textContent = msg;
  elements.uploadFeedback.className = `feedback-banner ${type}`;
  elements.uploadFeedback.classList.remove('hidden');
}

function hideBanner() {
  elements.uploadFeedback.classList.add('hidden');
}

function showSection(sectionKey) {
  ['uploadSection', 'quizSection', 'resultsSection', 'flashcardsSection'].forEach(key => {
    if (elements[key]) {
      elements[key].classList.add('hidden');
      elements[key].classList.remove('active');
    }
  });
  elements[sectionKey].classList.remove('hidden');
  elements[sectionKey].classList.add('active');
}

// Placeholder Handlers for Stages 3-12
async function onUploadAndGenerate() {
  if (!selectedFile) return;
  elements.btnUploadGenerate.disabled = true;
  elements.uploadSpinner.classList.remove('hidden');
  showBanner('Processing document and generating quiz questions...', 'info');

  try {
    // 1. Upload Document
    const formData = new FormData();
    formData.append('file', selectedFile);
    
    const uploadRes = await fetch('/api/documents/upload', {
      method: 'POST',
      body: formData
    });
    
    if (!uploadRes.ok) {
      const errData = await uploadRes.json();
      throw new Error(errData.detail || 'Failed to upload document');
    }
    
    const uploadData = await uploadRes.json();
    state.documentId = uploadData.document_id;
    state.filename = uploadData.filename;
    state.totalPages = uploadData.total_pages;

    // 2. Generate Quiz
    const genRes = await fetch('/api/quiz/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        document_id: state.documentId,
        num_questions: state.selectedQuestionCount || parseInt(elements.numQuestionsSelect.value, 10) || 10,
        question_count: state.selectedQuestionCount || 10,
        difficulty: elements.difficultySelect.value,
        include_flashcards: true
      })
    });

    if (!genRes.ok) {
      const errData = await genRes.json();
      throw new Error(errData.detail || 'Failed to generate questions');
    }

    const quizData = await genRes.json();
    state.quizId = quizData.quiz_id;
    state.questions = quizData.questions || [];
    state.flashcards = quizData.flashcards || [];
    state.currentQuestionIndex = 0;
    state.userAnswers = {};

    renderQuestion();
    showSection('quizSection');
  } catch (err) {
    showBanner(err.message, 'error');
  } finally {
    elements.btnUploadGenerate.disabled = false;
    elements.uploadSpinner.classList.add('hidden');
  }
}

function renderQuestion() {
  if (!state.questions.length) return;
  const q = state.questions[state.currentQuestionIndex];
  
  elements.currentQIndex.textContent = state.currentQuestionIndex + 1;
  elements.totalQCount.textContent = state.questions.length;
  elements.qTopicBadge.textContent = q.topic || 'General';
  elements.qDiffBadge.textContent = q.difficulty ? q.difficulty.toUpperCase() : 'MEDIUM';
  elements.questionText.textContent = q.question || q.question_text;
  
  const progressPct = ((state.currentQuestionIndex + 1) / state.questions.length) * 100;
  elements.quizProgressBar.style.width = `${progressPct}%`;

  // Render Options
  elements.optionsContainer.innerHTML = '';
  const options = q.options || {
    A: q.option_a,
    B: q.option_b,
    C: q.option_c,
    D: q.option_d
  };

  const currentSelection = state.userAnswers[q.id];

  Object.entries(options).forEach(([key, text]) => {
    const optDiv = document.createElement('div');
    optDiv.className = `option-item ${currentSelection === key ? 'selected' : ''}`;
    optDiv.innerHTML = `
      <span class="option-key">${key}</span>
      <span class="option-text">${text}</span>
    `;
    optDiv.addEventListener('click', () => {
      state.userAnswers[q.id] = key;
      renderQuestion();
    });
    elements.optionsContainer.appendChild(optDiv);
  });

  // Button States
  elements.btnPrevQuestion.disabled = state.currentQuestionIndex === 0;
  const isLast = state.currentQuestionIndex === state.questions.length - 1;
  elements.btnNextQuestion.classList.toggle('hidden', isLast);
  elements.btnSubmitQuiz.classList.toggle('hidden', !isLast);
}

function navigateQuestion(direction) {
  const newIndex = state.currentQuestionIndex + direction;
  if (newIndex >= 0 && newIndex < state.questions.length) {
    state.currentQuestionIndex = newIndex;
    renderQuestion();
  }
}

async function onSubmitQuiz() {
  if (Object.keys(state.userAnswers).length < state.questions.length) {
    const confirmSubmit = confirm("You have unanswered questions. Are you sure you want to submit?");
    if (!confirmSubmit) return;
  }

  const payload = {
    quiz_id: state.quizId,
    answers: Object.entries(state.userAnswers).map(([qid, opt]) => ({
      question_id: qid,
      selected_option: opt
    }))
  };

  try {
    const res = await fetch('/api/quiz/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error('Submission failed');
    const resultData = await res.json();
    state.attemptResults = resultData;
    renderResults(resultData);
    showSection('resultsSection');
  } catch (err) {
    alert(`Error submitting quiz: ${err.message}`);
  }
}

function renderResults(results) {
  elements.resScore.textContent = `${results.score} / ${results.total_questions}`;
  elements.resAccuracy.textContent = `${Math.round(results.accuracy_percentage)}%`;
  elements.resNextDiff.textContent = (results.recommended_next_difficulty || 'Medium').toUpperCase();

  // Knowledge Map
  elements.knowledgeMapContainer.innerHTML = '';
  const breakdown = results.topic_breakdown || {};
  Object.entries(breakdown).forEach(([topic, stats]) => {
    const row = document.createElement('div');
    row.className = 'km-row';
    const statusClass = stats.status === 'Strong' ? 'badge-strong' : (stats.status === 'Medium' ? 'badge-medium' : 'badge-weak');
    const statusIcon = stats.badge || (stats.status === 'Strong' ? '🟢' : (stats.status === 'Medium' ? '🟡' : '🔴'));
    const barColor = stats.status === 'Strong' ? 'var(--success)' : (stats.status === 'Medium' ? 'var(--warning)' : 'var(--danger)');
    
    row.innerHTML = `
      <div style="flex: 1; margin-right: 16px;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
          <span class="km-topic">${topic}</span>
          <span style="font-size: 13px; font-weight: 600;">${Math.round(stats.accuracy)}% (${stats.correct}/${stats.total})</span>
        </div>
        <div style="height: 6px; background: #e2e8f0; border-radius: 99px; overflow: hidden;">
          <div style="height: 100%; width: ${Math.max(stats.accuracy, 4)}%; background: ${barColor}; border-radius: 99px;"></div>
        </div>
      </div>
      <div class="km-stats">
        <span class="badge ${statusClass}">${statusIcon} ${stats.status}</span>
      </div>
    `;
    elements.knowledgeMapContainer.appendChild(row);
  });

  // Review List
  elements.reviewAnswersList.innerHTML = '';
  (results.results || []).forEach((item, idx) => {
    const div = document.createElement('div');
    div.className = `review-item ${item.is_correct ? 'is-correct' : 'is-wrong'}`;
    div.innerHTML = `
      <div class="review-q-text">Q${idx + 1}. ${item.question}</div>
      <div class="review-ans-diff">
        <span>Your Answer: <strong>${item.selected_option || 'None'}</strong></span>
        <span>Correct Answer: <strong>${item.correct_option}</strong></span>
      </div>
      <div class="review-explanation"><strong>Explanation:</strong> ${item.explanation}</div>
      ${item.source_reference ? `<div class="review-source">Reference: ${item.source_reference}</div>` : ''}
      ${!item.is_correct ? `
        <div class="review-actions">
          <button class="btn btn-secondary btn-sm" onclick="openTeachMeModal('${item.question_id}', '${item.selected_option}', '${item.topic}')">
            💡 Teach Me This
          </button>
        </div>` : ''}
    `;
    elements.reviewAnswersList.appendChild(div);
  });
}

function showFlashcardsView() {
  if (!state.flashcards.length) {
    alert("No flashcards generated for this document.");
    return;
  }
  state.currentFlashcardIndex = 0;
  renderFlashcard();
  showSection('flashcardsSection');
}

function renderFlashcard() {
  const fc = state.flashcards[state.currentFlashcardIndex];
  elements.activeFlashcard.classList.remove('flipped');
  elements.fcTopicFront.textContent = fc.topic || 'Flashcard';
  elements.fcFrontText.textContent = fc.front;
  elements.fcTopicBack.textContent = 'Answer';
  elements.fcBackText.textContent = fc.back;
  elements.fcSourceTag.textContent = fc.source_reference ? `Source: ${fc.source_reference}` : '';
  elements.fcCounter.textContent = `${state.currentFlashcardIndex + 1} / ${state.flashcards.length}`;
}

function navigateFlashcard(direction) {
  const newIdx = state.currentFlashcardIndex + direction;
  if (newIdx >= 0 && newIdx < state.flashcards.length) {
    state.currentFlashcardIndex = newIdx;
    renderFlashcard();
  }
}

// "Teach Me This" Modal Handler
window.openTeachMeModal = async function(questionId, selectedOpt, topic) {
  elements.teachMeModal.classList.remove('hidden');
  elements.modalLoading.classList.remove('hidden');
  elements.modalLoadedContent.classList.add('hidden');
  elements.modalConceptTitle.textContent = `Concept Review: ${topic}`;

  try {
    const res = await fetch('/api/quiz/teach-me', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        document_id: state.documentId,
        question_id: questionId,
        user_answer: selectedOpt,
        topic: topic
      })
    });
    if (!res.ok) throw new Error("Could not retrieve grounded explanation.");
    const data = await res.json();
    
    elements.teachExplanation.textContent = data.explanation;
    elements.teachKeyIdea.textContent = data.key_idea;
    elements.teachExample.textContent = data.example || 'N/A';
    elements.teachSource.textContent = `Source Reference: ${data.source_reference || 'Study Material'}`;
    
    // Quick check question
    if (data.quick_check) {
      elements.teachQuickQ.textContent = data.quick_check.question;
      elements.teachQuickOptions.innerHTML = '';
      elements.teachQuickFeedback.classList.add('hidden');
      (data.quick_check.options || []).forEach(opt => {
        const btn = document.createElement('button');
        btn.className = 'quick-opt-btn';
        btn.textContent = opt;
        btn.onclick = () => {
          if (opt.toLowerCase().trim() === (data.quick_check.correct_answer || '').toLowerCase().trim()) {
            elements.teachQuickFeedback.textContent = "✓ Correct! Concept mastered.";
            elements.teachQuickFeedback.className = "quick-feedback correct";
          } else {
            elements.teachQuickFeedback.textContent = `✗ Not quite. The correct answer is: ${data.quick_check.correct_answer}`;
            elements.teachQuickFeedback.className = "quick-feedback wrong";
          }
          elements.teachQuickFeedback.classList.remove('hidden');
        };
        elements.teachQuickOptions.appendChild(btn);
      });
    }

    elements.modalLoading.classList.add('hidden');
    elements.modalLoadedContent.classList.remove('hidden');
  } catch (err) {
    elements.modalLoading.textContent = `Error: ${err.message}`;
  }
};

function closeModal() {
  elements.teachMeModal.classList.add('hidden');
}

async function onStartAdaptiveQuiz() {
  if (!state.attemptResults || state.isGeneratingAdaptiveQuiz) return;
  state.isGeneratingAdaptiveQuiz = true;

  const btn = elements.btnStartAdaptiveQuiz;
  btn.disabled = true;

  const weakTopics = state.attemptResults.weak_topics || [];
  const nextDiff = state.attemptResults.recommended_next_difficulty || 'medium';

  // 1. Populate dynamic in-page loading modal
  if (elements.adaptiveFocusList) {
    elements.adaptiveFocusList.innerHTML = '';
    const topicsToShow = (weakTopics && weakTopics.length > 0)
      ? weakTopics
      : ((state.attemptResults.medium_topics && state.attemptResults.medium_topics.length > 0)
          ? state.attemptResults.medium_topics
          : ['Consolidating Core Concepts']);

    topicsToShow.forEach(topic => {
      const li = document.createElement('li');
      li.textContent = `• ${topic}`;
      elements.adaptiveFocusList.appendChild(li);
    });
  }

  if (elements.adaptiveDiffDisplay) {
    elements.adaptiveDiffDisplay.textContent = nextDiff.charAt(0).toUpperCase() + nextDiff.slice(1);
  }

  // 2. Display the in-page loading modal (replacing browser alert)
  if (elements.adaptiveLoadingModal) {
    elements.adaptiveLoadingModal.classList.remove('hidden');
  }

  try {
    const res = await fetch('/api/quiz/adaptive-generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        document_id: state.documentId,
        previous_attempt_id: state.attemptResults.attempt_id,
        target_topics: weakTopics,
        target_difficulty: nextDiff,
        num_questions: state.selectedQuestionCount || 10,
        question_count: state.selectedQuestionCount || 10
      })
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || 'Failed to generate targeted adaptive quiz.');
    }

    const adaptiveQuiz = await res.json();
    state.quizId = adaptiveQuiz.quiz_id;
    state.questions = adaptiveQuiz.questions;
    state.currentQuestionIndex = 0;
    state.userAnswers = {};
    renderQuestion();
    showSection('quizSection');
  } catch (err) {
    alert(`Could not generate targeted quiz: ${err.message}`);
  } finally {
    if (elements.adaptiveLoadingModal) {
      elements.adaptiveLoadingModal.classList.add('hidden');
    }
    btn.disabled = false;
    state.isGeneratingAdaptiveQuiz = false;
  }
}

function restartWorkflow() {
  clearSelectedFile();
  state.documentId = null;
  state.quizId = null;
  state.questions = [];
  state.flashcards = [];
  state.userAnswers = {};
  showSection('uploadSection');
}

async function onGenerateStudyPlan() {
  if (!state.documentId) return;
  const btn = elements.btnGenerateStudyPlan;
  const originalText = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Creating Plan...';
  elements.studyPlanContainer.classList.remove('hidden');
  elements.spSummary.textContent = "Synthesizing your assessment profile and creating personalized roadmap...";
  elements.spSequenceList.innerHTML = '<div style="padding: 16px; text-align: center; color: var(--text-muted);"><span class="spinner"></span> Consulting AI Academic Strategist...</div>';
  elements.spRecommendation.textContent = "";

  try {
    const attemptId = state.attemptResults ? state.attemptResults.attempt_id : null;
    const res = await fetch(`/api/documents/${state.documentId}/study-plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ attempt_id: attemptId })
    });
    if (!res.ok) throw new Error("Could not generate study plan.");
    const data = await res.json();
    renderStudyPlan(data);
  } catch (err) {
    elements.spSummary.textContent = `Error: ${err.message}`;
    elements.spSequenceList.innerHTML = '';
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalText;
  }
}

function renderStudyPlan(data) {
  const plan = data.plan || {};
  elements.studyPlanContainer.classList.remove('hidden');
  elements.spTotalTime.textContent = `Est. ${plan.total_estimated_time_minutes || 30} mins`;
  elements.spSummary.textContent = plan.summary || "Here is your personalized roadmap to achieve complete mastery:";
  
  elements.spSequenceList.innerHTML = '';
  (plan.study_sequence || []).forEach(step => {
    const card = document.createElement('div');
    card.className = 'study-step-card';
    const isHigh = (step.priority || '').toLowerCase() === 'high';
    const prioColor = isHigh ? '#b91c1c' : '#0369a1';
    const prioBg = isHigh ? '#fee2e2' : '#e0f2fe';
    card.innerHTML = `
      <div class="step-badge">${step.step}</div>
      <div class="step-content">
        <div class="step-header">
          <span class="step-topic">${step.topic}</span>
          <span class="badge" style="background:${prioBg}; color:${prioColor}; font-size:11px;">${step.priority || 'High'} Priority</span>
        </div>
        <div class="step-action">${step.action}</div>
        <div class="step-meta">
          <span>⏱️ ${step.estimated_minutes || 10} minutes</span>
        </div>
      </div>
    `;
    elements.spSequenceList.appendChild(card);
  });

  if (plan.practice_recommendation) {
    elements.spRecommendation.innerHTML = `<strong>💡 Recommended Practice Routine:</strong> ${plan.practice_recommendation}`;
    elements.spRecommendation.classList.remove('hidden');
  } else {
    elements.spRecommendation.classList.add('hidden');
  }
  
  elements.studyPlanContainer.scrollIntoView({ behavior: 'smooth' });
}


