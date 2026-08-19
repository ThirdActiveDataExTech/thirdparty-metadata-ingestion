"""P05 — paper_KIICE_ko.md → KIICE 2단 A4 '페이지 분리' 미리보기 HTML 생성기.

목적: 제출본(HWP)이 아니라, 브라우저에서 'HWP→PDF처럼 A4 페이지가 나뉜 논문 배치'를
확인하고 인쇄(⌘P)→PDF로 뽑기 위한 시각 미리보기.
- 페이지 분리: paged.js(온라인이면 화면에 A4 페이지 박스로 렌더) + print CSS(⌘P 정확)
- 폰트/표/그림 캡션을 KIICE 양식(2025)에 맞춤. ⟦DATA⟧·【결과】의 노란 강조는 제거.
- 소스(.md)에서 자동 변환 → 본문 바뀌면 재실행만.

실행: python3 docs/research/P05_thumbnail_fusion/code/build_preview_html.py
출력: docs/research/P05_thumbnail_fusion/paper_KIICE_preview.html
"""

import html
import re
from pathlib import Path

DOC = Path(__file__).resolve().parent.parent / "paper_KIICE_ko.md"
OUT = Path(__file__).resolve().parent.parent / "paper_KIICE_preview.html"


def strip_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def placeholders(s: str) -> str:
    """⟦DATA:x⟧→x, ⟦DATA⟧→얇은 밑줄 빈칸, 【…】→빈칸 (노란 강조 없음)."""
    s = re.sub(r"⟦DATA:([^⟧]*)⟧", r"\1", s)
    s = re.sub(r"⟦[^⟧]*⟧", '<span class="tbd">&nbsp;&nbsp;&nbsp;</span>', s)
    s = re.sub(r"【[^】]*】", '<span class="tbd">&nbsp;&nbsp;&nbsp;</span>', s)
    return s


def inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    s = placeholders(s)
    return s


def clean_eq(s: str) -> str:
    s = s.replace("\\big", "").replace("\\!", "").replace("\\,", " ")
    s = s.replace("\\cos", "cos").replace("\\mathrm", "").replace("\\times", "×")
    s = re.sub(r"\\tag\{(.+?)\}", "", s)
    s = s.replace("{", "").replace("}", "")
    s = re.sub(r"\^([A-Za-z0-9]+)", r"<sup>\1</sup>", s)
    s = re.sub(r"_([A-Za-z0-9]+)", r"<sub>\1</sub>", s)
    s = s.replace("\\", "")
    return s.strip()


def _is_block_start(st: str) -> bool:
    return (st.startswith("#") or st.startswith("|") or st.startswith("```")
            or st == "$$" or st.startswith("- ") or st == "---")


def parse(raw: str):
    lines = strip_comments(raw).split("\n")
    blocks, i, in_body = [], 0, False
    while i < len(lines):
        ln = lines[i]; st = ln.strip()
        if st in ("", "---"):
            i += 1; continue
        if st.startswith("```"):
            buf = []; i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i]); i += 1
            i += 1; blocks.append(("pre", "\n".join(buf))); continue
        if st == "$$":
            buf = []; i += 1
            while i < len(lines) and lines[i].strip() != "$$":
                buf.append(lines[i]); i += 1
            i += 1
            body = " ".join(x.strip() for x in buf)
            m = re.search(r"\\tag\{(.+?)\}", body)
            blocks.append(("eq", (clean_eq(body), m.group(1) if m else ""))); continue
        if st.startswith("|"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                buf.append(lines[i].strip()); i += 1
            blocks.append(("table", buf)); continue
        if st.startswith("# "):
            blocks.append(("title_ko", st[2:].strip())); i += 1; continue
        if st.startswith("## "):
            h = st[3:].strip()
            if h.startswith("Ⅰ"):
                in_body = True
            blocks.append(("h2", h)); i += 1; continue
        if st.startswith("### "):
            blocks.append(("h3", st[4:].strip())); i += 1; continue
        if st.startswith("- "):
            buf = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                buf.append(lines[i].strip()[2:]); i += 1
            blocks.append(("ul", buf)); continue
        if re.fullmatch(r"\*\*.+\*\*", st) and blocks and blocks[-1][0] == "title_ko":
            blocks.append(("title_en", st.strip("*").strip())); i += 1; continue
        buf = [ln]; i += 1
        while i < len(lines) and lines[i].strip() != "" and not _is_block_start(lines[i].strip()):
            buf.append(lines[i]); i += 1
        para = " ".join(x.strip() for x in buf)
        blocks.append(("body" if in_body else "front", para))
    return blocks


def md_table(rows):
    cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows]
    if len(cells) >= 2 and set("".join(cells[1])) <= set("-: |"):
        header, body = cells[0], cells[2:]
    else:
        header, body = cells[0], cells[1:]
    out = ['<table><thead><tr>' + "".join(f"<th>{inline(c)}</th>" for c in header) + "</tr></thead><tbody>"]
    for r in body:
        out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


CAP_RE = re.compile(r"^(표|그림)\s*\d+\.")


def render(blocks):
    parts = []
    for kind, pl in blocks:
        if kind == "title_ko":
            parts.append(f'<h1 class="title-ko span">{inline(pl)}</h1>')
        elif kind == "title_en":
            parts.append(f'<div class="title-en span">{inline(pl)}</div>')
        elif kind == "h2":
            # 요약/ABSTRACT 헤더만 전폭(1단). 본문 장(Ⅰ~Ⅶ)·Acknowledgement·References는 2단 내 중앙.
            front_hdr = pl.startswith("요") or pl.startswith("ABSTRACT")
            cls = "sec span" if front_hdr else "sec"
            parts.append(f'<h2 class="{cls}">{inline(pl)}</h2>')
        elif kind == "h3":
            parts.append(f'<h3>{inline(pl)}</h3>')
        elif kind == "eq":
            eq, tag = pl
            parts.append(f'<div class="eq"><span>{eq}</span><span class="eqtag">({html.escape(tag)})</span></div>')
        elif kind == "pre":
            parts.append(f'<pre class="fig">{html.escape(pl)}</pre>')
        elif kind == "table":
            parts.append(f'<div class="tbl">{md_table(pl)}</div>')
        elif kind == "ul":
            parts.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in pl) + "</ul>")
        else:  # front / body paragraph
            raw = pl.strip("*").strip()
            if CAP_RE.match(raw):
                parts.append(f'<p class="caption">{inline(pl)}</p>')
            elif kind == "front":
                # 저자/키워드/초록 본문 구분
                if raw.startswith("키워드") or raw.startswith("Keywords"):
                    parts.append(f'<p class="kw span">{inline(pl)}</p>')
                elif raw.startswith("[저자") or raw.startswith("[Author") or raw.startswith("E-mail"):
                    parts.append(f'<p class="authors span">{inline(pl)}</p>')
                else:
                    parts.append(f'<p class="abs span">{inline(pl)}</p>')
            else:
                parts.append(f"<p>{inline(pl)}</p>")
    return "\n".join(parts)


def _is_frontish(h):
    return h.startswith("요") or h.startswith("ABSTRACT") or h.startswith("키") \
        or h.startswith("Acknowledgement") or h.startswith("References")


CSS = r"""
:root{ --serif:"함초롱바탕","HCR Batang LVT","HCR Batang","Batang","AppleMyungjo",serif;
       --gothic:"HCR Dotum","함초롱돋움","Malgun Gothic","AppleGothic","Dotum",sans-serif;
       --tnr:"Times New Roman",serif; --arial:Arial,"Malgun Gothic",sans-serif; }
*{ box-sizing:border-box; }
html,body{ background:#8a8f98; margin:0; }
@page{ size:A4; margin:30mm 30mm 30mm 30mm; }
@page{ @bottom-center{ content:"— " counter(page) " —"; font-family:var(--tnr); font-size:8pt; color:#888; } }
.paper{ font-family:var(--serif); font-size:9pt; line-height:1.45; color:#000;
        column-count:2; column-gap:7mm; text-align:justify; }
.paper p{ margin:0 0 1.6mm; text-indent:2em; }
.paper p.authors,.paper p.kw,.paper p.caption,.paper li{ text-indent:0; }
.span{ column-span:all; -webkit-column-span:all; }
h1.title-ko{ font-family:var(--serif); font-size:15pt; font-weight:700; text-align:center;
             margin:0 0 2mm; }
.title-en{ font-family:var(--arial); font-size:12pt; font-weight:700; text-align:center; margin:0 0 3mm; }
.authors{ font-family:var(--serif); text-align:center; font-size:9pt; margin:0 0 1mm; }
h2.sec{ font-family:var(--gothic); font-size:10pt; font-weight:700; text-align:center;
        margin:5mm 0 2mm; }
h2.sec.span{ margin-top:3mm; }
h3{ font-family:var(--gothic); font-size:9pt; font-weight:700; margin:3mm 0 1mm; text-indent:0; }
.abs{ font-size:9pt; }
.kw{ font-family:var(--gothic); font-size:8.5pt; margin:2mm 0 0; }
.caption{ font-family:var(--gothic); font-size:8.5pt; margin:1mm 0 1.6mm; }
ul{ margin:0 0 1.6mm 0; padding-left:4.5mm; }
li{ margin:0 0 .8mm; }
code{ font-family:Consolas,"D2Coding",monospace; font-size:8.2pt; }
.eq{ text-align:center; margin:2mm 0; font-family:var(--tnr); font-size:10.5pt; position:relative; }
.eqtag{ position:absolute; right:2mm; color:#333; }
pre.fig{ font-family:Consolas,"D2Coding",monospace; font-size:7pt; line-height:1.3;
         white-space:pre; overflow-x:auto; margin:2mm 0; padding:2mm; background:#f6f6f8;
         border:1px solid #ddd; border-radius:3px; break-inside:avoid; }
.tbl{ margin:2mm 0; overflow-x:auto; break-inside:avoid; }
table{ border-collapse:collapse; width:100%; font-size:8pt; }
th,td{ border:1px solid #666; padding:1mm 1.6mm; text-align:left; vertical-align:top;
       font-family:var(--serif); }
th{ font-family:var(--gothic); background:#eef1f5; }
.tbd{ border-bottom:1px solid #aaa; }
.abstract-sep{}
/* 화면(paged.js 미동작 시) 폴백: A4 폭 흰 종이처럼 */
@media screen{
  body{ padding:14mm 0; }
  .paper{ background:#fff; width:210mm; min-height:297mm; margin:0 auto;
          padding:30mm; box-shadow:0 2px 14px rgba(0,0,0,.35); }
}
/* paged.js 동작 시 종이 박스 스타일 */
.pagedjs_page{ background:#fff; box-shadow:0 2px 14px rgba(0,0,0,.35); margin:8mm auto; }
@media screen{ .pagedjs_pages{ padding:10mm 0; } }
"""

BANNER = ('<div class="banner">📄 <b>KIICE 배치 미리보기</b>(제출본 아님) · '
          '온라인이면 A4 페이지로 나뉘어 보입니다. 안 나뉘면 <b>⌘P(인쇄 미리보기)</b>로 '
          '페이지 수·배치를 확인하세요(HWP→PDF와 동일 배치). '
          '실제 폰트(함초롱바탕/휴먼고딕)·정밀 여백은 HWP에서 확정. '
          '결과 미확정부는 빈칸으로 표시.</div>')

BANNER_CSS = ('.banner{font-family:sans-serif;max-width:210mm;margin:0 auto 8mm;padding:8px 12px;'
              'background:#eef7ff;border:1px solid #b6d8f2;border-radius:6px;font-size:12px;color:#245;}'
              '@media print{.banner{display:none;}}')

PAGEDJS = '<script src="https://unpkg.com/pagedjs/dist/paged.polyfill.js"></script>'


def main():
    blocks = parse(DOC.read_text(encoding="utf-8"))
    body_html = render(blocks)
    out = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>KIICE 미리보기 — 썸네일–제목 의미 격차</title>
<style>{CSS}{BANNER_CSS}</style></head><body>
{BANNER}
<div class="paper">
{body_html}
</div>
{PAGEDJS}
</body></html>"""
    OUT.write_text(out, encoding="utf-8")
    print(f"생성: {OUT}  (블록 {len(blocks)}개)")


if __name__ == "__main__":
    main()
