Sprint 18: Auth0 Authentication + Cloudflare Worker API Gateway

BACKEND (recordhealth-api):
- Cloudflare Worker API gateway deployed
  JWT verification via Auth0 JWKS (jose library)
  Auto user creation on first Auth0 login (ensureUser)
  Neon Postgres: users, health_records, audit_log tables
- /ai/chat endpoint: Chat Completions relay for iOS app
  Accepts standard OpenAI messages format
  Forwards to OpenAI with store: false (HIPAA)
  Audit logs every request with user ID + metadata
- Full CRUD for health_records (user-scoped)
- Relay token fallback for dev/terminal testing
- Database: users.email changed to nullable

NEW FEATURES (iOS):
- Auth0 SDK integration (Swift Package Manager, Auth0 2.17.1)
  Auth0.plist with tenant domain + client ID
  URL scheme registered: com.recordhealth.app
- AuthManager (login, logout, token storage, silent renewal)
  Stores access + refresh tokens in Keychain
  Publishes isAuthenticated for SwiftUI
- LoginView (sign-in screen, shown when not authenticated)
- App entry gated on authentication (RecordHealth.swift)

MODIFIED (iOS):
- LLMClient.swift: resolveAuth() reads Auth0 token from Keychain
  Routes through worker when authenticated, direct API fallback
  Automatic token renewal on 401 (retry once)
  Worker URL hardcoded (avoids MainActor concurrency issues)
- LLMClient+Chat.swift: same worker routing via resolveAuth()
- KeychainService.swift: added .accessToken, .refreshToken keys
- RecordHealth.swift: @StateObject authManager, auth gating

AUTH FLOW:
  Login → Auth0 Universal Login → JWT → Keychain
  AI Request → Keychain token → Worker → JWT verify → OpenAI
  401 → renewToken() → retry once → or show login

FILES CREATED:
- AuthManager.swift (Auth0 integration)
- LoginView.swift (sign-in screen)
- Auth0.plist (Auth0 configuration)

FILES MODIFIED:
- LLMClient.swift (worker routing)
- LLMClient+Chat.swift (worker routing)
- KeychainService.swift (new token keys)
- RecordHealth.swift (auth gating)

FILES UNCHANGED:
- AIContextBuilder.swift (system prompts preserved)
- RecordAskAIView.swift, ConversationModels.swift
- AudioPlayerView.swift, VoiceRecorderView.swift, SpeechRecognizer.swift
- RecordV2.swift, RecordsStore.swift, SourceFormat.swift
- EncryptionService.swift, Anonymizer.swift, AuditLogger.swift
