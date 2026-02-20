# Record Health — New Conversation Template

Use this to start a new AI coding session. Copy/paste into a fresh conversation.

---

## Project Context

I'm building **Record Health**, an iOS SwiftUI app that digitizes and organizes medical documents with AI-powered explanations. I'm not a professional programmer — this is vibe coding. I work in Xcode, testing on an iPhone 13 Pro Max running iOS 26.3.

**Goal:** Help end-users be more educated, "doctor-ready" healthcare consumers using their own records. Eventually HIPAA/GDPR/NIST ready, phased in incrementally.

**Key guardrails:** No medical advice. No treatment suggestions. PHI anonymized before any AI call. Mandatory doctor-review disclaimer on every AI response.

## Current State (as of Sprint 19 — 2026-02-19)

### What Works
- Auth0 authentication (email/password login, JWT-based)
- Logout button with confirmation dialog ("Your records stay on this device")
- Cloudflare Worker API gateway (JWT verification, audit logging, OpenAI relay)
- AI calls routed through worker (OpenAI key never on device, `store: false`)
- Automatic token renewal on 401
- Settings view hides API key field when authenticated
- File-based record storage (RecordV2 + encrypted index)
- PDF, text, and image import with OCR
- Voice memo recording with live transcription + audio file storage (.m4a)
- Audio playback (play/pause, scrub, ±15s skip, time display)
- Multi-page PDF viewer with floating modal nav bars
- Per-record AI chat with conversation persistence
- PHI anonymization + audit logging (local + server-side)
- Suggested prompts + contextual follow-ups with dedup
- AI responses: emoji sections (👤🏥🔍📋💡), accessible language, no filler openers
- Chat panel: slides from right, keyboard-aware, rounded card UI
- Tap-to-tag manual field identification
- AI field classification
- Consolidated KeychainService + EncryptionService (AES-256-GCM)
- BodySection emoji vocabulary (21 cases, code-level data model)

### Known Issues
- Sign in with Apple pending Auth0 Apple connection propagation
- ~200-500ms added latency from worker relay
- OCRService MainActor isolation warnings (pre-existing, non-blocking)
- SpeechRecognizer iOS 18 deprecation warnings (pre-existing, non-blocking)
- TapToTagView UIScreen.main iOS 26 deprecation warnings (pre-existing, non-blocking)

### Backend
- **Worker:** https://recordhealth-api.jason-nolte.workers.dev
- **Database:** Neon Postgres (users, health_records, audit_log)
- **Auth0 tenant:** dev-br2xi1kdn6smgx7p.us.auth0.com
- **Worker repo:** ~/Projects/RecordHealth.IO/recordhealth-api/

### Key Files (iOS)
| File | Contains |
|------|----------|
| AuthManager.swift | Auth0 login/logout/token management |
| LoginView.swift | Sign-in screen |
| RecordHealth.swift | App entry point (auth-gated) |
| AppRootView.swift | Tab view root (passes AppSettings.shared to SettingsView) |
| SettingsView.swift | Logout button, API key hidden when authenticated |
| AIContextBuilder.swift | System prompts, context assembly |
| ChatMessage.swift | ChatMessage struct (role + content for API) |
| RecordAskAIView.swift | Chat UI, KeyboardObserver, ChatFlowLayout |
| ConversationModels.swift | ConversationMessage, SuggestedPrompts, FollowUpPrompts |
| RecordDetailView.swift | Document viewer (PDF/photo/audio/text), AI overlay host |
| AudioPlayerView.swift | Audio playback component (AVAudioPlayer) |
| VoiceRecorderView.swift | Voice recording UI + transcript + save |
| SpeechRecognizer.swift | AVAudioEngine + SFSpeech + audio file recording |
| BodySection.swift | Medical section emoji vocabulary enum |
| LLMClient.swift | Base HTTP client (routes through worker when authenticated) |
| LLMClient+Chat.swift | Chat completions extension (same routing) |
| KeychainService.swift | Consolidated keychain (apiKey, accessToken, refreshToken) |
| EncryptionService.swift | AES-256-GCM encryption |
| RecordV2.swift | Core record model |
| SourceFormat.swift | Import source types (pdf, audio, photo, etc.) |
| AppSettings.swift | ObservableObject: endpointURL, model |

### Key Files (Worker)
| File | Contains |
|------|----------|
| src/index.js | All routes: auth, CRUD, /ai/chat, /ai/query, audit logging |
| schema.sql | Neon database schema |
| wrangler.toml | Cloudflare Worker config |

### Architecture Notes
- LLMClient.resolveAuth() reads Auth0 token from Keychain (avoids MainActor issues)
- Worker URL hardcoded in LLMClient, not dependent on actor-isolated state
- Auth0.plist keys must be exactly `Domain` and `ClientId` (case-sensitive)
- Bundle ID / URL scheme: com.recordhealth.app
- AppSettings has `endpointURL` and `model` properties (not `modelName`)
- API key lives in Keychain only, not in AppSettings — read via KeychainService.shared.load(.apiKey)
- SettingsView requires `settings: AppSettings.shared` passed at init (see AppRootView)
- AI prompts: chips show short label in chat, send full detailed prompt to AI
- Keyboard: KeyboardObserver tracks height, `.padding(.bottom, keyboard.height)` pushes input above keyboard
- Follow-up dedup: intent-based classification, filters already-asked intents from suggestions
- System prompt: 5th-grade reading level (implicit), emoji section headers, document-only answers
- Voice recording: AVAudioEngine tap feeds both SFSpeech and file writer simultaneously
- Audio storage: PCM → m4a conversion after recording, stored via FileStorageManager
- RecordDetailView rendering chain: PDF → Photo → Audio → Text fallback

## How I Work
- **Complete file replacements** — I replace entire files in Xcode (Cmd+A → Delete → Paste), not manual line edits
- **One type per file** — Each struct/class/enum lives in exactly one .swift file
- **Sprint-based** — Focused scope per sprint, changelog after each
- **Test on device** — iPhone 13 Pro Max, iOS 26.3
- **When things break** — I share build errors and screenshots; I need clear instructions on what to fix
- **Always provide full files** — Never partial edits or snippets

## What I Need Next
[Describe your next task here]

---

**Reference docs:** PROJECT_STATE.md, PROJECT_BIBLE.md, SPRINT_CHANGELOG.md, ROADMAP.md
