#!/usr/bin/env python3
"""구분선 솎아내기 — 장면 전환이 아닌 비트 구분선을 없앤다.

남기는 것
  · 시각 표시(##) 바로 앞뒤
  · 앞뒤 블록 중 하나라도 충분히 긴 것 (진짜 장면 전환)
  · 화 마지막 구간 (결말의 호흡)
"""
import io, re, sys

MINBLOCK = 260   # 앞뒤 블록이 둘 다 이보다 짧으면 비트 구분선으로 본다
TAILKEEP = 0.12  # 화 끝 12% 안의 구분선은 남긴다

def thin(md):
    F = chr(96)*3
    head, sep, rest = md.partition('\n---\n')
    if not sep: return md
    body, f2, tail = rest.partition(F)
    lines = body.split('\n')

    idx = [i for i,l in enumerate(lines) if set(l.strip())<=set('-') and len(l.strip())>=3]
    drop = set()
    for i in idx:
        if i > len(lines)*(1-TAILKEEP):        # 결말부는 보존
            continue
        # 앞뒤 블록 크기
        j = i-1
        before = []
        while j >= 0 and not (set(lines[j].strip())<=set('-') and len(lines[j].strip())>=3):
            if lines[j].strip().startswith('#'): break
            before.append(lines[j]); j -= 1
        k = i+1
        after = []
        while k < len(lines) and not (set(lines[k].strip())<=set('-') and len(lines[k].strip())>=3):
            if lines[k].strip().startswith('#'): break
            after.append(lines[k]); k += 1
        # 시각 표시 인접이면 보존
        if (j >= 0 and lines[j].strip().startswith('#')) or (k < len(lines) and lines[k].strip().startswith('#')):
            continue
        if len(''.join(before)) < MINBLOCK and len(''.join(after)) < MINBLOCK:
            drop.add(i)

    out = []
    for i,l in enumerate(lines):
        if i in drop:
            continue
        out.append(l)
    # 구분선을 뺀 자리에 빈 줄이 겹치는 것 정리
    txt = '\n'.join(out)
    txt = re.sub(r'\n{4,}', '\n\n', txt)
    return head + sep + txt + f2 + tail

if __name__ == '__main__':
    for p in sys.argv[1:]:
        s = io.open(p, encoding='utf-8').read()
        io.open(p,'w',encoding='utf-8').write(thin(s))
