# MIDI Voice Splitter

Load a MIDI file, preview tracks with audio, and export them as MIDI, WAV, or MP3 — with per-track volume control, per-track soundfonts, and an optional metronome.

---

## Requirements

- Python 3.10+
- [fluidsynth](https://www.fluidsynth.org/) — for WAV/MP3 audio rendering and preview
- [ffmpeg](https://ffmpeg.org/) — for MP3 export

## Install

**1. Clone or download the repo**

```bash
cd midi-exporter
```

**2. Install Python dependencies**

```bash
pip install PyQt6 mido pygame numpy
```

**3. Install system tools**

<details>
<summary>macOS</summary>

```bash
brew install fluid-synth ffmpeg
```
</details>

<details>
<summary>Windows</summary>

Download and install both tools manually, then make sure they are on your `PATH`:

- **fluidsynth** — download the latest release from [github.com/FluidSynth/fluidsynth/releases](https://github.com/FluidSynth/fluidsynth/releases), extract the zip, and add the `bin/` folder to your system `PATH`.
- **ffmpeg** — download a build from [ffmpeg.org/download.html](https://ffmpeg.org/download.html) (e.g. the gyan.dev release), extract it, and add the `bin/` folder to your system `PATH`.

To add a folder to `PATH`: *System Properties → Environment Variables → Path → Edit → New*.
</details>

<details>
<summary>Linux (Debian / Ubuntu)</summary>

```bash
sudo apt update
sudo apt install fluidsynth ffmpeg
```

For Fedora/RHEL:

```bash
sudo dnf install fluidsynth ffmpeg
```
</details>

## Run

```bash
python midi_splitter.py
```

## Usage

The app is organised as a 4-step wizard. Use **Next / Back** or click any step directly.

1. **Import** — open a MIDI file. Optionally override the soundfonts for tracks or metronome.
2. **Tracks** — mute or solo individual tracks, rename them, pick an instrument preset from the active soundfont, and assign per-track soundfonts. Check the **Export** column to select which tracks to include.
3. **Settings** — adjust playback speed, normal/quiet volume levels, FluidSynth reverb/chorus, and metronome (enable, instrument, volume, include in export).
4. **Export** — pick an export mode, output format, and base filename, then click **Export selected tracks**. A progress bar shows the status for each file.

The waveform and playback controls at the bottom are available at all times. Press **Play mix** to preview with audio.

### Audio effects

When you preview with a soundfont or export to WAV/MP3, you can control:

- Reverb on/off
- Reverb wetness
- Reverb room size
- Chorus on/off
- Chorus wetness
- Chorus depth

These controls affect rendered audio only. MIDI exports keep the note data and instrument changes, but do not bake in audio effects.

For WAV/MP3 exports, `Others Quiet` now uses real audio attenuation during rendering instead of only reducing MIDI note velocity, so the backing parts come out more predictably quieter across different soundfonts.

By default, new sessions start with the metronome enabled, quiet volume set to `20`, metronome volume set to `20`, and both reverb and chorus turned off.

### Export modes

| Mode | Output |
|---|---|
| **Both (Quiet + Silent)** | Two files per track: one with others quiet, one with others silent |
| **All Normal** | One file with all selected tracks at full volume |
| **Others Quiet** | One file per track; other tracks play at quiet volume |
| **Others Silent** | One file per track; other tracks are silent |

## Bundled Soundfonts

Two soundfonts are included in `soundfonts/` and loaded automatically:

| File | Used for |
|---|---|
| `piano.sf2` | All MIDI tracks |
| `metronome.sf2` | Metronome (High Wood Block, Bank 0 / Preset 115) |

You can override either in the **Import** tab, or assign a different soundfont to individual tracks in the **Tracks** tab. Each track row also exposes an **Inst** picker so you can choose the bank/program preset to use from that soundfont for preview and export. The metronome section has its own instrument picker as well, using the metronome soundfont or falling back to the tracks soundfont if no separate metronome soundfont is set.
