#!/usr/bin/env python3
"""1~3부를 한 권으로 묶은 완성본 원고를 만든다.

    python3 tools/make_book.py

만드는 것:
    원고/pdf/어디서_개가_짖는구나_완성본.pdf

구성:
    속표지 → 백면 → 차례(2면) → 제1부 도비라 → 12화 → 제2부 도비라 → 10화
    → 제3부 도비라 → 10화

쪽번호:
    본문 첫 면부터 1로 세고, 하단 중앙에 찍는다.
    관행대로 속표지·차례·부 도비라에는 찍지 않는다(세기는 센다).
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
SUBTITLE = "3부 연작 장편소설"

PARTS = [
    ("1부", ("제 1 부", "묵산타워 15층,", "김민지 대리")),
    ("2부", ("제 2 부", "율목정밀,", "윤소라 사무직")),
    ("3부", ("제 3 부", "야간 라인,", "14번")),
]

SERIF = "/System/Library/Fonts/Supplemental/AppleMyungjo.ttf"

FRONT_CSS = """
@page { size: 152mm 225mm; margin: 20mm 16mm 18mm; }
@import url('https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@400;700&display=swap');
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0;
  font-family: 'Nanum Myeongjo', 'AppleMyungjo', serif; color: #111; }

.title-page { page-break-after: always; padding-top: 78mm; text-align: center; }
.title-page h1 { font-size: 27pt; font-weight: 400; margin: 0; letter-spacing: .06em; }
.title-page .sub { margin-top: 14mm; font-family: 'Apple SD Gothic Neo', sans-serif;
  font-size: 9pt; font-weight: 300; color: #7a7a7a; letter-spacing: .3em; }

.blank { page-break-after: always; }

.toc { page-break-before: always; }
.toc h2 { font-size: 14pt; font-weight: 400; text-align: center;
  letter-spacing: .5em; margin: 6mm 0 14mm; text-indent: .5em; }

.toc-part { display: flex; align-items: baseline; margin: 8mm 0 3.5mm;
  font-size: 10.5pt; }
.toc-part .no { font-family: 'Apple SD Gothic Neo', sans-serif; font-size: 8pt;
  color: #8a8a8a; letter-spacing: .24em; margin-right: 4mm; white-space: nowrap; }
.toc-part .nm { font-weight: 700; }

.toc-row { display: flex; align-items: baseline; font-size: 9.6pt;
  line-height: 1.95; padding-left: 7mm; }
.toc-row .ch { white-space: nowrap; color: #555; margin-right: 2mm;
  font-variant-numeric: tabular-nums; }
.toc-row .tt { white-space: nowrap; }
.toc-row .dots { flex: 1; border-bottom: .4pt dotted #bbb;
  margin: 0 2.5mm 1.1mm; min-width: 6mm; }
.toc-row .pg { font-variant-numeric: tabular-nums; color: #444; }
.toc-part .dots { flex: 1; border-bottom: .4pt dotted #bbb;
  margin: 0 2.5mm 1.3mm; min-width: 6mm; }
.toc-part .pg { font-variant-numeric: tabular-nums; }
"""


def chapters_of(part: str):
    return [parse(p.read_text(encoding="utf-8"))
            for p in sorted((ROOT / "원고" / part).glob("*.md"))]


def cover_html(no: str, place: str, who: str) -> str:
    return ('<section class="cover">'
            f'<div class="cv-no">{html.escape(no)}</div>'
            f'<h1>{html.escape(place)}<br>{html.escape(who)}</h1>'
            f'<div class="cv-sub">{html.escape(TITLE)}</div>'
            "</section>")


def build_body_html(groups) -> str:
    out = ["<!doctype html><html lang=ko><head><meta charset=utf-8>",
           f"<title>{html.escape(TITLE)}</title>",
           f"<style>{CSS}</style></head><body>"]
    for cover, chs in groups:
        out.append(cover_html(*cover))
        out += [render_chapter(c) for c in chs]
    out.append("</body></html>")
    return "\n".join(out)


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def locate(pdf: Path, groups):
    """부 도비라와 각 화가 시작하는 물리 면 번호(0부터)를 찾는다."""
    doc = fitz.open(pdf)
    pages = [norm(doc[i].get_text()) for i in range(doc.page_count)]
    doc.close()

    want = []                      # (종류, 표시문자열, 이름)
    for cover, chs in groups:
        want.append(("part", norm(cover[0]), f"{cover[1]} {cover[2]}"))
        for c in chs:
            want.append(("ch", norm(c["no"]), c["title"]))

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


def stamp(pdf: Path, part_pages: set):
    """본문 하단 중앙에 쪽번호. 부 도비라는 건너뛴다(번호는 센다)."""
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


def build_front_html(found) -> str:
    rows = []
    for kind, key, name, page in found:
        if kind == "part":
            rows.append(
                '<div class="toc-part">'
                f'<span class="no">{html.escape(key[:2] + " " + key[2:])}</span>'
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
        "</body></html>",
    ])


def main() -> None:
    groups = [(cover, chapters_of(part)) for part, cover in PARTS]
    n_ch = sum(len(c) for _, c in groups)
    tmpdir = ROOT / ".book.tmp"
    tmpdir.mkdir(exist_ok=True)
    body_html, body_pdf = tmpdir / "body.html", tmpdir / "body.pdf"
    front_html, front_pdf = tmpdir / "front.html", tmpdir / "front.pdf"

    body_html.write_text(build_body_html(groups), encoding="utf-8")
    to_pdf(body_html.resolve(), body_pdf.resolve())

    found, n_pages = locate(body_pdf, groups)
    stamp(body_pdf, {p for k, _, _, p in found if k == "part"})

    front_html.write_text(build_front_html(found), encoding="utf-8")
    to_pdf(front_html.resolve(), front_pdf.resolve())

    book = fitz.open(front_pdf)
    body = fitz.open(body_pdf)
    n_front = book.page_count
    book.insert_pdf(body)

    # PDF 뷰어 북마크
    toc = []
    for kind, key, name, page in found:
        toc.append([1 if kind == "part" else 2,
                    name if kind == "part" else f"{key} {name}",
                    n_front + page + 1])
    book.set_toc(toc)
    book.set_metadata({"title": TITLE, "subject": SUBTITLE, "author": ""})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    book.save(OUT, garbage=4, deflate=True)
    total = book.page_count
    book.close(); body.close()

    print(f"{OUT}")
    print(f"  앞붙이 {n_front}면(속표지·백면·차례) + 본문 {n_pages}면 = {total}면")
    print(f"  {n_ch}화 · 부 도비라 3면은 쪽번호 없음 · 북마크 {len(toc)}개")


if __name__ == "__main__":
    main()
