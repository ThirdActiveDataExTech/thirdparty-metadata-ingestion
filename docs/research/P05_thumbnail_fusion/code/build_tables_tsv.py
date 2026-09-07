"""P05 — paper_KIICE_ko.md의 표(표 1~5)를 HWP "문자열을 표로"용 TSV로 추출.

목적: 각 표를 탭 구분 텍스트로 뽑아, HWP에서
      (1) 해당 표 블록의 탭 줄만 선택 → (2) 표 → 문자열을 표로 → 구분자 '탭' →
      (3) 표 자동 생성. 특수문자(−, ×, –, α, Δ, ≥ 등)는 md 원문 그대로 보존.

마크다운 잔재 정리: **굵게**·`백틱`·[results/...] 마커 제거(굵게는 TSV로 표현 불가 →
생성 후 HWP에서 수동 재지정; 대상은 헤더 안내에 명시).

실행(저장소 루트):
  PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/build_tables_tsv.py
"""
import re
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent
SRC = DIR / "paper_KIICE_ko.md"
OUT = DIR / "표_TSV_붙여넣기용.txt"

BAR = "═" * 72
HEADER = f"""{BAR}
 KIICE 제출용 — 표 TSV(탭 구분)  ※ HWP "문자열을 표로"용
 원본: paper_KIICE_ko.md  (자동 생성 — 직접 수정 금지, code/build_tables_tsv.py 재실행)
{BAR}

■ 사용법
 1) 아래에서 한 표의 '탭 줄'만 드래그로 선택(캡션 '■' 줄은 제외).
 2) HWP에 텍스트로 붙여넣기(골라 붙이기 → 텍스트만, ⌘⌥V).
 3) 붙인 범위 선택 → 표 → 문자열을 표로 → 구분: '탭' → 확인.
 4) 캡션(■ 표 N. …)은 표 위에 따로 입력, "표 N."만 굵게.

■ 굵게가 필요한 곳(TSV는 굵게 전달 불가 → 표 생성 후 수동 지정)
 · 표 1: 셀 "CLIP 이미지와 같은 공간에서 …" 중 '같은 공간' 굵게
 · 모든 표: 헤더(첫 줄) 굵게·가운데 정렬 권장

■ 정렬 권장
 · 숫자 열 = 가운데, 맨 왼쪽(라벨) 열 = 왼쪽, 헤더 = 가운데·굵게
{BAR}
"""


def clean(cell: str) -> str:
    cell = cell.replace("**", "").replace("`", "")
    cell = re.sub(r"\s*\[results/[^\]]+\]", "", cell)
    return cell.strip()


def main():
    lines = SRC.read_text(encoding="utf-8").split("\n")
    blocks, i = [], 0
    caption = None
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^\*\*(표\s*\d+\..*?)\*\*(.*)$", ln.strip())
        if m:
            cap = clean(m.group(1) + m.group(2))
            caption = re.sub(r"\s{2,}", " ", cap).strip()
            i += 1
            continue
        if ln.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                row = lines[i].strip()
                if re.match(r"^\|[\s:|-]+\|$", row):  # |---| 구분행
                    i += 1
                    continue
                cells = [clean(c) for c in row.strip("|").split("|")]
                rows.append("\t".join(cells))
                i += 1
            if rows:
                blocks.append((caption, rows))
                caption = None
            continue
        i += 1

    out = [HEADER]
    for cap, rows in blocks:
        out.append(f"■ {cap}" if cap else "■ (표)")
        out.extend(rows)
        out.append("")  # 표 사이 빈 줄
    OUT.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    print(f"생성: {OUT}  (표 {len(blocks)}개)")


if __name__ == "__main__":
    main()
