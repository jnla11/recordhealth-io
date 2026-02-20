# Record Health — New Conversation Template

Use this to start a new AI coding session. Copy/paste into a fresh conversation.

---

## Project Context

I'm building **Record Health**, an iOS SwiftUI app that digitizes and organizes medical documents with AI-powered explanations. I'm not a professional programmer — this is vibe coding. I work in Xcode, testing on an iPhone 13 Pro Max running iOS 26.3.

**Goal:** Help end-users be more educated, "doctor-ready" healthcare consumers using their own records. Eventually HIPAA/GDPR/NIST ready, phased in incrementally.

**Key guardrails:** No medical advice. No treatment suggestions. PHI anonymized before any AI call. Mandatory doctor-review disclaimer on every AI response.

## Current State (as of Sprint 17 — 2026-02-18)

### What Works
- File-based record storage (RecordV2 + encrypted index)
- PDF, text, and image import with OCR
- Voice memo recording with live transcription + audio file storage (.m4a)
- Audio playback (play/pause, scrub, ±15s skip, time display)
- Multi-page PDF viewer with floating modal nav bars
- Per-record AI chat with conversation persistence
- PHI anonymization + audit logging
- Suggested prompts + contextual follow-ups with dedup
- AI responses: emoji sections (👤🏥🔍📋💡), accessible language, no filler openers
- Chat panel: slides from right, keyboard-aware, rounded card UI
- Tap-to-tag manual field identification
- AI field classification
- Consolidated KeychainService + EncryptionService (AES-256-GCM)
- BodySection emoji vocabulary (21 cases, code-level data model)

### Known Issues
- None currently — builds clean as of Sprint 17

### Key Files
| File | Contains |
|------|----------|
| AIContextBuilder.swift | System prompts, context assembly |
| ChatMessage.swift | ChatMessage struct (role + content for API) |
| RecordAskAIView.swift | Chat UI, KeyboardObserver, ChatFlowLayout |
| ConversationModels.swift | ConversationMessage, SuggestedPrompts, FollowUpPrompts |
| RecordDetailView.swift | Document viewer (PDF/photo/audio/text), AI overlay host |
| AudioPlayerView.swift | Audio playback component (AVAudioPlayer) |
| VoiceRecorderView.swift | Voice recording UI + transcript + save |
| SpeechRecognizer.swift | AVAudioEngine + SFSpeech + audio file recording |
| BodySection.swift | Medical section emoji vocabulary enum |
| LLMClient.swift | Base HTTP client |
| LLMClient+Chat.swift | Chat completions extension |
| KeychainService.swift | Consolidated keychain access |
| EncryptionService.swift | AES-256-GCM encryption |
| RecordV2.swift | Core record model |
| SourceFormat.swift | Import source types (pdf, audio, photo, etc.) |

### Architecture Notes
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

## What I Need Next
[Describe your next task here]

---

**Reference docs:** PROJECT_STATE.md, PROJECT_BIBLE.md, SPRINT_CHANGELOG.md, ROADMAP.md
