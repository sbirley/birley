#!/usr/bin/env python3
"""Build a cinematic "kittens ready for a new home" montage video.

Drop photos into kitten_video/photos/ (JPG, PNG or HEIC) and run:

    python3 kitten_video/build.py              # vertical 1080x1920 (Reels/TikTok/Stories)
    python3 kitten_video/build.py --landscape  # 1920x1080 (Facebook feed/YouTube)
    python3 kitten_video/build.py --demo       # preview with placeholder cards

Everything is generated locally: voiceover (Piper offline TTS), an original
music bed with a melodic hook (synthesised with numpy), and the montage
(Ken Burns moves, crossfades, film grade, grain, vignette, animated titles).
The music ducks automatically under the voiceover.
"""

import argparse
import math
import random
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
from scipy.signal import butter, fftconvolve, sawtooth, sosfilt

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent
FONTS = ROOT / "fonts"
CACHE = ROOT / ".cache"
VOICE_URL = "https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-en-us-lessac-medium.tar.gz"
VOICE_MODEL = CACHE / "en-us-lessac-medium.onnx"

FPS = 30
SR = 44100
BPM = 96
BEAT = 60 / BPM
BAR = 4 * BEAT
PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}

# Each voiceover line drives the on-screen title shown while it plays.
SCRIPT = [
    {"vo": "Stop scrolling. You need to meet these little ones.",
     "kicker": "STOP SCROLLING", "title": "Meet the little ones"},
    {"vo": "Tiny paws. Big personalities. And more cuddles than you can count.",
     "kicker": "TINY PAWS", "title": "Big personalities"},
    {"vo": "They've been growing up playful, curious, and so full of love.",
     "kicker": "PLAYFUL  ·  CURIOUS", "title": "So full of love"},
    {"vo": "And now, they're looking for a family of their own.",
     "kicker": "NOW LOOKING FOR", "title": "A family of their own"},
    {"vo": "Ready for their new home, mid-December!",
     "kicker": "READY FOR THEIR NEW HOME", "title": "Mid-December", "big": True},
    {"vo": "Don't miss your chance. Message me for more information.",
     "kicker": "DON'T MISS YOUR CHANCE", "title": "Message me for info", "end": True},
]

CREAM = (255, 244, 228)
GOLD = (240, 196, 132)


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


# ---------------------------------------------------------------- voiceover

def ensure_voice():
    if VOICE_MODEL.exists():
        return
    CACHE.mkdir(exist_ok=True)
    tgz = CACHE / "voice.tar.gz"
    print("Downloading Piper voice model...")
    urllib.request.urlretrieve(VOICE_URL, tgz)
    shutil.unpack_archive(tgz, CACHE)
    tgz.unlink()


def make_voiceover(work):
    """Synthesise each line and lay them on the musical grid. Returns (wav, timings)."""
    ensure_voice()
    piper = shutil.which("piper") or sys.exit("piper not found: pip install piper-tts")
    clips = []
    for i, line in enumerate(SCRIPT):
        raw, clean = work / f"vo{i}_raw.wav", work / f"vo{i}.wav"
        subprocess.run([piper, "-m", str(VOICE_MODEL), "-c", f"{VOICE_MODEL}.json",
                        "--length_scale", "1.08", "-f", str(raw)],
                       input=line["vo"], text=True, check=True, capture_output=True)
        # Broadcast-style polish: trim silence, warm EQ, gentle compression.
        run(["ffmpeg", "-y", "-i", str(raw), "-af",
             "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
             "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
             "highpass=f=90,equalizer=f=220:t=q:w=1:g=2,equalizer=f=3500:t=q:w=1.2:g=2.5,"
             "acompressor=threshold=-20dB:ratio=3:attack=5:release=90:makeup=2,"
             f"aresample={SR}", "-ac", "2", str(clean)])
        clips.append(clean)

    # Start each line on a half-bar so the voice lands with the music.
    grid = BAR / 2
    t = BEAT  # hook lands almost immediately
    timings = []
    for clip in clips:
        d = duration(clip)
        timings.append((t, t + d))
        t = math.ceil((t + d + 0.35) / grid) * grid
    total = math.ceil((timings[-1][1] + 3.2) / BAR) * BAR

    inputs, labels = [], []
    for i, (clip, (start, _)) in enumerate(zip(clips, timings)):
        inputs += ["-i", str(clip)]
        ms = int(start * 1000)
        labels.append(f"[{i}]adelay={ms}|{ms}[d{i}]")
    mix = ";".join(labels) + ";" + "".join(f"[d{i}]" for i in range(len(clips)))
    mix += f"amix=inputs={len(clips)}:normalize=0,apad,atrim=0:{total}"
    vo = work / "voiceover.wav"
    run(["ffmpeg", "-y", *inputs, "-filter_complex", mix, "-ar", str(SR), str(vo)])
    return vo, timings, total


# ---------------------------------------------------------------- music

def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


CHORDS = [  # I - V - vi - IV in C major (one chord per bar)
    {"bass": 36, "pad": [60, 64, 67, 72]},
    {"bass": 43, "pad": [59, 62, 67, 71]},
    {"bass": 45, "pad": [57, 60, 64, 69]},
    {"bass": 41, "pad": [57, 60, 65, 69]},
]

# The hook: a four-bar melody that repeats once the beat drops.
HOOK = [
    (76, 0, .5), (79, .5, .5), (84, 1, 1.5), (79, 2.5, .5), (76, 3, 1),
    (74, 4, .5), (79, 4.5, .5), (83, 5, 1.5), (79, 6.5, .5), (74, 7, 1),
    (72, 8, .5), (76, 8.5, .5), (81, 9, 1.5), (79, 10.5, .5), (76, 11, 1),
    (77, 12, .5), (76, 12.5, .5), (74, 13, .5), (72, 13.5, .5), (74, 14, 2),
]


def env(n, attack, release):
    e = np.ones(n)
    a, r = min(int(attack * SR), n), min(int(release * SR), n)
    if a:
        e[:a] = np.linspace(0, 1, a)
    if r:
        e[-r:] *= np.linspace(1, 0, r)
    return e


def add(buf, start, sig):
    i = int(start * SR)
    if i >= len(buf):
        return
    sig = sig[: len(buf) - i]
    buf[i:i + len(sig)] += sig


def pluck(freq, length, bright=1.0):
    n = int(length * SR)
    t = np.arange(n) / SR
    sig = sum(a * np.sin(2 * np.pi * freq * k * t) * np.exp(-t * (2.2 + k * 1.3 * bright))
              for k, a in [(1, 1), (2, .45), (3, .22), (4, .1), (6, .04)])
    return sig * env(n, .004, .05)


def pad_chord(notes, length):
    n = int(length * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n)
    for note in notes:
        for cents in (-7, 0, 7):
            f = midi(note) * 2 ** (cents / 1200)
            sig += sawtooth(2 * np.pi * f * t + random.random() * 6.28) * 0.06
    sig = sosfilt(butter(2, 1400, fs=SR, output="sos"), sig)
    return sig * env(n, .6, .9)


def kick():
    n = int(.35 * SR)
    t = np.arange(n) / SR
    f = 50 + 90 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)


def noise_hit(length, lo, hi, decay):
    n = int(length * SR)
    t = np.arange(n) / SR
    sig = sosfilt(butter(2, [lo, hi], btype="band", fs=SR, output="sos"), np.random.randn(n))
    return sig * np.exp(-t * decay)


def reverb(sig, seconds=2.2, wet=.28):
    n = int(seconds * SR)
    t = np.arange(n) / SR
    ir = np.random.randn(n) * np.exp(-t * 3.2)
    ir = sosfilt(butter(1, 5000, fs=SR, output="sos"), ir)
    ir /= np.abs(ir).sum() ** .5 * 8
    return sig + wet * fftconvolve(sig, ir)[: len(sig)]


def make_music(work, timings, total):
    random.seed(7)
    np.random.seed(7)
    n = int((total + 1) * SR)
    pads, keys, bass, drums, fx = (np.zeros(n) for _ in range(5))
    drop = timings[1][0]           # beat + hook come in with line 2
    reveal = timings[4][0]         # "mid-December" impact
    outro = timings[5][1] + .3     # drums out after the last line
    bars = int(total / BAR) + 1

    for b in range(bars):
        t0 = b * BAR
        ch = CHORDS[b % 4]
        add(pads, t0, pad_chord(ch["pad"], BAR + .9))
        full = drop <= t0 < outro
        if t0 < drop or t0 >= outro:  # music-box arpeggio for intro/outro
            for k, note in enumerate(ch["pad"] + [ch["pad"][1] + 12]):
                if t0 + k * BEAT * .75 < total - .5:
                    add(keys, t0 + k * BEAT * .75, .35 * pluck(midi(note + 12), 1.6, .6))
        if full:
            for k in range(4):
                add(bass, t0 + k * BEAT, .5 * pluck(midi(ch["bass"]), BEAT * .95, .2))
            for k in range(4):
                tb = t0 + k * BEAT
                if reveal - BEAT * 1.5 < tb < reveal:  # breath before the reveal
                    continue
                add(drums, tb, .9 * kick() if k in (0, 2) else .45 * noise_hit(.25, 900, 5000, 18))
                add(drums, tb + BEAT / 2, .12 * noise_hit(.08, 6000, 14000, 60))
                add(drums, tb, .08 * noise_hit(.06, 6000, 14000, 70))
            # the hook melody, looping every four bars from the drop
            phrase_bar = int(round((t0 - drop) / BAR)) % 4
            for note, beat, length in HOOK:
                if phrase_bar * 4 <= beat < phrase_bar * 4 + 4:
                    add(keys, t0 + (beat - phrase_bar * 4) * BEAT, .55 * pluck(midi(note), length * BEAT + 1.2))

    # riser into the reveal, then an impact swell
    rl = BAR
    rn = int(rl * SR)
    rt = np.linspace(0, 1, rn)
    riser = np.random.randn(rn)
    riser = sosfilt(butter(2, 3000, btype="high", fs=SR, output="sos"), riser) * rt ** 2.5 * .25
    add(fx, reveal - rl, riser)
    add(fx, reveal, .9 * kick())
    add(fx, reveal, .5 * noise_hit(2.5, 200, 9000, 1.6))

    mix = .55 * pads + keys + .6 * bass + .55 * drums + fx
    mix = reverb(mix)
    mix = np.tanh(mix * 1.2)
    mix *= env(len(mix), .05, 2.5)
    mix = mix[: int(total * SR)]
    mix /= np.abs(mix).max() + 1e-9
    stereo = np.stack([mix, np.roll(mix, 220)], axis=1)  # slight width
    pcm = (stereo * 0.8 * 32767).astype("<i2").tobytes()
    out = work / "music.wav"
    import wave
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm)
    return out


def mix_audio(work, vo, music):
    out = work / "mix.wav"
    run(["ffmpeg", "-y", "-i", str(music), "-i", str(vo), "-filter_complex",
         "[0]volume=0.55[m];[1]asplit=2[v][sc];"
         "[m][sc]sidechaincompress=threshold=0.03:ratio=6:attack=30:release=450[duck];"
         "[duck][v]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=9",
         "-ar", str(SR), str(out)])
    return out


# ---------------------------------------------------------------- pictures

def photo_date(path):
    try:
        exif = Image.open(path).getexif()
        stamp = exif.get(36867) or exif.get_ifd(0x8769).get(36867) or exif.get(306)
        if stamp:
            return str(stamp)
    except Exception:
        pass
    return ""


def load_photos(folder):
    files = [p for p in sorted(folder.iterdir()) if p.suffix.lower() in PHOTO_EXTS]
    skipped = [p.name for p in folder.iterdir() if p.is_file() and p.suffix.lower() not in PHOTO_EXTS
               and not p.name.startswith(".")]
    if skipped:
        print("Skipping non-photo files:", ", ".join(skipped))
    files.sort(key=lambda p: (photo_date(p) or "9999", p.name))
    return files


def font(name, size, weight):
    f = ImageFont.truetype(str(FONTS / name), size)
    f.set_variation_by_axes([weight])
    return f


def cover(img, w, h):
    return ImageOps.fit(img, (w, h), Image.LANCZOS, centering=(.5, .45))


def compose(path, W, H, k):
    """Photo on a blurred, darkened copy of itself, sized k× the frame for Ken Burns room."""
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    BW, BH = int(W * k), int(H * k)
    ar, car = img.width / img.height, BW / BH
    if abs(ar - car) / car < .14:
        return cover(img, BW, BH)
    bg = cover(img, BW // 8, BH // 8).filter(ImageFilter.GaussianBlur(6)).resize((BW, BH), Image.BICUBIC)
    bg = Image.blend(bg, Image.new("RGB", bg.size, (12, 8, 6)), .45)
    # between "contain" and "cover": fills more of the frame, crops at most ~12% per side
    s_contain = min(BW / img.width, BH / img.height)
    s = min(max(BW / img.width, BH / img.height), s_contain * 1.3)
    fg = img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)
    fw, fh = min(fg.width, BW), min(fg.height, BH)
    fg = fg.crop(((fg.width - fw) // 2, int((fg.height - fh) * .45), (fg.width - fw) // 2 + fw,
                  int((fg.height - fh) * .45) + fh))
    shadow = Image.new("L", (BW, BH), 0)
    x, y = (BW - fg.width) // 2, (BH - fg.height) // 2
    ImageDraw.Draw(shadow).rectangle([x, y, x + fg.width, y + fg.height], fill=170)
    shadow = shadow.filter(ImageFilter.GaussianBlur(30))
    bg.paste(Image.new("RGB", bg.size, (0, 0, 0)), (0, 0), shadow)
    bg.paste(fg, (x, y))
    return bg


def demo_photos(folder, n=10):
    folder.mkdir(parents=True, exist_ok=True)
    palette = [(214, 170, 132), (160, 140, 120), (226, 200, 170), (120, 104, 96), (238, 214, 190)]
    f = font("PlayfairDisplay-Italic.ttf", 120, 600)
    for i in range(n):
        w, h = (1536, 2048) if i % 3 else (2048, 1536)
        base = np.zeros((h, w, 3), np.float32)
        c1, c2 = np.array(palette[i % 5]), np.array(palette[(i + 2) % 5])
        yy = np.linspace(0, 1, h)[:, None, None]
        base[:] = c1 * (1 - yy) + c2 * yy
        img = Image.fromarray(base.astype(np.uint8))
        d = ImageDraw.Draw(img)
        cx, cy = w // 2, h // 2
        d.ellipse([cx - 260, cy - 200, cx + 260, cy + 260], fill=(60, 45, 40))  # head
        d.polygon([(cx - 250, cy - 60), (cx - 200, cy - 360), (cx - 60, cy - 180)], fill=(60, 45, 40))
        d.polygon([(cx + 250, cy - 60), (cx + 200, cy - 360), (cx + 60, cy - 180)], fill=(60, 45, 40))
        for ex in (-100, 100):
            d.ellipse([cx + ex - 40, cy - 20, cx + ex + 40, cy + 60], fill=(250, 220, 120))
        d.text((cx, cy + 420), f"your photo {i + 1}", font=f, fill=(40, 30, 28), anchor="mm")
        img.save(folder / f"demo_{i:02d}.jpg", quality=92)


# ---------------------------------------------------------------- titles

def spaced(draw, xy, text, fnt, fill, tracking, anchor_center=True):
    widths = [draw.textlength(ch, font=fnt) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x, y = xy
    if anchor_center:
        x -= total / 2
    for ch, w in zip(text, widths):
        draw.text((x, y), ch, font=fnt, fill=fill, anchor="ls")
        x += w + tracking


def title_layer(W, H, line, vertical):
    """RGBA overlay with kicker + title and a soft drop shadow."""
    scale = W / 1080 if vertical else H / 1080
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    big, end = line.get("big"), line.get("end")
    cy = H * (.5 if end else (.74 if vertical else .76))
    kf = font("Montserrat.ttf", int(34 * scale), 600)
    tsize = 150 if big else (104 if end else 96)
    tf = font("PlayfairDisplay-Italic.ttf" if not big else "PlayfairDisplay.ttf", int(tsize * scale), 700)
    words = line["title"]
    max_w = W * .86
    lines = [words]
    while " " not in words and d.textlength(words, font=tf) > max_w:
        tf = font(Path(tf.path).name, int(tf.size * .92), 700)
    if d.textlength(words, font=tf) > max_w:
        parts = words.split()
        best = min(range(1, len(parts)), key=lambda i: abs(len(" ".join(parts[:i])) - len(" ".join(parts[i:]))))
        lines = [" ".join(parts[:best]), " ".join(parts[best:])]
    lh = tf.size * 1.1
    spaced(d, (W / 2, cy - lh * (len(lines) - 1) / 2 - tf.size * .55), line["kicker"], kf, GOLD + (255,), 8 * scale)
    for i, l in enumerate(lines):
        d.text((W / 2, cy + i * lh + tf.size * .35), l, font=tf, fill=CREAM + (255,), anchor="ms")
    if end:  # a little paw print and a hairline under the call to action
        y = cy + len(lines) * lh + 40 * scale
        d.line([(W / 2 - 120 * scale, y), (W / 2 + 120 * scale, y)], fill=GOLD + (220,), width=max(2, int(2 * scale)))
        px, py, r = W / 2, y + 90 * scale, 26 * scale
        d.ellipse([px - r * 1.3, py - r, px + r * 1.3, py + r * 1.2], fill=CREAM + (255,))
        for dx, dy in ((-1.5, -1.6), (-.55, -2.3), (.55, -2.3), (1.5, -1.6)):
            d.ellipse([px + dx * r - r * .45, py + dy * r - r * .55, px + dx * r + r * .45, py + dy * r + r * .55],
                      fill=CREAM + (255,))
    alpha = layer.getchannel("A")
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow.putalpha(alpha.filter(ImageFilter.GaussianBlur(14 * scale)).point(lambda v: int(v * .85)))
    return Image.alpha_composite(shadow, layer)


def bottom_gradient(W, H):
    g = np.zeros((H, W, 1), np.float32)
    y = np.linspace(0, 1, H)
    g[:, :, 0] = (np.clip((y - .38) / .55, 0, 1) ** 1.2 * .86)[:, None]
    return g


# ---------------------------------------------------------------- render

def ease(x):
    return x * x * (3 - 2 * x)


def render_video(work, photos, timings, total, W, H, vertical):
    k = 1.16
    xf = .9  # crossfade length
    n = len(photos)
    per = (total + (n - 1) * xf) / n
    print(f"{n} photos, {per:.1f}s each, {total:.1f}s total")
    bases = [np.asarray(compose(p, W, H, k)) for p in photos]
    rng = random.Random(3)
    moves = []
    for i in range(n):
        zin = i % 2 == 0
        z0, z1 = (1.0, k) if zin else (k, 1.0)
        z0 = 1.0 + (z0 - 1.0) * .9
        z1 = 1.0 + (z1 - 1.0) * .9
        moves.append((z0, z1, rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))

    titles = []
    for i, (line, (s, e)) in enumerate(zip(SCRIPT, timings)):
        t_in = .25 if i == 0 else s - .15
        t_out = total if line.get("end") else min(e + .6, (timings[i + 1][0] - .15) if i + 1 < len(timings) else total)
        layer = np.asarray(title_layer(W, H, line, vertical)).astype(np.float32) / 255
        titles.append((t_in, t_out, layer, line.get("end")))
    grad = bottom_gradient(W, H)

    def frame_of(i, local):
        z0, z1, px0, py0, px1, py1 = moves[i]
        p = ease(min(max(local / per, 0), 1))
        z = z0 + (z1 - z0) * p
        BH, BW = bases[i].shape[:2]
        ww, wh = BW / z, BH / z
        px, py = px0 + (px1 - px0) * p, py0 + (py1 - py0) * p
        cx = BW / 2 + px * (BW - ww) / 2
        cy = BH / 2 + py * (BH - wh) / 2
        sx, sy = ww / W, wh / H
        img = Image.fromarray(bases[i]).transform((W, H), Image.AFFINE,
                                                   (sx, 0, cx - ww / 2, 0, sy, cy - wh / 2), Image.BICUBIC)
        return np.asarray(img).astype(np.float32) / 255

    grade = ("eq=contrast=1.07:saturation=1.1:gamma=0.97,"
             "colorbalance=rs=.04:bs=-.04:rm=.02:bm=-.03:rh=.03:bh=-.02,"
             "vignette=angle=PI/4.5,noise=alls=4:allf=t,"
             f"fade=t=in:st=0:d=0.8,fade=t=out:st={total - 1.2:.2f}:d=1.2")
    if not vertical:
        bar = int(H * .055)
        grade += f",drawbox=x=0:y=0:w=iw:h={bar}:c=black:t=fill,drawbox=x=0:y=ih-{bar}:w=iw:h={bar}:c=black:t=fill"
    silent = work / "video.mp4"
    proc = subprocess.Popen(["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-vf", grade, "-c:v", "libx264", "-preset", "medium",
                             "-crf", "20", "-maxrate", "12M", "-bufsize", "24M", "-pix_fmt", "yuv420p", str(silent)],
                            stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    frames = int(total * FPS)
    for f in range(frames):
        t = f / FPS
        i = min(int(t / (per - xf)), n - 1)
        local = t - i * (per - xf)
        img = frame_of(i, local)
        if i + 1 < n and local > per - xf:
            a = ease((local - (per - xf)) / xf)
            img = img * (1 - a) + frame_of(i + 1, local - (per - xf)) * a
        img = img * (1 - grad)
        for t_in, t_out, layer, end in titles:
            if t_in <= t <= t_out:
                a = min(1, (t - t_in) / .45, (t_out - t) / .45 if not end else 1)
                if end:  # dim the picture behind the final call to action
                    img = img * (1 - .6 * a)
                rise = int((1 - ease(min(1, (t - t_in) / .6))) * H * .015)
                lay = np.roll(layer, rise, axis=0) if rise else layer
                la = lay[..., 3:4] * a
                img = img * (1 - la) + lay[..., :3] * la
        proc.stdin.write((np.clip(img, 0, 1) * 255).astype(np.uint8).tobytes())
        if f % (FPS * 5) == 0:
            print(f"  rendering {t:4.1f}s / {total:.1f}s", flush=True)
    proc.stdin.close()
    if proc.wait():
        sys.exit("ffmpeg failed while encoding video")
    return silent


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--photos", type=Path, default=ROOT / "photos")
    ap.add_argument("--landscape", action="store_true", help="1920x1080 instead of vertical 1080x1920")
    ap.add_argument("--demo", action="store_true", help="use placeholder cards to preview the edit")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    vertical = not args.landscape
    W, H = (1080, 1920) if vertical else (1920, 1080)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        folder = args.photos
        if args.demo:
            folder = work / "demo"
            demo_photos(folder)
        photos = load_photos(folder) if folder.exists() else []
        if not photos:
            sys.exit(f"No photos found in {folder}. Add JPG/PNG/HEIC files or run with --demo.")
        print("Voiceover...")
        vo, timings, total = make_voiceover(work)
        print("Music...")
        music = make_music(work, timings, total)
        mix = mix_audio(work, vo, music)
        print("Montage...")
        video = render_video(work, photos, timings, total, W, H, vertical)
        out = args.out or ROOT / "output" / ("kittens_{}{}.mp4".format(
            "vertical" if vertical else "landscape", "_demo" if args.demo else ""))
        out.parent.mkdir(exist_ok=True)
        run(["ffmpeg", "-y", "-i", str(video), "-i", str(mix), "-c:v", "copy", "-c:a", "aac",
             "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)])
        shutil.copy(music, out.with_name("music_bed.wav"))
    print(f"Done: {out}")


if __name__ == "__main__":
    main()
