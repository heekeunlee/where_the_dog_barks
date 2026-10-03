#!/usr/bin/env python3
"""12부판 원고를 한 권으로 묶은 완성본을 만든다.

    python3 tools/make_book.py

만드는 것:
    원고/pdf/어디서_개가_짖는구나_완성본.pdf

구성:
    속표지 → 백면 → 차례 (→ 홀짝 맞춤 백면) → 제1부 ~ 제12부 → 작가의 말

    부 도비라는 두지 않는다. 각 부는 첫 면 위를 크게 비우는 형식(md2pdf .ch-head)으로 연다.
    작가의 말은 오른쪽(홀수) 면에서 시작한다.

쪽번호:
    본문 첫 면부터 1로 세고, 하단 중앙에 찍는다.
    백면에는 찍지 않는다(세기는 센다).
    앞붙이(속표지·차례)는 본문 번호와 별개라 아예 매기지 않는다.

본문 조판은 md2pdf.py 를 그대로 쓴다. 양쪽맞춤·음절 단위 줄바꿈 동일.
의존 : Chrome (md2pdf 와 동일) + PyMuPDF(fitz)
"""
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fitz
from md2pdf import CSS, parse, render_chapter, to_pdf

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "원고" / "pdf" / "어디서_개가_짖는구나_완성본.pdf"
TITLE = "어디서 개가 짖는구나"
SUBTITLE = "장편소설"
SRC = ROOT / "원고" / "12부"

BACK_MD = ROOT / "원고" / "작가의_말.md"      # 뒷붙이. 본문 쪽번호를 이어 받는다

SERIF = "/System/Library/Fonts/Supplemental/AppleMyungjo.ttf"

FRONT_CSS = """
@page { size: 152mm 225mm; margin: 20mm 16mm 18mm; }
@page :right { margin-left: 19mm; margin-right: 14mm; }
@page :left  { margin-left: 14mm; margin-right: 19mm; }
@import url('https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@400;700&family=Nanum+Gothic:wght@400;700&display=swap');
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0;
  font-family: 'Nanum Myeongjo', 'AppleMyungjo', serif; color: #111; }

.title-page { page-break-after: always; padding-top: 78mm; text-align: center; }
.title-page h1 { font-size: 27pt; font-weight: 400; margin: 0; letter-spacing: .06em; }
.title-page .sub { margin-top: 14mm; font-family: 'Nanum Gothic', sans-serif;
  font-size: 9pt; font-weight: 300; color: #7a7a7a; letter-spacing: .3em; }

.blank { page-break-after: always; }

.toc { page-break-before: always; }
.toc h2 { font-size: 14pt; font-weight: 400; text-align: center;
  letter-spacing: .5em; margin: 6mm 0 14mm; text-indent: .5em; }

.toc-part { display: flex; align-items: baseline; margin: 8mm 0 3.5mm;
  font-size: 10.5pt; }
.toc-part .no { font-family: 'Nanum Gothic', sans-serif; font-size: 8pt;
  color: #8a8a8a; letter-spacing: .24em; margin-right: 4mm; white-space: nowrap; }
.toc-part .nm { font-weight: 700; }

.toc-row { display: flex; align-items: baseline; font-size: 10pt;
  line-height: 2.25; padding-left: 0; }
.toc-row .ch { white-space: nowrap; color: #777; margin-right: 4mm; width: 12mm;
  font-variant-numeric: tabular-nums; }
.toc-row .tt { white-space: nowrap; }
.toc-row .dots { flex: 1; border-bottom: .4pt dotted #bbb;
  margin: 0 2.5mm 1.1mm; min-width: 6mm; }
.toc-row .pg { font-variant-numeric: tabular-nums; color: #444; }
.toc-part .dots { flex: 1; border-bottom: .4pt dotted #bbb;
  margin: 0 2.5mm 1.3mm; min-width: 6mm; }
.toc-part .pg { font-variant-numeric: tabular-nums; }
"""


def chapters():
    return [parse(p.read_text(encoding="utf-8")) for p in sorted(SRC.glob("*.md"))]


BLANK = '<section class="blank-page">&#160;</section>'


def build_body_html(chs, back=None, blanks=frozenset()) -> str:
    out = ["<!doctype html><html lang=ko><head><meta charset=utf-8>",
           f"<title>{html.escape(TITLE)}</title>",
           f"<style>{CSS}</style></head><body>"]
    out += [render_chapter(c) for c in chs]
    if back:
        if ("back", back["title"]) in blanks:
            out.append(BLANK)
        out.append(render_chapter(back))
    out.append("</body></html>")
    return "\n".join(out)


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def locate(pdf: Path, chs, back=None):
    """각 부와 작가의 말이 시작하는 물리 면 번호(0부터)를 찾는다."""
    doc = fitz.open(pdf)
    pages = [norm(doc[i].get_text()) for i in range(doc.page_count)]
    doc.close()

    want = [("ch", norm(c["no"]), c["title"]) for c in chs]   # (종류, 표시문자열, 이름)

    if back:
        want.append(("back", norm(back["title"]), back["title"]))

    found, at, i = [], 0, 0
    for kind, key, name in want:
        while at < len(pages) and key not in pages[at]:
            at += 1
        if at >= len(pages):
            raise SystemExit(f"찾지 못함: {key} {name}")
        found.append((kind, key, name, at))
        at += 1
        i += 1
    return found, len(pages)


def render_recto(chs, back, body_html: Path, body_pdf: Path, n_front: int):
    """작가의 말이 오른쪽(홀수) 면에서 시작하도록 백면을 넣고 다시 조판한다.

    Chrome 은 page-break-before: right 를 무시한다. 그리고 조판을 끝낸 뒤에
    백면을 끼우면 그 뒤 페이지의 홀짝이 뒤집혀 안쪽·바깥쪽 여백이 반대로 간다.
    그래서 HTML 단계에서 넣는다.

    백면은 페이지를 하나 더할 뿐 본문을 흘려보내지 않으므로,
    백면 없이 한 번 조판해 위치를 재면 필요한 자리를 한 번에 계산할 수 있다.
    """
    def bake(blanks):
        body_html.write_text(build_body_html(chs, back, blanks), encoding="utf-8")
        to_pdf(body_html.resolve(), body_pdf.resolve())
        return locate(body_pdf, chs, back)

    found, n_pages = bake(frozenset())

    key_of = {}
    if back:
        key_of[norm(back["title"])] = ("back", back["title"])

    blanks, cum = set(), 0
    for kind, key, name, page in found:
        if kind not in ("part", "back"):
            continue
        if (n_front + page + cum + 1) % 2 == 0:     # 왼쪽 면에 걸린다
            blanks.add(key_of[key])
            cum += 1

    if not blanks:
        return found, n_pages

    found, n_pages = bake(frozenset(blanks))
    bad = [n for k, _, n, pg in found
           if k in ("part", "back") and (n_front + pg + 1) % 2 == 0]
    if bad:
        raise SystemExit(f"백면을 넣었는데도 왼쪽 면에 남음: {bad}")
    return found, n_pages


def stamp(pdf: Path, part_pages: set):
    """본문 하단 중앙에 쪽번호. 백면은 건너뛴다(번호는 센다)."""
    doc = fitz.open(pdf)
    font = fitz.Font(fontfile=SERIF) if Path(SERIF).exists() else fitz.Font("times")
    size, y = 8.5, 225 * 72 / 25.4 - 11 * 72 / 25.4     # 아래에서 11mm
    for i in range(doc.page_count):
        if i in part_pages:
            continue
        page = doc[i]
        # Chrome 이 만든 스트림은 0.24배 cm 스케일을 걸고 복원하지 않는다.
        # 감싸 두지 않으면 덧붙인 쪽번호가 그 스케일을 물려받아 2pt 로 찍힌다.
        try:
            page.wrap_contents()
        except AttributeError:
            page.clean_contents()
        txt = str(i + 1)
        w = font.text_length(txt, size)
        tw = fitz.TextWriter(page.rect, color=(.42, .42, .42))
        tw.append(fitz.Point((page.rect.width - w) / 2, y), txt, font=font, fontsize=size)
        tw.write_text(page)
    doc.saveIncr()
    doc.close()


def build_front_html(found, pad=False) -> str:
    rows = []
    for kind, key, name, page in found:
        if kind == "back":
            rows.append(
                '<div class="toc-part" style="margin-top:10mm">'
                '<span class="no"></span>'
                f'<span class="nm">{html.escape(name)}</span>'
                '<span class="dots"></span>'
                f'<span class="pg">{page + 1}</span></div>')
        else:
            rows.append(
                '<div class="toc-row">'
                f'<span class="ch">{html.escape(key)}</span>'
                f'<span class="tt">{html.escape(name)}</span>'
                '<span class="dots"></span>'
                f'<span class="pg">{page + 1}</span></div>')
    return "\n".join([
        "<!doctype html><html lang=ko><head><meta charset=utf-8>",
        f"<title>{html.escape(TITLE)}</title>",
        f"<style>{FRONT_CSS}</style></head><body>",
        f'<section class="title-page"><h1>{html.escape(TITLE)}</h1>'
        f'<div class="sub">{html.escape(SUBTITLE)}</div></section>',
        '<section class="blank"></section>',
        '<section class="toc"><h2>차 례</h2>', *rows, "</section>",
        *(['<section class="blank" style="page-break-before:always">&#160;</section>'] if pad else []),
        "</body></html>",
    ])


def main() -> None:
    chs = chapters()
    back = parse(BACK_MD.read_text(encoding="utf-8")) if BACK_MD.exists() else None
    tmpdir = ROOT / ".book.tmp"
    tmpdir.mkdir(exist_ok=True)
    body_html, body_pdf = tmpdir / "body.html", tmpdir / "body.pdf"
    front_html, front_pdf = tmpdir / "front.html", tmpdir / "front.pdf"

    # 앞붙이 면수를 먼저 잰다. 홀수면 백면을 하나 더해 본문 1쪽이 오른쪽 면에 오게 한다.
    dummy = [("ch", norm(c["no"]), c["title"], 0) for c in chs]
    if back:
        dummy.append(("back", norm(back["title"]), back["title"], 0))
    front_html.write_text(build_front_html(dummy), encoding="utf-8")
    to_pdf(front_html.resolve(), front_pdf.resolve())
    n_front = fitz.open(front_pdf).page_count
    pad = n_front % 2 == 1
    n_front += pad

    found, n_pages = render_recto(chs, back, body_html, body_pdf, n_front=n_front)
    doc = fitz.open(body_pdf)
    blanks = [i for i in range(doc.page_count) if not doc[i].get_text().strip()]
    doc.close()
    stamp(body_pdf, set(blanks))

    front_html.write_text(build_front_html(found, pad), encoding="utf-8")
    to_pdf(front_html.resolve(), front_pdf.resolve())

    book = fitz.open(front_pdf)
    body = fitz.open(body_pdf)
    assert book.page_count == n_front, f"앞붙이 면수가 달라졌다: {book.page_count} != {n_front}"
    book.insert_pdf(body)

    # PDF 뷰어 북마크
    toc = [[1, name if kind == "back" else f"{key} · {name}", n_front + page + 1]
           for kind, key, name, page in found]
    book.set_toc(toc)
    book.set_metadata({"title": TITLE, "subject": SUBTITLE, "author": ""})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    book.save(OUT, garbage=4, deflate=True)
    total = book.page_count
    book.close(); body.close()

    print(f"{OUT}")
    print(f"  앞붙이 {n_front}면 + 본문 {n_pages}면 = {total}면")
    bp = [pg for k, _, _, pg in found if k == "back"]
    tail = f" · 작가의 말 {n_pages - bp[0]}면" if bp else ""
    nb = f" · 백면 {len(blanks)}면" if blanks else ""
    print(f"  {len(chs)}부{tail}{nb} · 북마크 {len(toc)}개")


if __name__ == "__main__":
    main()
