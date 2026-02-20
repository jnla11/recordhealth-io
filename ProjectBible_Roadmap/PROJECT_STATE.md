# Record Health — Project State

**Last Updated:** 2026-02-19 (Sprint 19 complete)
**Platform:** iOS 26.3 / SwiftUI / Xcode
**Test Device:** iPhone 13 Pro Max
**Bundle ID:** com.recordhealth.app

---

## Current Scope (POC Phase)

- Auth0 authentication (email/password; Sign in with Apple pending propagation)
- Cloudflare Worker API gateway (JWT verification, audit logging, OpenAI relay)
- Local-only document storage (Documents/records/)
- .txt, text-based .pdf, and image (.jpg/.png) import
- OCR via Apple Vision framework for scanned documents
- PDF rendering via PDFKit (multi-page, paged view)
- Voice memo recording with live transcription + audio file storage
- Audio playback with scrubber, skip, and time display
- Per-record AI chat with conversation persistence (routed through worker)
- PHI anonymization before any AI API call
- Audit logging of all AI interactions (local + server-side)
- Manual tap-to-tag field identification (TapToTagView)
- AI-powered field classification (AIFieldClassifier)
- Encrypted index (AES-256-GCM) + iOS file protection
- Single LLM endpoint via Cloudflare Worker (fallback to direct API for dev)
- Logout button with confirmation dialog
- Settings view hides API key when authenticated
- No sync, no analytics, no HIPAA claims yet

## Architecture

- **SwiftUI** (iOS 17+)
- **Auth0** for authentication (JWT-based, Universal Login)
- **Cloudflare Worker** as API gateway (verifies JWT, relays to OpenAI, audit logs)
- **Neon Postgres** for server-side user data and audit log
- **File-based local storage:** Documents/records/ with encrypted index_v2.enc (RecordV2 schema)
- **Original files:** Documents/originals/{uuid}.{ext} (PDF, m4a, jpg, etc.)
- **Processed files:** Documents/processed/ (searchable PDFs, AI text)
- **KeychainService:** Consolidated keychain wrapper (apiKey, accessToken, refreshToken)
- **AuthManager:** Auth0 login/logout/token management, publishes isAuthenticated
- **EncryptionService:** AES-256-GCM via CryptoKit, key in Keychain
- **AppSettings:** ObservableObject for endpoint URL + model name (dev fallback)
- **LLMClient:** URLSession-based, routes through worker when authenticated, direct API fallback
- **LLMClient+Chat:** Extension for multi-turn conversation calls (same routing)
- **AIContextBuilder:** Builds system prompts with guardrails, record context, conversation history
- **ConversationStore:** Per-record chat persistence (JSON files)
- **ConversationModels:** Message types, suggested prompts, follow-up prompt hierarchy with deduplication
- **Anonymizer:** PHI redaction (names, DOB, dates, facility) before API calls
- **AuditLogger:** Logs all AI share events locally (chars sent, redaction types, success/failure)
- **RecordTextPreparer:** Cleans OCR text, assesses confidence level
- **SpeechRecognizer:** AVAudioEngine + SFSpeech for live transcription + audio file recording
- **CanonicalRecordParserV2:** Extracts header metadata from canonical record format
- **PDFKit** for PDF text extraction and rendering

## Authentication Flow

- Login: Auth0 Universal Login → browser sheet → JWT credentials
- Token storage: Keychain (.accessToken, .refreshToken)
- API routing: LLMClient reads token from Keychain → routes to worker
- Token renewal: automatic on 401, uses refresh token
- App gating: RecordHealth.swift checks AuthManager.isAuthenticated → LoginView or AppRootView
- Logout: AuthManager clears tokens → isAuthenticated flips → LoginView shown
- Dev fallback: no Auth0 token → uses Keychain API key + Settings endpoint

## Backend

- **Worker URL:** https://recordhealth-api.jason-nolte.workers.dev
- **Database:** Neon Postgres (users, health_records, audit_log tables)
- **Auth0 tenant:** dev-br2xi1kdn6smgx7p.us.auth0.com
- **API audience:** https://recordhealth-api
- **Git repo:** ~/Projects/RecordHealth.IO/recordhealth-api/

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
- All AI requests routed through worker with `store: false`

## Key UI Components

- **LoginView:** Auth0 sign-in screen, shown when not authenticated
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
  - Error bubble display
- **AudioPlayerView:** Play/pause, ±15s skip, progress slider, time display
- **VoiceRecorderView:** Record button, live transcript, title/category, save with audio
- **TapToTagView:** Visual field tagging on OCR text blocks
- **PagedPDFView:** Multi-page PDF renderer with page controls
- **SettingsView:** Logout button (authenticated), API key hidden when authenticated

## BodySection Emoji Vocabulary

- 21 cases covering medical specialties + utility sections
- Code-level data model (not yet injected into AI prompt)
- Each case: emoji, displayName, sfSymbol, keywords for topic matching
- Future: selective injection of 2-3 relevant labels per record category

## Known Limitations

- Sign in with Apple pending Auth0 Apple connection propagation
- ~200-500ms added latency from worker relay
- No token-level counting (char-based estimation)
- No background task cancellation
- No multi-record cross-analysis (placeholder exists)
- No text message import yet
- No camera capture with real-time OCR yet
- No bulk import yet
- No Apple Health integration yet
- No embeddings or vector search
- No sync / cloud backup
- Settings view still shows endpoint/model fields when authenticated (dev fallback, intentional)
- Remove relay token before production
- Remove /debug/secrets endpoint before production
- Lock down CORS to production domain
- OCRService MainActor isolation warnings (pre-existing)
- SpeechRecognizer iOS 18 deprecation warnings (pre-existing)
- TapToTagView UIScreen.main iOS 26 deprecation warnings (pre-existing)
