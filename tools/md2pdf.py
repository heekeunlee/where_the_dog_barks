#!/usr/bin/env python3
"""원고 마크다운 → 신국판 PDF 조판.

사용법:
    python3 tools/md2pdf.py 원고/1부/01_퇴근_20분_전.md
    python3 tools/md2pdf.py 원고/1부/*.md          # 여러 화 각각 출력
    python3 tools/md2pdf.py --merge 원고/1부/*.md  # 한 권으로 합본

판형 : 신국판 152 x 225mm
본문 : 나눔명조 10.5pt / 행간 1.9 / 왼끝맞춤 / keep-all
       (한국어는 브라우저가 자간이 아닌 공백만 늘려 양쪽정렬 시 어절 간격이 벌어진다)
의존 : Chrome (헤드리스 인쇄). 별도 설치 불필요.
"""
import html
import re
import subprocess
import sys
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CSS = """
@page { size: 152mm 225mm; margin: 20mm 16mm 18mm; }
@import url('https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@400;700&display=swap');

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: 'Nanum Myeongjo', 'AppleMyungjo', 'Apple SD Gothic Neo', serif;
  font-size: 10.5pt;
  line-height: 1.9;
  color: #111;
  text-align: left;
  word-break: keep-all;
  overflow-wrap: break-word;
  -webkit-font-smoothing: antialiased;
}

/* ---- 장 도비라 ---- */
.chapter { page-break-before: always; }
.chapter:first-of-type { page-break-before: avoid; }
.ch-head { margin: 8mm 0 14mm; }
.ch-no {
  font-family: 'Apple SD Gothic Neo', sans-serif;
  font-size: 8.5pt; font-weight: 300; letter-spacing: .32em;
  color: #8a8a8a; margin-bottom: 5mm;
}
.ch-title {
  font-family: 'Apple SD Gothic Neo', sans-serif;
  font-size: 20pt; font-weight: 200; letter-spacing: -.01em;
  line-height: 1.35; color: #111; margin: 0;
}
.ch-sub {
  font-family: 'Apple SD Gothic Neo', sans-serif;
  font-size: 8.5pt; font-weight: 300; color: #7a7a7a;
  margin-top: 4mm; letter-spacing: .04em;
}
.ch-rule { border: 0; border-top: .4pt solid #c8c8c8; margin: 6mm 0 8mm; }

/* ---- 본문 ---- */
p { margin: 0; text-indent: 1em; orphans: 2; widows: 2; }
p.noindent { text-indent: 0; }
p + p { margin-top: 0; }

/* 화면에 뜬 메시지 */
.msg {
  margin: 4mm 0 4mm 2em;
  font-family: 'Apple SD Gothic Neo', sans-serif;
  font-size: 9.5pt; font-weight: 500; line-height: 1.65;
  color: #111; text-indent: 0; letter-spacing: -.01em;
  page-break-inside: avoid;
}

/* 시각 표시 (## 02:00) */
.timemark {
  font-family: 'Apple SD Gothic Neo', sans-serif;
  font-size: 9pt; font-weight: 300; letter-spacing: .3em;
  color: #6a6a6a; text-indent: 0;
  margin: 9mm 0 5mm; padding-bottom: 2mm;
  border-bottom: .4pt solid #d0d0d0;
  page-break-after: avoid; page-break-inside: avoid;
}

/* 장면 구분 */
.sep { text-align: center; margin: 7mm 0; color: #999; letter-spacing: .8em; text-indent: 0; }

/* ---- 삽입 문서 ---- */
.doc-wrap { page-break-inside: avoid; margin-top: 10mm; }
.doc {
  font-family: 'D2Coding', 'Apple SD Gothic Neo', monospace;
  font-size: 7.6pt; line-height: 1.62; color: #2a2a2a;
  white-space: pre; word-break: normal;
  margin: 0; padding: 5mm 4mm;
  background: #f6f6f4; border: .4pt solid #d8d8d4;
  page-break-inside: avoid; overflow: hidden;
}
.doc-label {
  font-family: 'Apple SD Gothic Neo', sans-serif;
  font-size: 7pt; font-weight: 400; letter-spacing: .22em;
  color: #9a9a9a; margin: 0 0 2mm; text-indent: 0;
}

/* ---- 합본 표지 ---- */
.cover { page-break-after: always; padding-top: 55mm; text-align: center; }
.cover h1 {
  font-family: 'Nanum Myeongjo', 'AppleMyungjo', serif;
  font-size: 26pt; font-weight: 400; margin: 0; letter-spacing: .02em;
}
.cover .cv-sub {
  font-family: 'Apple SD Gothic Neo', sans-serif;
  font-size: 9pt; font-weight: 300; color: #7a7a7a;
  margin-top: 8mm; letter-spacing: .18em;
}
"""


def parse(md: str) -> dict:
    """원고 마크다운 한 편을 구조로 분해한다."""
    lines = md.split("\n")
    out = {"no": "", "title": "", "sub": "", "blocks": []}

    i = 0
    # 제목: "# 제1화 · 퇴근 20분 전"
    while i < len(lines) and not lines[i].startswith("# "):
        i += 1
    if i < len(lines):
        head = lines[i][2:].strip()
        if "·" in head:
            out["no"], out["title"] = [x.strip() for x in head.split("·", 1)]
        else:
            out["title"] = head
        i += 1

    # 부제: 굵게 표시된 한 줄
    while i < len(lines):
        t = lines[i].strip()
        if t.startswith("**") and t.endswith("**"):
            out["sub"] = t[2:-2].strip()
            i += 1
            break
        if t.startswith("---") or t:
            break
        i += 1

    body = "\n".join(lines[i:])

    # 코드펜스(삽입 문서) 분리
    fence = chr(96) * 3
    parts = body.split(fence)
    prose, docs = parts[0], parts[1::2]

    for raw in prose.split("\n"):
        t = raw.rstrip()
        s = t.strip()
        if not s:
            continue
        if set(s) <= set("-") and len(s) >= 3:
            # 제목 아래 첫 구분선과 연속 구분선은 버린다
            if not out["blocks"] or out["blocks"][-1][0] == "sep":
                continue
            out["blocks"].append(("sep", ""))
            continue
        if s.startswith("## "):
            out["blocks"].append(("time", s[3:].strip()))
            continue
        if s.startswith("**") and s.endswith("**") and s.count("**") == 2:
            out["blocks"].append(("msg", s[2:-2].strip()))
            continue
        out["blocks"].append(("p", s))

    while out["blocks"] and out["blocks"][-1][0] == "sep":
        out["blocks"].pop()

    for d in docs:
        out["blocks"].append(("doc", d.strip("\n")))
    return out


def inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return s


def render_chapter(ch: dict) -> str:
    h = ['<section class="chapter">', '<div class="ch-head">']
    if ch["no"]:
        h.append(f'<div class="ch-no">{html.escape(ch["no"])}</div>')
    h.append(f'<h1 class="ch-title">{html.escape(ch["title"])}</h1>')
    if ch["sub"]:
        h.append(f'<div class="ch-sub">{html.escape(ch["sub"])}</div>')
    h.append("</div><hr class=\"ch-rule\">")

    prev_msg = False
    for kind, text in ch["blocks"]:
        if kind == "p":
            h.append(f"<p>{inline(text)}</p>")
            prev_msg = False
        elif kind == "msg":
            # 연속된 메시지 줄은 한 덩어리로 묶는다
            if prev_msg:
                h[-1] = h[-1][:-len("</div>")] + "<br>" + inline(text) + "</div>"
            else:
                h.append(f'<div class="msg">{inline(text)}</div>')
            prev_msg = True
        elif kind == "time":
            h.append(f'<div class="timemark">{html.escape(text)}</div>')
            prev_msg = False
        elif kind == "sep":
            h.append('<p class="sep">·   ·   ·</p>')
            prev_msg = False
        elif kind == "doc":
            h.append(
                '<div class="doc-wrap">'
                '<div class="doc-label">삽입 문서</div>'
                f'<div class="doc">{html.escape(text)}</div>'
                '</div>'
            )
            prev_msg = False
    h.append("</section>")
    return "\n".join(h)


def build_html(chapters: list, cover: str = "") -> str:
    parts = [
        "<!doctype html><html lang=ko><head><meta charset=utf-8>",
        f"<title>{html.escape(cover or chapters[0]['title'])}</title>",
        f"<style>{CSS}</style></head><body>",
    ]
    if cover:
        parts.append(
            '<section class="cover">'
            f"<h1>{html.escape(cover)}</h1>"
            '<div class="cv-sub">어디서 개가 짖는구나</div>'
            "</section>"
        )
    parts += [render_chapter(c) for c in chapters]
    parts.append("</body></html>")
    return "\n".join(parts)


def to_pdf(html_path: Path, pdf_path: Path) -> None:
    subprocess.run(
        [
            CHROME, "--headless=new", "--disable-gpu",
            "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=12000",
            f"--print-to-pdf={pdf_path}", html_path.as_uri(),
        ],
        check=True, capture_output=True,
    )


def main() -> None:
    args = sys.argv[1:]
    merge = "--merge" in args
    paths = [Path(a) for a in args if not a.startswith("--")]
    if not paths:
        print(__doc__)
        sys.exit(1)

    outdir = Path("원고/pdf")
    outdir.mkdir(parents=True, exist_ok=True)
    tmp = Path(".md2pdf.tmp.html")

    if merge:
        chapters = [parse(p.read_text(encoding="utf-8")) for p in sorted(paths)]
        part = sorted(paths)[0].parent.name or "합본"
        covers = {"1부": "제1부 대기업", "2부": "제2부 중소기업", "3부": "제3부 알바·취준"}
        tmp.write_text(build_html(chapters, cover=covers.get(part, part)), encoding="utf-8")
        pdf = outdir / f"{part}_합본.pdf"
        to_pdf(tmp.resolve(), pdf.resolve())
        print(f"{pdf}  ({len(chapters)}화 합본, {pdf.stat().st_size:,} bytes)")
    else:
        for p in sorted(paths):
            ch = parse(p.read_text(encoding="utf-8"))
            tmp.write_text(build_html([ch]), encoding="utf-8")
            pdf = outdir / (p.stem + ".pdf")
            to_pdf(tmp.resolve(), pdf.resolve())
            print(f"{pdf}  ({pdf.stat().st_size:,} bytes)")

    tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
