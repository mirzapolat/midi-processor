# MIDI Voice Splitter

Load a MIDI file, preview tracks with audio, and export them as MIDI, WAV, or MP3 — with per-track volume control and an optional metronome.

---

## Requirements

- Python 3.10+
- [fluidsynth](https://www.fluidsynth.org/) — for WAV/MP3 audio rendering
- [ffmpeg](https://ffmpeg.org/) — for MP3 export

## Install

```bash
# 1. Clone or download the repo
cd midi-exporter

# 2. Install Python dependencies
pip install PyQt6 mido pygame numpy

# 3. Install system tools (macOS)
brew install fluid-synth ffmpeg
```

## Run

```bash
python midi_splitter.py
```

## Usage

1. **Import** — open a MIDI file and optionally change the soundfonts.
2. **Tracks** — mute/solo tracks and rename them for export.
3. **Settings** — adjust playback speed, normal/quiet volume, and metronome.
4. **Export** — choose a mode, format (MP3/WAV/MIDI), and export.

The waveform and playback controls at the bottom are available at all times.

## Bundled Soundfonts

Two soundfonts are included in `soundfonts/` and loaded automatically:

| File | Used for |
|---|---|
| `UprightPianoKW-20220221.sf2` | All MIDI tracks |
| `FluidR3 GM.sf2` | Metronome |

You can override either in the **Import** tab.
