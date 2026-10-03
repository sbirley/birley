# Kitten adoption montage

A cinematic vertical (9:16) or landscape (16:9) video built from kitten photos, with:

- **Voiceover** (offline Piper voice) that announces the kittens are ready for their new home **mid-December** and to **message me for info**
- **Original background music** with a melodic hook that comes in on line 2, a riser into the "Mid-December" reveal, and automatic ducking under the voice
- **Montage**: slow Ken Burns push-ins/pull-outs, crossfades, warm film grade, grain, vignette, animated serif titles, and a final "Message me for info" card

## Make the video

1. Put the kitten photos (JPG, PNG or HEIC straight from iPhone) in `kitten_video/photos/`.
   They're ordered by the date the photo was taken. 8–14 photos works best.
2. Run:

```bash
pip install -r kitten_video/requirements.txt
python3 kitten_video/build.py              # vertical, for Reels / TikTok / Stories / Marketplace
python3 kitten_video/build.py --landscape  # 16:9 with letterbox bars, for Facebook feed / YouTube
python3 kitten_video/build.py --demo       # preview the edit with placeholder cards
```

The video is written to `kitten_video/output/`. To change the words, edit `SCRIPT` at the top of `build.py`.

Fonts: Playfair Display and Montserrat (SIL Open Font License, see `fonts/`).
