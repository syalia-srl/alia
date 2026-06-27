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

import logging
import os
import subprocess
import tempfile
import threading
import urllib.request
from pathlib import Path
from typing import Callable

_log = logging.getLogger("alia.voice")
if not _log.handlers and os.getenv("ALIA_VOICE_LOG", "1") != "0":
    _h = logging.FileHandler("/tmp/alia-voice.log")
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _log.addHandler(_h)
    _log.setLevel(logging.DEBUG)

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
    """Push-to-talk STT — record a clip, then transcribe it.

    Records with a fresh sounddevice ``InputStream`` per session and transcribes
    the whole clip with harp's ``LocalWhisperEngine``. Record-then-transcribe
    (no live partials) was chosen over harp's streaming ``HarpSession`` because
    repeated open/close of the streaming mic across sessions proved unreliable;
    a fresh InputStream + one-shot transcribe is solid across many sessions.
    """

    def __init__(self, model_size: str = STT_MODEL, language: str | None = STT_LANGUAGE) -> None:
        self._model_size = model_size
        self._language = language
        self._engine = None
        self._stream = None
        self._frames: list = []

    def _ensure_engine(self) -> None:
        if self._engine is None:
            from harp.whisper import LocalWhisperEngine

            self._engine = LocalWhisperEngine(
                model_size=self._model_size, device="cpu", compute_type="int8")
            self._engine.load_model()

    @property
    def listening(self) -> bool:
        return self._stream is not None

    def start(self, on_partial: Callable[[str], None] | None = None) -> None:
        """Begin recording. (on_partial is unused — text arrives on stop().)"""
        if self._stream is not None:
            _log.warning("start() ignored: already recording")
            return
        self._ensure_engine()
        import sounddevice as sd

        self._frames = []

        def _cb(indata, _frames, _time, _status) -> None:
            self._frames.append(indata[:, 0].copy())

        self._stream = sd.InputStream(
            samplerate=16000, channels=1, dtype="float32", callback=_cb)
        self._stream.start()
        _log.info("recording started")

    def stop(self) -> str:
        """Stop recording, transcribe the clip, return the text. Always resets."""
        import numpy as np

        stream = self._stream
        if stream is None:
            _log.warning("stop() with no active recording")
            return ""
        try:
            stream.stop()
            stream.close()
        except Exception:
            _log.exception("stream close failed")
        finally:
            self._stream = None

        if not self._frames:
            _log.info("stopped: no audio captured")
            return ""
        audio = np.concatenate(self._frames).astype("float32")
        secs = len(audio) / 16000
        rms = float(np.sqrt(np.mean(audio**2))) if audio.size else 0.0
        if rms < 0.006:  # essentially silence — skip (whisper hallucinates on it)
            _log.info("stopped: silent (%.1fs rms=%.4f), skipping", secs, rms)
            return ""
        try:
            text = (self._engine.transcribe(audio, None, self._language) or "").strip()
        except Exception:
            _log.exception("transcribe failed")
            return ""
        _log.info("stopped: %.1fs audio -> %r", secs, text)
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
