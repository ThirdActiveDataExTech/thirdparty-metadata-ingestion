"""P05 — paper_KIICE_ko.md → KIICE 2단 배치 미리보기 HTML 생성기.

목적: 제출본(HWP)이 아니라, 브라우저에서 '논문처럼 배치된 모습'을 확인하고 인쇄→PDF로
뽑기 위한 시각 미리보기. 소스(.md)에서 자동 변환하므로 본문이 바뀌면 재실행만 하면 동기화됨.

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


def inline(s: str) -> str:
    """마크다운 인라인 → HTML (bold, ⟦DATA⟧/【】 강조, `code`)."""
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    # ⟦...⟧ 와 【...】 는 미채움 표시로 강조
    s = re.sub(r"(⟦[^⟧]*⟧)", r'<span class="ph">\1</span>', s)
    s = re.sub(r"(【[^】]*】)", r'<span class="ph">\1</span>', s)
    return s


def clean_eq(s: str) -> str:
    """$$ 안의 LaTeX-유사 표기를 읽기 쉬운 HTML로 대략 변환."""
    s = s.replace("\\big", "").replace("\\!", "").replace("\\,", " ")
    s = s.replace("\\cos", "cos").replace("\\mathrm", "").replace("\\times", "×")
    s = re.sub(r"\\tag\{(.+?)\}", r"", s)  # 태그는 따로 우측 표기
    s = s.replace("{", "").replace("}", "")
    s = re.sub(r"\^([A-Za-z0-9]+)", r"<sup>\1</sup>", s)
    s = re.sub(r"_([A-Za-z0-9]+)", r"<sub>\1</sub>", s)
    s = s.replace("\\", "")
    return s.strip()


def main():
    raw = strip_comments(DOC.read_text(encoding="utf-8"))
    lines = raw.split("\n")

    # --- 파싱: 블록 리스트로 ---
    blocks = []  # (kind, payload)
    i = 0
    in_body = False  # Ⅰ 이후 = 2단
    while i < len(lines):
        ln = lines[i]
        st = ln.strip()

        if st == "":
            i += 1
            continue
        if st == "---":
            i += 1
            continue

        # 코드펜스
        if st.startswith("```"):
            buf = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            blocks.append(("pre", "\n".join(buf)))
            continue

        # 수식 $$
        if st == "$$":
            buf = []
            i += 1
            while i < len(lines) and lines[i].strip() != "$$":
                buf.append(lines[i])
                i += 1
            i += 1
            body = " ".join(x.strip() for x in buf)
            m = re.search(r"\\tag\{(.+?)\}", body)
            tag = m.group(1) if m else ""
            blocks.append(("eq", (clean_eq(body), tag)))
            continue

        # 표
        if st.startswith("|"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                buf.append(lines[i].strip())
                i += 1
            blocks.append(("table", buf))
            continue

        # 제목(H1) / 영문제목
        if st.startswith("# "):
            blocks.append(("title_ko", st[2:].strip()))
            i += 1
            continue

        # 섹션 헤더
        if st.startswith("## "):
            h = st[3:].strip()
            if h.startswith("Ⅰ"):
                in_body = True
            blocks.append(("h2", h))
            i += 1
            continue
        if st.startswith("### "):
            blocks.append(("h3", st[4:].strip()))
            i += 1
            continue

        # 불릿
        if st.startswith("- "):
            buf = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                buf.append(lines[i].strip()[2:])
                i += 1
            blocks.append(("ul", buf))
            continue

        # 저자 블록(영문제목 바로 아래 [저자]…) 및 일반 문단
        # 영문 제목: 단독 **...** 한 줄
        if re.fullmatch(r"\*\*.+\*\*", st) and not in_body and _prev_is_title(blocks):
            blocks.append(("title_en", st.strip("*").strip()))
            i += 1
            continue

        # 일반 문단(연속 줄 합치기)
        buf = [ln]
        i += 1
        while i < len(lines) and lines[i].strip() != "" and not _is_block_start(lines[i].strip()):
            buf.append(lines[i])
            i += 1
        para = " ".join(x.strip() for x in buf)
        blocks.append(("body_marker" if in_body else "front", para))

    html_out = render(blocks)
    OUT.write_text(html_out, encoding="utf-8")
    print(f"생성: {OUT}  (블록 {len(blocks)}개)")


def _prev_is_title(blocks):
    return blocks and blocks[-1][0] == "title_ko"


def _is_block_start(st: str) -> bool:
    return (st.startswith("#") or st.startswith("|") or st.startswith("```")
            or st == "$$" or st.startswith("- ") or st == "---")


def md_table(rows):
    cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows]
    if len(cells) >= 2 and set("".join(cells[1]).replace("|", "")) <= set("-: "):
        header, body = cells[0], cells[2:]
    else:
        header, body = cells[0], cells[1:]
    out = ['<table>']
    out.append("<thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in header) + "</tr></thead>")
    out.append("<tbody>")
    for r in body:
        out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def render(blocks):
    head = []      # 1단 (제목~키워드)
    body = []      # 2단 (Ⅰ~)
    target = head
    for kind, pl in blocks:
        if kind == "h2" and pl.startswith("Ⅰ"):
            target = body
        if kind == "title_ko":
            head.append(f'<h1 class="title-ko">{inline(pl)}</h1>')
        elif kind == "title_en":
            head.append(f'<div class="title-en">{inline(pl)}</div>')
        elif kind == "h2":
            target.append(f'<h2>{inline(pl)}</h2>')
        elif kind == "h3":
            target.append(f'<h3>{inline(pl)}</h3>')
        elif kind == "eq":
            eq, tag = pl
            target.append(f'<div class="eq"><span class="eqbody">{eq}</span>'
                          f'<span class="eqtag">{html.escape(tag)}</span></div>')
        elif kind == "pre":
            target.append(f'<pre class="fig">{html.escape(pl)}</pre>')
        elif kind == "table":
            target.append(f'<div class="tbl">{md_table(pl)}</div>')
        elif kind == "ul":
            items = "".join(f"<li>{inline(x)}</li>" for x in pl)
            target.append(f"<ul>{items}</ul>")
        else:  # front / body_marker
            cls = "abs" if (kind == "front") else ""
            target.append(f'<p class="{cls}">{inline(pl)}</p>')

    css = """
@page { size: A4; margin: 30mm; }
* { box-sizing: border-box; }
body { font-family: "함초롱바탕","HCR Batang","Batang","Times New Roman",serif;
       font-size: 9.6pt; line-height: 1.55; color:#111; background:#fff;
       max-width: 210mm; margin: 0 auto; padding: 18mm 16mm; }
.title-ko { font-size: 16pt; font-weight: 700; text-align:center; margin: 0 0 2mm; letter-spacing:-.2px; }
.title-en { font-family: Arial, "Malgun Gothic", sans-serif; font-size: 12pt; font-weight:700;
            text-align:center; margin: 0 0 4mm; }
.authors, .front-authors { text-align:center; font-size: 9pt; color:#333; margin: 0 0 5mm; }
h2 { font-family:"HCR Dotum","Malgun Gothic",sans-serif; font-size: 10.5pt; font-weight:700;
     text-align:center; margin: 6mm 0 2mm; }
h3 { font-family:"HCR Dotum","Malgun Gothic",sans-serif; font-size: 9.8pt; font-weight:700;
     margin: 4mm 0 1.5mm; }
p { margin: 0 0 2.2mm; text-align: justify; text-justify: inter-character; }
.abs { }
ul { margin: 0 0 2.5mm 0; padding-left: 5mm; }
li { margin: 0 0 1mm; text-align: justify; }
code { font-family: "D2Coding", Consolas, monospace; font-size: 8.6pt; background:#f4f4f4; padding:0 2px; }
.ph { background:#fff3cd; color:#7a5b00; border:1px solid #ffe08a; border-radius:3px;
      padding:0 3px; font-size: 8.8pt; }
.eq { text-align:center; margin: 3mm 0; position:relative; font-family:"Times New Roman",serif; font-size:10.5pt; }
.eqtag { position:absolute; right:0; color:#555; }
pre.fig { background:#f7f7f9; border:1px solid #ddd; border-radius:4px; padding:3mm;
          font-family:"D2Coding",Consolas,monospace; font-size: 7.7pt; line-height:1.35;
          white-space:pre; overflow-x:auto; margin: 2.5mm 0; }
.tbl { margin: 2.5mm 0; overflow-x:auto; }
table { border-collapse: collapse; width:100%; font-size: 8.6pt; }
th, td { border:1px solid #999; padding: 1.2mm 2mm; text-align:left; vertical-align:top; }
th { background:#eef1f5; font-family:"HCR Dotum","Malgun Gothic",sans-serif; }
.frontmatter { border-bottom: 1.5px solid #222; padding-bottom: 3mm; margin-bottom: 5mm; }
.abshead { font-family:"HCR Dotum","Malgun Gothic",sans-serif; font-weight:700; }
.twocol { column-count: 2; column-gap: 8mm; }
.twocol h2 { column-span: none; }
.tbl, pre.fig { break-inside: avoid; }
/* 넓은 표·pipeline 그림은 2단 가로지르기 */
.twocol .tbl, .twocol pre.fig, .twocol .eq { break-inside: avoid; }
.note { max-width:210mm; margin: 0 auto 6mm; padding: 3mm 4mm; background:#eef7ff;
        border:1px solid #b6d8f2; border-radius:5px; font-size: 8.6pt; color:#245; }
@media print { .note { display:none; } body { padding: 0; } }
"""
    note = ('<div class="note">📄 <b>KIICE 배치 미리보기</b> — 제출본(HWP) 아님. '
            '실제 폰트(함초롱바탕/휴먼고딕)·정밀 여백은 HWP 양식에서 확정. '
            '노란 표시(⟦DATA⟧·【결과】)는 라벨링·실험 후 채움. 인쇄(⌘P)→PDF로 배치 확인용.</div>')
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>KIICE 미리보기 — 썸네일–제목 의미 격차</title>
<style>{css}</style></head><body>
{note}
<div class="frontmatter">
{''.join(head)}
</div>
<div class="twocol">
{''.join(body)}
</div>
</body></html>"""


if __name__ == "__main__":
    main()
