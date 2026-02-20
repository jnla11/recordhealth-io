# Record Health — Project Bible

**Purpose:** Living reference for all architectural decisions, conventions, and patterns.

---

## Mission

Enable end-users to be more educated, "doctor-ready" healthcare consumers using their own medical records. The app digitizes, organizes, and explains health documents with AI — without ever giving direct medical advice or suggesting treatment plans.

## Design Principles

1. **Privacy first** — PHI never leaves the device unredacted. All AI requests anonymize patient data.
2. **No medical advice** — AI explains documents; it never diagnoses, prescribes, or recommends.
3. **Accessible language** — All AI output targets 5th-grade reading level without stating so.
4. **Vibe-code workable** — Architecture stays simple enough for a non-professional programmer to maintain.
5. **Incremental compliance** — HIPAA/GDPR/NIST readiness phased in over time, not all at once.

## File Organization

```
RecordHealth/
├── Models/
│   ├── RecordV2.swift              # Core record model (standalone)
│   ├── BodySection.swift           # Medical section emoji vocabulary (21 cases)
│   ├── ConversationModels.swift    # Chat messages, prompts, follow-ups
│   └── SourceFormat.swift          # Import source types (pdf, audio, photo, etc.)
├── Services/
│   ├── KeychainService.swift       # Consolidated keychain (single source)
│   ├── RecordsStore.swift          # Record CRUD + encrypted index management
│   ├── FileStorageManager.swift    # File I/O for records/originals/processed dirs
│   ├── FileStorageManager+AI.swift # AI text + conversation file paths
│   ├── EncryptionService.swift     # AES-256-GCM encryption, Keychain-stored key
│   ├── Anonymizer.swift            # PHI redaction engine
│   ├── AuditLogger.swift           # AI interaction logging
│   ├── RecordTextPreparer.swift    # OCR text cleaning + confidence
│   ├── SpeechRecognizer.swift      # Live transcription + audio file recording
│   └── CanonicalRecordParserV2.swift
├── LLM/
│   ├── AIContextBuilder.swift      # System prompts + context assembly
│   ├── ChatMessage.swift           # ChatMessage struct (role + content)
│   ├── LLMClient.swift             # Base HTTP client
│   ├── LLMClient+Chat.swift        # Chat completions extension
│   └── RecordAskAIView.swift       # Chat UI (includes KeyboardObserver, ChatFlowLayout)
├── Views/
│   ├── RecordDetailView.swift      # Document viewer + AI overlay host (PDF, photo, audio, text)
│   ├── AudioPlayerView.swift       # Audio playback (play/pause, scrub, skip, time)
│   ├── VoiceRecorderView.swift     # Voice recording UI + transcript + save
│   ├── TapToTagView.swift          # Manual field tagging
│   ├── RecordEditView.swift        # Metadata editor
│   └── SettingsView.swift          # API key, endpoint, model config
└── App/
    ├── RecordHealth.swift           # App entry point
    ├── AppSettings.swift            # ObservableObject for settings
    └── SchemaMigration.swift        # V1 → V2 migration
```

## Data Model (RecordV2)

- **Storage:** Encrypted index at Documents/records/index_v2.enc (AES-256-GCM)
- **Text files:** Documents/records/{uuid}.txt (canonical format with header)
- **Original files:** Documents/originals/{uuid}.{ext} (PDF, m4a, jpg, etc.)
- **Processed files:** Documents/processed/ (searchable PDFs, AI text)
- **Schema:** RecordV2 struct with category, source format, tags, dates, char count
- **AI Metadata:** Stored separately (not in index) to avoid migration risk
- **Conversations:** Per-record JSON files via ConversationStore

## Voice Recording Architecture

### Recording Pipeline
1. User taps "Start Recording" in VoiceRecorderView
2. SpeechRecognizer configures AVAudioEngine + SFSpeechRecognitionRequest
3. Audio tap on inputNode feeds both:
   - SFSpeechRecognizer for live transcription → published `transcript`
   - AVAudioFile writer → raw PCM temp .caf file
4. User taps "Stop Recording"
5. AVAssetExportSession converts .caf → compressed .m4a
6. Published `audioFileURL` points to the m4a

### Save Flow
1. VoiceRecorderView calls `store.addRecord(originalFileURL: speechRecognizer.audioFileURL)`
2. RecordsStore creates RecordV2 with `sourceFormat: .audio`
3. FileStorageManager copies m4a to `originals/{uuid}.m4a`
4. Transcript saved as canonical text file

### Playback
- RecordDetailView detects `.audio` source format → shows AudioPlayerView
- AudioPlayerView uses AVAudioPlayer for playback
- Controls: play/pause, ±15s skip, slider scrubber, time display
- Transcript shown below player

## AI Architecture

### Request Flow
1. User taps prompt chip or types question
2. RecordAskAIView calls `sendPrompt()` (shows label) or `sendMessage()` (shows typed text)
3. Record text loaded → cleaned via RecordTextPreparer → anonymized via Anonymizer
4. AIContextBuilder assembles: system prompt + history (6-turn window) + user question
5. LLMClient.chat() sends to configured endpoint
6. Response stored in ConversationStore, audit event logged

### Prompt Architecture
- **Suggested prompts:** 4 per category, defined in SuggestedPrompts.forRecord()
- **Follow-up prompts:** Intent-based hierarchy (FollowUpPrompts), 1-2 after each AI response
- **Deduplication:** Tracks asked intents across conversation; stops suggesting once exhausted
- **Display vs. AI prompt:** Chips show short label; full detailed prompt sent to AI

### System Prompt Sections
1. Role definition (educational only)
2. Communication style (accessible, no filler, accept user's document framing)
3. Response format (5-section emoji headers: 👤 🏥 🔍 📋 💡)
4. Rules (document-only, no advice)
5. Mandatory closing (doctor review reminder)
6. OCR confidence warning (conditional)
7. Record text (truncated at 16k chars)

### BodySection Emoji Vocabulary
- Defined in BodySection.swift — 21 medical section cases
- Each case has: emoji, displayName, sfSymbol, keywords, promptEntry
- `aiPromptVocabulary` static property builds prompt-ready vocabulary block
- Currently used as code-level data model only (not injected into AI prompt)
- Future: inject relevant 2-3 labels per record category, not all 19 medical sections

## Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| Separate AI metadata from RecordV2 index | Avoids forced migration on AI feature changes |
| KeychainService consolidation | Was two implementations; unified to prevent drift |
| RecordV2 as standalone file | Prevents circular dependency issues |
| Custom overlay vs. .sheet for AI panel | iOS sheets always animate bottom-up; needed right-slide + nav bar positioning |
| KeyboardObserver as ObservableObject | Keyboard notifications → published height; input bar padding responds |
| Intent-based follow-up dedup | Keyword matching on labels handles phrasing variations |
| Simultaneous transcription + audio recording | Single AVAudioEngine tap feeds both SFSpeech and file writer |
| PCM → m4a conversion after recording | Raw PCM during recording (reliable), compress to m4a after (smaller file) |
| BodySection not in AI prompt | Dumping 19 categories confused the AI; keep as code-level enum for future selective injection |
| Ask AI button matches modal bar style | Consistent visual language across floating UI elements |

## Conventions

- **Complete file replacements** — Developer works by replacing entire files, not manual patches
- **No partial edits** — Every code delivery is a complete, buildable file
- **One type per file** — Avoid defining multiple public types in one file (prevents redeclaration errors)
- **Sprint-based iteration** — Each sprint has a focused scope with changelog
- **Commit after each sprint** — Detailed commit messages documenting feature additions
