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
6. **Server-side secrets** — API keys and sensitive credentials live on the server, never on the device.

## File Organization

```
RecordHealth/
├── Models/
│   ├── RecordV2.swift              # Core record model (standalone)
│   ├── BodySection.swift           # Medical section emoji vocabulary (21 cases)
│   ├── ConversationModels.swift    # Chat messages, prompts, follow-ups
│   └── SourceFormat.swift          # Import source types (pdf, audio, photo, etc.)
├── Services/
│   ├── AuthManager.swift           # Auth0 login/logout/token management (Sprint 18)
│   ├── KeychainService.swift       # Consolidated keychain (apiKey, accessToken, refreshToken)
│   ├── RecordsStore.swift          # Record CRUD + encrypted index management
│   ├── FileStorageManager.swift    # File I/O for records/originals/processed dirs
│   ├── FileStorageManager+AI.swift # AI text + conversation file paths
│   ├── EncryptionService.swift     # AES-256-GCM encryption, Keychain-stored key
│   ├── Anonymizer.swift            # PHI redaction engine
│   ├── AuditLogger.swift           # AI interaction logging (local)
│   ├── RecordTextPreparer.swift    # OCR text cleaning + confidence
│   ├── SpeechRecognizer.swift      # Live transcription + audio file recording
│   └── CanonicalRecordParserV2.swift
├── LLM/
│   ├── AIContextBuilder.swift      # System prompts + context assembly
│   ├── ChatMessage.swift           # ChatMessage struct (role + content)
│   ├── LLMClient.swift             # Base HTTP client (routes through worker when authenticated)
│   ├── LLMClient+Chat.swift        # Chat completions extension (same worker routing)
│   └── RecordAskAIView.swift       # Chat UI (includes KeyboardObserver, ChatFlowLayout)
├── Views/
│   ├── LoginView.swift             # Auth0 sign-in screen (Sprint 18)
│   ├── RecordDetailView.swift      # Document viewer + AI overlay host (PDF, photo, audio, text)
│   ├── AudioPlayerView.swift       # Audio playback (play/pause, scrub, skip, time)
│   ├── VoiceRecorderView.swift     # Voice recording UI + transcript + save
│   ├── TapToTagView.swift          # Manual field tagging
│   ├── RecordEditView.swift        # Metadata editor
│   └── SettingsView.swift          # API key, endpoint, model config
└── App/
    ├── RecordHealth.swift           # App entry point (auth-gated — Sprint 18)
    ├── AppSettings.swift            # ObservableObject for settings
    └── SchemaMigration.swift        # V1 → V2 migration
```

## Backend Architecture (Sprint 18)

### Overview

```
iOS App → Auth0 (Sign in with Apple / email) → JWT
       → Cloudflare Worker (edge) → verifies JWT via JWKS
                                   → Neon Postgres (user data, audit log)
                                   → OpenAI API (AI summaries, store: false)
```

The Cloudflare Worker is the sole entry point for all API calls. The OpenAI API key lives on the server and never touches the device. Every request is authenticated, user-scoped, and audit logged.

### Backend Stack

| Layer | Service | Purpose |
|-------|---------|---------|
| Runtime | Cloudflare Workers | Edge serverless API |
| Database | Neon | Serverless Postgres via WebSocket |
| AI | OpenAI Chat Completions API | Health record summarization |
| Auth | Auth0 | Identity management, JWT issuance |
| Auth method | Email/password (Sign in with Apple pending) | Primary login |

### Worker Project

```
recordhealth-api/
├── src/
│   └── index.js          ← Worker entry point (all routes and logic)
├── schema.sql            ← Database schema (run in Neon SQL Editor)
├── wrangler.toml         ← Cloudflare Worker configuration
├── package.json          ← Dependencies (@neondatabase/serverless, jose)
├── SECRETS.md            ← Local-only secrets reference (gitignored)
├── .gitignore
└── README.md
```

**Worker URL:** `https://recordhealth-api.jason-nolte.workers.dev`

### Worker Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /health | No | Service health check |
| GET | /health/db | No | Database connectivity check |
| GET | /debug/secrets | No | Confirms loaded secrets (remove before production) |
| GET | /me | Yes | Current user profile |
| GET | /records | Yes | List health records (user-scoped) |
| GET | /records/:id | Yes | Get single record |
| POST | /records | Yes | Create record |
| PUT | /records/:id | Yes | Update record |
| DELETE | /records/:id | Yes | Delete record |
| POST | /ai/chat | Yes | Chat Completions relay (used by iOS app) |
| POST | /ai/query | Yes | AI query against stored records |
| POST | /ai/test | Yes | Standalone OpenAI test |

### Worker Secrets (Cloudflare)

| Secret | Description |
|--------|-------------|
| DATABASE_URL | Neon Postgres connection string (?sslmode=require) |
| OPENAI_API_KEY | OpenAI API key |
| JWT_SIGNING_SECRET | JWT signing secret |
| RELAY_AUTH_TOKEN | Dev/testing bypass token |

### Database Schema (Neon)

- **users** — App users. Linked to Auth0 via `auth0_sub`. Email is nullable. Auto-created on first authenticated request.
- **health_records** — Health data. `content` is JSONB, flexible per `record_type`. Scoped to user via `user_id`.
- **audit_log** — Every read, create, update, delete, and AI query is logged with timestamp, user, action, and metadata.

### Auth0 Configuration

| Setting | Value |
|---------|-------|
| Tenant domain | dev-br2xi1kdn6smgx7p.us.auth0.com |
| Application type | Native/Mobile |
| Application name | RecordHealth |
| API identifier (audience) | https://recordhealth-api |
| Signing algorithm | RS256 |
| Bundle ID / callback URL scheme | com.recordhealth.app |

Config file: `Auth0.plist` in Xcode project root (keys: `Domain`, `ClientId`).

## Authentication Architecture (Sprint 18)

### Login Flow
1. User taps "Sign In" on LoginView
2. Auth0 SDK opens browser sheet with Universal Login
3. User authenticates (email/password, or Sign in with Apple when configured)
4. Auth0 returns JWT credentials to the app
5. AuthManager stores access token + refresh token in Keychain
6. RecordHealth.swift observes `isAuthenticated` → shows AppRootView

### API Request Flow (Authenticated)
1. LLMClient.resolveAuth() checks Keychain for Auth0 access token
2. If token exists → routes to `https://recordhealth-api.jason-nolte.workers.dev/ai/chat`
3. Worker verifies JWT against Auth0 JWKS public keys
4. Worker finds/creates user in Neon (ensureUser)
5. Worker forwards chat request to OpenAI with `store: false`
6. Worker logs the request to audit_log
7. Response returned to app in standard Chat Completions format

### API Request Flow (Dev/Fallback)
1. No Auth0 token in Keychain
2. LLMClient falls back to Keychain API key + configured endpoint from AppSettings
3. Direct call to OpenAI (no worker, no audit log)

### Token Management
- Access token: stored in Keychain as `.accessToken`, read directly by LLMClient (avoids MainActor issues)
- Refresh token: stored in Keychain as `.refreshToken`, used for silent renewal
- On 401 response: LLMClient calls AuthManager.renewToken(), retries once
- On app launch: AuthManager loads stored tokens, attempts background renewal

### Keychain Keys

| Key | Raw Value | Purpose |
|-----|-----------|---------|
| .apiKey | llm_api_key | OpenAI key for dev/fallback mode |
| .accessToken | auth0_access_token | Auth0 JWT for worker authentication |
| .refreshToken | auth0_refresh_token | Auth0 refresh token for silent renewal |

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
5. LLMClient.chat() resolves auth → routes to worker or direct API
6. Response stored in ConversationStore, audit event logged (local + server-side)

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
| Cloudflare Worker as API gateway | OpenAI key never touches device; all requests audited; user-scoped data |
| Auth0 for identity | Handles Sign in with Apple, token issuance, refresh — no custom auth code |
| JWT verification via JWKS | Worker verifies tokens against Auth0 public keys; no shared secrets needed |
| Keychain-based token read in LLMClient | Avoids MainActor concurrency issues; direct Keychain read is thread-safe |
| Worker URL hardcoded in LLMClient | Single source of truth; no dependency on actor-isolated state |
| Dev fallback (Settings endpoint + API key) | Allows direct OpenAI calls without auth for development/testing |
| Relay token for terminal testing | Bypasses JWT verification; dev-only, removed before production |
| `store: false` on all OpenAI calls | HIPAA: health data not retained by OpenAI |
| Nullable email in users table | Auth0 access tokens don't always include email claim |
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

## Account Information

| Service | Account | Tier |
|---------|---------|------|
| Apple Developer | Personal Apple ID (jasonnolte@instamatic.org) | Paid ($99/yr) |
| Cloudflare | Personal @hotmail.com | Free (100K requests/day) |
| Neon | Personal @hotmail.com | Free (0.5GB storage) |
| OpenAI | Personal @hotmail.com | Paid (API usage) |
| Auth0 | Personal @hotmail.com | Free (25K MAU) |

**Migration plan:** Create fresh accounts under dedicated project email when approaching handoff. Redeploy worker from Git, re-set secrets, transfer Auth0 tenant.

## Conventions

- **Complete file replacements** — Developer works by replacing entire files, not manual patches
- **No partial edits** — Every code delivery is a complete, buildable file
- **One type per file** — Avoid defining multiple public types in one file (prevents redeclaration errors)
- **Sprint-based iteration** — Each sprint has a focused scope with changelog
- **Commit after each sprint** — Detailed commit messages documenting feature additions
- **Auth0.plist** — Keys must be exactly `Domain` and `ClientId` (case-sensitive)
- **Bundle ID** — `com.recordhealth.app` (also the URL scheme for Auth0 callback)
