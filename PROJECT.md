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
   **Vlad starts it himself with `render.bat`** (double-click, or drag a PDF onto it): processes
   Claude starts die when the Claude Code session ends. The render resumes itself:
   chapters whose .m4a already exists are skipped. Keep the PC awake.
5. Publish: `publish.bat` (or `autopublish.ps1`, which publishes new chapters every 5 minutes while
   the render runs; Claude isn't allowed to start it, Vlad runs it himself).
6. The page opens the first book in `books/index.json`. Any other book: `...?book=<slug>`
   (slug = PDF file name in lowercase with `-` instead of spaces). There is no book picker on the page yet.

## Text artifacts: check BEFORE rendering every new book

A full render takes hours, and every one of these was found only after 12 chapters were done.
After `--dry`, audit the split sentences of the **whole** book (not just the first paragraphs) for the
patterns below; convert.py handles the ones marked ✔, a new book will have its own variants.

| Artifact in the PDF | What it sounds/looks like | Status |
|---|---|---|
| Spaced ellipsis `. . .` | each dot becomes its own TTS call = half a second of audible noise; sentence cut in pieces. Must be one `…` = a pause only slightly longer than a period | ✔ `clean()` |
| Any piece with no letters/digits (stray `.` `.”` `?`) | noise when spoken alone | ✔ merged into the previous sentence in `split_sentences()` |
| Divider page of the next chapter ("WEEK 7") before its TOC target | stray word at the end of the previous chapter | ✔ `build_chapters()` |
| Heading/subtitle repeated at the top of the chapter | title spoken twice | ✔ |
| Small-caps paragraph openers `ONE OF OUR Chief` | read letter by letter as acronyms | ✔ lowercased |
| Lines entirely in caps (epigraph authors `BEN SHAHN`) | same; in text must become `Ben Shahn`, not `Ben shahn` | ✔ Title Case |
| List number in its own block (`1.` then the item) | number and item split into separate paragraphs/sentences | ✔ merged |
| Initials and abbreviations (`C. G. Jung`, `Sept. 2`) | sentence wrongly split after the period | ✔ `NO_BREAK`, `ABBREV` (extend per book) |
| Print hyphenation left in the text (`dic- tated`) | read as two words | ✔ (keeps `two- to three-year`) |
| Ligatures ﬁ ﬂ ﬀ | wrong characters | ✔ NFKC |
| Bullets `•`, fill-in lines `______` | symbols in text / unknown sound | ✔ bullet stripped, blanks read as "blank" |
| Paragraph split by a page break | pause mid-sentence | ✔ joined |
| Page numbers, running headers/footers | read aloud in the middle of the text | this book had none; **check for the next one** |
| Footnote markers, tables, URLs, captions | unknown | not handled; **check** |

Run `python audit.py Book.pdf`. It flags: pieces with no letters, `. .`,
`[a-z]- [a-z]`, leftover 4+ letter ALL-CAPS words, odd symbols, one-word pieces without end punctuation,
very long pieces (>450 chars), first and last item of every chapter.

After rendering, verify one chapter numerically before trusting the rest: file duration = `book.json`
duration, last segment text = last text of the chapter in the PDF, every segment's time range contains speech.

Already rendered chapters can be repaired without re-rendering (decode → cut ranges by the segment
times → re-encode → shift the times in chNN.json and the section times in book.json).
Don't run such a repair while convert.py is rendering: it rewrites book.json from its own copy.

## Settings Vlad chose (The Artist's Way, 2026-09-30)

- Voice `af_heart`, render speed 0.9 (so 1.00× in the player = this tempo). American voices only.
  Everything else in the Kokoro model: `a`/`b` = American/British English, `f`/`m` = female/male.
- Pauses (2026-10-02, "natural human reading" rework): Kokoro clips used to be concatenated
  back-to-back, so sentences inside a paragraph had **zero** pause between them. Now each clip's
  variable edge silence (0.03–0.17 s) is trimmed to a fixed pad and explicit gaps are inserted:
  0.6 s after `.`, 0.7 s after `?`/`!`, 0.85 s after `…`, +0.1 s after sentences longer than 6 s;
  paragraph end adds +0.5 s on top, headings +0.6 s, 1.5 s before a section heading.
  All constants sit at the top of convert.py. Kokoro needs no help *inside* a sentence —
  measured: comma/dash/parens ≈ 0.2 s, semicolon/ellipsis/quotes ≈ 0.3 s, and it intones
  questions/exclamations itself (no SSML support; punctuation reaching the model is the only lever).
  A/B of the old vs new ch01 is in `samples/ch01-old-pauses.m4a` / `ch01-new-pauses.m4a`.
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
