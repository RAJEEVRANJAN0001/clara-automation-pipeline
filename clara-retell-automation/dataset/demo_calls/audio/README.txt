Demo Call Audio Files
=====================

This folder contains TTS-generated audio (.m4a) for each demo call transcript.
Generated using macOS `say` (Samantha voice) + `afconvert` (AAC encoding).

Files:
  demo_call_1.m4a  — ABC Plumbing
  demo_call_2.m4a  — Sunshine HVAC Services
  demo_call_3.m4a  — GreenLeaf Landscaping
  demo_call_4.m4a  — Apex Electrical Solutions
  demo_call_5.m4a  — ClearView Pest Control

To regenerate from transcripts:
  say -f ../demo_call_1.txt -o demo_call_1.aiff --voice Samantha
  afconvert -f mp4f -d aac demo_call_1.aiff demo_call_1.m4a

To transcribe real recordings with Whisper:
  python scripts/transcribe.py dataset/demo_calls/audio/demo_call_1.m4a --model tiny
