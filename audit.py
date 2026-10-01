"""Dry audit of a PDF before rendering: python audit.py Book.pdf
Lists text pieces that would sound wrong (see PROJECT.md, "Text artifacts")."""
import re, sys, collections
sys.stdout.reconfigure(encoding="utf-8")
import convert, pymupdf

doc = pymupdf.open(sys.argv[1])
chs = convert.build_chapters(doc)
cnt = collections.Counter()
shown = collections.Counter()
def show(tag, n, s):
    cnt[tag] += 1
    if shown[tag] < 12:
        shown[tag] += 1
        print(f"  {tag} ch{n:02d}: {s[:120]}")
for n, ch in enumerate(chs, 1):
    last = ch["items"][-1][1] if ch["items"] else ""
    print(f"ch{n:02d} {ch['title'][:50]!r} items={len(ch['items'])} last={last[-50:]!r}")
    for kind, t in ch["items"]:
        segs = convert.split_sentences(t) if kind == "para" else [t]
        for s in segs:
            if not re.search(r"[A-Za-z]", s): show("no-letters", n, s)
            if re.search(r"\. \.", s): show("spaced-dots", n, s)
            if re.search(r"[a-z]- [a-z]", s): show("hyphen-space", n, s)
            if re.search(r"\b[A-Z]{4,}\b", s): show("caps-left", n, s)
            if re.search(r"[•·▪■_|#<>{}\\^~]", s): show("symbol", n, s)
            if len(s) > 450: show("very-long", n, s)
            if len(s.split()) == 1 and kind == "para" and not re.search(r"[.?!…:”]$", s): show("one-word", n, s)
            if re.search(r"[^\x00-\x7F’‘“”—–…éèáíóúñüöäçàêâîôûëïÉ½¼¾°£€]", s): show("odd-char", n, s)
print(dict(cnt))
