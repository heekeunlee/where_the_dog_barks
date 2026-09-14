#!/usr/bin/env python3
"""원고 마크다운 → 신국판 PDF 조판.

사용법:
    python3 tools/md2pdf.py 원고/1부/01_퇴근_20분_전.md
    python3 tools/md2pdf.py 원고/1부/*.md          # 여러 화 각각 출력
    python3 tools/md2pdf.py --merge 원고/1부/*.md  # 한 권으로 합본

판형 : 신국판 152 x 225mm
본문 : 나눔명조 10.5pt / 행간 1.9 / 양쪽맞춤 / 음절 단위 줄바꿈
       한국 단행본 관행대로 양쪽을 맞추고 어절 중간에서도 줄을 바꾼다.
       word-break: keep-all 을 쓰면 어절이 안 쪼개져 공백이 벌어지므로 쓰지 않는다.
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
  line-height: 2.1;
  color: #111;
  text-align: justify;
  text-justify: inter-character;
  word-break: normal;
  line-break: strict;
  overflow-wrap: normal;
  hanging-punctuation: allow-end;
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
  line-height: 2.1; color: #111; margin: 0;
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

/* ---- 삽입 문서 공통 ---- */
.doc-wrap { page-break-inside: avoid; margin-top: 10mm; }
.doc-label {
  font-family: 'Apple SD Gothic Neo', sans-serif;
  font-size: 7pt; font-weight: 400; letter-spacing: .22em;
  color: #9a9a9a; margin: 0 0 2.5mm; text-indent: 0;
}
.doc {
  font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;
  font-size: 8pt; line-height: 1.55; color: #1a1a1a;
  text-align: left; text-indent: 0; word-break: normal;
  background: #fff; border: .5pt solid #b8b8b8;
  padding: 0; margin: 0; overflow: hidden;
}
.doc * { box-sizing: border-box; }
.doc .pad { padding: 5mm 5.5mm; }
.doc table { width: 100%; border-collapse: collapse; font-size: 7.6pt; }
.doc th, .doc td { border: .4pt solid #c4c4c4; padding: 1.4mm 2mm; text-align: left;
                   vertical-align: middle; font-weight: 400; }
.doc th { background: #f2f2f2; font-weight: 500; color: #333; white-space: nowrap; }
.doc td.n { text-align: right; font-variant-numeric: tabular-nums; }
.doc td.c { text-align: center; }
.doc .mono { font-family: 'D2Coding', monospace; font-size: 7.2pt; }
.doc .sm { font-size: 6.8pt; color: #6a6a6a; }
.doc .hr { border-top: .4pt solid #d0d0d0; margin: 3mm 0; }

/* 공문 */
.doc-official .org {
  text-align: center; font-size: 13pt; font-weight: 300;
  letter-spacing: .5em; padding: 5mm 0 1mm; color: #111;
}
.doc-official .orgline { border-bottom: 1.2pt solid #333; margin: 0 5mm 4mm; }
.doc-official .fld { display: grid; grid-template-columns: 15mm 1fr; gap: .8mm 0; margin-bottom: 1mm; }
.doc-official .fld b { font-weight: 500; color: #444; letter-spacing: .3em; }
.doc-official .subj { font-weight: 600; font-size: 8.6pt; margin: 3.5mm 0 3mm; }
.doc-official ol { margin: 0 0 3mm; padding-left: 4.5mm; }
.doc-official li { margin-bottom: 1.5mm; }
.doc-official .end { text-align: right; margin: 2mm 0 4mm; }
.doc-official .signer {
  text-align: center; font-size: 10.5pt; font-weight: 400;
  letter-spacing: .18em; margin: 2mm 0 1mm; position: relative;
}
.doc-official .stamp {
  display: inline-block; width: 11mm; height: 11mm; margin-left: 2.5mm;
  border: .9pt solid #b03a30; border-radius: 50%; color: #b03a30;
  font-size: 4.4pt; line-height: 1.15; text-align: center;
  letter-spacing: 0; vertical-align: middle; opacity: .78;
  padding-top: 3.1mm; box-sizing: border-box; font-weight: 600;
}
.doc-official .fld span { line-height: 1.5; }
.doc-official .foot {
  border-top: .5pt solid #333; margin: 3mm 5mm 0; padding: 2mm 0 4mm;
  font-size: 6.6pt; color: #666; text-align: center; letter-spacing: .02em;
}

/* 결재란 — 문서 우측 상단에 별도 블록으로 놓는다 */
.approve-box { text-align: right; margin: 0 0 3mm; }
.approve { display: inline-table; border-collapse: collapse; width: auto; }
.approve th, .approve td { border: .4pt solid #999; width: 12mm; text-align: center; font-size: 6.2pt; padding: .6mm 0; }
.approve th { height: 4mm; background: #f2f2f2; }
.approve td { height: 9mm; font-size: 7pt; color: #444; }

/* 사내 메신저 */
.doc-msg-app { background: #b3c4d4; }
.doc-msg-app .bar {
  background: #4a5a6a; color: #fff; padding: 2mm 3mm; font-size: 7.4pt;
  display: flex; justify-content: space-between;
}
.doc-msg-app .room { padding: 3.5mm 3mm; }
.doc-msg-app .datebar { text-align: center; margin: 1mm 0 3mm; }
.doc-msg-app .datebar span {
  background: rgba(0,0,0,.16); color: #fff; font-size: 6.4pt;
  padding: .6mm 2.5mm; border-radius: 4mm;
}
.doc-msg-app .m { margin-bottom: 3mm; display: flex; gap: 1.6mm; align-items: flex-start; }
.doc-msg-app .av {
  width: 6mm; height: 6mm; border-radius: 1.6mm; background: #d9dfe5;
  flex: none; font-size: 5pt; color: #8a96a2; text-align: center; line-height: 6mm;
}
.doc-msg-app .who { font-size: 6.6pt; color: #33404d; margin-bottom: .8mm; }
.doc-msg-app .bub {
  background: #fff; border-radius: 1mm 3mm 3mm 3mm; padding: 1.8mm 2.6mm;
  display: inline-block; max-width: 62mm; font-size: 7.6pt; line-height: 1.5;
}
.doc-msg-app .meta { font-size: 5.8pt; color: #55636f; margin-left: 1.4mm; align-self: flex-end; }
.doc-msg-app .meta i { font-style: normal; color: #d98324; font-weight: 600; }
.doc-msg-app .file {
  background: #fff; border: .4pt solid #dde3e8; border-radius: 1.5mm;
  padding: 1.8mm 2.6mm; font-size: 7pt; display: inline-block;
}

/* 문자 */
.doc-sms { background: #eef0f3; max-width: 82mm; margin-left: auto; margin-right: auto; }
.doc-sms .head { padding: 2.5mm 3mm 0; font-size: 6.6pt; color: #7b828a; }
.doc-sms .b {
  margin: 2.5mm 3mm 4mm; background: #fff; border-radius: 2mm;
  padding: 3mm 3.4mm; font-size: 7.8pt; line-height: 1.65;
}

/* 메일 */
.doc-mail .mh { background: #f6f7f8; border-bottom: .4pt solid #ddd; padding: 3mm 4mm; }
.doc-mail .mh .t { font-size: 8.6pt; font-weight: 600; margin-bottom: 2mm; }
.doc-mail .mh .r { display: grid; grid-template-columns: 13mm 1fr; font-size: 7pt; color: #555; gap: .5mm 0; }
.doc-mail .mb { padding: 4mm; font-size: 7.8pt; line-height: 1.75; }
.doc-mail .sig { margin-top: 4mm; padding-top: 2.5mm; border-top: .4pt dashed #ccc; font-size: 6.8pt; color: #777; }

/* 시스템 로그 */
.doc-log { background: #1e2228; border-color: #1e2228; }
.doc-log .pad { color: #cfd6dd; }
.doc-log .mono { font-family: 'D2Coding', monospace; font-size: 7pt; line-height: 1.7; white-space: pre; }
.doc-log .k { color: #7fb3d5; }
.doc-log .w { color: #d9a441; }

/* 커뮤니티 게시글 */
.doc-post .ph { border-bottom: .4pt solid #e2e2e2; padding: 3mm 4mm; }
.doc-post .ph .app { font-size: 6.6pt; color: #2f7d6e; font-weight: 600; letter-spacing: .04em; }
.doc-post .ph .t { font-size: 9pt; font-weight: 600; margin: 1.5mm 0 1.5mm; }
.doc-post .ph .s { font-size: 6.6pt; color: #999; }
.doc-post .pb { padding: 4mm; font-size: 7.8pt; line-height: 1.8; }
.doc-post .blur { color: #c9c9c9; letter-spacing: .1em; }

/* 서식/표 문서 */
.doc-form .ft {
  text-align: center; font-size: 10pt; font-weight: 500; letter-spacing: .35em;
  padding: 4mm 0 3mm; border-bottom: 1pt solid #444; margin: 0 5mm 4mm;
}

/* ---- 합본 표지 ---- */
/* ---- 합본 표지 ---- */
.cover { page-break-after: always; padding-top: 52mm; text-align: center; }
.cover .cv-no {
  font-family: 'Apple SD Gothic Neo', sans-serif;
  font-size: 9.5pt; font-weight: 300; color: #8a8a8a;
  letter-spacing: .34em; margin-bottom: 11mm;
}
.cover h1 {
  font-family: 'Nanum Myeongjo', 'AppleMyungjo', serif;
  font-size: 21pt; font-weight: 400; margin: 0;
  letter-spacing: .02em; line-height: 1.78;
}
.cover .cv-sub {
  font-family: 'Apple SD Gothic Neo', sans-serif;
  font-size: 9pt; font-weight: 300; color: #7a7a7a;
  margin-top: 13mm; letter-spacing: .18em;
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
        d = d.strip("\n")
        if d.lstrip().startswith("<"):
            out["blocks"].append(("html", d))
        else:
            out["blocks"].append(("doc", d))
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
                f'<div class="doc"><div class="pad" style="white-space:pre;'
                'font-family:\'D2Coding\',monospace;font-size:7.4pt">'
                f'{html.escape(text)}</div></div>'
                '</div>'
            )
        elif kind == "html":
            h.append('<div class="doc-wrap"><div class="doc-label">삽입 문서</div>'
                     + text + '</div>')
            prev_msg = False
    h.append("</section>")
    return "\n".join(h)


def build_html(chapters: list, cover=None) -> str:
    """cover 는 (부 번호, 장소, 사람) 세 칸. 없으면 표지를 붙이지 않는다."""
    title = " ".join(cover) if cover else chapters[0]["title"]
    parts = [
        "<!doctype html><html lang=ko><head><meta charset=utf-8>",
        f"<title>{html.escape(title)}</title>",
        f"<style>{CSS}</style></head><body>",
    ]
    if cover:
        no, place, who = cover
        parts.append(
            '<section class="cover">'
            f'<div class="cv-no">{html.escape(no)}</div>'
            f"<h1>{html.escape(place)}<br>{html.escape(who)}</h1>"
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
        covers = {
            "1부": ("제 1 부", "묵산타워 15층,", "김민지 대리"),
            "2부": ("제 2 부", "율목정밀,", "윤소라 사무직"),
            "3부": ("제 3 부", "야간 라인,", "14번"),
        }
        tmp.write_text(build_html(chapters, cover=covers.get(part)), encoding="utf-8")
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
