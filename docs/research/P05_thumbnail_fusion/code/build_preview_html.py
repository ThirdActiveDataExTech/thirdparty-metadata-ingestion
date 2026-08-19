"""P05 — paper_KIICE_ko.md → KIICE 2단 A4 '페이지 분리' 미리보기 HTML 생성기 (v2).

개선점(v2):
- 요약/ABSTRACT/키워드는 1페이지(1단), 서론(Ⅰ)부터 page-break로 다음 페이지·2단.
- 수식: 코드블록이 아니라 serif·아래첨자·중앙정렬·식번호의 '진짜 수식' 형태.
- 표·그림1은 전폭(column-span:all) 배치 → 가로 스크롤바 제거, 셀 긴 토큰 줄바꿈.
- 그림 1: ASCII 대신 SVG 파이프라인 도형(3-인코더 이중 인코딩 라우팅).
- 페이지 분리: paged.js(온라인) + print CSS(⌘P). ⟦DATA⟧·【결과】는 빈칸(강조 없음).

실행: python3 docs/research/P05_thumbnail_fusion/code/build_preview_html.py
"""

import html
import re
from pathlib import Path

DOC = Path(__file__).resolve().parent.parent / "paper_KIICE_ko.md"
OUT = Path(__file__).resolve().parent.parent / "paper_KIICE_preview.html"


def strip_comments(t): return re.sub(r"<!--.*?-->", "", t, flags=re.DOTALL)


def placeholders(s):
    s = re.sub(r"⟦DATA:([^⟧]*)⟧", r"\1", s)
    s = re.sub(r"⟦[^⟧]*⟧", '<span class="tbd">[결과]</span>', s)
    s = re.sub(r"【[^】]*】", '<span class="tbd">[결과]</span>', s)
    return s


def inline(s):
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return placeholders(s)


def eqfmt(s):
    """plain 수식 문자열 → serif 수식 HTML(아래첨자/위첨자, 이탤릭 변수 최소)."""
    s = html.escape(s)
    s = re.sub(r"\^\{?([A-Za-z0-9]+)\}?", r"<sup>\1</sup>", s)
    s = re.sub(r"_\{?([A-Za-z0-9가-힣]+)\}?", r"<sub>\1</sub>", s)
    return s


def clean_latex_eq(s):
    s = s.replace("\\big", "").replace("\\!", "").replace("\\,", " ")
    s = s.replace("\\cos", "cos").replace("\\mathrm", "")
    s = re.sub(r"\\tag\{(.+?)\}", "", s).replace("{", "").replace("}", "")
    s = re.sub(r"\^([A-Za-z0-9]+)", r"<sup>\1</sup>", s)
    s = re.sub(r"_([A-Za-z0-9]+)", r"<sub>\1</sub>", s)
    return s.replace("\\", "").strip()


def _is_block_start(st):
    return (st.startswith("#") or st.startswith("|") or st.startswith("```")
            or st == "$$" or st.startswith("- ") or st == "---")


def parse(raw):
    lines = strip_comments(raw).split("\n"); blocks = []; i = 0; in_body = False
    while i < len(lines):
        ln = lines[i]; st = ln.strip()
        if st in ("", "---"):
            i += 1; continue
        if st.startswith("```"):
            buf = []; i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i]); i += 1
            i += 1; blocks.append(("pre", "\n".join(buf), in_body)); continue
        if st == "$$":
            buf = []; i += 1
            while i < len(lines) and lines[i].strip() != "$$":
                buf.append(lines[i]); i += 1
            i += 1
            body = " ".join(x.strip() for x in buf)
            m = re.search(r"\\tag\{(.+?)\}", body)
            blocks.append(("eq", (clean_latex_eq(body), m.group(1) if m else ""), in_body)); continue
        if st.startswith("|"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                buf.append(lines[i].strip()); i += 1
            blocks.append(("table", buf, in_body)); continue
        if st.startswith("# "):
            blocks.append(("title_ko", st[2:].strip(), in_body)); i += 1; continue
        if st.startswith("## "):
            h = st[3:].strip()
            if h.startswith("Ⅰ"): in_body = True
            blocks.append(("h2", h, in_body)); i += 1; continue
        if st.startswith("### "):
            blocks.append(("h3", st[4:].strip(), in_body)); i += 1; continue
        if st.startswith("- "):
            buf = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                buf.append(lines[i].strip()[2:]); i += 1
            blocks.append(("ul", buf, in_body)); continue
        if re.fullmatch(r"\*\*.+\*\*", st) and blocks and blocks[-1][0] == "title_ko":
            blocks.append(("title_en", st.strip("*").strip(), in_body)); i += 1; continue
        buf = [ln]; i += 1
        while i < len(lines) and lines[i].strip() != "" and not _is_block_start(lines[i].strip()):
            buf.append(lines[i]); i += 1
        para = " ".join(x.strip() for x in buf)
        blocks.append(("para", para, in_body))
    return blocks


def md_table(rows):
    cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows]
    if len(cells) >= 2 and set("".join(cells[1])) <= set("-: |"):
        header, body = cells[0], cells[2:]
    else:
        header, body = cells[0], cells[1:]
    out = ["<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in header) + "</tr></thead><tbody>"]
    for r in body:
        out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
    return "".join(out) + "</tbody></table>"


CAP = re.compile(r"^(표|그림)\s*\d+\.")

# --- 그림 1: 파이프라인 SVG (3-인코더 이중 인코딩 라우팅, 개략도) ---
PIPE_SVG = r"""
<svg viewBox="0 0 720 388" class="pipe" xmlns="http://www.w3.org/2000/svg" font-family="'Malgun Gothic',sans-serif">
<defs><marker id="ar" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
<path d="M0,0 L6,3 L0,6 Z" fill="#555"/></marker></defs>
<style>
.b{fill:#fff;stroke:#556;stroke-width:1.2;rx:6}
.enc{fill:#eef3fb;stroke:#4a6fa5}
.cmp{fill:#f2f7ee;stroke:#5a8a4a}
.out{fill:#fbf3ee;stroke:#a5714a}
text{font-size:13px;fill:#111;font-weight:bold}
.s{font-size:11px;fill:#333}
line,path.e{stroke:#666;stroke-width:1.1;fill:none;marker-end:url(#ar)}
.lay{font-size:10.5px;fill:#889;font-weight:bold}
</style>
<!-- 구성 -->
<rect x="15" y="12" width="330" height="34" rx="6" class="b"/>
<text x="24" y="27" class="s">쿼리: 자동완성 초성 → curation → 결정적 표집</text>
<text x="24" y="41" class="s">⇒ Query 70 (14×5)</text>
<rect x="375" y="12" width="330" height="34" rx="6" class="b"/>
<text x="384" y="27" class="s">코퍼스: search + videos.list</text>
<text x="384" y="41" class="s">⇒ Video 840 (14×60; 제목 + 썸네일)</text>
<!-- 입력 -->
<text x="4" y="80" class="lay">입력</text>
<rect x="95" y="66" width="120" height="26" rx="6" class="b"/><text x="130" y="83">Query</text>
<rect x="300" y="66" width="120" height="26" rx="6" class="b"/><text x="345" y="83">제목</text>
<rect x="520" y="66" width="150" height="26" rx="6" class="b"/><text x="565" y="83">썸네일</text>
<!-- 인코더 -->
<text x="4" y="150" class="lay">인코더</text>
<rect x="70" y="132" width="120" height="30" rx="6" class="b enc"/><text x="97" y="151" class="s">mpnet(768d)</text>
<rect x="300" y="132" width="140" height="30" rx="6" class="b enc"/><text x="315" y="151" class="s">CLIP-text(512d)</text>
<rect x="520" y="132" width="150" height="30" rx="6" class="b enc"/><text x="533" y="151" class="s">CLIP-image(512d)</text>
<!-- 입력→인코더 (이중 인코딩) -->
<path class="e" d="M140,92 L135,132"/>
<path class="e" d="M155,92 C230,110 300,118 350,132"/>
<path class="e" d="M345,92 L360,132"/>
<path class="e" d="M330,92 C230,108 170,116 140,132"/>
<path class="e" d="M580,92 L590,132"/>
<!-- 계산 -->
<text x="4" y="230" class="lay">채널 계산</text>
<rect x="60" y="205" width="200" height="46" rx="6" class="b cmp"/>
<text x="70" y="223" class="s">Text 유사도</text><text x="70" y="239" class="s">cos(Query·mpnet, 제목·mpnet)</text>
<rect x="285" y="205" width="210" height="46" rx="6" class="b cmp"/>
<text x="295" y="223" class="s">Visual 유사도</text><text x="295" y="239" class="s">cos(Query·CLIP-t, 썸네일·CLIP-i)</text>
<rect x="510" y="205" width="195" height="46" rx="6" class="b cmp"/>
<text x="520" y="223" class="s">gap = 1 − cos</text><text x="520" y="239" class="s">(제목·CLIP-t, 썸네일·CLIP-i)</text>
<!-- 인코더→계산 -->
<path class="e" d="M120,162 L150,205"/>
<path class="e" d="M360,162 L370,205"/>
<path class="e" d="M590,162 L600,205"/>
<path class="e" d="M410,162 C440,185 470,195 430,205"/>
<!-- 검색·융합 -->
<text x="4" y="315" class="lay">검색·융합</text>
<rect x="60" y="292" width="200" height="28" rx="6" class="b"/><text x="105" y="311" class="s">Text Retrieval</text>
<rect x="285" y="292" width="210" height="28" rx="6" class="b"/><text x="330" y="311" class="s">Visual Retrieval</text>
<path class="e" d="M160,251 L160,292"/>
<path class="e" d="M390,251 L390,292"/>
<rect x="170" y="345" width="230" height="30" rx="6" class="b out"/>
<text x="200" y="364" class="s">Late Fusion (α=0.5) → Δrank</text>
<path class="e" d="M160,320 L250,345"/>
<path class="e" d="M390,320 L320,345"/>
<!-- 분석 -->
<rect x="450" y="345" width="255" height="30" rx="6" class="b out"/>
<text x="460" y="364" class="s">RQ1: gap ↔ Δrank 연관 / RQ2: 성능</text>
<path class="e" d="M400,360 L450,360"/>
<path class="e" d="M600,251 C640,300 620,330 600,345"/>
</svg>
"""


def render_body_pre(pl):
    """본문 코드펜스 → 파이프라인 SVG / 수식군 / (기타)."""
    if "인코더 3종" in pl or "이중 인코딩" in pl:
        return f'<div class="figbox">{PIPE_SVG}</div>'
    if "Late Fusion" in pl and "score" in pl:
        return ('<div class="eqn">Text-only: <i>sim</i> = cos(<i>q</i><sub>txt</sub>, <i>d</i><sub>txt</sub>)'
                '&nbsp;&nbsp;·&nbsp;&nbsp;Visual-only: <i>sim</i> = cos(<i>q</i><sub>clip</sub>, '
                '<i>d</i><sub>img</sub>) <span class="ann">(교차모달)</span></div>'
                '<div class="eqn"><i>score</i> = α·norm(<i>sim</i><sub>text</sub>) + '
                '(1−α)·norm(<i>sim</i><sub>visual</sub>)<span class="eqtag">(2)</span></div>')
    if "Δrank(v,q)" in pl or "rank_text" in pl:
        return ('<div class="eqn">Δrank(<i>v,q</i>) = rank<sub>text</sub>(<i>v</i>|<i>q</i>) − '
                'rank<sub>fusion</sub>(<i>v</i>|<i>q</i>)'
                '<span class="ann">&nbsp;(양수 = 융합이 순위 개선)</span><span class="eqtag">(3)</span></div>')
    return f'<pre class="fig">{html.escape(pl)}</pre>'


def render(blocks):
    front, body = [], []
    for kind, pl, in_body in blocks:
        tgt = body if in_body else front
        if kind == "title_ko":
            front.append(f'<h1 class="title-ko">{inline(pl)}</h1>')
        elif kind == "title_en":
            front.append(f'<div class="title-en">{inline(pl)}</div>')
        elif kind == "h2":
            front_hdr = pl.startswith("요") or pl.startswith("ABSTRACT")
            (front if front_hdr else tgt).append(f'<h2 class="sec">{inline(pl)}</h2>')
        elif kind == "h3":
            tgt.append(f'<h3>{inline(pl)}</h3>')
        elif kind == "eq":
            eq, tag = pl
            tgt.append(f'<div class="eqn">{eq}<span class="eqtag">({html.escape(tag)})</span></div>')
        elif kind == "pre":
            tgt.append(render_body_pre(pl) if in_body else f'<pre class="fig">{html.escape(pl)}</pre>')
        elif kind == "table":
            tgt.append(f'<div class="tblbox">{md_table(pl)}</div>')
        elif kind == "ul":
            tgt.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in pl) + "</ul>")
        else:  # para
            raw = pl.strip("*").strip()
            if CAP.match(raw):
                tgt.append(f'<p class="caption">{inline(pl)}</p>')
            elif not in_body and (raw.startswith("키워드") or raw.startswith("Keywords")):
                m = re.match(r"(키워드|Keywords)[\s:*]*(.*)", raw)
                head, terms = (m.group(1), m.group(2).strip("* ").strip()) if m else ("키워드", raw)
                front.append(f'<h2 class="sec">{head}</h2>')       # ABSTRACT 헤더와 동일 스타일
                front.append(f'<p class="kwterms">{inline(terms)}</p>')  # 색인어 8pt 가운데
            elif not in_body and (raw.startswith("[저자") or raw.startswith("[Author") or raw.startswith("E-mail")):
                front.append(f'<p class="authors">{inline(pl)}</p>')
            elif not in_body:
                front.append(f'<p class="abs">{inline(pl)}</p>')
            else:
                tgt.append(f"<p>{inline(pl)}</p>")
    return "\n".join(front), "\n".join(body)


CSS = r"""
:root{ --serif:"함초롱바탕","HCR Batang LVT","HCR Batang","Batang","AppleMyungjo",serif;
       --gothic:"HCR Dotum","함초롱돋움","Malgun Gothic","AppleGothic","Dotum",sans-serif;
       --tnr:"Times New Roman",serif; --arial:Arial,"Malgun Gothic",sans-serif; }
*{ box-sizing:border-box; }
html,body{ background:#8a8f98; margin:0; }
@page{ size:A4; margin:30mm; }
@page{ @bottom-center{ content:"— " counter(page) " —"; font-family:var(--tnr); font-size:8pt; color:#888; } }
.front,.body{ font-family:var(--serif); color:#000; word-break:keep-all; overflow-wrap:break-word; }
.front{ font-size:9pt; line-height:1.5; }
.body{ font-size:9pt; line-height:1.45; column-count:2; column-gap:7mm;
       break-before:page; -webkit-column-break-before:page; }
.front p,.body p{ margin:0 0 1.6mm; text-align:left; }
.body p{ text-indent:1.5em; }
.body p.caption,.body li,.front p.authors,.front p.kw,.front p.abs{ text-indent:0; }
h1.title-ko{ font-size:14pt; font-weight:700; text-align:center; margin:2mm 0; }
.title-en{ font-family:var(--arial); font-size:12pt; font-weight:700; text-align:center; margin:0 0 3mm; }
.authors{ text-align:center; font-size:9pt; margin:.5mm 0; }
h2.sec{ font-family:var(--gothic); font-size:10pt; font-weight:700; text-align:center; margin:4mm 0 2mm; }
.body h2.sec{ margin:4mm 0 2mm; }
h3{ font-family:var(--gothic); font-size:9pt; font-weight:700; margin:2.5mm 0 1mm; }
.abs{ text-align:justify; }
.front p.kwterms{ font-family:var(--gothic); font-size:8pt; text-align:center; margin:0 0 2mm; }
.caption{ font-family:var(--gothic); font-size:9pt; margin:1mm 0 1.6mm; }
ul{ margin:0 0 1.6mm; padding-left:4.5mm; }
li{ margin:0 0 .8mm; }
code{ font-family:Consolas,"D2Coding",monospace; font-size:8.2pt; overflow-wrap:anywhere; }
/* 수식 */
.eqn{ font-family:var(--tnr); font-size:10.5pt; text-align:center; margin:2.5mm 0; position:relative; }
.eqn i{ font-style:italic; }
.eqn .ann{ font-family:var(--serif); font-size:8.5pt; color:#444; }
.eqn .eqtag{ position:absolute; right:0; font-size:9pt; color:#333; }
/* 표: 한쪽 단 안, 스크롤 없음(줄바꿈으로 축소) */
.tblbox{ margin:2mm 0; break-inside:avoid; }
table{ border-collapse:collapse; width:100%; font-size:7pt; }
th,td{ border:1px solid #555; padding:.7mm 1mm; text-align:left; vertical-align:top;
       font-family:var(--serif); overflow-wrap:anywhere; word-break:break-all; }
th{ font-family:var(--gothic); background:#eef1f5; }
td code{ font-size:6.6pt; }
/* 그림: 한쪽 단 안, 컬럼 폭에 맞춰 축소 */
.figbox{ text-align:center; margin:2mm 0; break-inside:avoid; }
svg.pipe{ width:100%; max-width:100%; height:auto; border:1px solid #e0e0e0; border-radius:4px; background:#fff; }
pre.fig{ font-family:Consolas,monospace; font-size:7pt; line-height:1.3; white-space:pre-wrap; margin:2mm 0;
         padding:2mm; background:#f6f6f8; border:1px solid #ddd; border-radius:3px; break-inside:avoid; }
.tbd{ color:#8a8a8a; font-style:italic; font-size:8.4pt; }
@media screen{
  body:not(.paged-done) .doc{ background:#fff; width:210mm; margin:14mm auto; padding:30mm;
          min-height:297mm; box-shadow:0 3px 16px rgba(0,0,0,.35); }
}
.pagedjs_page{ background:#fff; box-shadow:0 3px 16px rgba(0,0,0,.35); margin:8mm auto; }
"""

BANNER = ('<div class="banner">📄 <b>KIICE 배치 미리보기</b>(제출본 아님) · '
          '온라인이면 A4 페이지로 나뉘어 보입니다(안 나뉘면 <b>⌘P</b>로 페이지 확인). '
          '요약·ABSTRACT 1페이지 → 서론부터 다음 페이지·2단. '
          '수식/표/그림은 근사 렌더(실폰트·정밀조판은 HWP). 결과 미확정부는 빈칸.</div>')
BANNER_CSS = ('.banner{font-family:sans-serif;max-width:210mm;margin:0 auto 8mm;padding:8px 12px;'
              'background:#eef7ff;border:1px solid #b6d8f2;border-radius:6px;font-size:12px;color:#245}'
              '@media print{.banner{display:none}}')
PAGEDJS = ('<script>window.PagedConfig={after(){document.body.classList.add("paged-done");}};</script>'
           '<script src="https://unpkg.com/pagedjs/dist/paged.polyfill.js"></script>')


def main():
    blocks = parse(DOC.read_text(encoding="utf-8"))
    front_html, body_html = render(blocks)
    out = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>KIICE 미리보기 — 썸네일–제목 의미 격차</title>
<style>{CSS}{BANNER_CSS}</style></head><body>
{BANNER}
<div class="doc">
<div class="front">
{front_html}
</div>
<div class="body">
{body_html}
</div>
</div>
{PAGEDJS}
</body></html>"""
    OUT.write_text(out, encoding="utf-8")
    print(f"생성: {OUT}  (블록 {len(blocks)}개)")


if __name__ == "__main__":
    main()
