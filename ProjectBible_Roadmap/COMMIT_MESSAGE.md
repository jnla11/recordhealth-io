Sprint 17: Voice Recording Audio Storage + Playback

NEW FEATURES:
- Audio file recording during live transcription (SpeechRecognizer)
  AVAudioEngine tap feeds both SFSpeech and AVAudioFile writer
  PCM → compressed m4a conversion after recording stops
- Audio playback component (AudioPlayerView)
  Play/pause, ±15s skip, progress slider, time display
  AVAudioPlayer-based, MainActor-isolated timer
- Audio record detail view (RecordDetailView)
  Detects .audio source format, shows player card above transcript
  Ask AI available on audio records
- Voice recorder saves audio alongside transcript (VoiceRecorderView)
  Passes audioFileURL to store.addRecord(originalFileURL:)
  Save disabled during audio processing

AUDIO PIPELINE:
  Record → AVAudioEngine tap → PCM buffers → temp .caf
  Stop → AVAssetExportSession → compressed .m4a
  Save → FileStorageManager → originals/{uuid}.m4a
  View → AudioPlayerView (AVAudioPlayer) + transcript

FILES MODIFIED:
- SpeechRecognizer.swift (audio file recording added)
- VoiceRecorderView.swift (passes audio URL on save)
- RecordDetailView.swift (audio record view, Ask AI button restyle)

FILES CREATED:
- AudioPlayerView.swift (playback component)
- BodySection.swift (medical emoji vocabulary — Sprint 16a)

FILES UNCHANGED:
- AIContextBuilder.swift (original Sprint 15b prompt preserved)
- LLMClient.swift, LLMClient+Chat.swift, KeychainService.swift
- RecordV2.swift, RecordsStore.swift, SourceFormat.swift
- RecordAskAIView.swift (OCR warning reorder — Sprint 16a)
