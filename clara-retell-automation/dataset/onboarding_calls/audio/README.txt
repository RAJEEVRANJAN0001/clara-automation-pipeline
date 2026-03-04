Onboarding Call Audio Files
============================
Place your actual onboarding call recordings here as .mp3 files:

  onboard_call_1.mp3  ->  ABC Plumbing
  onboard_call_2.mp3  ->  Sunshine HVAC Services
  onboard_call_3.mp3  ->  GreenLeaf Landscaping
  onboard_call_4.mp3  ->  Apex Electrical Solutions
  onboard_call_5.mp3  ->  ClearView Pest Control

The corresponding .txt transcripts are in the parent folder (onboarding_calls/).

To transcribe an audio file to text, run:
  python3 scripts/transcribe.py dataset/onboarding_calls/audio/onboard_call_1.mp3

Requires Whisper (optional, zero-cost):
  pip install openai-whisper
