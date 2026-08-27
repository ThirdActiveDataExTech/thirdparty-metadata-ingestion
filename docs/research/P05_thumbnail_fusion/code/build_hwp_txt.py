"""P05 — paper_KIICE_ko.md → HWP(한글) 붙여넣기용 txt 자동 생성.

목적: 논문 본문(.md)이 바뀔 때마다 재실행하면 붙여넣기용 txt가 항상 최신과 동기화됨.
변환 규칙(붙여넣기 친화):
  - HTML 주석(<!-- -->)·상단 메타 주석 제거
  - 헤더(#, ##, ###) → 기호 제거하고 제목 텍스트만
  - 굵게(**...**)·인라인코드(`...`) 마커 제거
  - 그림 마커 [results/...] 제거(캡션 텍스트만 남김)
  - 펜스 코드블록(```): 파이프라인 도식·수식은 내용만 남기고 ``` 제거
  - $$...$$ (식 1) → 붙여넣기용 readable 식으로 치환
  - 마크다운 표: 구분행(|---|) 제거, 셀은 ' | '로 유지(HWP에서 표로 재작성)
머리말(스타일 가이드·체크리스트)은 고정 프리앰블로 유지.

실행: 저장소 루트에서
  PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/build_hwp_txt.py
"""
import re
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent
SRC = DIR / "paper_KIICE_ko.md"
OUT = DIR / "paper_KIICE_hwp_붙여넣기용.txt"

BAR = "═" * 72

PREAMBLE = f"""{BAR}
 KIICE 제출용 — 한글(HWP) 붙여넣기용 원고
 원본: paper_KIICE_ko.md  (이 파일은 code/build_hwp_txt.py로 자동 생성 — 직접 수정 금지)
 갱신: 논문 수정 후 위 스크립트를 재실행하면 이 파일이 최신 상태로 재생성됨.
{BAR}

■ 사용 방법
 1) 한글에서 KIICE 양식(.hwp)을 연다.
 2) 아래 본문을 순서대로 "골라 붙이기 → 텍스트만"으로 붙여넣는다(양식 스타일 상속).
 3) 아래 수작업 체크리스트(2단·수식·표·그림·참고문헌)를 처리한다.

■ 전역 서식(양식 규정 요약)
 - 용지 A4, 여백 상·하·좌·우 30mm, 페이지번호 없음.
 - 제목~키워드: 1단.  서론(Ⅰ)부터: 2단.
 - 본문 국문=함초롱바탕 9pt, 영문=Times New Roman 9pt, 들여쓰기 2, 줄간격 130%.
 - 장 제목(Ⅰ,Ⅱ…): 국문 휴먼고딕 / 영문 Arial 10pt, 중간 정렬.
 - 표·그림 캡션: 왼쪽 정렬, 국문 돋움 9pt / 영문 Arial 9pt.
 - 참고문헌: 영문 표기, Times New Roman 9pt, 인용(등장) 순서.

■ 수작업 체크리스트(스크립트가 대신 못 하는 것)
 [ ] 서론(Ⅰ)부터 2단 설정
 [ ] 식 (1)(2)(3)을 한글 수식편집기로 입력(본문 〔식〕 블록 참조)
 [ ] 그림 1(파이프라인)·그림 2(α 곡선)·그림 3(gap 산점도) 작도/삽입
 [ ] 표 1~5 테두리·정렬, 캡션 폰트(본문 〔표〕 블록의 텍스트를 표로 재작성)
 [ ] 참고문헌 TNR 9pt, 저자 * (교신) 표시·E-mail
 [ ] 3p 이상이면 머리말에 논문 제목

{BAR}
 ↓↓↓ 본문 (paper_KIICE_ko.md 파생) ↓↓↓
{BAR}
"""

# 식 (1): $$...$$ 블록을 붙여넣기용 readable 식으로 치환
EQ1 = "〔식 (1) — 수식편집기로 입력〕\ngap_i = 1 − cos( center(v_img,i) , center(g_txt,i) )        … (1)"


def strip_inline(s: str) -> str:
    # 전역 정리에서 이미 굵게/이탤릭/코드/그림마커를 처리하므로 여기선 잔여 방어만
    s = s.replace("**", "").replace("`", "")
    s = re.sub(r"\s*\[results/[^\]]+\]", "", s)
    return s


def convert(md: str) -> str:
    # 1) HTML 주석 제거(멀티라인)
    md = re.sub(r"<!--.*?-->", "", md, flags=re.DOTALL)
    # 2) 전역 인라인 정리(붙여넣기 친화) — 구조 처리 전에 수행
    md = md.replace("<sup>*</sup>", "＊")          # 교신저자 표시 보호(이탤릭 제거에서 제외)
    md = re.sub(r"</?sup>", "", md)                # 잔여 <sup> 태그 제거(내용 유지)
    md = re.sub(r"\s*\[results/[^\]]+\]", "", md)  # 그림 마커 제거
    md = md.replace("**", "")                       # 굵게 마커
    md = re.sub(r"\*([^*]+?)\*", r"\1", md)         # 이탤릭 *...*(멀티라인 참고문헌 포함) 제거
    md = md.replace("＊", "*")                       # 교신저자 표시 복원
    md = md.replace("`", "")                        # 인라인 코드 마커
    lines = md.split("\n")
    out, i = [], 0
    eq_no = {"fusion": False}
    while i < len(lines):
        ln = lines[i]

        # $$ 수식 블록 → 식 (1)
        if ln.strip().startswith("$$"):
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("$$"):
                j += 1
            out.append(EQ1)
            i = j + 1
            continue

        # 펜스 코드블록
        if ln.strip().startswith("```"):
            j = i + 1
            block = []
            while j < len(lines) and not lines[j].strip().startswith("```"):
                block.append(lines[j]); j += 1
            body = "\n".join(block)
            # Late Fusion score 식 포함 블록 → 식 (2) 주석 부여
            if "score = α" in body:
                body = body.replace(
                    "Late Fusion : score = α·norm(sim_text) + (1−α)·norm(sim_visual)",
                    "〔식 (2) — 수식편집기로 입력〕\nscore = α·norm(sim_text) + (1−α)·norm(sim_visual)        … (2)")
            if "Δrank(v,q) = rank_text" in body:
                body = body.rstrip() + "        … (3)"
                out.append("〔식 (3) — 수식편집기로 입력〕")
            out.append(body)
            i = j + 1
            continue

        # 마크다운 표
        if ln.lstrip().startswith("|"):
            # 표 블록 수집
            tbl = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                row = lines[i].strip()
                if re.match(r"^\|[\s:|-]+\|$", row):  # 구분행 |---|
                    i += 1; continue
                cells = [c.strip() for c in row.strip("|").split("|")]
                tbl.append(" | ".join(strip_inline(c) for c in cells))
                i += 1
            out.append("〔표 — HWP에서 표로 재작성〕")
            out.extend(tbl)
            continue

        # 헤더
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            out.append(strip_inline(m.group(2)).strip())
            i += 1
            continue

        # 구분선 --- → 빈 줄
        if ln.strip() == "---":
            out.append("")
            i += 1
            continue

        # 리스트 마커 - → ·
        m = re.match(r"^(\s*)-\s+(.*)$", ln)
        if m:
            out.append(f"{m.group(1)}· {strip_inline(m.group(2))}")
            i += 1
            continue

        out.append(strip_inline(ln))
        i += 1

    text = "\n".join(out)
    # 3개 이상 연속 빈 줄 → 2개로
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def main():
    md = SRC.read_text(encoding="utf-8")
    body = convert(md)
    OUT.write_text(PREAMBLE + "\n" + body + "\n", encoding="utf-8")
    n = len(body.split("\n"))
    print(f"생성: {OUT}  (본문 {n}줄)")


if __name__ == "__main__":
    main()
