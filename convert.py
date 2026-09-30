"""PDF -> per-chapter audiobook for the web player.

Usage:
  python convert.py book.pdf [--voice af_heart] [--speed 0.9] [--only 3] [--limit 10]

Chapters come from the PDF's level-1 TOC entries, sections from level-2 entries.
Output goes to site/books/<slug>/ (chNN.m4a + book.json) and site/books/index.json.
Re-running skips chapters whose .m4a already exists, so an interrupted render resumes.
"""
import argparse, json, re, subprocess, sys, unicodedata
from pathlib import Path

import numpy as np
import pymupdf
import soundfile as sf

ROOT = Path(__file__).parent
SITE_BOOKS = ROOT / "site" / "books"
SR = 24000
PARA_GAP = 0.45   # seconds of silence between paragraphs
SECTION_GAP = 1.2  # before a section heading

# TOC entries that make no sense read aloud
SKIP = re.compile(r"^(also by|copyright|contents|index|reading list|resources)\b", re.I)


KEEP_CAPS = {"AA", "TV", "USA", "UK", "NYC", "LA", "CD", "AIDS", "OK"}


def clean(text, title=False):
    text = unicodedata.normalize("NFKC", text)  # ligatures: ﬂ ﬀ ﬃ -> fl ff ffi
    text = re.sub(r"-\n(?=\w)", "-", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # ALL-CAPS words (small-caps paragraph openers, epigraph authors) would be spelled
    # out as acronyms, so lowercase them and re-capitalize sentence starts
    def fix(m):
        w = m.group(0)
        if w in KEEP_CAPS:
            return w
        return w.capitalize() if title else w.lower()
    text = re.sub(r"\b[A-Z][A-Z’']+\b", fix, text)
    text = re.sub(r"\bi\b(?![.])", "I", text)  # "I’M" -> "i’m" -> "I’m"
    text = re.sub(r"(^|[.?!]\s+|[“\"]\s*)([a-z])", lambda m: m.group(1) + m.group(2).upper(), text)
    return text


def norm_key(s):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKC", s).lower())


def page_paragraphs(doc, first, last):
    """Text blocks of pages first..last (0-based, inclusive) as (page, text), joining
    paragraphs that were split by a page break."""
    out = []
    for pno in range(first, last + 1):
        blocks = [b for b in doc[pno].get_text("blocks", sort=True) if b[6] == 0]
        for i, b in enumerate(blocks):
            t = clean(b[4])
            if not t or t.isdigit():
                continue
            if i == 0 and out and not re.search(r"[.?!:;”\"’)\]—]$", out[-1][1]) and t[:1].islower():
                out[-1] = (out[-1][0], out[-1][1] + " " + t)
                continue
            out.append((pno, t))
    return out


def build_chapters(doc):
    toc = doc.get_toc()
    lvl1 = [i for i, e in enumerate(toc) if e[0] == 1]
    chapters = []
    for n, i in enumerate(lvl1):
        title, start = toc[i][1], toc[i][2] - 1
        end_idx = lvl1[n + 1] if n + 1 < len(lvl1) else len(toc)
        end = (toc[end_idx][2] - 2) if end_idx < len(toc) else doc.page_count - 1
        if SKIP.match(title):
            continue
        subs = [(e[1], e[2] - 1) for e in toc[i + 1:end_idx] if e[0] == 2 and not SKIP.match(e[1])]
        paras = page_paragraphs(doc, start, max(start, end))
        # drop heading/subtitle blocks at the top; we speak the TOC title instead
        while paras and len(paras[0][1]) < 120 and norm_key(paras[0][1]) in norm_key(title):
            paras = paras[1:]
        items = []  # ("section", title) | ("para", text)
        pending = list(subs)
        for pno, t in paras:
            if pending and pno >= pending[0][1] and norm_key(t) == norm_key(pending[0][0]):
                items.append(("section", clean(pending.pop(0)[0], title=True)))
                continue
            items.append(("para", t))
        chapters.append({"title": clean(title, title=True), "items": items})
    return chapters


def render_chapter(tts, ch, voice, speed, lang, wav_path, limit=None):
    silence = lambda s: np.zeros(int(SR * s), dtype=np.float32)
    parts, t, sections = [], 0.0, []
    segs = []  # [start, end, text, kind]; kind 0 = same paragraph, 1 = new paragraph, 2 = heading
    items = [("title", ch["title"])] + ch["items"]
    if limit:
        items = items[:limit]
    for k, (kind, text) in enumerate(items):
        if kind == "section":
            parts.append(silence(SECTION_GAP)); t += SECTION_GAP
            sections.append({"title": text, "t": round(t, 2)})
        # one TTS call per sentence so the page knows when each sentence is spoken
        sentences = [text] if kind != "para" else split_sentences(text)
        for j, s in enumerate(sentences):
            audio, sr = tts.create(s, voice=voice, speed=speed, lang=lang)
            assert sr == SR
            start = t
            parts.append(audio.astype(np.float32)); t += len(audio) / SR
            segs.append([round(start, 2), round(t, 2), s, 2 if kind != "para" else int(j == 0)])
        gap = 1.0 if kind in ("title", "section") else PARA_GAP
        parts.append(silence(gap)); t += gap
        print(f"\r  {k + 1}/{len(items)} paragraphs", end="", flush=True)
    print()
    sf.write(wav_path, np.concatenate(parts), SR)
    return round(t, 2), sections, segs


ABBREV = re.compile(r"\b(Mr|Mrs|Ms|Dr|St|Jr|Sr|vs|etc|e\.g|i\.e|No|Mt|Prof)\.$", re.I)


def split_sentences(text):
    # break after . ? ! … (plus closing quotes/brackets) when followed by space
    pieces = re.split(r"(?<=[.?!…])([”\"’)\]]*)\s+", text)
    out, buf = [], ""
    for i in range(0, len(pieces), 2):
        buf += pieces[i] + (pieces[i + 1] if i + 1 < len(pieces) else "")
        if ABBREV.search(buf) or (i + 2 < len(pieces) and pieces[i + 2][:1].islower()):
            buf += " "
            continue
        out.append(buf.strip()); buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out


def encode(wav, m4a, title, album, track):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav),
                    "-af", "loudnorm=I=-18:TP=-2", "-ar", str(SR), "-ac", "1",
                    "-c:a", "aac", "-b:a", "48k", "-movflags", "+faststart",
                    "-metadata", f"title={title}", "-metadata", f"album={album}",
                    "-metadata", f"track={track}", str(m4a)], check=True)
    wav.unlink()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--voice", default="af_heart")
    ap.add_argument("--speed", type=float, default=0.9)
    ap.add_argument("--only", type=int, help="render just this chapter number (1-based)")
    ap.add_argument("--limit", type=int, help="only the first N paragraphs per chapter (preview)")
    ap.add_argument("--dry", action="store_true", help="print extracted text, no audio")
    a = ap.parse_args()

    pdf = Path(a.pdf)
    doc = pymupdf.open(pdf)
    meta = doc.metadata or {}
    title = meta.get("title") or pdf.stem.replace("_", " ")
    author = meta.get("author") or ""
    slug = re.sub(r"[^a-z0-9]+", "-", pdf.stem.lower()).strip("-")
    chapters = build_chapters(doc)

    if a.dry:
        for n, ch in enumerate(chapters, 1):
            words = sum(len(t.split()) for _, t in ch["items"])
            print(f"\n=== {n:02d} {ch['title']}  ({words} words)")
            for kind, t in ch["items"][: a.limit or 6]:
                print(f"  [{kind}] {t[:150]}")
        return

    from kokoro_onnx import Kokoro
    tts = Kokoro(str(ROOT / "models/kokoro-v1.0.onnx"), str(ROOT / "models/voices-v1.0.bin"))
    lang = "en-gb" if a.voice.startswith("b") else "en-us"

    out = SITE_BOOKS / slug
    out.mkdir(parents=True, exist_ok=True)
    jpath = out / "book.json"
    book = json.loads(jpath.read_text("utf-8")) if jpath.exists() else {}
    book.update({"title": title, "author": author, "voice": a.voice})
    done = {c["file"]: c for c in book.get("chapters", [])}
    book["chapters"] = []

    # register the book up front so the page can show chapters while the rest renders
    ipath = SITE_BOOKS / "index.json"
    index = json.loads(ipath.read_text("utf-8")) if ipath.exists() else []
    index = [b for b in index if b["slug"] != slug] + [{"slug": slug, "title": title, "author": author}]
    ipath.write_text(json.dumps(index, ensure_ascii=False, indent=1), "utf-8")

    for n, ch in enumerate(chapters, 1):
        fname = f"ch{n:02d}.m4a"
        if (a.only and n != a.only) or ((out / fname).exists() and fname in done):
            if fname in done:
                book["chapters"].append(done[fname])
            continue
        print(f"[{n}/{len(chapters)}] {ch['title']}")
        wav = out / f"ch{n:02d}.wav"
        dur, sections, segs = render_chapter(tts, ch, a.voice, a.speed, lang, wav, a.limit)
        encode(wav, out / fname, ch["title"], title, n)
        tname = f"ch{n:02d}.json"
        (out / tname).write_text(json.dumps(segs, ensure_ascii=False, separators=(",", ":")), "utf-8")
        book["chapters"].append({"n": n, "title": ch["title"], "file": fname, "text": tname,
                                 "duration": dur, "sections": sections})
        book["chapters"].sort(key=lambda c: c["n"])
        jpath.write_text(json.dumps(book, ensure_ascii=False, indent=1), "utf-8")

    book["chapters"].sort(key=lambda c: c["n"])
    jpath.write_text(json.dumps(book, ensure_ascii=False, indent=1), "utf-8")
    print("done:", out)


if __name__ == "__main__":
    sys.exit(main())
