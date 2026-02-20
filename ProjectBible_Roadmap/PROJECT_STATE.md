# Record Health — Project State

**Last Updated:** 2026-02-18 (Sprint 17 complete)
**Platform:** iOS 26.3 / SwiftUI / Xcode
**Test Device:** iPhone 13 Pro Max

---

## Current Scope (POC Phase)

- Local-only document storage (Documents/records/)
- .txt, text-based .pdf, and image (.jpg/.png) import
- OCR via Apple Vision framework for scanned documents
- PDF rendering via PDFKit (multi-page, paged view)
- Voice memo recording with live transcription + audio file storage
- Audio playback with scrubber, skip, and time display
- Per-record AI chat with conversation persistence
- PHI anonymization before any AI API call
- Audit logging of all AI interactions
- Manual tap-to-tag field identification (TapToTagView)
- AI-powered field classification (AIFieldClassifier)
- Encrypted index (AES-256-GCM) + iOS file protection
- Single LLM endpoint (configurable: OpenAI, Anthropic, local)
- No sync, no analytics, no HIPAA claims yet

## Architecture

- **SwiftUI** (iOS 17+)
- **File-based storage:** Documents/records/ with encrypted index_v2.enc (RecordV2 schema)
- **Original files:** Documents/originals/{uuid}.{ext} (PDF, m4a, jpg, etc.)
- **Processed files:** Documents/processed/ (searchable PDFs, AI text)
- **KeychainService:** Consolidated keychain wrapper
- **EncryptionService:** AES-256-GCM via CryptoKit, key in Keychain
- **AppSettings:** ObservableObject for endpoint URL + model name
- **LLMClient:** URLSession-based, supports chat completions API
- **LLMClient+Chat:** Extension for multi-turn conversation calls
- **AIContextBuilder:** Builds system prompts with guardrails, record context, conversation history
- **ConversationStore:** Per-record chat persistence (JSON files)
- **ConversationModels:** Message types, suggested prompts, follow-up prompt hierarchy with deduplication
- **Anonymizer:** PHI redaction (names, DOB, dates, facility) before API calls
- **AuditLogger:** Logs all AI share events (chars sent, redaction types, success/failure)
- **RecordTextPreparer:** Cleans OCR text, assesses confidence level
- **SpeechRecognizer:** AVAudioEngine + SFSpeech for live transcription + audio file recording
- **CanonicalRecordParserV2:** Extracts header metadata from canonical record format
- **PDFKit** for PDF text extraction and rendering

## Voice Recording Pipeline

- Record: AVAudioEngine tap → PCM buffers → SFSpeech (transcription) + AVAudioFile (.caf)
- Stop: AVAssetExportSession converts .caf → compressed .m4a
- Save: RecordsStore creates record, FileStorageManager stores m4a in originals/
- View: RecordDetailView detects .audio → AudioPlayerView (AVAudioPlayer) + transcript below

## AI System Prompt Guardrails

- Document-only answers (no outside medical knowledge speculation)
- No diagnoses, treatment recommendations, or medical advice
- Accept user's framing of document type (no corrections)
- No filler openers ("Absolutely!", "Sure!", etc.)
- Structured responses with emoji section headers (👤 🏥 🔍 📋 💡)
- 5th-grade accessible reading level (not stated to user)
- Mandatory doctor-review closing on every response
- OCR confidence warnings injected when applicable
- Record text truncated at 16k chars
- Sliding window conversation history (last 6 turns)
- PHI anonymization verified before every API call

## Key UI Components

- **RecordDetailView:** Full-screen document viewer with floating modal nav bars
  - Conditional rendering: PDF → Photo → Audio → Text
  - Audio view: AudioPlayerView card + transcript below
- **RecordAskAIView:** Per-record AI chat panel (slides from right, rounded card matching nav bar)
  - KeyboardObserver for keyboard height tracking
  - Input bar always visible above keyboard
  - Keyboard dismiss button
  - Suggested prompt chips (ChatFlowLayout) — display short label, send full prompt
  - Contextual follow-up prompts with intent-based deduplication
  - OCR confidence warning above suggested prompts
  - Share button on AI messages with disclaimer
  - Typing indicator animation
- **AudioPlayerView:** Play/pause, ±15s skip, progress slider, time display
- **VoiceRecorderView:** Record button, live transcript, title/category, save with audio
- **TapToTagView:** Visual field tagging on OCR text blocks
- **PagedPDFView:** Multi-page PDF renderer with page controls

## BodySection Emoji Vocabulary

- 21 cases covering medical specialties + utility sections
- Code-level data model (not yet injected into AI prompt)
- Each case: emoji, displayName, sfSymbol, keywords for topic matching
- Future: selective injection of 2-3 relevant labels per record category

## Known Limitations

- No token-level counting (char-based estimation)
- No background task cancellation
- No multi-record cross-analysis (placeholder exists)
- No text message import yet
- No camera capture with real-time OCR yet
- No bulk import yet
- No Apple Health integration yet
- No embeddings or vector search
- No sync / cloud backup
