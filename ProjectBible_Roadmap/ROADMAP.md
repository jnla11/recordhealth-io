# Record Health — Roadmap

**Philosophy:** Phased iteration, each step vibe-code workable. Privacy and safety always come first.

---

## Phase 1 — POC Foundation ✅ (Complete)
- [x] SwiftUI app structure
- [x] File-based record storage (RecordV2 + index.json)
- [x] .txt and .pdf import with text extraction
- [x] Image import with OCR (Apple Vision)
- [x] Multi-page PDF viewer with floating nav bars
- [x] Keychain-based API key storage (consolidated KeychainService)
- [x] Settings UI (endpoint, model, API key)
- [x] Schema migration (V1 → V2)

## Phase 2 — AI Chat + Document Understanding ✅ (Complete)
- [x] LLMClient for OpenAI-compatible endpoints
- [x] PHI anonymization (Anonymizer) before all API calls
- [x] Audit logging of all AI interactions
- [x] Per-record AI chat with conversation persistence
- [x] System prompt guardrails (no advice, document-only, mandatory disclaimer)
- [x] Accessible language (5th-grade level, emoji sections)
- [x] Suggested prompts per record category
- [x] Contextual follow-up prompts with deduplication
- [x] OCR confidence warnings
- [x] Manual tap-to-tag field identification
- [x] AI-powered field classification

## Phase 3 — Chat UI Polish ✅ (Complete)
- [x] Redesigned chat panel (high-contrast, readable)
- [x] Slide-from-right card presentation matching nav bar
- [x] Keyboard handling (observer, dismiss button, input above keyboard)
- [x] Display label vs. full AI prompt split
- [x] No filler openers in AI responses
- [x] Emoji section headers in AI responses
- [x] Resolve duplicate type build errors (ChatMessage, AIContextBuilder)
- [x] OCR warning positioned above suggested prompts
- [x] Ask AI button restyled to match modal bar aesthetic
- [x] BodySection emoji vocabulary (code-level, future prompt integration)

## Phase 4 — Input Expansion 🔧 (Current)
- [x] Voice memo recording + transcription + audio file storage + playback
- [ ] Text message / iMessage screenshot import
- [ ] Camera capture with real-time OCR
- [ ] Bulk import from Files app
- [ ] Apple Health integration (HealthKit)

## Phase 5 — Multi-Record Intelligence
- [ ] Cross-record AI analysis ("What's trending across my labs?")
- [ ] Timeline view (records on a date axis)
- [ ] Appointment prep mode (synthesize recent records into doctor visit summary)
- [ ] Record tagging improvements (auto-suggest based on content)
- [ ] Embeddings for semantic search across records

## Phase 6 — Compliance & Security Hardening
- [ ] HIPAA readiness audit
  - [x] Encryption at rest (AES-256-GCM field-level + iOS file protection)
  - [ ] Access controls (biometric lock)
  - [ ] Audit trail export
  - [ ] Data retention policies
- [ ] GDPR readiness
  - [ ] Data export (all records as ZIP)
  - [ ] Right to deletion
  - [ ] Consent management UI
- [ ] NIST Cybersecurity framework alignment
  - [ ] Threat model documentation
  - [ ] Key rotation
  - [ ] Secure enclave usage for API keys

## Phase 7 — Sync & Sharing
- [ ] iCloud sync (CloudKit)
- [ ] Family sharing (multiple patients per account)
- [ ] Secure record sharing (time-limited links)
- [ ] Provider portal (share summary with doctor before visit)

## Phase 8 — Analytics & Insights
- [ ] Personal health dashboard (trends, charts)
- [ ] Lab value tracking over time
- [ ] Medication list management
- [ ] Preventive care reminders

---

## Non-Goals (Explicitly Out of Scope)
- Direct medical advice or treatment suggestions
- Prescription management or pharmacy integration
- Insurance billing or claims processing
- Social features or community forums
- Real-time health monitoring (wearable integration)
