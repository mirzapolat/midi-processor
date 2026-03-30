#!/usr/bin/env python3
"""
MIDI Voice Splitter
-------------------
Load a MIDI file, assign levels to each track, generate an internal
metronome, preview with soundfont audio, see a live waveform, and export
selected tracks as MIDI, WAV, or MP3.

Requirements:  pip install PyQt6 mido pygame numpy
Optional:      brew install fluid-synth ffmpeg  (for WAV/MP3 export + audio preview)
"""

import glob
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time as _time
import wave

import mido
import numpy as np
import pygame

from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QLineEdit, QFileDialog,
    QScrollArea, QFrame, QMessageBox, QCheckBox, QSizePolicy,
    QStackedWidget, QButtonGroup,
)


_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Bundled soundfonts shipped alongside this script
_SF_TRACKS    = os.path.join(_SCRIPT_DIR, "soundfonts", "UprightPianoKW-20220221.sf2")
_SF_METRONOME = os.path.join(_SCRIPT_DIR, "soundfonts", "FluidR3 GM.sf2")

# ---------------------------------------------------------------------------
# Design system
# ---------------------------------------------------------------------------

APP_STYLE = """
/* ── Base ──────────────────────────────────────────────────────── */
QWidget {
    font-family: "Segoe UI", "SF Pro Display", "Ubuntu", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    color: #1e293b;
    background-color: transparent;
}
QMainWindow { background: #f1f5f9; }
QDialog     { background: #ffffff; }

/* ── Scrollbars ─────────────────────────────────────────────────── */
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #cbd5e1;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #94a3b8; }
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical     { height: 0; }
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical     { background: transparent; }

/* ── Buttons ────────────────────────────────────────────────────── */
QPushButton {
    background: #ffffff;
    color: #374151;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 3px 14px;
    font-size: 12px;
    font-weight: 500;
}
QPushButton:hover   { background: #f8fafc; border-color: #cbd5e1; }
QPushButton:pressed { background: #f1f5f9; border-color: #94a3b8; }
QPushButton:disabled { color: #9ca3af; background: #f9fafb; border-color: #e2e8f0; }

/* ── Sliders ────────────────────────────────────────────────────── */
QSlider { background: transparent; }
QSlider::groove:horizontal {
    height: 4px;
    background: #e2e8f0;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #6366f1;
    border: 2px solid #ffffff;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}
QSlider::handle:horizontal:hover { background: #4f46e5; }
QSlider::sub-page:horizontal {
    background: #6366f1;
    border-radius: 2px;
}

/* ── Combo boxes ────────────────────────────────────────────────── */
QComboBox {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 3px 10px;
    font-size: 12px;
    color: #374151;
}
QComboBox:hover { border-color: #cbd5e1; }
QComboBox:focus { border-color: #6366f1; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    selection-background-color: #ede9fe;
    selection-color: #4338ca;
    padding: 2px;
    outline: none;
}

/* ── Line edits ─────────────────────────────────────────────────── */
QLineEdit {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 3px 10px;
    font-size: 12px;
    color: #374151;
    selection-background-color: #c7d2fe;
    selection-color: #1e293b;
}
QLineEdit:hover { border-color: #cbd5e1; }
QLineEdit:focus { border-color: #6366f1; }

/* ── Checkboxes ─────────────────────────────────────────────────── */
QCheckBox {
    spacing: 7px;
    color: #374151;
    background: transparent;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1.5px solid #d1d5db;
    border-radius: 4px;
    background: #ffffff;
}
QCheckBox::indicator:hover            { border-color: #6366f1; }
QCheckBox::indicator:checked          { background: #6366f1; border-color: #6366f1; }
QCheckBox::indicator:checked:hover    { background: #4f46e5; border-color: #4f46e5; }

/* ── Labels ─────────────────────────────────────────────────────── */
QLabel { background: transparent; border: none; color: #374151; }

/* ── Tooltips ───────────────────────────────────────────────────── */
QToolTip {
    background: #1e293b;
    color: #f8fafc;
    border: none;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
}


/* ── Message boxes ──────────────────────────────────────────────── */
QMessageBox { background: #ffffff; }
QMessageBox QLabel { color: #1e293b; }
QMessageBox QPushButton { min-width: 72px; }
"""

# Design tokens for programmatic styles
_C_PRIMARY        = "#6366f1"
_C_PRIMARY_DARK   = "#4f46e5"
_C_PRIMARY_DARKER = "#3730a3"
_C_PRIMARY_DEEPER = "#4338ca"
_C_PRIMARY_BG     = "#ede9fe"
_C_PRIMARY_BORDER = "#c7d2fe"
_C_DANGER         = "#dc2626"
_C_DANGER_BG      = "#fef2f2"
_C_DANGER_BORDER  = "#fecaca"
_C_WARN_BG        = "#fffbeb"
_C_WARN_TEXT      = "#92400e"
_C_WARN_BORDER    = "#fde68a"

_BTN_PRIMARY = (
    f"QPushButton{{background:{_C_PRIMARY};color:#ffffff;border:none;"
    f"border-radius:8px;font-weight:600;font-size:13px;}}"
    f"QPushButton:hover{{background:{_C_PRIMARY_DARK};}}"
    f"QPushButton:pressed{{background:{_C_PRIMARY_DEEPER};}}"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_time(secs: float) -> str:
    s = max(0, int(secs))
    return f"{s // 60}:{s % 60:02d}"


# ---------------------------------------------------------------------------
# MIDI helpers
# ---------------------------------------------------------------------------

def track_note_count(track) -> int:
    return sum(1 for m in track if m.type == "note_on" and m.velocity > 0)


def get_total_ticks(midi_file) -> int:
    return max((sum(msg.time for msg in t) for t in midi_file.tracks), default=0)


def generate_metronome_track(ticks_per_beat: int, total_ticks: int) -> mido.MidiTrack:
    track = mido.MidiTrack()
    track.name = "Metronome"
    note = 76
    note_dur = max(5, ticks_per_beat // 8)
    last_tick = 0
    beat = 0
    while True:
        tick = beat * ticks_per_beat
        if tick > total_ticks + ticks_per_beat:
            break
        track.append(mido.Message("note_on",  channel=9, note=note, velocity=100, time=tick - last_tick))
        track.append(mido.Message("note_off", channel=9, note=note, velocity=0,   time=note_dur))
        last_tick = tick + note_dur
        beat += 1
    return track


def _apply_metro_vel(track: mido.MidiTrack, metro_vel: int) -> mido.MidiTrack:
    new = mido.MidiTrack()
    new.name = track.name
    for msg in track:
        if msg.type == "note_on" and msg.velocity > 0:
            new.append(msg.copy(velocity=min(metro_vel, msg.velocity)))
        else:
            new.append(msg)
    return new


def build_output_midi(src, active_idx, normal_velocity, quiet_velocity, speed,
                      track_levels=None, metro_track=None, metro_vel=None):
    """Export one track at normal_velocity ceiling; other tracks follow their Level setting."""
    out_type = 1 if (metro_track is not None or len(src.tracks) > 1) else src.type
    out = mido.MidiFile(type=out_type, ticks_per_beat=src.ticks_per_beat)
    nv, qv = normal_velocity, quiet_velocity
    for ti, track in enumerate(src.tracks):
        new_track = mido.MidiTrack()
        new_track.name = track.name
        is_active = (ti == active_idx)
        level = (track_levels[ti] if track_levels and ti < len(track_levels) else "quiet")
        for msg in track:
            if msg.type == "set_tempo" and speed != 1.0:
                new_track.append(msg.copy(tempo=max(1, int(msg.tempo / speed))))
            elif msg.type == "note_on":
                if msg.velocity == 0:
                    new_track.append(msg)
                elif is_active or level == "normal":
                    new_track.append(msg.copy(velocity=min(nv, msg.velocity)))
                elif level == "quiet":
                    new_track.append(msg.copy(velocity=min(qv, msg.velocity)))
                else:  # muted
                    new_track.append(msg.copy(velocity=0))
            else:
                new_track.append(msg)
        out.tracks.append(new_track)

    if metro_track is not None:
        mv = metro_vel if metro_vel is not None else max(1, int(qv * 0.8))
        out.tracks.append(_apply_metro_vel(metro_track, mv))
    return out


def build_preview_midi(src, solo_idx, normal_velocity, quiet_velocity, speed, track_levels,
                       metro_track=None, metro_vel=None):
    out_type = 1 if (metro_track is not None or len(src.tracks) > 1) else src.type
    out = mido.MidiFile(type=out_type, ticks_per_beat=src.ticks_per_beat)
    nv, qv = normal_velocity, quiet_velocity
    for ti, track in enumerate(src.tracks):
        new_track = mido.MidiTrack()
        new_track.name = track.name
        for msg in track:
            if msg.type == "set_tempo" and speed != 1.0:
                new_track.append(msg.copy(tempo=max(1, int(msg.tempo / speed))))
            elif msg.type == "note_on" and msg.velocity > 0:
                if solo_idx is not None:
                    vel = min(nv, msg.velocity) if ti == solo_idx else 0
                    new_track.append(msg.copy(velocity=vel))
                else:
                    level = track_levels[ti] if ti < len(track_levels) else "muted"
                    if level == "normal":
                        new_track.append(msg.copy(velocity=min(nv, msg.velocity)))
                    elif level == "quiet":
                        new_track.append(msg.copy(velocity=min(qv, msg.velocity)))
                    else:
                        new_track.append(msg.copy(velocity=0))
            else:
                new_track.append(msg)
        out.tracks.append(new_track)

    if metro_track is not None:
        mv = metro_vel if metro_vel is not None else max(1, int(qv * 0.8))
        out.tracks.append(_apply_metro_vel(metro_track, mv))
    return out


# ---------------------------------------------------------------------------
# Soundfont detection + audio helpers
# ---------------------------------------------------------------------------

_SF2_SEARCH_PATHS = [
    "~/Library/Audio/Sounds/Banks/*.sf2",
    "~/.sounds/*.sf2",
    "~/.soundfonts/*.sf2",
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",
    "/usr/share/sounds/sf2/*.sf2",
    "/usr/share/soundfonts/*.sf2",
    "/usr/local/share/soundfonts/*.sf2",
    "/opt/homebrew/share/soundfonts/*.sf2",
    "/opt/homebrew/Cellar/fluid-synth/*/share/fluid-synth/sf2/VintageDreamsWaves-v2.sf2",
    "/usr/local/Cellar/fluid-synth/*/share/fluid-synth/sf2/VintageDreamsWaves-v2.sf2",
]


def find_soundfont() -> str:
    for pattern in _SF2_SEARCH_PATHS:
        hits = glob.glob(os.path.expanduser(pattern))
        if hits:
            return hits[0]
    return ""


def _render_midi_to_wav(midi_path: str, wav_path: str, sf: str) -> None:
    bin_ = shutil.which("fluidsynth")
    if not bin_:
        raise RuntimeError("fluidsynth not found.\n\nInstall:  brew install fluid-synth  (macOS)")
    result = subprocess.run(
        [bin_, "-ni", "-g", "1.0", "-F", wav_path, "-r", "44100", sf, midi_path],
        capture_output=True, text=True,
    )
    if not os.path.isfile(wav_path) or os.path.getsize(wav_path) == 0:
        raise RuntimeError(
            f"fluidsynth failed to render audio.\n\nstderr:\n{result.stderr.strip()}\n\n"
            "Make sure the SoundFont is a valid General MIDI .sf2 file."
        )


def _normalize_wav(wav_path: str, target: float = 0.90) -> None:
    """Normalize WAV amplitude in-place to target fraction of max."""
    with wave.open(wav_path, "rb") as wf:
        params = wf.getparams()
        raw = wf.readframes(wf.getnframes())
    dtype = {1: np.int8, 2: np.int16, 4: np.int32}.get(params.sampwidth, np.int16)
    arr = np.frombuffer(raw, dtype=dtype).astype(np.float64)
    peak = np.abs(arr).max()
    if peak == 0:
        return
    max_val = float(np.iinfo(dtype).max)
    arr = (arr * (target * max_val / peak)).clip(-max_val, max_val).astype(dtype)
    with wave.open(wav_path, "wb") as wf:
        wf.setparams(params)
        wf.writeframes(arr.tobytes())


def _extract_tracks_midi(src: mido.MidiFile, include_indices: set) -> mido.MidiFile:
    """Return copy of src with notes zeroed for tracks not in include_indices."""
    out = mido.MidiFile(type=src.type, ticks_per_beat=src.ticks_per_beat)
    for ti, track in enumerate(src.tracks):
        new_track = mido.MidiTrack()
        new_track.name = track.name
        for msg in track:
            if msg.type == "note_on" and msg.velocity > 0 and ti not in include_indices:
                new_track.append(msg.copy(velocity=0))
            else:
                new_track.append(msg)
        out.tracks.append(new_track)
    return out


def _mix_wav_files(wav_paths: list[str], out_path: str) -> None:
    """Sum multiple WAV files into one, clamping to prevent clipping."""
    arrays, params, max_len = [], None, 0
    for path in wav_paths:
        with wave.open(path, "rb") as wf:
            p = wf.getparams()
            if params is None:
                params = p
            raw = wf.readframes(wf.getnframes())
        dtype = {1: np.int8, 2: np.int16, 4: np.int32}.get(p.sampwidth, np.int16)
        arr = np.frombuffer(raw, dtype=dtype).astype(np.float64)
        arrays.append(arr)
        max_len = max(max_len, len(arr))
    mixed = np.zeros(max_len, dtype=np.float64)
    for arr in arrays:
        mixed[:len(arr)] += arr
    dtype = {1: np.int8, 2: np.int16, 4: np.int32}.get(params.sampwidth, np.int16)
    max_val = float(np.iinfo(dtype).max)
    mixed = mixed.clip(-max_val, max_val).astype(dtype)
    with wave.open(out_path, "wb") as wf:
        wf.setparams(params)
        wf.writeframes(mixed.tobytes())


def _render_with_sf_map(
    output_midi: mido.MidiFile,
    n_src_tracks: int,
    track_sf_map: dict,
    global_sf: str,
    metro_sf: str,
    wav_path: str,
) -> None:
    """Render output_midi to wav_path, routing each track through its soundfont."""
    sf_groups: dict[str, list[int]] = {}
    for ti in range(len(output_midi.tracks)):
        sf = (track_sf_map.get(ti, "") if ti < n_src_tracks else metro_sf) or global_sf
        if not sf:
            raise RuntimeError(
                "No SoundFont (.sf2) file found.\n\n"
                "Select one with Browse. A free GM soundfont (GeneralUser GS, FluidR3 GM)\n"
                "will give you grand piano and all standard instruments."
            )
        sf_groups.setdefault(sf, []).append(ti)

    tmp_files: list[str] = []
    try:
        if len(sf_groups) == 1:
            sf = next(iter(sf_groups))
            with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
                output_midi.save(file=f)
                tmp_files.append(f.name)
            _render_midi_to_wav(f.name, wav_path, sf)
        else:
            wav_parts: list[str] = []
            for sf, indices in sf_groups.items():
                partial = _extract_tracks_midi(output_midi, set(indices))
                with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
                    partial.save(file=f)
                    tmp_files.append(f.name)
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as g:
                    tmp_files.append(g.name)
                _render_midi_to_wav(f.name, g.name, sf)
                wav_parts.append(g.name)
            _mix_wav_files(wav_parts, wav_path)
        _normalize_wav(wav_path)
    finally:
        for p in tmp_files:
            try: os.unlink(p)
            except Exception: pass


def _load_wav_envelope(wav_path: str, n_points: int = 1000) -> tuple[list[float], float]:
    """Return (envelope[0..1], duration_secs) using numpy."""
    with wave.open(wav_path, "rb") as wf:
        n_ch = wf.getnchannels()
        n_frames = wf.getnframes()
        sw = wf.getsampwidth()
        rate = wf.getframerate()
        raw = wf.readframes(n_frames)
    duration = n_frames / rate
    dtype = {1: np.uint8, 2: np.int16, 4: np.int32}.get(sw, np.int16)
    arr = np.frombuffer(raw, dtype=dtype).astype(np.float32)
    if sw == 1:
        arr = arr / 128.0 - 1.0
    else:
        arr = arr / float(np.iinfo(dtype).max)
    if n_ch == 2:
        arr = arr.reshape(-1, 2).mean(axis=1)
    chunk = max(1, len(arr) // n_points)
    trimmed = arr[: chunk * n_points].reshape(n_points, chunk)
    envelope = np.abs(trimmed).max(axis=1)
    mx = envelope.max()
    if mx > 0:
        envelope /= mx
    return envelope.tolist(), duration


# ---------------------------------------------------------------------------
# Preview worker  (render → WAV → pygame, with pause/seek)
# ---------------------------------------------------------------------------

class PreviewWorker(QObject):
    rendering      = pyqtSignal()
    ready          = pyqtSignal(str, float)   # wav_path, duration
    render_error   = pyqtSignal(str)
    finished       = pyqtSignal()
    paused_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self._thread: threading.Thread | None = None
        self._stop_ev = threading.Event()
        self._wav_path: str | None = None
        self._midi_tmp: str | None = None
        self._duration: float = 0.0
        self._is_paused = False
        self._pause_pos: float = 0.0
        self._play_start_wall: float = 0.0
        self._play_start_offset: float = 0.0
        self._audio_mode = False
        self._sf_map: dict = {}
        self._metro_sf: str = ""
        self._n_src_tracks: int = 0

    # ── public ────────────────────────────────────────────────────────────

    def play(self, midi_file, sound_font: str = "",
             sf_map: dict | None = None, metro_sf: str = "", n_src_tracks: int = 0):
        self.stop()
        self._stop_ev = threading.Event()
        self._is_paused = False
        self._sf_map = sf_map or {}
        self._metro_sf = metro_sf
        self._n_src_tracks = n_src_tracks
        any_sf = sound_font or any(self._sf_map.values()) or metro_sf
        self._audio_mode = bool(any_sf)
        if self._audio_mode:
            self.rendering.emit()
            self._thread = threading.Thread(
                target=self._render_thread, args=(midi_file, sound_font), daemon=True)
        else:
            self._thread = threading.Thread(
                target=self._midi_thread, args=(midi_file,), daemon=True)
        self._thread.start()

    def pause_resume(self):
        if not self.is_playing():
            return
        if self._is_paused:
            pygame.mixer.music.unpause()
            self._play_start_wall = _time.time()
            self._play_start_offset = self._pause_pos
            self._is_paused = False
        else:
            self._pause_pos = self._current_secs()
            pygame.mixer.music.pause()
            self._is_paused = True
        self.paused_changed.emit(self._is_paused)

    def seek(self, fraction: float):
        if not self._audio_mode or self._duration <= 0:
            return
        target = max(0.0, min(self._duration, fraction * self._duration))
        was_paused = self._is_paused
        if was_paused:
            pygame.mixer.music.unpause()
        pygame.mixer.music.set_pos(target)
        self._play_start_wall = _time.time()
        self._play_start_offset = target
        self._pause_pos = target
        if was_paused:
            pygame.mixer.music.pause()

    def restart(self):
        if self._audio_mode:
            self.seek(0.0)
        elif self.is_playing():
            pygame.mixer.music.rewind()
            self._play_start_wall = _time.time()
            self._play_start_offset = 0.0

    def stop(self):
        self._stop_ev.set()
        try: pygame.mixer.music.stop()
        except Exception: pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.5)
        self._thread = None
        self._is_paused = False
        self._cleanup()

    def is_playing(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def is_paused(self) -> bool:
        return self._is_paused

    def get_position_fraction(self) -> float:
        if self._duration <= 0:
            return 0.0
        return max(0.0, min(1.0, self._current_secs() / self._duration))

    def get_time_str(self) -> str:
        return f"{_fmt_time(self._current_secs())} / {_fmt_time(self._duration)}"

    def is_audio_mode(self) -> bool:
        return self._audio_mode

    # ── internal ──────────────────────────────────────────────────────────

    def _render_thread(self, midi_file, sound_font):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav = f.name
        try:
            _render_with_sf_map(
                midi_file, self._n_src_tracks, self._sf_map,
                sound_font, self._metro_sf, wav)
        except Exception as e:
            try: os.unlink(wav)
            except Exception: pass
            if not self._stop_ev.is_set():
                self.render_error.emit(str(e))
            self.finished.emit()
            return
        if self._stop_ev.is_set():
            try: os.unlink(wav)
            except Exception: pass
            self.finished.emit()
            return
        try:
            with wave.open(wav, "rb") as wf:
                dur = wf.getnframes() / wf.getframerate()
        except Exception:
            dur = 0.0
        self._wav_path = wav
        self._duration = dur
        self.ready.emit(wav, dur)
        self._play_loop(wav)

    def _play_loop(self, path):
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            self._play_start_wall = _time.time()
            self._play_start_offset = 0.0
            while pygame.mixer.music.get_busy() or self._is_paused:
                if self._stop_ev.is_set():
                    pygame.mixer.music.stop()
                    break
                _time.sleep(0.05)
        finally:
            try: pygame.mixer.music.unload()
            except Exception: pass
            self.finished.emit()

    def _midi_thread(self, midi_file):
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            midi_file.save(file=f)
            tmp = f.name
        self._midi_tmp = tmp
        try:
            pygame.mixer.music.load(tmp)
            pygame.mixer.music.play()
            self._play_start_wall = _time.time()
            self._play_start_offset = 0.0
            while pygame.mixer.music.get_busy() or self._is_paused:
                if self._stop_ev.is_set():
                    pygame.mixer.music.stop()
                    break
                _time.sleep(0.05)
        finally:
            try: pygame.mixer.music.unload()
            except Exception: pass
            self.finished.emit()

    def _current_secs(self) -> float:
        if self._is_paused:
            return self._pause_pos
        if self._play_start_wall == 0.0:
            return 0.0
        return self._play_start_offset + (_time.time() - self._play_start_wall)

    def _cleanup(self):
        for path in [self._wav_path, self._midi_tmp]:
            if path:
                try: os.unlink(path)
                except Exception: pass
        self._wav_path = None
        self._midi_tmp = None
        self._duration = 0.0
        self._play_start_wall = 0.0
        self._play_start_offset = 0.0


# ---------------------------------------------------------------------------
# Waveform widget
# ---------------------------------------------------------------------------

class WaveformWidget(QWidget):
    seek_requested = pyqtSignal(float)   # 0.0 – 1.0

    _BG      = QColor("#0f172a")   # slate-900
    _WAVE    = QColor("#6366f1")   # indigo-500
    _WAVE_LO = QColor("#4338ca")   # indigo-700
    _HEAD    = QColor("#f43f5e")   # rose-500
    _HINT    = QColor("#334155")   # slate-700

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(88)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self._envelope: list[float] = []
        self._position: float = 0.0
        self._dragging = False

    def set_envelope(self, envelope: list[float]):
        self._envelope = envelope
        self._position = 0.0
        self.update()

    def set_position(self, fraction: float):
        self._position = max(0.0, min(1.0, fraction))
        self.update()

    def clear(self):
        self._envelope = []
        self._position = 0.0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Clip to rounded rect
        clip = QPainterPath()
        clip.addRoundedRect(0, 0, w, h, 12, 12)
        p.setClipPath(clip)

        # Background
        p.fillRect(0, 0, w, h, self._BG)

        if not self._envelope:
            p.setPen(QColor("#475569"))
            font = p.font()
            font.setPointSize(10)
            p.setFont(font)
            p.drawText(0, 0, w, h, Qt.AlignmentFlag.AlignCenter,
                       "Select a soundfont and press Play to see waveform")
            return

        # Waveform bars (mirrored top/bottom)
        n = len(self._envelope)
        bar_w = max(1, w / n)
        cy = h / 2

        for i, amp in enumerate(self._envelope):
            x = int(i * bar_w)
            bw = max(1, int((i + 1) * bar_w) - x)
            bh = max(1, int(amp * cy * 0.92))
            # Gradient: brighter top, darker bottom
            p.fillRect(x, int(cy - bh), bw, bh, self._WAVE)
            p.fillRect(x, int(cy),      bw, bh, self._WAVE_LO)

        # Centre line
        p.setPen(QPen(QColor(80, 100, 160), 1))
        p.drawLine(0, int(cy), w, int(cy))

        # Playhead
        px = int(self._position * w)
        p.setPen(QPen(self._HEAD, 2))
        p.drawLine(px, 0, px, h)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton and self._envelope:
            self._dragging = True
            self._emit_seek(ev.position().x())

    def mouseMoveEvent(self, ev):
        if self._dragging and self._envelope:
            self._emit_seek(ev.position().x())

    def mouseReleaseEvent(self, _):
        self._dragging = False

    def _emit_seek(self, x: float):
        self.seek_requested.emit(max(0.0, min(1.0, x / self.width())))


# ---------------------------------------------------------------------------
# Level segment control
# ---------------------------------------------------------------------------

_MUTE_ON  = (f"background:{_C_DANGER_BG};color:{_C_DANGER};border:1.5px solid {_C_DANGER_BORDER};"
             "border-radius:8px;font-size:12px;font-weight:600;")
_MUTE_OFF = ""   # inherits global QPushButton style


# ---------------------------------------------------------------------------
# Track row
# ---------------------------------------------------------------------------

class TrackRow(QWidget):
    solo_clicked  = pyqtSignal(int)
    level_changed = pyqtSignal(int, str)

    def __init__(self, track_idx, track_name, note_count, parent=None):
        super().__init__(parent)
        self.track_idx = track_idx

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(8)

        num = QLabel(str(track_idx + 1))
        num.setFixedWidth(32)
        num.setStyleSheet("color:#94a3b8;font-size:11px;")
        layout.addWidget(num)

        self.name_edit = QLineEdit(track_name)
        self.name_edit.setMinimumWidth(120)
        self.name_edit.setFixedHeight(26)
        self.name_edit.setToolTip("Edit to customise export filename")
        layout.addWidget(self.name_edit, stretch=1)

        self._sf_path = ""
        self.sf_btn = QPushButton("SF…")
        self.sf_btn.setFixedHeight(26)
        self.sf_btn.setFixedWidth(90)
        self.sf_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sf_btn.setToolTip("No custom soundfont — uses the global one")
        self.sf_btn.setStyleSheet("")   # inherits global QPushButton style
        self.sf_btn.clicked.connect(self._browse_sf)
        layout.addWidget(self.sf_btn)

        self.solo_btn = QPushButton("▶  Solo")
        self.solo_btn.setFixedHeight(26)
        self.solo_btn.setFixedWidth(80)
        self.solo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.solo_btn.setStyleSheet("border:1px solid #e2e8f0;border-radius:8px;font-size:12px;")
        self.solo_btn.clicked.connect(lambda: self.solo_clicked.emit(self.track_idx))
        layout.addWidget(self.solo_btn)

        self.mute_btn = QPushButton("Mute")
        self.mute_btn.setCheckable(True)
        self.mute_btn.setFixedHeight(26)
        self.mute_btn.setFixedWidth(70)
        self.mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mute_btn.setStyleSheet(_MUTE_OFF)
        self.mute_btn.toggled.connect(self._on_mute_toggled)
        layout.addWidget(self.mute_btn)

        notes_text = str(note_count) if note_count > 0 else "–"
        notes_lbl = QLabel(notes_text)
        notes_lbl.setFixedWidth(50)
        notes_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if note_count > 0:
            notes_lbl.setStyleSheet(
                f"color:{_C_PRIMARY_DARK};background:{_C_PRIMARY_BG};"
                "border-radius:9px;padding:1px 4px;font-size:11px;font-weight:600;")
        else:
            notes_lbl.setStyleSheet("color:#cbd5e1;font-size:11px;")
        layout.addWidget(notes_lbl)

        self.export_cb = QCheckBox()
        self.export_cb.setChecked(True)
        self.export_cb.setFixedWidth(44)
        self.export_cb.setToolTip("Include in export")
        layout.addWidget(self.export_cb)
        layout.addStretch()

    def _browse_sf(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select SoundFont for this track", "", "SoundFont files (*.sf2);;All files (*)")
        if path:
            self._sf_path = path
            short = os.path.basename(path)
            self.sf_btn.setToolTip(path)
            self.sf_btn.setText(short[:6] + "…" if len(short) > 7 else short)
            self.sf_btn.setStyleSheet(
                f"border:1.5px solid {_C_PRIMARY_BORDER};border-radius:8px;font-size:11px;"
                f"background:{_C_PRIMARY_BG};color:{_C_PRIMARY_DARK};")

    def get_soundfont(self) -> str:
        return self._sf_path

    def _on_mute_toggled(self, checked: bool):
        self.mute_btn.setStyleSheet(_MUTE_ON if checked else _MUTE_OFF)
        if checked:
            self.export_cb.setChecked(False)
        self.level_changed.emit(self.track_idx, "muted" if checked else "normal")

    def get_export_name(self):
        return self.name_edit.text().strip() or f"track_{self.track_idx + 1}"

    def get_level(self): return "muted" if self.mute_btn.isChecked() else "normal"
    def get_export_enabled(self): return self.export_cb.isChecked()

    def set_solo_active(self, active: bool):
        if active:
            self.solo_btn.setText("⏸  Solo")
            self.solo_btn.setStyleSheet(
                f"background:{_C_PRIMARY_BG};color:{_C_PRIMARY_DARKER};"
                f"border:1.5px solid {_C_PRIMARY_BORDER};"
                "border-radius:8px;font-size:12px;font-weight:600;")
        else:
            self.solo_btn.setText("▶  Solo")
            self.solo_btn.setStyleSheet("")


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MIDI Voice Splitter")
        self.setMinimumSize(900, 560)
        self.resize(1020, 720)

        self.midi_file = None
        self.source_path = ""
        self.track_rows: list[TrackRow] = []
        self.current_solo = -1

        self.worker = PreviewWorker()
        self.worker.rendering.connect(self._on_rendering)
        self.worker.ready.connect(self._on_preview_ready)
        self.worker.render_error.connect(self._on_render_error)
        self.worker.finished.connect(self._on_playback_finished)
        self.worker.paused_changed.connect(self._on_paused_changed)

        self._pos_timer = QTimer()
        self._pos_timer.setInterval(50)
        self._pos_timer.timeout.connect(self._tick_position)

        pygame.init()
        pygame.mixer.init()
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root_widget = QWidget()
        root_widget.setObjectName("rootBg")
        # Use #objectName selector so this background does NOT cascade to children.
        root_widget.setStyleSheet("QWidget#rootBg { background: #f1f5f9; }")
        self.setCentralWidget(root_widget)
        root = QVBoxLayout(root_widget)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── custom nav header (single fixed-height row) ───────────────────
        header = QWidget()
        header.setObjectName("appHeader")
        header.setFixedHeight(48)
        header.setStyleSheet(
            "QWidget#appHeader { background: #ffffff; border-bottom: 1px solid #e2e8f0; }")
        hdr_l = QHBoxLayout(header)
        hdr_l.setContentsMargins(0, 0, 0, 0)
        hdr_l.setSpacing(0)

        _NAV = (
            "QPushButton{background:#ffffff;color:#6366f1;border:none;border-radius:0;"
            "padding:0 18px;font-size:12px;font-weight:600;min-width:80px;}"
            "QPushButton:hover{background:#f0f0ff;}"
            "QPushButton:disabled{color:#d1d5db;}")
        _TAB = (
            "QPushButton{background:#ffffff;color:#94a3b8;border:none;border-radius:0;"
            "border-bottom:2px solid transparent;"
            "padding:0 8px;font-size:13px;font-weight:500;}"
            "QPushButton:hover:!checked{color:#475569;background:#f8fafc;}"
            "QPushButton:checked{color:#6366f1;border-bottom:2px solid #6366f1;"
            "font-weight:600;}")

        self._nav_back = QPushButton("← Back")
        self._nav_back.setFixedHeight(48)
        self._nav_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self._nav_back.setStyleSheet(_NAV)
        self._nav_back.setEnabled(False)
        hdr_l.addWidget(self._nav_back)

        # thin separator
        sep_l = QFrame()
        sep_l.setFrameShape(QFrame.Shape.VLine)
        sep_l.setStyleSheet("QFrame{color:#e2e8f0;}")
        hdr_l.addWidget(sep_l)

        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)
        self._stack = QStackedWidget()

        for i, (label, page) in enumerate(zip(
            ["① Import", "② Tracks", "③ Settings", "④ Export"],
            [self._build_tab_import(), self._build_tab_tracks(),
             self._build_tab_settings(), self._build_tab_export()],
        )):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(48)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(_TAB)
            self._tab_group.addButton(btn, i)
            hdr_l.addWidget(btn)
            self._stack.addWidget(page)

        self._tab_group.button(0).setChecked(True)
        self._tab_group.idClicked.connect(self._go_to_tab)

        sep_r = QFrame()
        sep_r.setFrameShape(QFrame.Shape.VLine)
        sep_r.setStyleSheet("QFrame{color:#e2e8f0;}")
        hdr_l.addWidget(sep_r)

        self._nav_next = QPushButton("Next →")
        self._nav_next.setFixedHeight(48)
        self._nav_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self._nav_next.setStyleSheet(_NAV)
        self._nav_next.clicked.connect(
            lambda: self._go_to_tab(self._stack.currentIndex() + 1))
        self._nav_back.clicked.connect(
            lambda: self._go_to_tab(self._stack.currentIndex() - 1))
        hdr_l.addWidget(self._nav_next)

        root.addWidget(header)
        root.addWidget(self._stack, stretch=1)
        self._on_tab_changed(0)   # set initial enabled state of Back/Next

        # ── bottom bar (waveform + playback) — always visible ─────────────
        bottom = QFrame()
        bottom.setObjectName("bottomBar")
        bottom.setAutoFillBackground(True)
        bottom.setStyleSheet(
            "QFrame#bottomBar { background: #ffffff; border-top: 1px solid #e2e8f0; }")
        bottom_v = QVBoxLayout(bottom)
        bottom_v.setContentsMargins(16, 10, 16, 10)
        bottom_v.setSpacing(8)

        self.waveform = WaveformWidget()
        self.waveform.seek_requested.connect(self._on_seek)
        bottom_v.addWidget(self.waveform)

        pb = QHBoxLayout()
        pb.setSpacing(8)

        self.restart_btn = QPushButton("⏮")
        self.restart_btn.setFixedSize(36, 36)
        self.restart_btn.setToolTip("Restart")
        self.restart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.restart_btn.clicked.connect(self._restart)
        pb.addWidget(self.restart_btn)

        self.play_btn = QPushButton("▶  Play mix")
        self.play_btn.setFixedHeight(36)
        self.play_btn.setMinimumWidth(120)
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.clicked.connect(self._play_or_pause)
        pb.addWidget(self.play_btn)

        self.stop_btn = QPushButton("■  Stop")
        self.stop_btn.setFixedHeight(36)
        self.stop_btn.setFixedWidth(88)
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.clicked.connect(self._stop)
        pb.addWidget(self.stop_btn)

        pb.addSpacing(10)
        self.time_lbl = QLabel("0:00 / 0:00")
        self.time_lbl.setFixedWidth(96)
        self.time_lbl.setStyleSheet(
            "color:#64748b;font-family:monospace;font-size:12px;font-weight:500;")
        pb.addWidget(self.time_lbl)

        pb.addSpacing(6)
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color:#94a3b8;font-size:12px;")
        pb.addWidget(self.status_lbl, stretch=1)
        bottom_v.addLayout(pb)
        root.addWidget(bottom)

    # ── tab builders ──────────────────────────────────────────────────────

    def _card(self, title: str = "") -> tuple[QFrame, QVBoxLayout]:
        """Return (card_frame, content_vbox). Optionally adds a title label."""
        card = QFrame()
        # Use a specific #name selector so the white background only paints THIS
        # frame and does not cascade down to descendant QFrames/QScrollAreas.
        name = f"card{id(card)}"
        card.setObjectName(name)
        card.setAutoFillBackground(True)
        card.setStyleSheet(
            f"QFrame#{name} {{ background: #ffffff; border: 1px solid #e2e8f0;"
            " border-radius: 12px; }")
        v = QVBoxLayout(card)
        v.setContentsMargins(18, 14, 18, 14)
        v.setSpacing(10)
        if title:
            lbl = QLabel(title)
            lbl.setStyleSheet(
                "font-size: 11px; font-weight: 700; color: #94a3b8;"
                " letter-spacing: 0.06em; text-transform: uppercase;")
            v.addWidget(lbl)
        return card, v

    def _choice_btn(self, text: str, tooltip: str = "") -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(34)
        btn.setStyleSheet(
            "QPushButton{background:#f8fafc;color:#374151;border:1.5px solid #e2e8f0;"
            "border-radius:8px;padding:4px 18px;font-size:12px;font-weight:500;}"
            "QPushButton:hover{background:#ede9fe;color:#4f46e5;border-color:#c7d2fe;}"
            "QPushButton:checked{background:#6366f1;color:#ffffff;border-color:#6366f1;"
            "font-weight:600;}"
            "QPushButton:checked:hover{background:#4f46e5;border-color:#4f46e5;}")
        if tooltip:
            btn.setToolTip(tooltip)
        return btn

    def _tab_page(self) -> QWidget:
        """Create a tab page QWidget whose background only applies to itself."""
        w = QWidget()
        name = f"tabPage{id(w)}"
        w.setObjectName(name)
        w.setStyleSheet(f"QWidget#{name} {{ background: #f1f5f9; }}")
        return w

    def _build_tab_import(self) -> QWidget:
        w = self._tab_page()
        v = QVBoxLayout(w)
        v.setContentsMargins(24, 20, 24, 20)
        v.setSpacing(16)

        # ── MIDI File card ─────────────────────────────────────────────
        midi_card, midi_v = self._card("MIDI File")
        row = QHBoxLayout()
        row.setSpacing(10)
        open_btn = QPushButton("Open MIDI…")
        open_btn.setFixedHeight(36)
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(self._open_file)
        row.addWidget(open_btn)
        self.file_label = QLabel("No file loaded")
        self.file_label.setStyleSheet("color:#94a3b8;font-size:13px;font-weight:500;")
        row.addWidget(self.file_label, stretch=1)
        midi_v.addLayout(row)
        v.addWidget(midi_card)

        # ── Soundfonts card ────────────────────────────────────────────
        sf_card, sf_v = self._card("Soundfonts")
        hint = QLabel(
            "SoundFont (.sf2) files are needed for audio preview and WAV/MP3 export."
            " The bundled fonts are auto-loaded when found.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#64748b;font-size:12px;")
        sf_v.addWidget(hint)

        # Tracks SF row
        tr_row = QHBoxLayout()
        tr_row.setSpacing(8)
        tr_lbl = QLabel("Tracks soundfont:")
        tr_lbl.setFixedWidth(140)
        tr_lbl.setStyleSheet("color:#374151;font-size:12px;")
        tr_row.addWidget(tr_lbl)
        self.sf_edit = QLineEdit()
        self.sf_edit.setFixedHeight(30)
        self.sf_edit.setPlaceholderText("path/to/GeneralUser_GS.sf2")
        self.sf_edit.setToolTip(
            "General MIDI .sf2 for WAV/MP3 export and audio preview.\n"
            "Free options: GeneralUser GS, FluidR3 GM, MuseScore General.")
        if os.path.isfile(_SF_TRACKS):
            self.sf_edit.setText(_SF_TRACKS)
        else:
            detected = find_soundfont()
            if detected and "VintageDreams" not in detected:
                self.sf_edit.setText(detected)
        tr_row.addWidget(self.sf_edit, stretch=1)
        sf_browse_btn = QPushButton("Browse…")
        sf_browse_btn.setFixedHeight(30)
        sf_browse_btn.clicked.connect(self._browse_soundfont)
        tr_row.addWidget(sf_browse_btn)
        sf_v.addLayout(tr_row)

        # Metronome SF row
        mt_row = QHBoxLayout()
        mt_row.setSpacing(8)
        mt_lbl = QLabel("Metronome soundfont:")
        mt_lbl.setFixedWidth(140)
        mt_lbl.setStyleSheet("color:#374151;font-size:12px;")
        mt_row.addWidget(mt_lbl)
        self.metro_sf_edit = QLineEdit()
        self.metro_sf_edit.setFixedHeight(30)
        self.metro_sf_edit.setPlaceholderText("uses tracks soundfont if empty")
        self.metro_sf_edit.setToolTip("Optional separate soundfont for the metronome track.")
        if os.path.isfile(_SF_METRONOME):
            self.metro_sf_edit.setText(_SF_METRONOME)
        mt_row.addWidget(self.metro_sf_edit, stretch=1)
        metro_sf_btn = QPushButton("Browse…")
        metro_sf_btn.setFixedHeight(30)
        metro_sf_btn.clicked.connect(self._browse_metro_sf)
        mt_row.addWidget(metro_sf_btn)
        sf_v.addLayout(mt_row)
        v.addWidget(sf_card)

        v.addStretch()
        return w

    def _build_tab_tracks(self) -> QWidget:
        track_card = QFrame()
        track_card.setObjectName("trackCard")
        track_card.setStyleSheet("""
            QFrame#trackCard {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 0px;
            }
        """)
        track_card_v = QVBoxLayout(track_card)
        track_card_v.setContentsMargins(0, 0, 0, 0)
        track_card_v.setSpacing(0)

        # column header
        hdr = QWidget()
        hdr.setObjectName("trackHdr")
        hdr.setStyleSheet("""
            QWidget#trackHdr {
                background: #f8fafc;
                border-bottom: 1px solid #e2e8f0;
            }
            QLabel { color: #94a3b8; font-size: 11px; font-weight: 600; }
        """)
        hdr_l = QHBoxLayout(hdr)
        hdr_l.setContentsMargins(10, 6, 10, 6)
        hdr_l.setSpacing(8)
        # #
        n_lbl = QLabel("#")
        n_lbl.setFixedWidth(32)
        hdr_l.addWidget(n_lbl)
        # Track name — expands to fill available space
        name_lbl = QLabel("Track name / export filename")
        name_lbl.setMinimumWidth(120)
        hdr_l.addWidget(name_lbl, stretch=1)
        # Fixed-width columns
        for text, fw in [("SF", 90), ("Solo", 80), ("Mute", 70), ("Notes", 50), ("Export", 44)]:
            lbl = QLabel(text)
            lbl.setFixedWidth(fw)
            hdr_l.addWidget(lbl)
        track_card_v.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.track_container = QWidget()
        self.track_container.setStyleSheet("background: transparent;")
        self.track_layout = QVBoxLayout(self.track_container)
        self.track_layout.setContentsMargins(0, 0, 0, 0)
        self.track_layout.setSpacing(0)
        self.track_layout.addStretch()
        scroll.setWidget(self.track_container)
        track_card_v.addWidget(scroll, stretch=1)
        return track_card

    def _build_tab_settings(self) -> QWidget:
        w = self._tab_page()
        v = QVBoxLayout(w)
        v.setContentsMargins(24, 20, 24, 20)
        v.setSpacing(16)

        # ── Playback Speed ─────────────────────────────────────────────
        spd_card, spd_v = self._card("Playback Speed")
        spd_row = QHBoxLayout()
        spd_row.setSpacing(10)
        spd_row.addWidget(QLabel("Speed:"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(25, 200)
        self.speed_slider.setValue(100)
        self.speed_slider.setMinimumWidth(160)
        self.speed_slider.valueChanged.connect(lambda val: self.speed_lbl.setText(f"{val}%"))
        spd_row.addWidget(self.speed_slider)
        self.speed_lbl = QLabel("100%")
        self.speed_lbl.setFixedWidth(40)
        spd_row.addWidget(self.speed_lbl)
        spd_row.addStretch()
        spd_v.addLayout(spd_row)
        v.addWidget(spd_card)

        # ── Volume Levels ──────────────────────────────────────────────
        vol_card, vol_v = self._card("Volume Levels")

        def _slider_row(label: str, default: int, lbl_attr: str, slider_attr: str):
            row = QHBoxLayout()
            row.setSpacing(10)
            l = QLabel(label)
            l.setFixedWidth(90)
            row.addWidget(l)
            sl = QSlider(Qt.Orientation.Horizontal)
            sl.setRange(1, 127)
            sl.setValue(default)
            sl.setMinimumWidth(160)
            row.addWidget(sl)
            vl = QLabel(str(default))
            vl.setFixedWidth(28)
            row.addWidget(vl)
            sl.valueChanged.connect(lambda val, _vl=vl: _vl.setText(str(val)))
            row.addStretch()
            setattr(self, slider_attr, sl)
            setattr(self, lbl_attr, vl)
            return row

        vol_v.addLayout(_slider_row("Normal volume:", 100, "normal_lbl", "normal_slider"))
        vol_v.addLayout(_slider_row("Quiet volume:",   30, "quiet_lbl",  "quiet_slider"))
        v.addWidget(vol_card)

        # ── Metronome ──────────────────────────────────────────────────
        metro_card, metro_v = self._card("Metronome")

        metro_top = QHBoxLayout()
        metro_top.setSpacing(16)
        self.metro_toggle = QCheckBox("Enable metronome")
        self.metro_toggle.setChecked(False)
        metro_top.addWidget(self.metro_toggle)
        self.metro_export_cb = QCheckBox("Include in export")
        self.metro_export_cb.setChecked(True)
        metro_top.addWidget(self.metro_export_cb)
        metro_top.addStretch()
        metro_v.addLayout(metro_top)

        metro_vol_row = QHBoxLayout()
        metro_vol_row.setSpacing(10)
        mvl = QLabel("Metro volume:")
        mvl.setFixedWidth(90)
        metro_vol_row.addWidget(mvl)
        self.metro_vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.metro_vol_slider.setRange(1, 127)
        self.metro_vol_slider.setValue(64)
        self.metro_vol_slider.setMinimumWidth(160)
        metro_vol_row.addWidget(self.metro_vol_slider)
        self.metro_vol_lbl = QLabel("64")
        self.metro_vol_lbl.setFixedWidth(28)
        metro_vol_row.addWidget(self.metro_vol_lbl)
        self.metro_vol_slider.valueChanged.connect(
            lambda val: self.metro_vol_lbl.setText(str(val)))
        metro_vol_row.addStretch()
        metro_v.addLayout(metro_vol_row)
        v.addWidget(metro_card)

        v.addStretch()
        return w

    def _build_tab_export(self) -> QWidget:
        w = self._tab_page()
        v = QVBoxLayout(w)
        v.setContentsMargins(24, 20, 24, 20)
        v.setSpacing(16)

        # ── Export Mode card ───────────────────────────────────────────
        mode_card, mode_v = self._card("Export Mode")
        mode_hint = QLabel(
            "Both: two files per track (quiet + silent).  "
            "All Normal: one file, all tracks full volume.  "
            "Others Quiet / Silent: one file per track.")
        mode_hint.setWordWrap(True)
        mode_hint.setStyleSheet("color:#64748b;font-size:12px;")
        mode_v.addWidget(mode_hint)

        mode_btns = QHBoxLayout()
        mode_btns.setSpacing(8)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        for i, (label, tip) in enumerate([
            ("Both (Quiet + Silent)", "Two files per track: quiet version and silent version"),
            ("All Normal",            "One file with all checked tracks at full volume"),
            ("Others Quiet",          "One file per track; other tracks play quietly"),
            ("Others Silent",         "One file per track; other tracks are silent"),
        ]):
            btn = self._choice_btn(label, tip)
            self.mode_group.addButton(btn, i)
            mode_btns.addWidget(btn)
        mode_btns.addStretch()
        self.mode_group.button(0).setChecked(True)
        mode_v.addLayout(mode_btns)
        v.addWidget(mode_card)

        # ── File Settings card ─────────────────────────────────────────
        file_card, file_v = self._card("File Settings")

        fn_row = QHBoxLayout()
        fn_row.setSpacing(10)
        fn_lbl = QLabel("Base filename:")
        fn_lbl.setFixedWidth(105)
        fn_row.addWidget(fn_lbl)
        self.basename_edit = QLineEdit()
        self.basename_edit.setFixedHeight(32)
        self.basename_edit.setPlaceholderText("e.g. MySong")
        self.basename_edit.setToolTip(
            "Used as the prefix for all exported filenames.\n"
            "Edit this if the original filename is too long.")
        fn_row.addWidget(self.basename_edit, stretch=1)
        file_v.addLayout(fn_row)

        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(8)
        fmt_lbl = QLabel("Format:")
        fmt_lbl.setFixedWidth(105)
        fmt_row.addWidget(fmt_lbl)
        self.format_group = QButtonGroup(self)
        self.format_group.setExclusive(True)
        for i, (label, tip) in enumerate([
            ("MP3", "Export as MP3 (requires ffmpeg)"),
            ("WAV", "Export as WAV (requires fluidsynth)"),
            ("MIDI", "Export as MIDI file (no audio rendering)"),
        ]):
            btn = self._choice_btn(label, tip)
            self.format_group.addButton(btn, i)
            fmt_row.addWidget(btn)
        fmt_row.addStretch()
        self.format_group.button(0).setChecked(True)
        file_v.addLayout(fmt_row)
        v.addWidget(file_card)

        v.addStretch()

        # ── Export button ──────────────────────────────────────────────
        export_btn = QPushButton("Export selected tracks")
        export_btn.setFixedHeight(44)
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.setStyleSheet(_BTN_PRIMARY)
        export_btn.clicked.connect(self._export_all)
        v.addWidget(export_btn)
        return w

    # ── file loading ──────────────────────────────────────────────────────

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open MIDI file", "", "MIDI files (*.mid *.midi);;All files (*)")
        if not path:
            return
        try:
            self.midi_file = mido.MidiFile(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open MIDI:\n{e}")
            return
        self.source_path = path
        self.file_label.setText(os.path.basename(path))
        self.file_label.setStyleSheet("color:#1e293b;font-weight:600;font-size:13px;")
        self.basename_edit.setText(os.path.splitext(os.path.basename(path))[0])
        self._populate_tracks()

    def _populate_tracks(self):
        self._stop()
        self.waveform.clear()
        for row in self.track_rows:
            row.setParent(None)
        self.track_rows.clear()
        visible = 0
        for i, track in enumerate(self.midi_file.tracks):
            nc = track_note_count(track)
            if nc == 0:
                continue  # skip empty/metadata tracks (e.g. type-1 tempo track)
            name = track.name or f"Track {i + 1}"
            row = TrackRow(i, name, nc)
            row.solo_clicked.connect(self._toggle_solo)
            row.level_changed.connect(self._on_level_changed)
            if visible % 2 != 0:
                row.setObjectName(f"rowAlt{id(row)}")
                row.setStyleSheet(f"QWidget#rowAlt{id(row)} {{ background:#fafbff; }}")
            self.track_layout.insertWidget(self.track_layout.count() - 1, row)
            self.track_rows.append(row)
            visible += 1
        self.status_lbl.setText(
            f"{visible} track(s) — {os.path.basename(self.source_path)}")

    # ── metronome / settings helpers ──────────────────────────────────────

    def _get_metro_track(self):
        if not self.metro_toggle.isChecked() or self.midi_file is None:
            return None
        return generate_metronome_track(self.midi_file.ticks_per_beat, get_total_ticks(self.midi_file))

    def _get_metro_track_for_export(self):
        if not self.metro_toggle.isChecked() or not self.metro_export_cb.isChecked():
            return None
        if self.midi_file is None:
            return None
        return generate_metronome_track(self.midi_file.ticks_per_beat, get_total_ticks(self.midi_file))

    def _get_metro_vel(self):   return self.metro_vol_slider.value()
    def _get_speed(self):       return self.speed_slider.value() / 100.0
    def _get_normal_vel(self):  return self.normal_slider.value()
    def _get_quiet_vel(self):   return self.quiet_slider.value()
    def _get_levels(self):
        levels = ["muted"] * len(self.midi_file.tracks)
        for r in self.track_rows:
            levels[r.track_idx] = r.get_level()
        return levels
    def _get_soundfont(self):  return self.sf_edit.text().strip()

    # ── playback ──────────────────────────────────────────────────────────

    def _play_or_pause(self):
        if self.worker.is_playing():
            if self.worker.is_paused():
                self.worker.pause_resume()
                self._set_play_btn_state("playing")
            else:
                self.worker.pause_resume()
                self._set_play_btn_state("paused")
        else:
            self._play_mix()

    def _play_mix(self):
        if self.midi_file is None:
            return
        self._stop()
        preview = build_preview_midi(
            self.midi_file, None,
            self._get_normal_vel(), self._get_quiet_vel(), self._get_speed(), self._get_levels(),
            self._get_metro_track(), self._get_metro_vel(),
        )
        self.current_solo = -1
        self.worker.play(preview, self._get_soundfont(),
                         self._get_track_sf_map(), self._get_metro_sf(),
                         len(self.midi_file.tracks))
        self._set_play_btn_state("playing")
        self.status_lbl.setText("Playing mix…")

    def _toggle_solo(self, track_idx):
        if self.worker.is_playing() and self.current_solo == track_idx:
            self._stop()
            return
        self._stop()
        self.current_solo = track_idx
        preview = build_preview_midi(
            self.midi_file, track_idx,
            self._get_normal_vel(), self._get_quiet_vel(), self._get_speed(), [],
            self._get_metro_track(), self._get_metro_vel(),
        )
        self.worker.play(preview, self._get_soundfont(),
                         self._get_track_sf_map(), self._get_metro_sf(),
                         len(self.midi_file.tracks))
        for row in self.track_rows:
            row.set_solo_active(row.track_idx == track_idx)
        self._set_play_btn_state("playing")
        row = next((r for r in self.track_rows if r.track_idx == track_idx), None)
        self.status_lbl.setText(f"Solo: {row.get_export_name() if row else track_idx}")

    def _restart(self):
        if self.worker.is_playing() or self.worker.is_paused():
            self.worker.restart()
            if self.worker.is_paused():
                self.worker.pause_resume()  # resume after restart
                self._set_play_btn_state("playing")

    def _stop(self):
        self._pos_timer.stop()
        self.worker.stop()
        self._reset_ui()

    def _reset_ui(self):
        self.current_solo = -1
        self.play_btn.setText("▶  Play mix")
        self.play_btn.setStyleSheet("")
        self.time_lbl.setText("0:00 / 0:00")
        self.waveform.set_position(0.0)
        for row in self.track_rows:
            row.set_solo_active(False)

    def _set_play_btn_state(self, state: str):
        if state == "playing":
            self.play_btn.setText("⏸  Pause")
            self.play_btn.setStyleSheet(
                f"QPushButton{{background:{_C_PRIMARY};color:#ffffff;border:none;"
                f"border-radius:8px;font-weight:600;font-size:13px;}}"
                f"QPushButton:hover{{background:{_C_PRIMARY_DARK};}}")
        elif state == "paused":
            self.play_btn.setText("▶  Resume")
            self.play_btn.setStyleSheet(
                f"QPushButton{{background:{_C_WARN_BG};color:{_C_WARN_TEXT};"
                f"border:1.5px solid {_C_WARN_BORDER};"
                "border-radius:8px;font-weight:600;font-size:13px;}}"
                f"QPushButton:hover{{background:#fef3c7;}}")
        else:
            self.play_btn.setText("▶  Play mix")
            self.play_btn.setStyleSheet("")

    # ── worker signal handlers ─────────────────────────────────────────────

    def _on_rendering(self):
        self.status_lbl.setText("Rendering audio…")
        self.play_btn.setText("⏳  Rendering…")
        self.play_btn.setStyleSheet("color:#94a3b8;")

    def _on_preview_ready(self, wav_path: str, duration: float):
        self._set_play_btn_state("playing")
        self.status_lbl.setText("Playing…")
        try:
            envelope, _ = _load_wav_envelope(wav_path)
            self.waveform.set_envelope(envelope)
        except Exception:
            pass
        self._pos_timer.start()

    def _on_render_error(self, msg: str):
        self.status_lbl.setText("Render error")
        QMessageBox.critical(self, "Preview error", msg)

    def _on_playback_finished(self):
        self._pos_timer.stop()
        self._reset_ui()
        self.status_lbl.setText("Done.")

    def _on_paused_changed(self, paused: bool):
        if paused:
            self._set_play_btn_state("paused")
            self._pos_timer.stop()
        else:
            self._set_play_btn_state("playing")
            self._pos_timer.start()

    def _go_to_tab(self, index: int):
        index = max(0, min(self._stack.count() - 1, index))
        self._stack.setCurrentIndex(index)
        self._tab_group.button(index).setChecked(True)
        self._on_tab_changed(index)

    def _on_tab_changed(self, index: int):
        self._nav_back.setEnabled(index > 0)
        self._nav_next.setEnabled(index < self._stack.count() - 1)

    def _on_level_changed(self, track_idx, level):
        if self.worker.is_playing() and self.current_solo == -1:
            self._stop()
            self._play_mix()

    def _tick_position(self):
        if not self.worker.is_playing() and not self.worker.is_paused():
            self._pos_timer.stop()
            return
        frac = self.worker.get_position_fraction()
        self.waveform.set_position(frac)
        self.time_lbl.setText(self.worker.get_time_str())

    def _on_seek(self, fraction: float):
        self.worker.seek(fraction)
        self.waveform.set_position(fraction)

    # ── format / soundfont ────────────────────────────────────────────────

    def _browse_soundfont(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select SoundFont", "", "SoundFont files (*.sf2);;All files (*)")
        if path:
            self.sf_edit.setText(path)

    def _browse_metro_sf(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Metronome SoundFont", "", "SoundFont files (*.sf2);;All files (*)")
        if path:
            self.metro_sf_edit.setText(path)

    def _get_metro_sf(self) -> str:
        return self.metro_sf_edit.text().strip()

    def _get_track_sf_map(self) -> dict:
        return {r.track_idx: r.get_soundfont() for r in self.track_rows}

    # ── export ────────────────────────────────────────────────────────────

    def _save_midi_file(self, out_midi, out_path: str, fmt: str,
                        errors: list, label: str) -> bool:
        """Save out_midi to out_path in the given format. Returns True on success."""
        if fmt == "mid":
            out_midi.save(out_path)
            return True
        tmp_wav = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_wav = f.name
            _render_with_sf_map(
                out_midi, len(self.midi_file.tracks),
                self._get_track_sf_map(), self._get_soundfont(),
                self._get_metro_sf(), tmp_wav)
            if fmt == "wav":
                os.replace(tmp_wav, out_path)
                tmp_wav = None
            elif fmt == "mp3":
                ffmpeg_bin = shutil.which("ffmpeg")
                if not ffmpeg_bin:
                    raise RuntimeError("MP3 export requires ffmpeg.\n\nInstall:  brew install ffmpeg  (macOS)")
                result = subprocess.run(
                    [ffmpeg_bin, "-y", "-i", tmp_wav, "-b:a", "192k", out_path],
                    capture_output=True, text=True,
                )
                if result.returncode != 0:
                    raise RuntimeError(f"ffmpeg failed:\n{result.stderr.strip()}")
            return True
        except RuntimeError as e:
            QMessageBox.critical(self, "Export error", str(e))
            return False
        except Exception as e:
            errors.append(f"{label}: {e}")
            return True  # non-fatal, continue
        finally:
            if tmp_wav:
                try: os.unlink(tmp_wav)
                except Exception: pass

    def _export_all(self):
        if self.midi_file is None:
            QMessageBox.information(self, "No file", "Open a MIDI file first.")
            return
        selected = [r for r in self.track_rows if r.get_export_enabled()]
        if not selected:
            QMessageBox.information(self, "Nothing selected",
                                    "Check at least one track in the Export column.")
            return
        out_dir = QFileDialog.getExistingDirectory(self, "Choose export folder")
        if not out_dir:
            return

        speed     = self._get_speed()
        nv        = self._get_normal_vel()
        qv        = self._get_quiet_vel()
        metro_trk = self._get_metro_track_for_export()
        metro_vel = self._get_metro_vel()
        base      = self.basename_edit.text().strip() or os.path.splitext(os.path.basename(self.source_path))[0]
        fmt  = ["mp3", "wav", "mid"][self.format_group.checkedId()]
        mode = ["Both (Quiet + Silent)", "All Normal", "Others Quiet", "Others Silent"][
                   self.mode_group.checkedId()]

        n_tracks = len(self.midi_file.tracks)
        count = 0
        errors = []

        def levels_for(active_idx, other_mode):
            """Build track-levels list. active_idx track is handled by build_output_midi.
            Non-muted tracks that aren't active get other_mode; muted tracks stay muted."""
            lvls = ["muted"] * n_tracks
            for r in self.track_rows:
                if r.get_level() != "muted" and r.track_idx != active_idx:
                    lvls[r.track_idx] = other_mode
            return lvls

        if mode == "All Normal":
            # Single file: all non-muted tracks at full volume
            lvls = ["muted"] * n_tracks
            for r in self.track_rows:
                if r.get_level() != "muted":
                    lvls[r.track_idx] = "normal"
            out_midi = build_output_midi(
                self.midi_file, -1, nv, qv, speed, lvls, metro_trk, metro_vel)
            out_path = os.path.join(out_dir, f"{base}.{fmt}")
            if self._save_midi_file(out_midi, out_path, fmt, errors, base):
                count += 1

        elif mode == "Others Quiet":
            for row in selected:
                lvls = levels_for(row.track_idx, "quiet")
                out_midi = build_output_midi(
                    self.midi_file, row.track_idx, nv, qv, speed, lvls, metro_trk, metro_vel)
                name = row.get_export_name()
                out_path = os.path.join(out_dir, f"{base}_{name}.{fmt}")
                if self._save_midi_file(out_midi, out_path, fmt, errors, name):
                    count += 1
                else:
                    break

        elif mode == "Others Silent":
            for row in selected:
                lvls = levels_for(row.track_idx, "muted")
                out_midi = build_output_midi(
                    self.midi_file, row.track_idx, nv, qv, speed, lvls, metro_trk, metro_vel)
                name = row.get_export_name()
                out_path = os.path.join(out_dir, f"{base}_{name}.{fmt}")
                if self._save_midi_file(out_midi, out_path, fmt, errors, name):
                    count += 1
                else:
                    break

        else:  # Both (Quiet + Silent)
            for row in selected:
                name = row.get_export_name()

                lvls_q = levels_for(row.track_idx, "quiet")
                out_q = build_output_midi(
                    self.midi_file, row.track_idx, nv, qv, speed, lvls_q, metro_trk, metro_vel)
                path_q = os.path.join(out_dir, f"{base}_{name}_quiet.{fmt}")
                if not self._save_midi_file(out_q, path_q, fmt, errors, f"{name}_quiet"):
                    break
                count += 1

                lvls_s = levels_for(row.track_idx, "muted")
                out_s = build_output_midi(
                    self.midi_file, row.track_idx, nv, qv, speed, lvls_s, metro_trk, metro_vel)
                path_s = os.path.join(out_dir, f"{base}_{name}_silent.{fmt}")
                if not self._save_midi_file(out_s, path_s, fmt, errors, f"{name}_silent"):
                    break
                count += 1

        if errors:
            QMessageBox.warning(self, "Some exports failed", "\n".join(errors))
        self.status_lbl.setText(f"Exported {count} file(s) → {out_dir}")
        if count:
            QMessageBox.information(self, "Done", f"Exported {count} file(s) to:\n{out_dir}")

    def closeEvent(self, event):
        self._stop()
        pygame.quit()
        event.accept()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")   # base style; our QSS overrides visuals on top
    app.setStyleSheet(APP_STYLE)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
