#!/usr/bin/env python3
"""문단 병합 — 연속된 한 문장 문단을 읽는 호흡에 맞게 합친다.

원칙
  · 같은 장면·같은 동작이 이어지는 한 문장 문단은 합친다
  · 독립해야 힘이 나는 문단은 남긴다
      - 14자 미만의 타격 문장  ("한 줄이었다.", "열여섯 단.")
      - 절 구분선 --- 바로 앞뒤
      - 시각 표시 ## 바로 뒤
      - 대사 바로 앞뒤 (호흡을 끊어야 대사가 산다)
      - 굵은 글씨 블록(삽입 문서·복원문) 인접
  · 합친 문단이 MAXLEN 을 넘지 않게 한다
"""
import io, re, sys

MAXLEN = 200      # 합친 문단 최대 길이
RUNMAX = 4        # 한 번에 합칠 문장 수
PUNCH  = 13       # 이보다 짧으면 타격 문장으로 보고 남긴다

def kind(l):
    s = l.strip()
    if not s: return 'blank'
    if s.startswith('#'): return 'head'
    if s.startswith('**') or s.startswith('!['): return 'bold'
    if s.startswith('"') or s.startswith('“'): return 'dial'
    if set(s) <= set('-') and len(s) >= 3: return 'sep'
    if s.startswith(('|', '```', '━', '─', ' ')): return 'raw'
    return 'para'

def nsent(s):
    return len([x for x in re.split(r'(?<=[.!?])\s+', s.strip()) if x.strip()])

# 새 동작의 시작으로 보는 문단 첫머리 — 앞 문단에 붙이지 않고 새 문단을 연다
ACTOR = re.compile(
    r'^(김민지|윤소라|남해인|이강토|박종두|최정남|장독고|정수경|'
    r'구본철|조태산|하민우|김단|응우옌|조장|관리자|의사|과장|사장|부사장|'
    r'그|그녀|그가|그는)\s*(는|은|가|도|의|를|을)?\s')
TIME = re.compile(r'^(그날|그때|다음 날|이튿날|이후|얼마 뒤|잠시 뒤|[0-9가-힣]+ ?(시|분|초|일|주|달|년)\b)')

def opens_new(t):
    return bool(ACTOR.match(t) or TIME.match(t))

def merge(md):
    F = chr(96)*3
    head, sep, rest = md.partition('\n---\n')
    if not sep: return md
    body, f2, tail = rest.partition(F)
    lines = body.split('\n')

    # 문단 블록 인덱스 수집
    out = []
    i = 0
    while i < len(lines):
        if kind(lines[i]) != 'para':
            out.append(lines[i]); i += 1; continue

        # 연속 문단 run 찾기 (사이에 빈 줄 하나만 허용)
        run = [i]
        j = i
        while True:
            if j+2 < len(lines) and kind(lines[j+1]) == 'blank' and kind(lines[j+2]) == 'para':
                run.append(j+2); j += 2
            else:
                break

        # run 안에서 합치기
        buf = []
        cur = ''
        for idx, li in enumerate(run):
            t = lines[li].strip()
            prev_is_dial = li >= 2 and kind(lines[li-2]) == 'dial'
            next_is_dial = li+2 < len(lines) and kind(lines[li+2]) == 'dial'
            nxt = lines[li+2].strip() if (li+2 < len(lines) and kind(lines[li+2])=='para') else ''
            protect = (len(t) < PUNCH
                       or nsent(t) > 3
                       or next_is_dial
                       or idx == 0 and li >= 2 and kind(lines[li-2]) in ('sep','head','bold')
                       or li+2 >= len(lines))
            if protect:
                if cur: buf.append(cur); cur = ''
                buf.append(t); continue
            if not cur:
                cur = t
            elif opens_new(t):
                buf.append(cur); cur = t
            elif len(cur) + 1 + len(t) <= MAXLEN and cur.count('。')+cur.count('.') < RUNMAX:
                cur = cur + ' ' + t
            else:
                buf.append(cur); cur = t
        if cur: buf.append(cur)

        for k, p in enumerate(buf):
            out.append(p)
            if k < len(buf)-1: out.append('')
        i = run[-1] + 1
        # run 뒤 빈 줄 보존
        if i < len(lines) and kind(lines[i]) == 'blank':
            out.append(''); i += 1

    return head + sep + '\n'.join(out) + f2 + tail

if __name__ == '__main__':
    for p in sys.argv[1:]:
        s = io.open(p, encoding='utf-8').read()
        io.open(p, 'w', encoding='utf-8').write(merge(s))
        print(f"  merged {p}")
