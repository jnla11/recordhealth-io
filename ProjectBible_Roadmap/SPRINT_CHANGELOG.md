# Record Health — Sprint Changelog

---

## Sprint 19 — Logout + Settings Cleanup + Sign in with Apple Config
**Date:** 2026-02-19
**Status:** ✅ Complete

### Changes

#### SettingsView
- Sign Out button added (Account section, visible when authenticated only)
- Confirmation dialog before logout ("Your records stay on this device")
- API key field hidden when authenticated
- LLM Configuration footer is contextual (worker vs. direct mode)

#### AppRootView
- Fixed SettingsView initializer to pass settings: AppSettings.shared

#### Sign in with Apple
- Key created in Apple Developer portal
- Apple social connection configured in Auth0 (Team ID, Services ID, Key ID, .p8)
- Connection enabled on RecordHealth (Native) application
- Will appear in Universal Login browser sheet once propagated

### Files Modified
- SettingsView.swift
- AppRootView.swift

### Known Issues
- Sign in with Apple pending Auth0 Apple connection propagation

---

## Sprint 18 — Auth0 Integration + Cloudflare Worker API Gateway
**Date:** 2026-02-19
**Status:** ✅ Complete

### Changes

#### Cloudflare Worker API (recordhealth-api)
- Serverless API gateway on Cloudflare Workers
- Neon Postgres database (users, health_records, audit_log tables)
- Auth0 JWT verification via JWKS (jose library)
- Auto-creates user on first Auth0 login (ensureUser)
- /ai/chat endpoint: relays Chat Completions format to OpenAI with `store: false`
- /ai/query endpoint: AI queries against stored health records
- Full CRUD for health_records (user-scoped when authenticated)
- Audit logging on every data access
- Relay token fallback for dev/terminal testing
- Deployed: https://recordhealth-api.jason-nolte.workers.dev

#### Auth0 Authentication (iOS)
- Auth0 SDK integrated via Swift Package Manager (Auth0 2.17.1)
- Auth0.plist with tenant domain and client ID
- Sign in with Apple capability added (Apple Developer Program enrolled)
- URL scheme registered: com.recordhealth.app
- AuthManager.swift: login, logout, token storage, silent renewal
- LoginView.swift: sign-in screen shown when not authenticated
- RecordHealth.swift: gates on authManager.isAuthenticated

#### LLM Client Rerouting
- LLMClient.resolveAuth() reads Auth0 token directly from Keychain
- Worker URL hardcoded in LLMClient (avoids MainActor concurrency issues)
- When authenticated: routes all AI calls through Cloudflare Worker
- When not authenticated: falls back to Settings endpoint + Keychain API key
- Automatic token renewal on 401 response (retry once)

#### KeychainService Updates
- Added .accessToken key (auth0_access_token)
- Added .refreshToken key (auth0_refresh_token)

#### Database Schema Updates
- users.email changed to nullable (Auth0 tokens don't always include email)

### Files Created (iOS)
- AuthManager.swift (Auth0 integration)
- LoginView.swift (sign-in screen)
- Auth0.plist (Auth0 configuration)

### Files Modified (iOS)
- LLMClient.swift (worker routing via resolveAuth)
- LLMClient+Chat.swift (same worker routing)
- KeychainService.swift (added accessToken, refreshToken keys)
- RecordHealth.swift (auth gating)

### Files Created (Worker)
- src/index.js (complete API with /ai/chat endpoint)
- schema.sql (database schema)
- wrangler.toml (worker config)
- package.json (dependencies)
- README.md (setup documentation)
- SECRETS.md (local reference, gitignored)
- .gitignore

### Known Issues
- No logout button in app UI yet
- Settings view still shows API key field when authenticated
- Sign in with Apple not yet configured (Auth0 social connection pending)
- Debug print statements in login() need removal

---

## Sprint 17 — Voice Recording Audio Storage + Playback
**Date:** 2026-02-18
**Status:** ✅ Complete

### Changes

#### Audio File Recording (SpeechRecognizer)
- Simultaneous audio file recording during live transcription
- AVAudioEngine tap feeds both SFSpeechRecognizer and AVAudioFile writer
- Records raw PCM to temp .caf file during recording
- AVAssetExportSession converts to compressed .m4a after stopping
- New published properties: `audioFileURL` (m4a path), `isProcessingAudio`
- Temp file cleanup on clear/restart

#### Voice Recorder Updates (VoiceRecorderView)
- Passes `audioFileURL` to `store.addRecord(originalFileURL:)` on save
- Save button disabled during audio processing
- Processing indicator shown during m4a conversion
- Button text: "Save Recording", footer mentions audio saved for playback

#### Audio Playback (AudioPlayerView — NEW)
- Play/pause with large circle button
- ±15 second skip forward/back
- Progress slider with current/total time display
- Waveform icon (animated when playing)
- AVAudioPlayer-based, MainActor-isolated timer updates
- Auto-stops and resets on playback completion

#### Record Detail Audio View (RecordDetailView)
- Detects `.audio` source format with stored audio file
- Shows AudioPlayerView in card above transcript
- Ask AI button available on audio records
- View chain: PDF → Photo → Audio → Text fallback

### Files Modified/Created
- SpeechRecognizer.swift (audio file recording added)
- VoiceRecorderView.swift (passes audio URL on save)
- AudioPlayerView.swift (new — playback component)
- RecordDetailView.swift (audio record view added)

---

## Sprint 16a — BodySection Emoji Vocabulary + UI Tweaks
**Date:** 2026-02-18
**Status:** ✅ Complete

### Changes

#### BodySection Emoji Vocabulary (NEW)
- 21-case enum: neuro, eye, entOral, cardio, vascular, pulmonary, gi, metabolic, msk, derm, uro, mental, reproF, reproM, obCare, peds, labs, imaging, meds, documents, ai
- Each case: emoji, displayName, sfSymbol, keywords, promptEntry
- `aiPromptVocabulary` static property for prompt-ready vocabulary block
- Code-level data model only — NOT injected into AI prompt (caused regressions)

#### UI Tweaks
- OCR confidence warning moved above suggested prompt chips (RecordAskAIView)
- Ask AI button restyled to match modal bar aesthetic (RecordDetailView)
  - Uses modalGradient, cornerRadius 20, categoryBorder stroke, matching shadow

### Files Modified/Created
- BodySection.swift (new — emoji vocabulary enum)
- RecordAskAIView.swift (warning/prompts order swap)
- RecordDetailView.swift (Ask AI button restyle)

### Notes
- AIContextBuilder unchanged — original Sprint 15b prompt preserved
- Injecting all 19 medical categories into AI prompt confused the model
- Future: selectively inject 2-3 relevant labels per record category

---

## Sprint 15b — Per-Record AI Chat UI Redesign
**Date:** 2026-02-18
**Status:** ✅ Complete

### Changes

#### Chat UI Redesign (RecordAskAIView)
- Complete rewrite matching iPhone mockup aesthetic
- "Record Assistant" header with brain.head.profile icon
- Light gradient background for readability
- High-contrast AI bubbles (solid blue-gray) replacing transparent overlays
- User bubbles with blue gradient + white text
- Paper plane send button with blue circle
- Horizontal-wrapping prompt chips via ChatFlowLayout (custom Layout protocol)
- Share button on every AI message (ShareLink with formatted text + disclaimer)
- Typing indicator (animated dots)
- Error bubble display

#### Modal Presentation
- AI panel slides from right (`.transition(.move(edge: .trailing))`)
- Rounded card matching top nav bar styling (20pt radius, same border + margins)
- Positioned below top nav bar via spacer
- Dim background overlay, tap to dismiss
- Starts at 65% height, expands on interaction or keyboard

#### Keyboard Handling
- KeyboardObserver class (ObservableObject) tracks keyboard height via notifications
- `.padding(.bottom, keyboard.height)` pushes input bar above keyboard
- Keyboard dismiss button (`keyboard.chevron.compact.down`) appears when keyboard visible
- `.scrollDismissesKeyboard(.interactively)` on chat scroll view
- Auto-scroll to bottom when keyboard appears

#### Suggested Prompts
- 4 prompts per record category (labs, imaging, visit notes, prescriptions, pathology, default)
- Document-focused: "Summarize", "Explain findings", "Translate to plain English", "Ask my doctor?"
- **Display vs. AI prompt split:** Chips show short label in chat bubble, send full detailed prompt to AI
- Doctor prompt scoped to document content only

#### Follow-Up Prompts
- 1-2 contextual chips after each AI response
- Intent-based hierarchy: summarize → abnormal values → translate → doctor questions → etc.
- Deduplication: tracks all intents asked in conversation, filters already-asked
- Visually distinct: subtle blue border, icon, slightly transparent
- Empty array once all intents exhausted (no repeated suggestions)

#### System Prompt Updates (AIContextBuilder)
- No filler openers ("Absolutely!", "Sure!", "Great question!", etc.)
- Structured responses with emoji section headers (👤 🏥 🔍 📋 💡)
- Inline emojis for comprehension (✅ normal, ⚠️ abnormal, 💊 medication)
- 5th-grade accessible reading level (implicit, not stated to user)
- Communication style block: short sentences, common words, everyday analogies
- Document-only answers enforced
- Mandatory doctor-review closing (varied wording)

#### OCR Warning
- Full-width card with large icon, bold title, descriptive subtitle
- `eye.trianglebadge.exclamationmark.fill` for OCR docs
- `doc.questionmark.fill` for low-text docs
- Orange-tinted background with visible border

### Files Modified/Created
- RecordAskAIView.swift (complete rewrite)
- RecordDetailView.swift (overlay host, right-slide transition)
- ConversationModels.swift (prompts, follow-ups, deduplication)
- AIContextBuilder.swift (system prompt overhaul)

### Build Issues Resolved
- `ChatMessage` was defined in both `ChatMessage.swift` and `AIContextBuilder.swift` — removed from AIContextBuilder
- `AIContextBuilder` was defined in both `AIContextBuilder.swift` and `ChatMessage.swift` — cleaned ChatMessage.swift to struct only
- Enforced one-type-per-file convention going forward

---

## Sprint 15a — RecordV2 Extraction + Keychain Consolidation
**Date:** 2026-02-18
**Status:** ✅ Complete

### Changes
- Extracted RecordV2 model to standalone file (was embedded, caused circular deps)
- Consolidated two Keychain implementations (KeychainHelper + KeychainManager) into single KeychainService
- Added migration helper: KeychainService reads from old keys, writes to new
- Updated all dependent files: SettingsView, RefinementView, LLMClient, AppSettings
- Resolved FlowLayout naming conflict (renamed to avoid collision)

### Files Modified
- RecordV2.swift (new standalone file)
- KeychainService.swift (new consolidated service)
- SettingsView.swift, RefinementView.swift, LLMClient.swift, SchemaMigration.swift

### Notes
- API key requires re-entry after Keychain migration (expected, one-time)

---

## Pre-Sprint 15 (Prior Work Summary)

### Core Infrastructure
- RecordV2 data model with category, source format, tags, dates
- File-based storage with index.json metadata
- PDF import + text extraction (PDFKit)
- Image import with OCR (Apple Vision)
- Multi-page PDF viewer (PagedPDFView) with floating nav bars

### AI Features
- LLMClient for OpenAI-compatible chat completions
- Anonymizer for PHI redaction before API calls
- AuditLogger for AI interaction tracking
- RecordTextPreparer for OCR text cleaning + confidence assessment
- ConversationStore for per-record chat persistence

### UI
- Dashboard with patient picker
- Record list with category filtering
- Record detail view with floating modal nav bars
- TapToTagView for manual field identification
- Settings view for API key, endpoint, model configuration
- Schema migration (V1 → V2)
