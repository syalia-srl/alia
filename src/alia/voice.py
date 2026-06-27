"""ALIA voice — local STT (harp) and local TTS (Kokoro).

- ``Transcriber``: push-to-talk speech-to-text over harp's ``HarpSession``
  (mic → live committed text → final). Reuses harp's ``LocalWhisperEngine``.
- ``Speaker``: text-to-speech via Kokoro (``KPipeline``), played through
  ``aplay``. Spanish/English by lang code.

Everything is local/offline. Engines load lazily — the first call is slow
(model load / first-use download), later calls are fast. Heavy imports
(harp/kokoro) are deferred so importing this module stays cheap.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import threading
import urllib.request
from pathlib import Path
from typing import Callable

# STT: whisper model size (tiny/base/small/...). base is a good CPU default.
STT_MODEL = os.getenv("ALIA_STT_MODEL", "base")
STT_LANGUAGE = os.getenv("ALIA_STT_LANGUAGE") or None  # None = autodetect
# TTS (kokoro-onnx): lang ("en-us", "es", …) + a voice id (see Kokoro VOICES.md).
TTS_LANG = os.getenv("ALIA_TTS_LANG", "en-us")
TTS_VOICE = os.getenv("ALIA_TTS_VOICE", "af_heart")

# Kokoro ONNX model + voices — fetched once into ~/.cache/alia on first use.
_CACHE = Path(os.path.expanduser("~/.cache/alia"))
_KOKORO_BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
_KOKORO_FILES = {
    "kokoro-v1.0.onnx": f"{_KOKORO_BASE}/kokoro-v1.0.onnx",
    "voices-v1.0.bin": f"{_KOKORO_BASE}/voices-v1.0.bin",
}


class Transcriber:
    """Push-to-talk STT. start() begins capture; stop() returns the final text."""

    def __init__(self, model_size: str = STT_MODEL, language: str | None = STT_LANGUAGE) -> None:
        self._model_size = model_size
        self._language = language
        self._engine = None
        self._session = None
        self._worker: threading.Thread | None = None

    def _ensure_engine(self) -> None:
        if self._engine is None:
            from harp.whisper import LocalWhisperEngine

            self._engine = LocalWhisperEngine(
                model_size=self._model_size, device="cpu", compute_type="int8")
            self._engine.load_model()

    @property
    def listening(self) -> bool:
        return self._session is not None

    def start(self, on_partial: Callable[[str], None] | None = None) -> None:
        """Open the mic and begin streaming. on_partial(text) gets live prefixes."""
        if self._session is not None:
            return
        self._ensure_engine()
        from harp import HarpSession, MicrophoneSource

        mic = MicrophoneSource(sample_rate=16000)
        self._session = HarpSession(
            audio=mic, transcribe=self._engine.transcribe,
            slide_interval=0.5, language=self._language)
        self._session.__enter__()

        def _pump() -> None:
            for event in self._session.events():
                if on_partial is not None:
                    on_partial(event.text)

        self._worker = threading.Thread(target=_pump, daemon=True)
        self._worker.start()

    def stop(self) -> str:
        """Stop capture, return the final transcription."""
        if self._session is None:
            return ""
        session = self._session
        session.stop()
        if self._worker is not None:
            self._worker.join(timeout=15)
        text = session.final_text
        session.__exit__(None, None, None)
        self._session = None
        self._worker = None
        return text


class Speaker:
    """TTS via kokoro-onnx (no torch) → aplay. speak() blocks; stop() cuts it.

    The Kokoro ONNX model + voices are downloaded once into ~/.cache/alia.
    """

    def __init__(self, voice: str = TTS_VOICE, lang: str = TTS_LANG) -> None:
        self._voice = voice
        self._lang = lang
        self._kokoro = None
        self._proc: subprocess.Popen | None = None

    @staticmethod
    def _fetch(name: str, url: str, on_status: Callable[[str], None] | None = None) -> Path:
        _CACHE.mkdir(parents=True, exist_ok=True)
        dest = _CACHE / name
        if not dest.exists():
            if on_status:
                on_status(f"downloading {name}…")
            tmp = dest.with_suffix(dest.suffix + ".part")
            urllib.request.urlretrieve(url, tmp)
            tmp.rename(dest)
        return dest

    def _ensure(self, on_status: Callable[[str], None] | None = None) -> None:
        if self._kokoro is None:
            model = self._fetch("kokoro-v1.0.onnx", _KOKORO_FILES["kokoro-v1.0.onnx"], on_status)
            voices = self._fetch("voices-v1.0.bin", _KOKORO_FILES["voices-v1.0.bin"], on_status)
            from kokoro_onnx import Kokoro

            self._kokoro = Kokoro(str(model), str(voices))

    def speak(self, text: str, on_status: Callable[[str], None] | None = None) -> None:
        if not text.strip():
            return
        self._ensure(on_status)
        import soundfile as sf

        samples, sample_rate = self._kokoro.create(
            text, voice=self._voice, speed=1.0, lang=self._lang)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fh:
            path = fh.name
        sf.write(path, samples, sample_rate)
        try:
            self._proc = subprocess.Popen(["aplay", "-q", path])
            self._proc.wait()
        finally:
            self._proc = None
            os.unlink(path)

    def stop(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
