# text2speech — bedtime audiobook reader

A PDF book is rendered on this PC with Kokoro TTS (offline) into audio per chapter
plus text with per-sentence timings, then published to GitHub Pages and listened to on iPhone.

- Site: https://vladislavgeneralov.github.io/text2speech/
- Repo: github.com/VladislavGeneralov/text2speech (code on `main`, `site/` published as the `gh-pages` branch)

## Adding a new book

1. Put the PDF in this folder (PDFs are git-ignored, so the book file itself never goes to GitHub).
2. Check how the text extracts, without making audio:
   `python convert.py Book.pdf --dry --limit 5`
   - Chapters = the PDF's level-1 bookmarks (TOC), sections = level-2.
     **A PDF with no TOC gives zero chapters**, so `build_chapters()` needs a fallback first.
   - TOC entries that are skipped: Also by / Copyright / Contents / Index / Reading List / Resources (`SKIP` regex).
   - Look for: duplicated headings, words in ALL CAPS (they get lowercased, otherwise TTS spells them out),
     page numbers or running headers leaking into the text.
3. Optional short preview before the full render: `python convert.py Book.pdf --only 7 --limit 4`,
   then delete `site/books/<slug>/` so the full run starts clean.
4. Full render (takes hours: ~2.2× realtime on the Ryzen 5 5500U, ~160 words per audio minute):
   `python convert.py Book.pdf --voice af_heart --speed 0.9`
   Run it as a separate process so it doesn't die with the terminal. The render resumes itself:
   chapters whose .m4a already exists are skipped. Keep the PC awake.
5. Publish: `publish.bat` (or `autopublish.ps1`, which publishes new chapters every 5 minutes while
   the render runs; Claude isn't allowed to start it, Vlad runs it himself).
6. The page opens the first book in `books/index.json`. Any other book: `...?book=<slug>`
   (slug = PDF file name in lowercase with `-` instead of spaces). There is no book picker on the page yet.

## Settings Vlad chose (The Artist's Way, 2026-09-30)

- Voice `af_heart`, render speed 0.9 (so 1.00× in the player = this tempo). American voices only.
  Everything else in the Kokoro model: `a`/`b` = American/British English, `f`/`m` = female/male.
- Audio: mono AAC 48 kbps m4a (~20 MB/hour; GitHub rejects files over 100 MB).
- Each chapter gets `chNN.json` = `[start, end, sentence, kind]`, kind 0 = same paragraph, 1 = new paragraph, 2 = heading.

## Player (site/index.html), what Vlad asked for

- One shared player (number + title, ▶/❚❚, position bar, ±15 s); the chapter list opens as a pop-up via "Chapters".
- Speed 0.7–1.5. Next chapter starts automatically.
- Text window ±15 s around the current spot, current sentence highlighted, **text must be selectable and copyable** (Copy button).
- Background music from a SoundCloud link, looped; loading copied from SCDJ (proxy `scdj-proxy.ptntonesix.workers.dev`).
- Two volumes: Book (default 100%) and Music (default 30%), mixed in Web Audio; the iPhone's buttons control the whole mix.

## iOS Safari gotchas found here

- A locked/background page cannot start a *different* `<audio>` → one shared element that switches `src`.
- `audio.volume` can't be changed from JS on iOS → GainNodes via `createMediaElementSource`.
- `playbackRate` resets when `src` changes → set it again on `play`.
- Pages lets browsers cache files for 10 minutes → `book.json`/`index.json` are fetched with `cache: "no-cache"`;
  to see a new version of the page itself right away, add `?v=N` to the URL.
- Font smaller than 16px in an input → Safari zooms the page when you tap into it.

## Files

- `convert.py`: PDF → `site/books/<slug>/` (chNN.m4a, chNN.json, book.json) + `site/books/index.json`
- `site/index.html`: the whole player
- `publish.bat` / `autopublish.ps1`: commit, push `main`, subtree-split `site` → `gh-pages`
- `start.bat`: local server (Vlad doesn't use it, he checks straight on Pages)
- `models/` (git-ignored): kokoro-v1.0.onnx + voices-v1.0.bin from github.com/thewh1teagle/kokoro-onnx releases
- `samples/`: voice samples
