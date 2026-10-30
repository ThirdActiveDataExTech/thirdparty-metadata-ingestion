"""공개 저장소(thirdparty-opensw-showcase)와 코드가 갈라졌는지 점검한다.

**운영 방침.** 이 저장소가 정본이고, 공개 저장소는 **갱신 시점의 스냅샷**이다.
상시 동기화 대상이 아니므로 평소 차이가 나는 것은 정상이다. 이 스크립트는
**공개본을 갱신하기 직전에만** 돌려서, 그동안 한쪽에만 들어간 수정이 없는지
확인하는 용도다.

**왜 필요한가.** 두 곳을 오가며 고치다 보면 한쪽에만 반영된 수정이 쌓인다.
2026-10-30에 실제로 세 건이 어긋나 있었고, 그중 하나는 **API 키 마스킹이
공개본에만 있어 이 저장소에서는 쿼터 초과 시 키가 터미널에 찍히는 상태**였다.

점검 방식은 두 가지다.

  1. 공통 파일의 내용 비교 — 공개본에만 있는 익명화 치환(협력기관 등)은
     무시하고, 그 밖의 차이를 보고한다
  2. 핵심 함수·패턴의 존재 여부 — 이름만 확인하므로 익명화 영향을 받지 않는다

실행 방법 (공개본 갱신 직전):
    python scripts/check_showcase_sync.py
    python scripts/check_showcase_sync.py --showcase ../thirdparty-opensw-showcase

차이가 있으면 종료 코드 1을 돌려준다. CI에 거는 것은 권하지 않는다 —
공개본은 상시 일치해야 하는 대상이 아니다.
"""

import argparse
import pathlib
import re
import sys

DEFAULT_SHOWCASE = "../thirdparty-opensw-showcase"

# 공개본에서만 치환되는 표현. 비교 전에 양쪽을 같은 형태로 정규화한다.
ANONYMIZED = [
    (re.compile(r"와이즈넛"), "협력기관"),
    (re.compile(r"케이웨어"), "포털"),
    (re.compile(r"sql/_received/\w+/"), "협력기관 수신본 "),
]

# 한쪽에만 들어가기 쉬운 수정들. (설명, 찾을 문자열, 찾을 경로)
MARKERS = [
    ("수집기 비본문 제거",      "_strip_non_content", "src/collectors"),
    ("API 키 마스킹",           "mask_secrets",       "src/common"),
    ("청크 노이즈 제거",        "_is_noise",          "src/embedding"),
    ("짧은 문서 보존",          "_keep_short",        "src/embedding"),
    ("매체 고정 문구 패턴",     "청소년",              "src/embedding"),
    ("파이프라인 분류 import",  "import category",    "src/pipelines"),
]

# 공개본에 의도적으로 없는 것들 — 비교 대상에서 뺀다.
EXCLUDE = ("__pycache__", "docs/infrastructure", "k8s", "sql/_received",
           "scripts/scenarios", "docs/promo", "research")


def _norm(text: str) -> str:
    for pat, repl in ANONYMIZED:
        text = pat.sub(repl, text)
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--showcase", default=DEFAULT_SHOWCASE, help=f"공개 저장소 경로 (기본 {DEFAULT_SHOWCASE})")
    args = ap.parse_args()

    here = pathlib.Path(__file__).resolve().parent.parent
    there = (here / args.showcase).resolve()
    if not (there / "src").is_dir():
        print(f"공개 저장소를 찾을 수 없습니다: {there}")
        return 2

    problems = 0

    print("\n핵심 수정 반영 여부")
    print("─" * 62)
    for label, needle, sub in MARKERS:
        a = any(needle in p.read_text(errors="ignore") for p in (here / sub).rglob("*.py"))
        b = any(needle in p.read_text(errors="ignore") for p in (there / sub).rglob("*.py"))
        mark = "OK" if a == b else ("공개본 누락" if a else "이 저장소 누락")
        if a != b:
            problems += 1
        print(f"  {label:<24}{'있음' if a else '없음':<6}{'있음' if b else '없음':<6}{mark}")

    print("\n공통 파일 내용 차이 (익명화 치환은 무시)")
    print("─" * 62)
    diffs = []
    for p in sorted((here / "src").rglob("*.py")):
        rel = p.relative_to(here)
        if any(e in str(rel) for e in EXCLUDE):
            continue
        q = there / rel
        if not q.exists():
            continue
        if _norm(p.read_text(errors="ignore")) != _norm(q.read_text(errors="ignore")):
            diffs.append(str(rel))
    if diffs:
        problems += len(diffs)
        for d in diffs:
            print(f"  다름  {d}")
    else:
        print("  차이 없음")

    print()
    if problems:
        print(f"불일치 {problems}건 — 한쪽에만 반영된 수정이 있는지 확인하세요.")
        return 1
    print("두 저장소가 일치합니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
