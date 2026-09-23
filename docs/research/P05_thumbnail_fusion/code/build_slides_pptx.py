"""P05 — 구두발표용 PPT 생성 (python-pptx).

paper_KIICE_ko.md의 핵심을 발표 슬라이드로 구성. 그림 1/2/3 + 수식 PNG 삽입.
설계 목표(2026-09 개정):
  - 학술대회(어느 정도 지식이 있는 청중) 기준으로 필요성·방법·결과를 전문적으로 상세 서술.
  - 문장을 '툭툭 끊지 않고' 완결형으로 풀어 씀. 묶음 사이 간격을 넓히고 세로 중앙 정렬로 여백 균형.
  - 수식은 matplotlib(mathtext, cm 폰트)로 논문 품질 PNG를 렌더해 삽입.
  - 핵심 수치는 메트릭 카드/표 하이라이트/인라인 강조([[ ]])로 부각(단색 네이비).
  - 각 결과 슬라이드 하단 '핵심' 스트립으로 so-what 명시.

본문 강조 마크업:  [[텍스트]] → 네이비 볼드 강조

실행(저장소 루트):
  .venv/bin/python docs/research/P05_thumbnail_fusion/code/build_slides_pptx.py
출력: docs/research/P05_thumbnail_fusion/paper_KIICE_발표초안.pptx
"""
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["mathtext.fontset"] = "cm"

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

DIR = Path(__file__).resolve().parent.parent
RES = DIR / "results"
OUT = DIR / "paper_KIICE_발표초안.pptx"

KFONT = "맑은 고딕"
ACCENT  = RGBColor(0x1B, 0x3A, 0x5C)   # 딥 네이비(제목·핵심 강조) — 한 톤 다운
ACCENT2 = RGBColor(0x3E, 0x5C, 0x82)   # 뮤트 슬레이트블루(액센트선·키커)
DARK    = RGBColor(0x25, 0x2A, 0x30)   # 본문 기본(차분한 먹색)
GRAY    = RGBColor(0x5A, 0x63, 0x6E)   # 보조설명
FAINT   = RGBColor(0x97, 0xA0, 0xAB)   # 푸터·마크
LIGHT   = RGBColor(0xEA, 0xEC, 0xF0)   # 콜아웃·옅은 배경(중립 그레이)
FORMBG  = RGBColor(0xED, 0xEF, 0xF2)   # 수식 박스 배경(중립)
CARDLN  = RGBColor(0xD3, 0xD8, 0xDF)   # 카드 테두리(중립)
CHIPBG  = RGBColor(0xE4, 0xE7, 0xEC)   # 키커 칩 배경(중립)
WHITE   = RGBColor(0xFF, 0xFF, 0xFF)
BG      = RGBColor(0xF3, 0xF4, 0xF6)   # 슬라이드 배경(오프화이트) — 순백 대신 톤다운
NAVYHEX = "#1B3A5C"

EMU = 914400
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
SW, SH = prs.slide_width, prs.slide_height

_TOK = re.compile(r"(\[\[.*?\]\])")


# ─────────────────────────── 수식 PNG 렌더(논문 품질) ───────────────────────────
def render_formula(tex, fname, fontsize=23, color=NAVYHEX):
    path = RES / fname
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0.5, 0.5, f"${tex}$", fontsize=fontsize, color=color, ha="center", va="center")
    fig.savefig(str(path), dpi=300, transparent=True, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return path


EQ_GAP = render_formula(
    r"\mathrm{gap}_i \;=\; 1 - \cos\!\left(\mathrm{center}(v^{\mathrm{img}}_i),\ \mathrm{center}(g^{\mathrm{txt}}_i)\right)",
    "eq_gap.png")
EQ_FUSION = render_formula(
    r"\mathrm{score} \;=\; \alpha \,\cdot\, \mathrm{norm}(s_{\mathrm{text}}) \;+\; (1-\alpha)\,\cdot\,\mathrm{norm}(s_{\mathrm{visual}})",
    "eq_fusion.png")
EQ_DRANK = render_formula(
    r"\Delta\mathrm{rank}(v,q) \;=\; \mathrm{rank}_{\mathrm{text}}(v\mid q) \;-\; \mathrm{rank}_{\mathrm{fusion}}(v\mid q)",
    "eq_drank.png")


# ─────────────────────────── 공용 헬퍼 ───────────────────────────
def blank():
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid(); s.background.fill.fore_color.rgb = BG   # 오프화이트 배경
    return s


def _run(p, text, size, color, bold=False, italic=False, font=None):
    r = p.add_run(); r.text = text
    r.font.size = Pt(size); r.font.color.rgb = color
    r.font.bold = bold; r.font.italic = italic; r.font.name = font or KFONT
    return r


def emit(p, text, size, base_color):
    for seg in _TOK.split(text):
        if not seg:
            continue
        if seg.startswith("[["):
            _run(p, seg[2:-2], size + 1, ACCENT, bold=True)
        else:
            _run(p, seg, size, base_color)


def _noshadow(shape):
    shape.shadow.inherit = False
    return shape


def _indent(p, marL_in, hang_in):
    pPr = p._p.get_or_add_pPr()
    pPr.set("marL", str(int(marL_in * EMU)))
    pPr.set("indent", str(int(-hang_in * EMU)))


def title_bar(slide, text, kicker=None):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(0.42), Inches(0.13), Inches(0.74))
    bar.fill.solid(); bar.fill.fore_color.rgb = ACCENT2; bar.line.fill.background(); _noshadow(bar)
    top = 0.40
    if kicker:
        chip = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.86), Inches(0.40), Inches(0.02 + 0.098 * len(kicker)), Inches(0.30))
        chip.fill.solid(); chip.fill.fore_color.rgb = CHIPBG; chip.line.fill.background(); _noshadow(chip)
        ctf = chip.text_frame; ctf.word_wrap = False
        ctf.margin_left = Inches(0.1); ctf.margin_right = Inches(0.1)
        ctf.margin_top = Inches(0.01); ctf.margin_bottom = Inches(0.01)
        cp = ctf.paragraphs[0]; cp.alignment = PP_ALIGN.CENTER
        _run(cp, kicker, 11, ACCENT2, bold=True)
        top = 0.72
    tb = slide.shapes.add_textbox(Inches(0.84), Inches(top), Inches(11.9), Inches(0.66))
    tf = tb.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]
    emit(p, text, 25, ACCENT)
    for r in p.runs:
        r.font.bold = True; r.font.color.rgb = ACCENT
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(1.34), Inches(12.13), Pt(2.4))
    line.fill.solid(); line.fill.fore_color.rgb = ACCENT2; line.line.fill.background(); _noshadow(line)


def footer(slide, total=17):
    n = len(prs.slides._sldIdLst)  # 현재(마지막 추가) 슬라이드의 1-based 번호
    tb2 = slide.shapes.add_textbox(Inches(11.4), Inches(7.12), Inches(1.4), Inches(0.3))
    p = tb2.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.RIGHT
    _run(p, f"{n} / {total}", 9, FAINT)


def bullets(slide, items, left=0.9, top=1.62, width=11.55, height=4.55, size=18, gap=15, middle=False):
    """items: (lvl, text) 또는 text. lvl0=묶음 머리, lvl1=풀어쓴 설명.
    묶음(lvl0) 앞에 gap pt를 줘 간격을 벌리고, lvl1은 들여쓰기 최소화."""
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame; tf.word_wrap = True
    if middle:
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    first = True
    for i, item in enumerate(items):
        lvl, txt = item if isinstance(item, tuple) else (0, item)
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = 1.08
        if lvl == 0:
            p.space_before = Pt(0 if first else gap); p.space_after = Pt(3)
            _indent(p, 0.26, 0.26)
            _run(p, "▍ ", size, ACCENT2, bold=True)
            emit(p, txt, size, DARK)
        else:
            p.space_before = Pt(3); p.space_after = Pt(2)
            _indent(p, 0.58, 0.24)
            _run(p, "✓ ", size - 2, ACCENT2)
            emit(p, txt, size - 2, GRAY)
        first = False
    return tb


def image_fit(slide, name, left, top, max_w, max_h, center_x=True):
    pic = slide.shapes.add_picture(str(RES / name), Inches(left), Inches(top))
    ratio = min(max_w * EMU / pic.width, max_h * EMU / pic.height)
    pic.width = int(pic.width * ratio); pic.height = int(pic.height * ratio)
    pic.left = int((SW - pic.width) / 2) if center_x else Inches(left)
    pic.top = Inches(top)
    return pic


def caption(slide, text, top):
    tb = slide.shapes.add_textbox(Inches(0.75), Inches(top), Inches(11.9), Inches(0.5))
    p = tb.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    _run(p, text, 12, GRAY, italic=True)


def metric_card(slide, x, y, w, h, value, label, sub=None, vsize=32):
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    card.fill.solid(); card.fill.fore_color.rgb = WHITE
    card.line.color.rgb = CARDLN; card.line.width = Pt(1); _noshadow(card)
    strip = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(0.085))
    strip.fill.solid(); strip.fill.fore_color.rgb = ACCENT2; strip.line.fill.background(); _noshadow(strip)
    tf = card.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.1); tf.margin_right = Inches(0.1)
    tf.margin_top = Inches(0.12); tf.margin_bottom = Inches(0.08)
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    _run(p, value, vsize, ACCENT, bold=True)
    p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER; p2.space_before = Pt(3)
    _run(p2, label, 12, DARK, bold=True)
    if sub:
        p3 = tf.add_paragraph(); p3.alignment = PP_ALIGN.CENTER; p3.space_before = Pt(1)
        _run(p3, sub, 10, GRAY)
    return card


def formula_img(slide, png, x, y, w, h, label=None):
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    box.fill.solid(); box.fill.fore_color.rgb = FORMBG
    box.line.color.rgb = ACCENT2; box.line.width = Pt(1.25); _noshadow(box)
    lab_h = 0.0
    if label:
        lt = slide.shapes.add_textbox(Inches(x + 0.20), Inches(y + 0.05), Inches(w - 0.4), Inches(0.26))
        _run(lt.text_frame.paragraphs[0], label, 11.5, ACCENT2, bold=True)
        lab_h = 0.28
    pic = slide.shapes.add_picture(str(png), Inches(x), Inches(y))
    avail_w = (w - 0.6) * EMU
    avail_h = (h - lab_h - 0.20) * EMU
    ratio = min(avail_w / pic.width, avail_h / pic.height)
    pic.width = int(pic.width * ratio); pic.height = int(pic.height * ratio)
    pic.left = int(Inches(x) + (Inches(w) - pic.width) / 2)
    pic.top = int(Inches(y) + Inches(lab_h) + (Inches(h - lab_h) - pic.height) / 2)
    return box


def callout(slide, text, top, left=0.86, width=11.6, height=1.0, size=17):
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
    box.fill.solid(); box.fill.fore_color.rgb = LIGHT
    box.line.color.rgb = ACCENT2; box.line.width = Pt(1.25); _noshadow(box)
    tf = box.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.3); tf.margin_right = Inches(0.3)
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    emit(p, text, size, ACCENT)
    for r in p.runs:
        r.font.bold = True
    return box


def takeaway(slide, text, top=6.42, size=14.5):
    tag = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(top), Inches(1.05), Inches(0.58))
    tag.fill.solid(); tag.fill.fore_color.rgb = ACCENT; tag.line.fill.background(); _noshadow(tag)
    ttf = tag.text_frame; ttf.vertical_anchor = MSO_ANCHOR.MIDDLE
    ttf.margin_top = Inches(0.01); ttf.margin_bottom = Inches(0.01)
    tp = ttf.paragraphs[0]; tp.alignment = PP_ALIGN.CENTER
    _run(tp, "핵심", 15, WHITE, bold=True)
    body = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.72), Inches(top), Inches(11.01), Inches(0.58))
    body.fill.solid(); body.fill.fore_color.rgb = LIGHT
    body.line.color.rgb = ACCENT2; body.line.width = Pt(1); _noshadow(body)
    btf = body.text_frame; btf.word_wrap = True; btf.vertical_anchor = MSO_ANCHOR.MIDDLE
    btf.margin_left = Inches(0.22); btf.margin_right = Inches(0.22)
    bp = btf.paragraphs[0]; bp.alignment = PP_ALIGN.LEFT; bp.line_spacing = 1.04
    emit(bp, text, size, DARK)


def table(slide, data, left, top, width, col_w=None, size=15, header=True, hl_rows=None):
    hl_rows = hl_rows or set()
    rows, cols = len(data), len(data[0])
    gtbl = slide.shapes.add_table(rows, cols, Inches(left), Inches(top), Inches(width), Inches(0.42 * rows)).table
    if col_w:
        for j, w in enumerate(col_w):
            gtbl.columns[j].width = Inches(w)
    for i, row in enumerate(data):
        for j, val in enumerate(row):
            c = gtbl.cell(i, j)
            c.margin_left = Inches(0.08); c.margin_right = Inches(0.08)
            c.margin_top = Inches(0.03); c.margin_bottom = Inches(0.03)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = c.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.CENTER if j > 0 else PP_ALIGN.LEFT
            ishdr = header and i == 0
            emph = (i in hl_rows) and not ishdr
            _run(p, str(val), size, WHITE if ishdr else (ACCENT if emph else DARK), bold=(ishdr or emph))
            c.fill.solid()
            c.fill.fore_color.rgb = ACCENT if ishdr else (CHIPBG if i in hl_rows else (LIGHT if i % 2 == 0 else WHITE))
    return gtbl


# ═══════════════════════════════════════════ 슬라이드 ═══════════════════════════════════════════

# S1 — 표지 (칩 제거)
s = blank()
band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(2.15), SW, Inches(2.7))
band.fill.solid(); band.fill.fore_color.rgb = ACCENT; band.line.fill.background(); _noshadow(band)
accentstrip = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(2.15), SW, Inches(0.08))
accentstrip.fill.solid(); accentstrip.fill.fore_color.rgb = ACCENT2; accentstrip.line.fill.background(); _noshadow(accentstrip)
tb = s.shapes.add_textbox(Inches(0.9), Inches(2.42), Inches(11.5), Inches(2.3)); tf = tb.text_frame; tf.word_wrap = True
p = tf.paragraphs[0]; _run(p, "영상 검색에서 썸네일과 텍스트의 후기 융합에 따른", 27, WHITE, bold=True)
p = tf.add_paragraph(); _run(p, "검색 순위 변화와 의미 간극 분석", 27, WHITE, bold=True)
p = tf.add_paragraph(); p.space_before = Pt(10)
_run(p, "Analysis of Search Ranking Changes and Semantic Gap in Video Retrieval", 14, RGBColor(0xCF, 0xDF, 0xEF))
p = tf.add_paragraph(); _run(p, "with Late Fusion of Thumbnail and Textual Information", 14, RGBColor(0xCF, 0xDF, 0xEF))
tb = s.shapes.add_textbox(Inches(0.9), Inches(5.18), Inches(11.5), Inches(1.9)); tf = tb.text_frame
p = tf.paragraphs[0]; _run(p, "김시황 · 전민철*", 18, DARK, bold=True); _run(p, "    (주)모비젠", 14, GRAY)
p = tf.add_paragraph(); p.space_before = Pt(3)
_run(p, "Si-hwang Kim · Min cheol, Jeon*    Mobigen Co., Ltd.", 13, GRAY)
p = tf.add_paragraph(); p.space_before = Pt(2)
_run(p, "author@example.com · author@example.com", 12, GRAY)
p = tf.add_paragraph(); p.space_before = Pt(10)
_run(p, "제60회 한국정보통신학회 추계종합학술대회   |   발표일 [YYYY.MM.DD]", 12.5, ACCENT, bold=True)

# S2 — 목차 (논문 구조: 서론-관련연구-연구방법-실험설계-결과-논의-결론)
s = blank(); title_bar(s, "목차", kicker="CONTENTS")
toc = [
    ("Ⅰ", "서 론", "연구 배경 · 연구 질문(RQ1·RQ2) · 기여"),
    ("Ⅱ", "관련 연구", "멀티모달 검색 · 정합성 측정 · 적응적 모달 활용 · 연구 공백"),
    ("Ⅲ", "연구 방법", "처리 파이프라인 · 임베딩·gap·후기 융합 정의"),
    ("Ⅳ", "실험 설계", "코퍼스 · 검색어 · 정답지(qrels) · 지표·검정"),
    ("Ⅴ", "결 과", "검색 성능 · α 민감도 · 순위 재배치 · gap–순위 관계"),
    ("Ⅵ", "논 의", "실무적 함의 · 한계"),
    ("Ⅶ", "주요 결과 및 시사점", "핵심 결과 · 시사점·활용 · 관점 · 향후"),
]
y = 1.72
for _num, _name, _sub in toc:
    ch = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.15), Inches(y), Inches(0.62), Inches(0.56))
    ch.fill.solid(); ch.fill.fore_color.rgb = ACCENT; ch.line.fill.background(); _noshadow(ch)
    ctf = ch.text_frame; ctf.vertical_anchor = MSO_ANCHOR.MIDDLE
    ctf.margin_top = Inches(0.01); ctf.margin_bottom = Inches(0.01)
    cp = ctf.paragraphs[0]; cp.alignment = PP_ALIGN.CENTER
    _run(cp, _num, 18, WHITE, bold=True)
    tb = s.shapes.add_textbox(Inches(2.0), Inches(y - 0.02), Inches(10.6), Inches(0.62))
    tf = tb.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    pp = tf.paragraphs[0]
    _run(pp, _name, 19, ACCENT, bold=True); _run(pp, "      " + _sub, 13, GRAY)
    y += 0.72
footer(s)

# S3 — 연구 배경
s = blank(); title_bar(s, "연구 배경 — 검색은 텍스트를 보고, 사용자는 썸네일을 본다", kicker="Ⅰ · INTRODUCTION")
bullets(s, [
    "영상 검색 플랫폼은 제목·설명·태그 등 [[텍스트 메타데이터]]를 중심으로 색인함.",
    (1, "정작 사용자의 클릭 판단을 크게 좌우하는 [[썸네일의 시각 정보]]는 검색 색인에 직접 반영되는 경우가 제한적임."),
    "텍스트와 시각 채널의 융합을 통한 검색 성능 향상이 지속적으로 보고됨.",
    (1, "그러나 그 개선이 모든 영상에서 균일하게 나타나는지, 아니면 [[특정 조건에서만]] 나타나는지에 대한 분석은 충분하지 않음."),
    "시각 임베딩은 계산·저장 비용을 수반하므로, ‘[[언제]] 기여하는가’를 이해하는 것이 실무 색인 설계에 직접 연결됨.",
], top=1.62, height=4.55, size=19, gap=17, middle=True)
takeaway(s, "시각 정보의 검색 기여는 [[조건적]]일 수 있으나 그 조건이 규명되지 않음 — 본 연구는 [[썸네일–제목 의미 간극(gap)]]을 조건 변수로 삼아 한국어 YouTube [[840편·70검색어]]에서 사전등록 실증함.")
footer(s)

# S3 — 연구 질문 & 핵심 지표
s = blank(); title_bar(s, "연구 질문과 핵심 지표(gap)", kicker="Ⅰ · RESEARCH QUESTIONS")
rq1 = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.86), Inches(1.58), Inches(5.75), Inches(1.5))
rq1.fill.solid(); rq1.fill.fore_color.rgb = WHITE; rq1.line.color.rgb = ACCENT2; rq1.line.width = Pt(1.25); _noshadow(rq1)
tf = rq1.text_frame; tf.word_wrap = True; tf.margin_left = Inches(0.22); tf.margin_top = Inches(0.14)
p = tf.paragraphs[0]; _run(p, "RQ1  ·  조건", 15, ACCENT, bold=True)
p = tf.add_paragraph(); p.space_before = Pt(4); p.line_spacing = 1.08
emit(p, "영상별 [[gap]]이 클수록 융합에 의한 순위 개선([[Δrank]])이 커지는가?", 15, DARK)
rq2 = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.98), Inches(1.58), Inches(5.75), Inches(1.5))
rq2.fill.solid(); rq2.fill.fore_color.rgb = WHITE; rq2.line.color.rgb = ACCENT2; rq2.line.width = Pt(1.25); _noshadow(rq2)
tf = rq2.text_frame; tf.word_wrap = True; tf.margin_left = Inches(0.22); tf.margin_top = Inches(0.14)
p = tf.paragraphs[0]; _run(p, "RQ2  ·  성능", 15, ACCENT, bold=True)
p = tf.add_paragraph(); p.space_before = Pt(4); p.line_spacing = 1.08
emit(p, "CLIP 썸네일과 다국어 텍스트의 [[후기 융합]]이 [[Text-only]] 대비 검색을 향상시키는가?", 15, DARK)
formula_img(s, EQ_GAP, 0.86, 3.28, 11.87, 1.15, label="핵심 지표 · 썸네일–제목 의미 간극  (모달별 mean-centering 적용)")
bullets(s, [
    "gap은 사람의 라벨링 없이 임베딩만으로 [[자동 산출·재현]]되며, 영상마다 하나의 [[연속값]]으로 주어짐.",
    "다만 gap은 표현 공간에서의 ‘비유사도’일 뿐, ‘시각 정보가 검색에 유용한 정도’와 [[동일하지 않음]].",
], top=4.62, height=1.5, size=16, gap=8)
takeaway(s, "‘썸네일이 검색을 얼마나 돕는가’를 [[성능(RQ2)]]과 [[조건(gap, RQ1)]]의 두 축으로 나누어 검증함.")
footer(s)

# 의미 간극 직관 (신규 개념 그림)
s = blank(); title_bar(s, "의미 간극(gap)이란?", kicker="Ⅰ · KEY METRIC")
image_fit(s, "fig_gap_concept.png", left=0.9, top=1.72, max_w=11.5, max_h=4.6)
takeaway(s, "gap이 낮으면 썸네일이 제목을 잘 대변하고, 높으면 어긋남 — 본 연구는 이 [[gap이 검색 기여의 조건]]이 되는지를 검증함.")
footer(s)

# S4 — 연구 기여
s = blank(); title_bar(s, "연구 기여", kicker="Ⅰ · CONTRIBUTIONS")
bullets(s, [
    "라벨링이 필요 없는 [[썸네일–제목 의미 간극(gap)]] 지표를 정의하고 자동 계산함.",
    (1, "영상마다 시각·텍스트 표현이 표현 공간에서 얼마나 벌어져 있는지를 사람 개입 없이 하나의 값으로 수치화함."),
    "융합의 [[검색 효과(RQ2)]]와 [[gap–순위변화 관계(RQ1)]]를 함께 검증하는 분석 프레임을 제시함.",
    "이를 [[한국어 YouTube]] 환경에서 실증적으로 평가함.",
    "가설·표집·지표·검정을 결과 관찰 이전에 [[사전등록(pre-registration)]]함.",
    (1, "사전등록 분석과 결과 이후의 탐색적 분석을 구분해 보고함으로써, 어떤 결과가 확증이고 어떤 것이 탐색적 관찰인지 투명하게 전달함."),
], top=1.62, height=4.55, size=18, gap=15, middle=True)
takeaway(s, "지표·분석 프레임·실증에 더해, [[사전등록]]으로 결과 해석의 [[투명성]]을 확보한 점이 방법론적 기여임.")
footer(s)

# S6 — 관련 연구
s = blank(); title_bar(s, "관련 연구", kicker="Ⅱ · RELATED WORK")
bullets(s, [
    "멀티모달 검색 — CLIP은 이미지·텍스트를 공동 임베딩 공간에 정렬해 코사인으로 유사도를 측정함.",
    (1, "영상–텍스트 검색에 적용한 프레임 집계·하이브리드 융합은 통합에 초점을 둘 뿐, 시각 채널의 [[기여 조건]]을 주된 분석 대상으로 삼지 않음."),
    "정합성 측정 — CLIPScore·BLIP은 이미지–텍스트 정합성을 캡션 품질 평가에 사용함.",
    (1, "본 연구는 같은 코사인 유사도를 캡션 평가가 아니라 [[검색에서 시각 정보의 기여를 분석하는 변수]]로 활용함."),
    "적응적 모달 활용 — 오도성 썸네일 탐지(분류 과제), 검색어별 후기 융합 가중 조정·모달 능동 선택이 있음.",
    (1, "다만 이들은 [[성능 향상을 위한 적응 메커니즘]]이 목적이며, 정합성 차이 자체를 조건 변수로 다루지 않음."),
    "연구 공백 — 기존 연구는 성능·정합성 자체, 또는 점수 기반 적응에 머묾.",
    (1, "→ 본 연구는 [[썸네일–제목 비정렬 정도(gap)]]를 영상 수준 연속 변수로 정의하고, 이를 [[실제 순위 변화]]와 연결함."),
], top=1.6, height=4.7, size=16.5, gap=12, middle=True)
takeaway(s, "기존 연구가 다루지 않은 [[‘시각 정보가 언제 기여하는가’]]를 gap이라는 조건 변수로 검증하는 것이 본 연구의 차별점임.")
footer(s)

# S7 — 방법: 파이프라인
s = blank(); title_bar(s, "전체 처리 과정", kicker="Ⅲ · METHOD · PIPELINE")
image_fit(s, "fig1_pipeline.png", left=0.9, top=1.75, max_w=11.6, max_h=4.6)
takeaway(s, "검색어와 제목은 [[mpnet과 CLIP-text로 이중 인코딩]]되어 텍스트 검색과 시각 검색이 [[별도 채널]]로 산출되고, 두 채널을 후기 융합해 순위 변화를 측정함.")
footer(s)

# S6 — 방법: 정의(인코더·gap·융합·Δrank)
s = blank(); title_bar(s, "임베딩 · 의미 간극 · 후기 융합의 정의", kicker="Ⅲ · METHOD · DEFINITIONS")
tb = s.shapes.add_textbox(Inches(0.9), Inches(1.5), Inches(11.6), Inches(0.78)); tf = tb.text_frame; tf.word_wrap = True
p = tf.paragraphs[0]; p.line_spacing = 1.08
emit(p, "인코더 3종(sentence-transformers) — [[CLIP-image]](썸네일 512d) · [[CLIP-text]](CLIP 정렬 다국어; gap·시각검색 512d) · [[mpnet]](한국어 검색 768d)", 15, DARK)
formula_img(s, EQ_GAP, 0.86, 2.42, 11.87, 0.8, label="① 의미 간극 — 모달별 평균 중심화한 썸네일·제목 임베딩의 코사인을 1에서 뺀 값")
formula_img(s, EQ_FUSION, 0.86, 3.28, 11.87, 0.8, label="② 후기 융합 — 텍스트·시각 유사도를 정규화해 α로 가중합 (α=0.5를 primary로 고정)")
formula_img(s, EQ_DRANK, 0.86, 4.14, 11.87, 0.8, label="③ 순위 개선 — 융합 전(text) 대비 후(fusion)의 순위 상승폭 (양수 = 개선)")
bullets(s, [
    "α 전체 곡선은 [[탐색적 sensitivity]]로만 관찰하며, 사후에 최고 α를 ‘최적’으로 재선정하지 않음.",
    "Text-only 검색 점수와 gap은 [[서로 다른 표현 공간]]에서 산출되므로, gap을 검색 점수에 직접 섞지 않음.",
], top=5.08, height=1.15, size=15, gap=6)
takeaway(s, "융합 가중 [[α=0.5]]만 확증 조건으로 사전 고정하고, 나머지 α와 카테고리 분석은 [[탐색적]]으로만 해석함.")
footer(s)

# S7 — 실험 설계
s = blank(); title_bar(s, "실험 설계", kicker="Ⅳ · EXPERIMENTAL SETUP")
metric_card(s, 0.86, 1.58, 3.72, 1.28, "840편", "영상 코퍼스", "14개 카테고리 × 60편")
metric_card(s, 4.80, 1.58, 3.72, 1.28, "70 → 63", "평가 검색어", "관련 0개 검색어 7개 제외")
metric_card(s, 8.74, 1.58, 3.72, 1.28, "κ = 0.486", "평가자 일치도", "Fleiss’ κ · 3인 blind")
bullets(s, [
    "검색어는 [[YouTube 공개 자동완성]]에서 생성하여, 검색 대상과 정답이 같은 신호에서 나오는 순환논리를 피함.",
    "정답지(qrels)는 세 방식의 [[Top-10 합집합 pooling]] 뒤, 3인 blind 3단계 라벨의 [[중앙값]]으로 확정함.",
    (1, "쌍별 일치율 77.2–77.8% · 관련 0개 검색어 7개 제외 → 63개로 평가함."),
    "성능(RQ2) = [[MRR@10·NDCG@10·Recall@10]], 조건(RQ1) = [[Spearman ρ]](gap, Δrank).",
    (1, "순위는 코퍼스 840편 전체에서 산정 · Δrank는 Top-10 밖 관련 영상 이동까지 포함."),
], left=0.86, top=3.02, width=5.95, height=3.7, size=14.5, gap=9)
image_fit(s, "fig_metrics.png", left=7.0, top=3.12, max_w=5.9, max_h=3.4, center_x=False)
footer(s)

# S8 — 결과 ① 검색 성능 (표·텍스트 겹침 수정)
s = blank(); title_bar(s, "결과 ① 검색 성능 — 동일가중 후기 융합은 평균 성능엔 중립", kicker="Ⅴ · RESULTS · RQ2")
table(s, [
    ["방법", "MRR@10", "NDCG@10", "Recall@10"],
    ["Text-only", "0.690", "0.556", "0.627"],
    ["Visual-only", "0.432", "0.301", "0.316"],
    ["Late Fusion (α=0.5)", "0.673", "0.561", "0.637"],
], left=0.86, top=1.62, width=7.1, col_w=[2.9, 1.4, 1.4, 1.4], size=15, hl_rows={3})
metric_card(s, 8.28, 1.62, 2.15, 1.05, "−0.016", "ΔMRR (융합−텍스트)", vsize=25)
metric_card(s, 10.62, 1.62, 2.11, 1.05, "p = 0.761", "Wilcoxon · 개선 없음", vsize=22)
bullets(s, [
    "썸네일 단독(Visual-only)은 텍스트보다 확실히 약함 — [[MRR 0.432 vs 0.690]].",
    "동일가중 후기 융합(α=0.5)은 텍스트 대비 [[통계적으로 유의한 개선을 주지 못함]].",
    (1, "ΔMRR = −0.016 (95% CI [−0.089, +0.055]) · rank-biserial r = −0.06 으로 효과크기가 사실상 0임."),
    (1, "표본은 [[약 0.11 개선]]이면 80% 검정력으로 탐지 가능한 규모 → ‘적어도 이 정도의 개선은 없었다’로 해석함."),
], left=0.86, top=3.62, width=11.8, height=2.6, size=16, gap=10)
takeaway(s, "단, 이는 [[동일가중(0.5:0.5)]] 조건의 확증 결과임 — 가중을 바꾸면 결과가 달라짐.")
footer(s)

# S9 — 결과 ② α 민감도
s = blank(); title_bar(s, "결과 ② 낮은 시각 가중(30%)의 탐색적 이점", kicker="Ⅴ · RESULTS · EXPLORATORY")
image_fit(s, "fig2_alpha_curve.png", left=0.7, top=1.62, max_w=6.5, max_h=4.55, center_x=False)
metric_card(s, 7.35, 1.62, 5.38, 1.18, "α = 0.7", "세 지표 모두 최고", "텍스트 70% · 시각 30%", vsize=30)
bullets(s, [
    "사전등록 밖에서 [[α(텍스트 가중)]]를 0.0–1.0 전 구간에 걸쳐 탐색함.",
    (1, "Text-only 대비 [[MRR +0.011 · NDCG +0.038 · Recall +0.071]]로, 세 지표가 α=0.7에서 동시에 최고였음."),
    "즉 동일가중(0.5)에선 중립이었으나, 시각을 [[낮은 가중(30%)]]으로 결합하면 Text-only를 상회함.",
    "다만 α는 [[결과를 본 뒤 선택]]했고 다중비교를 통제하지 않았음.",
    (1, "→ 확증이 아니라, 후속 연구에서 검증할 [[유망한 탐색적 신호]]로 제시함."),
], left=7.35, top=2.95, width=5.5, height=3.3, size=15.5, gap=9)
takeaway(s, "융합 자체의 실패가 아니라 [[가중 설정]]의 문제였음 — 방향 전환의 여지가 관찰됨.")
footer(s)

# S10 — 결과 ③ 순위 재배치
s = blank(); title_bar(s, "결과 ③ 융합은 ‘깊은 순위’를 재배치한다", kicker="Ⅴ · RESULTS · RANK COMPOSITION")
image_fit(s, "fig_rank_rebalance.png", left=0.4, top=2.05, max_w=6.9, max_h=3.55, center_x=False)
lt = s.shapes.add_textbox(Inches(7.75), Inches(2.0), Inches(5.0), Inches(0.3))
_run(lt.text_frame.paragraphs[0], "텍스트 순위 구간별 Δrank · 개선율", 12.5, ACCENT2, bold=True)
table(s, [
    ["텍스트 순위", "n", "mΔrank", "개선율"],
    ["1–10위", "253", "−2.0", "24%"],
    ["11–50위", "132", "+13.0", "93%"],
    ["51–100위", "18", "+53.5", "100%"],
    ["101위+", "37", "+201.0", "100%"],
], left=7.75, top=2.42, width=5.0, col_w=[1.9, 0.75, 1.4, 0.95], size=14, hl_rows={4})
takeaway(s, "효과는 상위 노출 개선이 아니라 [[깊은 순위의 구성 변화]]에 집중됨 — recall 지향·재순위 단계에서 추가 검토할 가치가 있음.")
footer(s)

# S11 — 결과 ④ gap–순위 관계
s = blank(); title_bar(s, "결과 ④ gap–순위변화 관계 — 유의하지 않음", kicker="Ⅴ · RESULTS · RQ1")
image_fit(s, "fig3_gap_scatter.png", left=0.7, top=1.62, max_w=6.3, max_h=4.55, center_x=False)
metric_card(s, 7.2, 1.62, 5.5, 1.18, "ρ = −0.049", "centered gap ↔ Δrank", "p = 0.42 · 관계 확인 안 됨", vsize=27)
bullets(s, [
    "사전등록한 centered gap과 순위 변화는 [[유의한 상관이 없었음]].",
    "raw 상관(ρ = −0.226)은 [[카테고리 간 차이]]에서 비롯됨.",
    (1, "between [[−0.679]] vs within [[−0.120]] — 카테고리 내부에서는 상관이 약화됨."),
    "분석 명세를 바꾸면 [[부호가 뒤집힘]](cluster-robust 회귀에서는 +).",
    (1, "→ 단일 gap 지표만으로 시각 기여를 설명하기엔 한계가 있음."),
], left=7.2, top=2.95, width=5.5, height=3.3, size=15.5, gap=9)
takeaway(s, "‘gap이 낮은 영상은 시각 임베딩을 생략’하는 식의 [[선별 색인]]은 이 결과로 지지되지 않음.")
footer(s)

# S12 — 논의·함의
s = blank(); title_bar(s, "논의 · 실무적 함의", kicker="Ⅵ · DISCUSSION")
bullets(s, [
    "당초 구상한 [[gap 기반 선별 색인]](낮은 gap 영상은 시각 임베딩 생략)은 본 결과로 지지되지 않음.",
    (1, "동일가중 후기 융합이 평균 성능을 못 올렸고, gap도 기여 영상을 안정적으로 식별하지 못했기 때문임."),
    "단순 후기 융합으로 썸네일 유사도를 더하는 것만으로는 [[일관된 성능 개선]]을 기대하기 어려움.",
    "탐색적으로는 시각을 [[낮은 가중(α=0.7)]]으로 결합한 설정이 상대적으로 높은 성능을 보였으나, 사후 탐색이므로 확증적으로 해석할 수 없음.",
    "강건성 — Short(코퍼스 12.5%) 제외 부분표본(735편)에서도 결론 유지: [[ΔMRR +0.033(p=0.30)]], gap–순위 ρ=−0.06.",
    "한계로는 [[OCR 미지원]], 단일 플랫폼·언어, 소표본, Top-10 pooling에 따른 편향이 있으며, 카테고리·α 분석은 탐색적임.",
], top=1.55, height=4.75, size=16, gap=13, middle=True)
takeaway(s, "실무 함의는 ‘썸네일을 더하라’가 아니라 [[언제·어떻게 더할지를 조건으로 판단하라]]는 것임.")
footer(s)

# 주요 결과 및 시사점 (결론 역할 — 논의 다음 마무리)
s = blank(); title_bar(s, "주요 결과 및 시사점", kicker="Ⅶ · CONCLUSION")
lt = s.shapes.add_textbox(Inches(0.86), Inches(1.5), Inches(5.9), Inches(0.32))
_run(lt.text_frame.paragraphs[0], "주요 결과", 15, ACCENT, bold=True)
bullets(s, [
    "썸네일 단독은 텍스트를 대체할 강한 신호가 아니었고, 동일가중 후기 융합도 [[평균 성능엔 중립]]이었음.",
    "융합은 관련 영상의 [[깊은 순위]]를 끌어올려 순위 구성을 재배치함.",
    "단일 gap 지표로는 시각 기여 설명에 한계가 있었고, 효과 방향은 [[카테고리]]에 따라 상이했음.",
], left=0.86, top=1.88, width=5.9, height=2.55, size=15, gap=10)
rt = s.shapes.add_textbox(Inches(7.05), Inches(1.5), Inches(5.7), Inches(0.32))
_run(rt.text_frame.paragraphs[0], "시사점 · 활용", 15, ACCENT, bold=True)
bullets(s, [
    "[[recall 지향·재순위]] 단계에서 깊은 순위 관련 영상을 끌어올리는 보조 신호로 활용될 여지가 있음.",
    "시각을 [[낮은 가중(α=0.7)]]으로 결합하면 Text-only를 상회 — 탐색적 신호임.",
    "시각 정보의 가치는 평균 성능이 아니라 [[순위 구성·조건]]의 관점에서 평가할 필요가 있음.",
], left=7.05, top=1.88, width=5.7, height=2.55, size=15, gap=10)
callout(s, "시각 정보의 기여는 ‘평균 성능이 오르는가’가 아니라 ‘어떤 조건에서 순위를 바꾸는가’로 볼 때 드러남.",
        top=4.6, height=0.92, size=16)
tb = s.shapes.add_textbox(Inches(0.9), Inches(5.72), Inches(11.6), Inches(0.7)); tf = tb.text_frame; tf.word_wrap = True
p = tf.paragraphs[0]; p.line_spacing = 1.05
_run(p, "▍ 향후  ", 14, ACCENT2, bold=True)
emit(p, "객체·장면·OCR 등 풍부한 시각 신호와 검색어 특성의 상호작용을 검토하고, 다양한 검색 환경에서 재현성을 확인할 필요가 있음.", 14, GRAY)
footer(s)

# S14 — 감사 & Q&A
s = blank()
band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(2.35), SW, Inches(2.45))
band.fill.solid(); band.fill.fore_color.rgb = ACCENT; band.line.fill.background(); _noshadow(band)
accentstrip = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(2.35), SW, Inches(0.08))
accentstrip.fill.solid(); accentstrip.fill.fore_color.rgb = ACCENT2; accentstrip.line.fill.background(); _noshadow(accentstrip)
tb = s.shapes.add_textbox(Inches(0.9), Inches(2.72), Inches(11.5), Inches(1.7)); tf = tb.text_frame; tf.word_wrap = True
p = tf.paragraphs[0]; _run(p, "감사합니다  ·  Q & A", 32, WHITE, bold=True)
p = tf.add_paragraph(); p.space_before = Pt(10)
_run(p, "김시황 · 전민철  |  (주)모비젠  |  author@example.com", 14, RGBColor(0xCF, 0xDF, 0xEF))
tb = s.shapes.add_textbox(Inches(0.9), Inches(5.15), Inches(11.5), Inches(1.4)); tf = tb.text_frame; tf.word_wrap = True
p = tf.paragraphs[0]; p.line_spacing = 1.06
_run(p, "이 논문은 2024년도 정부(과학기술정보통신부)의 재원으로 정보통신기획평가원의 지원을 받아 수행된 연구임", 11, GRAY)
p = tf.add_paragraph(); _run(p, "(No.RS-2024-00340834, 써드파티 데이터의 활용성 증대를 위한 액티브 메타데이터 기반 능동형 데이터 확장 기술 개발)", 11, GRAY)

# ─── [부록] 예상 질문 & 대응 (내부 검토용 · 발표 시 생략 가능 · 푸터/노트 없음) ───
s = blank(); title_bar(s, "[부록] 예상 질문 & 대응", kicker="APPENDIX · Q&A")
bullets(s, [
    "Q1. α=0.5를 primary로 고정한 이유는?",
    (1, "결과 관찰 이전에 사전등록으로 고정 → 사후 선택(HARKing) 방지. 나머지 α는 탐색적으로만 보고함."),
    "Q2. gap이 유의하지 않은데 의미가 있나?",
    (1, "귀무결과도 MDES로 정보성 보고. ‘단일 gap만으로는 시각 기여 설명이 불충분’이라는 것이 본 연구의 발견임."),
    "Q3. 63개 검색어면 표본이 작지 않나?",
    (1, "RR@10 기준 약 0.11 개선을 80% 검정력으로 탐지 가능한 규모. 대표성 한계는 논문에 명시함."),
    "Q4. OCR 없이 한국어 썸네일 자막을 놓치지 않나?",
    (1, "한계로 명시한 부분. gap·시각 유사도가 다국어 CLIP의 한국어 품질에 의존 → 후속 과제로 남김."),
    "Q5. 카테고리별로 효과 방향이 다른 원인은?",
    (1, "카테고리당 표본이 작고(3~5) 다중비교 미통제라 탐색적. 후속 연구에서 검증할 가설로 제시함."),
], top=1.6, height=4.95, size=15, gap=12, middle=True)
tbx = s.shapes.add_textbox(Inches(0.6), Inches(6.9), Inches(12), Inches(0.35))
_run(tbx.text_frame.paragraphs[0], "※ 내부 검토용 부록 — 실제 발표에서는 생략 가능", 11, FAINT, italic=True)

# ─────────────────────────── 발표 노트(구두 스크립트) ───────────────────────────
NOTES = [
    "안녕하세요. 모비젠의 김시황입니다. 오늘 ‘영상 검색에서 썸네일과 텍스트의 후기 융합에 따른 검색 순위 변화와 의미 간극 분석’이라는 제목으로 "
    "발표하겠습니다. 한국어 유튜브 영상 840편과 검색어 70개를 대상으로, 썸네일의 시각 정보가 텍스트 기반 영상 검색에 어떤 기여를 하는지를 "
    "사전등록 방식으로 분석했습니다. 이 연구의 핵심은 ‘썸네일이 평균 검색 성능을 올리는가’라는 익숙한 질문을 넘어서, 썸네일이 검색 결과의 순위 "
    "구성을 어떻게 바꾸는지, 그리고 그 기여를 하나의 지표로 설명할 수 있는지로 관점을 옮긴 데 있습니다.",
    "발표는 논문 구조를 그대로 따릅니다. 먼저 서론에서 연구 배경과 두 연구 질문, 기여를 말씀드리고, 관련 연구로 기존 접근과의 차이를 짚겠습니다. "
    "이어 연구 방법과 실험 설계를 설명한 뒤, 결과 네 가지 — 검색 성능, 가중 민감도, 순위 재배치, 그리고 gap–순위 관계 — 를 차례로 보여드리고, "
    "논의와 결론으로 마무리하겠습니다.",
    "먼저 배경입니다. 유튜브 같은 영상 검색은 제목·설명·태그 같은 텍스트를 주로 색인합니다. 정작 사용자가 클릭을 결정할 때 크게 작용하는 썸네일의 "
    "시각 정보는 검색 색인에 직접 쓰이는 경우가 드뭅니다. 시각 채널을 텍스트와 결합해 성능을 높이려는 시도는 있었지만, 그 개선이 모든 영상에서 "
    "균일한지 아니면 특정 조건에서만 나타나는지에 대한 분석은 부족했습니다. 시각 임베딩은 계산·저장 비용이 들기 때문에, ‘언제 도움이 되는가’를 "
    "아는 것은 실무 색인 설계에도 중요합니다. 그래서 저희는 이를 조건적 문제로 보고, 썸네일과 제목의 의미 간극을 조건 변수로 삼았습니다.",
    "그래서 두 가지 질문을 세웠습니다. RQ1은 조건에 대한 질문으로, 영상별로 썸네일과 제목의 의미 간극 즉 gap이 클수록 융합에 의한 순위 개선이 "
    "커지는가입니다. RQ2는 성능 질문으로, 썸네일과 텍스트의 후기 융합이 텍스트 단독보다 검색을 개선하는가입니다. 핵심 지표인 gap은 CLIP 공동 "
    "공간에서 썸네일과 제목 임베딩의 코사인 유사도를 1에서 뺀 값으로, 라벨링 없이 자동으로 계산되고 영상마다 하나의 연속값으로 주어집니다. 다만 "
    "gap은 표현이 얼마나 다른가를 재는 것이지, 시각 정보가 유용한가와 같은 뜻은 아니라는 점을 분명히 했습니다.",
    "핵심 지표인 gap을 직관적으로 보겠습니다. 왼쪽처럼 썸네일이 제목 내용과 잘 맞으면 두 임베딩의 코사인 유사도가 높아 gap이 0에 가깝고, 오른쪽처럼 "
    "클릭 유도형 썸네일이 제목과 어긋나면 유사도가 낮아 gap이 1에 가까워집니다. 다만 gap이 크다는 것은 표현이 다르다는 뜻일 뿐, 그 시각 정보가 "
    "검색에 유용하다는 뜻은 아니라는 점이 이후 결과 해석의 전제가 됩니다.",
    "기여는 세 가지입니다. 첫째, 라벨링이 필요 없는 gap 지표를 정의하고 자동 계산했습니다. 둘째, 융합의 검색 효과와 gap–순위변화 관계를 함께 "
    "검증하는 분석 프레임을 만들었습니다. 셋째, 한국어 유튜브를 대상으로 실증 평가했습니다. 특히 이 연구는 가설·표집·지표·검정을 결과를 보기 전에 "
    "사전등록했고, 사전등록 분석과 사후 탐색 분석을 명확히 구분해 보고했습니다. 덕분에 어떤 결과가 확증이고 어떤 것이 탐색적 관찰인지 투명하게 "
    "전달할 수 있습니다.",
    "관련 연구를 정리하겠습니다. CLIP 기반 멀티모달 검색, 이미지–텍스트 정합성 측정, 그리고 검색어별로 모달을 적응적으로 활용하는 연구들이 있었습니다. "
    "그러나 이들은 성능 향상이나 정합성 자체, 혹은 점수 기반 적응 메커니즘에 초점이 있었고, 정합성의 차이 자체를 시각 기여의 조건 변수로 다루지는 "
    "않았습니다. 본 연구는 바로 이 지점 — 썸네일과 제목의 의미 간극을 영상 수준 연속 변수로 정의하고 실제 순위 변화와 연결한다는 점 — 에서 "
    "기존 연구와 구분됩니다.",
    "연구 방법을 전체 그림으로 보겠습니다. 검색어와 코퍼스를 구성한 뒤, 세 개의 인코더로 임베딩을 만들고 거기서 gap을 산출합니다. 그다음 "
    "텍스트·시각·융합 세 가지 검색을 수행하고, 융합 전후의 순위 변화인 Δrank를 계산해 분석합니다. 한 가지 강조할 점은, 검색어와 제목이 각각 "
    "mpnet과 CLIP-text 두 인코더로 이중 인코딩된다는 점입니다. 한국어 텍스트 검색은 mpnet이, 시각 채널과 gap 계산은 CLIP 정렬 텍스트가 담당합니다.",
    "조금 더 구체적으로 정의를 보겠습니다. 인코더는 셋입니다. 썸네일은 CLIP 이미지 인코더, gap과 시각 검색용 텍스트는 CLIP에 정렬된 다국어 "
    "인코더, 한국어 검색은 mpnet을 씁니다. 식 1의 gap은 모달별 평균 중심화를 적용한 썸네일과 제목 임베딩의 코사인을 1에서 뺀 값입니다. 식 2의 융합 "
    "점수는 텍스트 유사도와 시각 유사도를 정규화해 알파로 가중합하며, 알파 0.5 즉 동일가중을 미리 primary로 고정했습니다. 식 3의 Δrank는 융합 전후 "
    "순위 상승폭입니다. 알파 전체 곡선은 나중에 탐색적으로만 봤고, 텍스트 검색 점수와 gap이 서로 다른 공간에서 나오기 때문에 gap을 검색 점수에 "
    "섞어 쓰지 않았습니다.",
    "실험 설계입니다. 14개 카테고리에서 카테고리당 60편씩 840편, 그리고 70개 검색어를 모았습니다. 검색어는 순환 논리를 피하려고 유튜브 공개 "
    "자동완성에서 생성했습니다. 정답지는 세 검색 방식의 Top-10을 합쳐 후보를 만들고, 세 명이 독립적으로 블라인드 라벨링한 중앙값으로 확정했습니다. "
    "평가자 일치도는 Fleiss 카파 0.486으로 보통 수준이었습니다. 관련 영상이 하나도 없는 7개 검색어는 제외해 63개로 평가했고, 지표는 MRR·NDCG·Recall과 "
    "Spearman 상관을 썼습니다. 순위는 코퍼스 840편 전체에서 산정했습니다.",
    "이제 결과입니다. 먼저 검색 성능입니다. 표에서 보시듯 썸네일 단독은 텍스트보다 확실히 약했습니다. MRR 기준 0.43 대 0.69입니다. 그리고 동일가중 "
    "융합은 텍스트 대비 유의한 개선을 주지 못했습니다. MRR 변화가 마이너스 0.016, p값이 0.76으로 통계적으로 차이가 없고 효과크기도 거의 0입니다. "
    "다만 이 표본은 0.11 정도의 개선이면 탐지할 수 있는 규모였기 때문에, ‘적어도 이 정도 개선은 없었다’고 해석할 수 있습니다.",
    "그런데 사전등록 밖에서 알파를 탐색적으로 전부 비교해봤더니, 흥미롭게도 세 지표 모두 알파 0.7, 즉 텍스트 70퍼센트 시각 30퍼센트에서 가장 "
    "높았습니다. 이때는 텍스트 단독보다도, 동일가중보다도 높았습니다. 즉 앞 슬라이드의 결론은 융합이 무조건 안 된다가 아니라 동일가중에서만 "
    "중립이었다는 것이고, 시각을 낮은 가중으로 섞으면 방향이 달라질 여지가 보입니다. 다만 이건 결과를 본 뒤 고른 사후 분석이고 다중비교를 통제하지 "
    "않았기 때문에, 확증이 아니라 후속 연구에서 검증할 가설로 제시합니다.",
    "다음은 이 연구에서 가장 흥미로운 관찰입니다. 융합이 평균 성능은 못 올렸지만, 관련 영상들의 순위 구성 자체는 바꿨습니다. 표를 보시면 원래 상위 "
    "10위 안에 있던 관련 영상은 오히려 약간 내려갔지만, 11위 이후 깊은 순위에 있던 관련 영상들은 대부분 크게 올라갔습니다. 51위 이후는 100퍼센트 "
    "상승입니다. 즉 융합의 효과는 상위 노출을 개선하는 게 아니라 깊은 순위를 재배치하는 쪽으로 나타났습니다. recall 지향 검색이나 재순위 단계에서 "
    "추가로 검토할 가치가 있다는 뜻입니다.",
    "그럼 RQ1, gap이 이 순위 변화를 설명하느냐. 답은 아니오였습니다. 사전등록한 centered gap과 순위 변화의 상관은 마이너스 0.05, p값 0.42로 유의하지 "
    "않았습니다. raw gap에서는 약한 음의 상관이 있었지만, 이건 카테고리 간 차이 때문이었고 카테고리 내부에서는 약해졌습니다. 게다가 분석 방법을 "
    "바꾸면 부호가 뒤집히기까지 했습니다. 결국 하나의 gap 값만으로 시각 정보의 기여를 설명하기엔 한계가 있었습니다.",
    "논의입니다. 당초에는 gap이 낮은 영상은 시각 임베딩을 생략하자는 선별 색인을 구상했는데, 이번 결과로는 지지되지 않았습니다. 단순히 후기 융합으로 "
    "썸네일 유사도를 더하는 것만으로는 일관된 개선을 기대하기 어렵습니다. 다만 탐색적으로는 시각을 낮은 가중으로 결합한 설정이 상대적으로 높은 "
    "성능을 보였는데, 이는 사후 탐색이라 확증적으로 해석하지는 않습니다. 한계로는 OCR 미지원, 단일 플랫폼과 언어, 작은 표본, 그리고 Top-10 pooling에 "
    "따른 편향 등이 있습니다.",
    "주요 결과와 시사점을 정리하겠습니다. 썸네일 단독은 텍스트를 대체할 만큼 강하지 않았고 동일가중 후기 융합도 평균 성능은 개선하지 못했습니다. 다만 "
    "융합은 관련 영상의 순위 구성을 바꿔 특히 깊은 순위의 관련 영상을 끌어올렸고, 단일 gap 지표로는 시각 기여를 설명하기 어려웠으며 효과 방향은 "
    "카테고리마다 달랐습니다. 시사점으로는, 이 순위 재배치를 recall 지향 검색이나 재순위 단계의 보조 신호로 활용할 여지가 있고, 시각을 낮은 가중으로 "
    "결합하면 텍스트 단독을 상회할 여지가 관찰됐습니다. 요컨대 시각 정보의 기여는 평균 성능이 오르는가보다 어떤 조건에서 순위를 바꾸는가로 볼 때 더 "
    "잘 드러납니다. 앞으로는 객체·장면·OCR 등 풍부한 시각 신호와 검색어 특성의 상호작용을 검증하고 다양한 환경에서 재현성을 확인할 필요가 있습니다.",
    "이상으로 발표를 마치겠습니다. 본 연구는 IITP 과제 지원으로 수행되었습니다. 경청해 주셔서 감사합니다. 질문 받겠습니다.",
]
for _slide, _note in zip(prs.slides, NOTES):
    _slide.notes_slide.notes_text_frame.text = _note

# ── 영어 복합어가 줄 끝에서 잘리지 않도록 non-breaking hyphen(‑) 처리 ──
_NB_TERMS = [
    "clip-ViT-B-32-multilingual-v1", "paraphrase-multilingual-mpnet-base-v2",
    "clip-ViT-B-32", "sentence-transformers", "cluster-robust", "rank-biserial",
    "re-ranking", "Text-only", "Text-only", "Visual-only",
    "CLIP-image", "CLIP-text", "Top-10", "zero-relevance",
]
def _nbhyphen(_prs):
    for _sl in _prs.slides:
        for _sh in _sl.shapes:
            _frames = []
            if _sh.has_text_frame:
                _frames.append(_sh.text_frame)
            if _sh.has_table:
                for _r in _sh.table.rows:
                    for _c in _r.cells:
                        _frames.append(_c.text_frame)
            for _tf in _frames:
                for _p in _tf.paragraphs:
                    for _run in _p.runs:
                        _t = _run.text
                        for _term in _NB_TERMS:
                            if _term in _t:
                                _t = _t.replace(_term, _term.replace("-", "‑"))
                        if _t != _run.text:
                            _run.text = _t
_nbhyphen(prs)

prs.save(str(OUT))
print(f"생성: {OUT}  (슬라이드 {len(prs.slides._sldIdLst)}장)")
