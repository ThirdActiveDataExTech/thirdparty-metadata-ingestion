"""P05 — 구두발표용 PPT 초안 생성 (python-pptx).

paper_KIICE_ko.md의 핵심을 14슬라이드로 구성. 그림 1/2/3(results/*.png) 삽입.
초안 목적: 골격·수치를 담아두고, 이후 함께 디자인·문구 수정.

실행(저장소 루트):
  .venv/bin/python docs/research/P05_thumbnail_fusion/code/build_slides_pptx.py
출력: docs/research/P05_thumbnail_fusion/paper_KIICE_발표초안.pptx
"""
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

DIR = Path(__file__).resolve().parent.parent
RES = DIR / "results"
OUT = DIR / "paper_KIICE_발표초안.pptx"

KFONT = "맑은 고딕"
ACCENT  = RGBColor(0x1F, 0x4E, 0x79)   # 진한 파랑(제목)
ACCENT2 = RGBColor(0x2E, 0x75, 0xB6)   # 중간 파랑(강조선)
DARK    = RGBColor(0x22, 0x22, 0x22)
GRAY    = RGBColor(0x55, 0x55, 0x55)
LIGHT   = RGBColor(0xEE, 0xF2, 0xF7)
WHITE   = RGBColor(0xFF, 0xFF, 0xFF)

EMU = 914400
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
SW, SH = prs.slide_width, prs.slide_height


def blank():
    return prs.slides.add_slide(prs.slide_layouts[6])


def _run(p, text, size, color, bold=False, italic=False):
    r = p.add_run(); r.text = text
    r.font.size = Pt(size); r.font.color.rgb = color
    r.font.bold = bold; r.font.italic = italic; r.font.name = KFONT
    return r


def title_bar(slide, text, kicker=None):
    tb = slide.shapes.add_textbox(Inches(0.6), Inches(0.32), Inches(12.1), Inches(0.95))
    tf = tb.text_frame; tf.word_wrap = True
    if kicker:
        p0 = tf.paragraphs[0]; _run(p0, kicker, 12, ACCENT2, bold=True)
        p = tf.add_paragraph()
    else:
        p = tf.paragraphs[0]
    _run(p, text, 27, ACCENT, bold=True)
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(1.33), Inches(12.1), Pt(3))
    line.fill.solid(); line.fill.fore_color.rgb = ACCENT2; line.line.fill.background()
    line.shadow.inherit = False


def bullets(slide, items, left=0.75, top=1.62, width=11.9, height=5.4, size=18):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame; tf.word_wrap = True
    for i, item in enumerate(items):
        lvl, txt = item if isinstance(item, tuple) else (0, item)
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.level = lvl; p.space_after = Pt(7); p.space_before = Pt(0)
        mark = "•  " if lvl == 0 else ("–  " if lvl == 1 else "·  ")
        pad = "    " * lvl
        _run(p, pad + mark, size - lvl * 2, ACCENT2 if lvl == 0 else GRAY, bold=(lvl == 0))
        _run(p, txt, size - lvl * 2, DARK if lvl == 0 else GRAY, bold=False)
    return tb


def image_fit(slide, name, left, top, max_w, max_h, center_x=True):
    pic = slide.shapes.add_picture(str(RES / name), Inches(left), Inches(top))
    ratio = min(max_w * EMU / pic.width, max_h * EMU / pic.height)
    pic.width = int(pic.width * ratio); pic.height = int(pic.height * ratio)
    if center_x:
        pic.left = int((SW - pic.width) / 2)
    pic.top = Inches(top)
    return pic


def caption(slide, text, top):
    tb = slide.shapes.add_textbox(Inches(0.75), Inches(top), Inches(11.9), Inches(0.5))
    tf = tb.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    _run(p, text, 12, GRAY, italic=True)


def callout(slide, text, top, left=0.75, width=11.9, height=1.0, size=18):
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
    box.fill.solid(); box.fill.fore_color.rgb = LIGHT
    box.line.color.rgb = ACCENT2; box.line.width = Pt(1.5); box.shadow.inherit = False
    tf = box.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.3); tf.margin_right = Inches(0.3)
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    _run(p, text, size, ACCENT, bold=True)
    return box


def table(slide, data, left, top, width, col_w=None, size=15, header=True):
    rows, cols = len(data), len(data[0])
    gtbl = slide.shapes.add_table(rows, cols, Inches(left), Inches(top), Inches(width), Inches(0.4 * rows)).table
    if col_w:
        for j, w in enumerate(col_w):
            gtbl.columns[j].width = Inches(w)
    for i, row in enumerate(data):
        for j, val in enumerate(row):
            c = gtbl.cell(i, j)
            c.margin_left = Inches(0.08); c.margin_right = Inches(0.08)
            c.margin_top = Inches(0.02); c.margin_bottom = Inches(0.02)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = c.text_frame; tf.word_wrap = True
            p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER if j > 0 else PP_ALIGN.LEFT
            ishdr = header and i == 0
            _run(p, str(val), size, WHITE if ishdr else DARK, bold=ishdr)
            c.fill.solid()
            c.fill.fore_color.rgb = ACCENT if ishdr else (LIGHT if i % 2 == 0 else WHITE)
    return gtbl


# ─────────────────────────────────────────── 슬라이드 ───────────────────────────────────────────

# S1 — 표지
s = blank()
band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(2.15), SW, Inches(2.7))
band.fill.solid(); band.fill.fore_color.rgb = ACCENT; band.line.fill.background(); band.shadow.inherit = False
tb = s.shapes.add_textbox(Inches(0.8), Inches(2.35), Inches(11.7), Inches(2.3)); tf = tb.text_frame; tf.word_wrap = True
p = tf.paragraphs[0]; _run(p, "영상 검색에서 썸네일과 텍스트의 후기 융합에 따른 검색 순위 변화와 의미 간극 분석", 28, WHITE, bold=True)
p = tf.add_paragraph(); _run(p, "Analysis of Search Ranking Changes and Semantic Gap in Video Retrieval with Late Fusion of Thumbnail and Textual Information", 16, WHITE)
p = tf.add_paragraph(); p.space_before = Pt(10)
_run(p, "사전등록 기반 실증 연구 · 한국어 YouTube 840편 · 70검색어", 14, RGBColor(0xD6, 0xE4, 0xF0))
tb = s.shapes.add_textbox(Inches(0.8), Inches(5.15), Inches(11.7), Inches(1.4)); tf = tb.text_frame
p = tf.paragraphs[0]; _run(p, "김시황 · 전민철*", 18, DARK, bold=True)
p = tf.add_paragraph(); _run(p, "(주)모비젠", 14, GRAY)
p = tf.add_paragraph(); p.space_before = Pt(8)
_run(p, "한국정보통신학회 춘·추계 종합학술대회  |  발표일 [YYYY.MM.DD]", 12, GRAY)

# S2 — 연구 배경
s = blank(); title_bar(s, "연구 배경", kicker="INTRODUCTION")
bullets(s, [
    "영상 검색 플랫폼은 제목·설명·태그 등 텍스트 메타데이터를 주로 색인한다.",
    "클릭 판단에 크게 작용하는 썸네일의 시각 정보는 검색 색인에 직접 반영되는 사례가 제한적이다.",
    "시각 채널을 텍스트와 후기 융합(late fusion)해 성능을 높이는 접근이 보고되어 왔다 [1][2].",
    (1, "그러나 그 개선이 모든 영상에서 균일한지, 특정 조건에서만 나타나는지에 대한 분석은 부족하다."),
    "시각 임베딩은 계산·저장 비용이 있어, ‘언제 기여하는가’를 이해하는 것은 색인 설계에 함의를 갖는다.",
    (1, "→ 본 연구는 이 문제를 한국어 YouTube 검색 환경에서 실증적으로 분석한다."),
])

# S3 — 연구 질문 & 핵심 개념
s = blank(); title_bar(s, "연구 질문과 핵심 지표(gap)", kicker="RESEARCH QUESTIONS")
bullets(s, [
    "RQ1 (조건): 영상별 gap이 클수록 융합에 의한 검색 순위 개선(Δrank)이 큰가?",
    "RQ2 (성능): CLIP 썸네일 + 다국어 텍스트 후기 융합이 text-only 대비 검색을 개선하는가?",
    "핵심 지표 — 썸네일–제목 의미 간극(gap)",
    (1, "gap = 1 − cos( center(썸네일 임베딩), center(제목 임베딩) )  (모달별 mean-centering)"),
    (1, "라벨링 불필요 · 자동·재현 가능 · 영상 수준 연속 지표"),
    (1, "주의: gap은 ‘표현 공간의 비유사도’이며, ‘시각 정보의 유용성’과 동일시하지 않는다."),
])

# S4 — 기여
s = blank(); title_bar(s, "연구 기여", kicker="CONTRIBUTIONS")
bullets(s, [
    "(1) 라벨링이 필요 없는 썸네일–제목 의미 간극(gap) 지표의 정의 및 자동 계산",
    "(2) 텍스트–시각 융합의 검색 효과와 gap–순위변화 관계를 검증하는 분석 프레임",
    "(3) 한국어 YouTube를 대상으로 한 실증 평가",
    "사전등록(pre-registration): 가설·표집·지표·검정을 결과 관찰 이전에 고정",
    (1, "사전등록 분석과 결과 이후의 탐색적 분석을 구분해 보고 → 결과 해석의 투명성 확보"),
])

# S5 — 방법: 파이프라인 그림
s = blank(); title_bar(s, "전체 처리 과정", kicker="METHOD · PIPELINE")
image_fit(s, "fig1_pipeline.png", left=0.9, top=1.7, max_w=11.5, max_h=4.6)
caption(s, "그림 1. 검색어·코퍼스 구성 → 임베딩 → gap 산출 → 검색·융합 → 순위 개선(Δrank) 분석", top=6.45)

# S6 — 방법: 인코더 & 융합
s = blank(); title_bar(s, "임베딩·gap·융합 정의", kicker="METHOD · DEFINITIONS")
bullets(s, [
    "세 인코더를 역할별로 사용 (모두 sentence-transformers)",
    (1, "CLIP-image(썸네일, 512d) · CLIP-text(다국어, gap·시각, 512d) · mpnet(한국어 검색, 768d)"),
    "gap = 1 − cos( center(v_img), center(g_txt) )",
    "Late fusion: score = α·norm(s_text) + (1−α)·norm(s_visual),  α=0.5를 primary로 고정",
    (1, "α∈{0.0 … 1.0} 전체 곡선은 탐색적 sensitivity로만 보고(최고 α를 ‘최적’으로 선택하지 않음)"),
    "Text-only 검색 점수와 gap은 서로 다른 표현 공간에서 산출 → gap을 점수에 사용하지 않음",
])

# S7 — 실험 설계
s = blank(); title_bar(s, "실험 설계", kicker="EXPERIMENTAL SETUP")
bullets(s, [
    "데이터: 14개 카테고리 × 60편 = 840편, 평가 검색어 70개(14×5) — 카테고리 층화표본",
    "검색어: YouTube 공개 자동완성에서 생성(순환논리 회피), 사전 정의 기준으로 부적합 후보 제외",
    "정답지(qrels): Text∪Visual∪Fusion 각 Top-10 pooling → 3인 blind 라벨(2=관련/1=부분/0=무관), 중앙값",
    (1, "일치도: Fleiss’ κ = 0.486, 쌍별 단순 일치율 77.2–77.8%"),
    "관련 0개 검색어 7개 제외 → 63개 검색어로 검색 평가 (검색어당 관련 영상 평균 7.0개)",
    "지표: MRR@10 · NDCG@10 · Recall@10 (RQ2),  Spearman ρ(gap, median Δrank) (RQ1)",
])

# S8 — 결과 ① 검색 성능
s = blank(); title_bar(s, "결과 ① 검색 성능 — 동일가중(0.5:0.5) 융합은 평균 성능엔 중립", kicker="RESULTS · RQ2")
table(s, [
    ["방법", "MRR@10", "NDCG@10", "Recall@10"],
    ["Text-only", "0.690", "0.556", "0.627"],
    ["Visual-only", "0.432", "0.301", "0.316"],
    ["Late Fusion (α=0.5)", "0.673", "0.561", "0.637"],
], left=1.4, top=1.75, width=8.0, col_w=[3.2, 1.6, 1.6, 1.6], size=15)
bullets(s, [
    "썸네일 단독(Visual-only)은 텍스트보다 약함 (MRR 0.432 vs 0.690).",
    "동일가중 융합(α=0.5)은 텍스트 대비 유의한 개선 없음",
    (1, "ΔMRR = −0.016 (95% CI [−0.089, +0.055]), Wilcoxon p = 0.761 · rank-biserial r = −0.06"),
    "단, 이는 ‘동일가중(0.5:0.5)’ 조건의 확증 결과 — 가중을 바꾸면 달라짐(다음 슬라이드)",
], top=4.05, size=17)

# S9 — 결과 ② α 민감도
s = blank(); title_bar(s, "결과 ② 낮은 시각 가중(30%)의 탐색적 이점", kicker="RESULTS · EXPLORATORY")
image_fit(s, "fig2_alpha_curve.png", left=0.7, top=1.65, max_w=6.6, max_h=4.9, center_x=False)
prs.slides[-1].shapes[-1].left = Inches(0.7)
bullets(s, [
    "사전등록 밖에서 α(텍스트 가중)를 전체 탐색",
    (1, "세 지표 모두 α=0.7(텍스트 70% · 시각 30%)에서 최고"),
    (1, "text-only 대비 MRR +0.011 · NDCG +0.038 · Recall +0.071"),
    "즉 동일가중(0.5)에선 중립이었지만,",
    (1, "시각을 낮은 가중(30%)으로 쓰면 text-only를 상회"),
    "단, α는 결과를 본 뒤 선택 + 다중비교 미통제",
    (1, "→ ‘확증’이 아닌 유망한 탐색적 신호 (후속 검증 과제)"),
], left=7.35, top=1.85, width=5.65, size=16)

# S10 — 결과 ③ 순위 재배치
s = blank(); title_bar(s, "결과 ③ 융합은 ‘깊은 순위’를 재배치", kicker="RESULTS · RANK COMPOSITION")
table(s, [
    ["Text 순위 구간", "n", "median Δrank", "개선(>0) 비율"],
    ["1–10", "253", "−2.0", "24%"],
    ["11–50", "132", "+13.0", "93%"],
    ["51–100", "18", "+53.5", "100%"],
    ["101+", "37", "+201.0", "100%"],
], left=1.4, top=1.75, width=8.2, col_w=[3.0, 1.4, 2.2, 1.6], size=14)
bullets(s, [
    "융합은 관련 영상의 전체 코퍼스 순위를 재배치 (검색어별 median Δrank +1, 양수 59%).",
    "상위 10위(1–10)는 오히려 소폭 하락(−2.0, 개선 24%).",
    "깊은 순위(11위 이후)의 관련 영상은 대부분 상승(11–50위 93%, 51위+ 100%).",
    "→ 상위 노출 개선이 아니라 깊은 순위 구성 변화에 집중 (Top-10 pooling 내 기술통계).",
], top=4.35, size=17)

# S11 — 결과 ④ gap–순위 관계
s = blank(); title_bar(s, "결과 ④ gap–순위변화 관계 — 유의하지 않음", kicker="RESULTS · RQ1")
image_fit(s, "fig3_gap_scatter.png", left=0.7, top=1.65, max_w=6.4, max_h=4.9, center_x=False)
prs.slides[-1].shapes[-1].left = Inches(0.7)
bullets(s, [
    "사전등록 centered gap ↔ 영상당 median Δrank",
    (1, "Spearman ρ = −0.049 (95% CI [−0.175, +0.080], p = 0.42) → 관계 확인 안 됨"),
    "raw 상관(ρ = −0.226)은 카테고리 간 차이에 기인",
    (1, "between −0.679 vs within −0.120 (카테고리 내부에서 약화)"),
    "분석 명세에 따라 방향이 뒤집힘(cluster-robust 회귀 +)",
    (1, "→ 단일 gap 지표만으로 시각 기여를 설명하기엔 한계"),
], left=7.2, top=1.9, width=5.7, size=16)

# S12 — 논의·함의
s = blank(); title_bar(s, "논의 · 실무적 함의", kicker="DISCUSSION")
bullets(s, [
    "‘낮은 gap 영상은 시각 임베딩 생략’ 식의 선별 색인 아이디어는 본 결과로 지지되지 않음.",
    (1, "동일가중 융합이 평균 성능을 못 올렸고, gap도 기여 영상을 안정적으로 식별하지 못함"),
    "단순 후기 융합으로 썸네일 유사도를 더하는 것만으로 일관된 개선을 기대하기 어렵다.",
    "탐색적으로는 시각을 낮은 가중으로 결합(α=0.7)하는 설정이 상대적으로 유망.",
    "한계: OCR 미지원 · 단일 플랫폼/언어 · 소표본 · Top-10 pooling bias · 카테고리/α 분석은 탐색적",
])

# S13 — 결론
s = blank(); title_bar(s, "결론", kicker="CONCLUSION")
bullets(s, [
    "① 썸네일 단독은 텍스트를 대체할 만큼 강한 검색 신호가 아니었다.",
    "② 동일가중(0.5:0.5) 융합은 평균 성능엔 중립 — 단, 시각을 낮은 가중(30%)으로 쓰면 탐색적으로 유망했다.",
    "③ 융합은 관련 영상의 순위 구성을 특히 ‘깊은 순위’에서 재배치했다.",
    "④ 융합 효과의 방향은 카테고리에 따라 상이했다.",
    "⑤ 단일 의미 간극(gap) 지표만으로 시각 기여를 설명하기엔 한계가 있었다.",
    "향후: 객체·장면·OCR 등 풍부한 시각 신호 × 검색어 특성의 상호작용 검증 · 다양한 환경에서 재현성 확인",
], top=1.5, size=16, height=4.05)
callout(s, "관점 전환: ‘평균 성능이 오르는가’가 아니라 — 시각 정보는 순위 구성과 조건을 바꾸며, 그 기여엔 단일 gap을 넘어선 신호가 필요하다.",
        top=5.85, height=1.05, size=17)

# S14 — 감사 & Q&A
s = blank()
band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(2.4), SW, Inches(2.4))
band.fill.solid(); band.fill.fore_color.rgb = ACCENT; band.line.fill.background(); band.shadow.inherit = False
tb = s.shapes.add_textbox(Inches(0.8), Inches(2.75), Inches(11.7), Inches(1.7)); tf = tb.text_frame; tf.word_wrap = True
p = tf.paragraphs[0]; _run(p, "감사합니다  ·  Q & A", 32, WHITE, bold=True)
p = tf.add_paragraph(); p.space_before = Pt(10)
_run(p, "김시황 · 전민철  |  (주)모비젠  |  author@example.com", 14, RGBColor(0xD6, 0xE4, 0xF0))
tb = s.shapes.add_textbox(Inches(0.8), Inches(5.15), Inches(11.7), Inches(1.4)); tf = tb.text_frame; tf.word_wrap = True
p = tf.paragraphs[0]
_run(p, "이 논문은 2024년도 정부(과학기술정보통신부)의 재원으로 정보통신기획평가원의 지원을 받아 수행된 연구임", 11, GRAY)
p = tf.add_paragraph(); _run(p, "(No.RS-2024-00340834, 써드파티 데이터의 활용성 증대를 위한 액티브 메타데이터 기반 능동형 데이터 확장 기술 개발)", 11, GRAY)

# ─────────────────────────── 발표 노트(구두 스크립트) ───────────────────────────
NOTES = [
    # S1 표지
    "안녕하세요. 모비젠의 김시황입니다. 오늘 ‘영상 검색에서 썸네일과 텍스트의 후기 융합에 따른 검색 순위 변화와 의미 간극 분석’이라는 제목으로 "
    "발표하겠습니다. 한국어 유튜브 영상 840편과 검색어 70개를 대상으로, 썸네일의 시각 정보가 텍스트 기반 영상 "
    "검색에 어떤 기여를 하는지를 사전등록 방식으로 분석했습니다. 이 연구의 핵심은, ‘썸네일이 평균 검색 성능을 "
    "올리는가’라는 익숙한 질문을 넘어서, 썸네일이 검색 결과의 순위 구성을 어떻게 바꾸는지, 그리고 그 기여를 하나의 "
    "지표로 설명할 수 있는지로 관점을 옮긴 데 있습니다. 결과적으로 시각 정보의 역할은 ‘평균 성능’이라는 단일 "
    "잣대만으로는 충분히 드러나지 않는다는 것을 보였습니다.",
    # S2 배경
    "먼저 배경입니다. 유튜브 같은 영상 검색은 제목·설명·태그 같은 텍스트를 주로 색인합니다. 정작 사용자가 클릭을 "
    "결정할 때 크게 작용하는 썸네일의 시각 정보는 검색 색인에 직접 쓰이는 경우가 드뭅니다. 시각 채널을 텍스트와 "
    "결합해 성능을 높이려는 시도는 있었지만, 그 개선이 모든 영상에서 균일한지 아니면 특정 조건에서만 나타나는지에 "
    "대한 분석은 부족했습니다. 시각 임베딩은 계산·저장 비용이 들기 때문에, ‘언제 도움이 되는가’를 아는 것은 실무 "
    "색인 설계에도 중요합니다.",
    # S3 RQ
    "그래서 두 가지 질문을 세웠습니다. RQ1은 ‘조건’에 대한 질문으로, 영상별로 썸네일과 제목의 의미 간극, 즉 gap이 "
    "클수록 융합에 의한 순위 개선이 커지는가입니다. RQ2는 ‘성능’ 질문으로, 썸네일과 텍스트의 후기 융합이 텍스트 "
    "단독보다 검색을 개선하는가입니다. 핵심 지표인 gap은 CLIP 공동 공간에서 썸네일과 제목 임베딩의 코사인 유사도를 "
    "1에서 뺀 값으로, 라벨링 없이 자동으로 계산됩니다. 다만 gap은 ‘표현이 얼마나 다른가’를 재는 것이지, ‘시각 정보가 "
    "유용한가’와 같은 뜻은 아니라는 점을 분명히 했습니다.",
    # S4 기여
    "기여는 세 가지입니다. 첫째, 라벨링이 필요 없는 gap 지표를 정의하고 자동 계산했습니다. 둘째, 융합의 검색 효과와 "
    "gap–순위변화 관계를 함께 검증하는 분석 프레임을 만들었습니다. 셋째, 한국어 유튜브를 대상으로 실증 평가했습니다. "
    "특히 이 연구는 가설·표집·지표·검정을 결과를 보기 전에 사전등록했고, 사전등록 분석과 사후 탐색 분석을 명확히 "
    "구분해 보고했습니다. 덕분에 어떤 결과가 확증이고 어떤 것이 탐색적 관찰인지 투명하게 전달할 수 있습니다.",
    # S5 파이프라인
    "연구 방법을 전체 그림으로 보겠습니다. 검색어와 코퍼스를 구성한 뒤, 세 개의 인코더로 임베딩을 만들고, 거기서 gap을 "
    "산출합니다. 그다음 텍스트·시각·융합 세 가지 검색을 수행하고, 융합 전후의 순위 변화인 Δrank를 계산해 분석합니다. "
    "한 가지 강조할 점은, 검색어와 제목이 각각 mpnet과 CLIP-text 두 인코더로 ‘이중 인코딩’된다는 점입니다.",
    # S6 정의
    "조금 더 구체적으로 보면 인코더는 셋입니다. 썸네일은 CLIP 이미지 인코더, gap과 시각 검색용 텍스트는 CLIP에 정렬된 "
    "다국어 인코더, 한국어 검색은 mpnet을 씁니다. gap은 mean-centering을 적용한 썸네일과 제목 임베딩의 코사인으로 "
    "정의합니다. 융합 점수는 텍스트 유사도와 시각 유사도를 정규화해 알파로 가중합하며, 알파 0.5 즉 동일가중을 미리 "
    "primary로 고정했습니다. 알파 전체 곡선은 나중에 탐색적으로만 봤습니다. 중요한 건, 텍스트 검색 점수와 gap이 서로 "
    "다른 공간에서 나오기 때문에 gap을 검색 점수에 섞어 쓰지 않았다는 점입니다.",
    # S7 실험 설계
    "실험 설계입니다. 14개 카테고리에서 카테고리당 60편씩 840편, 그리고 70개 검색어를 모았습니다. 검색어는 순환 논리를 "
    "피하려고 유튜브 공개 자동완성에서 생성했습니다. 정답지는 세 검색 방식의 Top-10을 합쳐 후보를 만들고, 세 명이 "
    "독립적으로 블라인드 라벨링했습니다. 평가자 일치도는 Fleiss 카파 0.486으로 보통 수준이었습니다. 관련 영상이 하나도 "
    "없는 7개 검색어는 제외해 63개 검색어로 평가했고, 지표는 MRR·NDCG·Recall과 Spearman 상관을 썼습니다.",
    # S8 결과1
    "이제 결과입니다. 먼저 검색 성능입니다. 표에서 보시듯 썸네일 단독은 텍스트보다 확실히 약했습니다. MRR 기준 0.43 대 "
    "0.69입니다. 그리고 동일가중 융합은 텍스트 대비 유의한 개선을 주지 못했습니다. MRR 변화가 마이너스 0.016, p값이 "
    "0.76으로 통계적으로 차이가 없습니다. 효과크기도 거의 0에 가깝습니다. 다만 이 표본은 0.11 정도의 개선이면 탐지할 "
    "수 있는 규모였기 때문에, ‘적어도 이 정도 개선은 없었다’고 해석할 수 있습니다.",
    # S9 결과2
    "그런데 사전등록 밖에서 알파를 탐색적으로 전부 비교해봤더니, 흥미롭게도 세 지표 모두 알파 0.7, 즉 텍스트 70퍼센트 "
    "시각 30퍼센트에서 가장 높았습니다. 이때는 텍스트 단독보다도, 동일가중보다도 높았습니다. 즉 앞 슬라이드의 결론은 "
    "‘융합이 무조건 안 된다’가 아니라 ‘동일가중에서만 중립이었다’는 것이고, 시각을 낮은 가중으로 섞으면 방향이 달라질 "
    "여지가 보입니다. 다만 이건 결과를 본 뒤에 고른 사후 분석이고 다중비교를 통제하지 않았기 때문에, 확증이 아니라 "
    "후속 연구에서 검증할 가설로만 제시합니다.",
    # S10 결과3
    "다음은 이 연구에서 가장 흥미로운 관찰입니다. 융합이 평균 성능은 못 올렸지만, 관련 영상들의 순위 구성 자체는 "
    "바꿨습니다. 표를 보시면 원래 상위 10위 안에 있던 관련 영상은 오히려 약간 내려갔지만, 11위 이후 깊은 순위에 있던 "
    "관련 영상들은 대부분 크게 올라갔습니다. 51위 이후는 100퍼센트 상승입니다. 즉 융합의 효과는 상위 노출을 개선하는 게 "
    "아니라 깊은 순위를 재배치하는 쪽으로 나타났습니다. recall 지향 검색이나 재순위 단계에서 쓸 여지가 있다는 뜻입니다.",
    # S11 결과4
    "그럼 RQ1, gap이 이 순위 변화를 설명하느냐. 답은 ‘아니오’였습니다. 사전등록한 centered gap과 순위 변화의 상관은 "
    "마이너스 0.05, p값 0.42로 유의하지 않았습니다. raw gap에서는 약한 음의 상관이 있었지만, 이건 카테고리 간 차이 "
    "때문이었고 카테고리 내부에서는 약해졌습니다. 게다가 분석 방법을 바꾸면 부호가 뒤집히기까지 했습니다. 결국 하나의 "
    "gap 값만으로 시각 정보의 기여를 설명하기엔 한계가 있었습니다.",
    # S12 논의
    "논의입니다. 당초에는 ‘gap이 낮은 영상은 시각 임베딩을 생략하자’는 선별 색인을 구상했는데, 이번 결과로는 지지되지 "
    "않았습니다. 단순히 후기 융합으로 썸네일 유사도를 더하는 것만으로는 일관된 개선을 기대하기 어렵습니다. 다만 "
    "탐색적으로는 시각을 낮은 가중으로 결합하는 설정이 상대적으로 유망해 보입니다. 한계로는 OCR 미지원, 단일 플랫폼과 "
    "언어, 작은 표본, 그리고 Top-10 pooling에 따른 편향 등이 있습니다.",
    # S13 결론
    "정리하겠습니다. 첫째, 썸네일 단독은 텍스트를 대체할 만큼 강한 신호가 아니었습니다. 둘째, 동일가중 융합은 평균 "
    "성능을 개선하지 못했습니다. 셋째, 그러나 융합은 깊은 순위의 관련 영상을 재배치했습니다. 넷째, 그 효과의 방향은 "
    "카테고리마다 달랐습니다. 다섯째, 단일 gap 지표만으로는 시각 기여를 설명하기 어려웠습니다. 요컨대 이 연구는 "
    "‘썸네일이 검색에 쓸모없다’는 이야기가 아니라, 시각 정보의 기여를 평균 성능이 아니라 ‘순위 구성’과 ‘조건’의 "
    "관점에서 봐야 하고, 그 조건을 포착하려면 단일 gap을 넘어선 더 풍부한 신호가 필요하다는 것을 보인 연구입니다. "
    "앞으로는 객체·장면·OCR 같은 시각 특성과 검색어 특성의 상호작용을 보고, 다양한 환경에서 재현성도 확인할 필요가 "
    "있습니다.",
    # S14 Q&A
    "이상으로 발표를 마치겠습니다. 본 연구는 IITP 과제 지원으로 수행되었습니다. 경청해 주셔서 감사합니다. 질문 "
    "받겠습니다.",
]
for _slide, _note in zip(prs.slides, NOTES):
    _slide.notes_slide.notes_text_frame.text = _note

prs.save(str(OUT))
print(f"생성: {OUT}  (슬라이드 {len(prs.slides._sldIdLst)}장)")
