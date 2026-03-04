#!/usr/bin/env python3
"""
transcribe.py — Transcribe audio files to text using OpenAI Whisper.

Usage:
    python scripts/transcribe.py <audio_file> [--model tiny] [--output <output_path>]

If the input file is already a .txt file, it will be treated as a pre-existing
transcript and simply read and output directly. This allows the pipeline to work
seamlessly with both audio files and text transcripts.

If an .mp3 / audio file is empty (0 bytes, i.e. a placeholder), the script
automatically falls back to the corresponding .txt transcript in the same base
directory so the pipeline can still run end-to-end.
"""

import argparse
import os
import ssl
import sys

# ── Fix macOS SSL certificate verification for Whisper model downloads ──────
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    pass  # certifi not installed; SSL may still work via system certs


def _fallback_txt_path(audio_path: str) -> str | None:
    """Return the .txt sibling path for an audio file, searching up one level."""
    base = os.path.splitext(audio_path)[0]
    # Same directory first: e.g. audio/demo_call_1.mp3 → audio/demo_call_1.txt
    candidate = base + ".txt"
    if os.path.exists(candidate):
        return candidate
    # One directory up: dataset/demo_calls/audio/demo_call_1.mp3
    #               → dataset/demo_calls/demo_call_1.txt
    parent_base = os.path.join(
        os.path.dirname(os.path.dirname(audio_path)),
        os.path.basename(base),
    )
    candidate2 = parent_base + ".txt"
    if os.path.exists(candidate2):
        return candidate2
    return None


def transcribe_audio(file_path: str, model_name: str = "tiny") -> str:
    """Transcribe an audio file using OpenAI Whisper.

    If the file is empty (placeholder), falls back to the matching .txt
    transcript automatically so the pipeline can still run end-to-end.
    """
    # ── Empty file guard ────────────────────────────────────────────────────
    if os.path.getsize(file_path) == 0:
        fallback = _fallback_txt_path(file_path)
        if fallback:
            print(
                f"[transcribe] '{os.path.basename(file_path)}' is a placeholder "
                f"(0 bytes) — falling back to: {fallback}",
                file=sys.stderr,
            )
            return read_transcript(fallback)
        print(
            f"ERROR: '{file_path}' is empty and no .txt fallback was found.\n"
            "Replace the placeholder with a real audio recording.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        import whisper
    except ImportError:
        print(
            "ERROR: openai-whisper is not installed.\n"
            "Install it with: pip install openai-whisper\n"
            "Falling back to reading file as text if possible.",
            file=sys.stderr,
        )
        # If the file is a text file, read it directly
        if file_path.endswith(".txt"):
            return read_transcript(file_path)
        sys.exit(1)

    print(f"[transcribe] Loading Whisper '{model_name}' model…", file=sys.stderr)
    model = whisper.load_model(model_name)
    print(f"[transcribe] Transcribing {os.path.basename(file_path)}…", file=sys.stderr)
    result = model.transcribe(file_path)
    return result["text"]


def read_transcript(file_path: str) -> str:
    """Read a text transcript file directly."""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe audio files or read text transcripts."
    )
    parser.add_argument("file", help="Path to the audio or transcript file")
    parser.add_argument(
        "--model",
        default="tiny",
        help="Whisper model size (tiny, base, small, medium, large). Default: tiny",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output file path to save the transcript",
    )
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"ERROR: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    # If the file is already a text transcript, read it directly
    if args.file.endswith(".txt"):
        transcript = read_transcript(args.file)
    else:
        transcript = transcribe_audio(args.file, args.model)

    # Output the transcript
    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(transcript)
        print(f"Transcript saved to: {args.output}")
    else:
        print(transcript)


if __name__ == "__main__":
    main()
