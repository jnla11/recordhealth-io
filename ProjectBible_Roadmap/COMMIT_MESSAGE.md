Sprint 19: Logout Button + Settings Cleanup + Sign in with Apple Configuration

iOS CHANGES:
- SettingsView: Added Sign Out button (Account section, authenticated only)
  Confirmation dialog before logout ("Your records stay on this device")
  API key field hidden when authenticated
  LLM Configuration footer contextual (worker mode vs. direct mode)
- AppRootView: Fixed SettingsView(settings: AppSettings.shared) call

AUTH0 / APPLE DEVELOPER:
- Created Key in Apple Developer portal (RecordHealth Sign In with Apple)
- Configured Apple social connection in Auth0 (Team ID, Services ID, Key ID, .p8)
- Enabled Apple connection on RecordHealth (Native) application in Auth0
- Sign in with Apple will appear in Universal Login once propagated

FILES MODIFIED (iOS):
- SettingsView.swift (logout button, API key conditional, settings parameter)
- AppRootView.swift (SettingsView initializer fix)

FILES UNCHANGED:
- AuthManager.swift, LoginView.swift, RecordHealth.swift
- LLMClient.swift, LLMClient+Chat.swift
- All other app files
