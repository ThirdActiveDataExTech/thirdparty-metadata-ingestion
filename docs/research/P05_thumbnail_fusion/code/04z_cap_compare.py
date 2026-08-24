"""P05 진단 — MAX_PER_CATEGORY 50 vs 100 비교 (동결본 미수정).

04_gen_jamo.py의 수집·canon·cross-drop 로직을 그대로 쓰되:
  1) uncapped로 fresh 수집(한 번의 fetch)
  2) 같은 raw에서 cap=50 / cap=100 슬라이스 → 캡 효과만 격리(시간 변동 confound 배제)
  3) 카테고리별 (50,100] 구간에 새로 들어오는 쿼리, 특히 게임 리포트
  4) 참고로 fresh cap50 vs 동결본(query_candidates_jamo.json) 차이(=시간 변동)도 출력

출력: data/cap_compare.json (진단 전용, frozen 파일 안 건드림)
실행: PYTHONPATH=. python docs/research/P05_thumbnail_fusion/code/04z_cap_compare.py
"""

import importlib.util
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

CODE = Path(__file__).resolve().parent
DATA = CODE.parent / "data"
JAMO = ["ㄱ", "ㄴ", "ㄷ", "ㄹ", "ㅁ", "ㅂ", "ㅅ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]


def _load(f, n):
    s = importlib.util.spec_from_file_location(n, CODE / f)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m


gen = _load("04_gen_queries.py", "gen04")


def collect_assigned():
    """04_gen_jamo main()의 1)~2) 단계 재현하되 cap 적용 전까지."""
    trig = json.loads((DATA / "query_triggers.json").read_text(encoding="utf-8"))["categories"]
    raw = []
    for cid, e in trig.items():
        for t0 in e["triggers"]:
            for t in [t0] + [f"{t0} {j}" for j in JAMO]:
                for sug in gen.fetch_suggest(t):
                    if len(sug.replace(" ", "")) >= gen.MIN_LEN:
                        raw.append({"query": sug, "category": cid, "trigger": t0})
                time.sleep(0.12)
        print(f"  수집 {e['name']:<10} 누적 raw {len(raw)}")
    groups = defaultdict(list)
    for r in raw:
        groups[gen._canon(r["query"])].append(r)
    assigned = defaultdict(list)  # 삽입순 = jamo sweep 순 (frozen과 동일 로직)
    for canon, es in groups.items():
        cats = sorted(set(x["category"] for x in es))
        rep = min((x["query"] for x in es), key=len)
        if len(cats) == 1:
            assigned[cats[0]].append(rep)
    return trig, assigned


def main():
    trig, assigned = collect_assigned()
    frozen = json.loads((DATA / "query_candidates_jamo.json").read_text(encoding="utf-8"))["categories"]

    report = {"_meta": {"purpose": "cap 50 vs 100 진단", "note": "동일 fresh fetch에서 슬라이스=캡효과 격리"},
              "categories": {}}
    print(f"\n  {'category':<12} {'uncapped':>8} {'@50':>4} {'@100':>5} {'new(50,100]':>11}")
    for cid, e in trig.items():
        full = assigned.get(cid, [])
        c50, c100 = full[:50], full[:100]
        new = c100[50:]  # 50~100 구간 신규
        # 동결본 대비 시간변동: fresh@50에는 있는데 frozen엔 없는 것 / 그 반대
        frz = frozen.get(cid, {}).get("candidates", [])
        drift_added = [q for q in c50 if q not in set(frz)]
        drift_lost = [q for q in frz if q not in set(c50)]
        report["categories"][cid] = {
            "name": e["name"], "n_uncapped": len(full),
            "at50": c50, "at100": c100, "new_50_100": new,
            "fresh_vs_frozen_added": drift_added, "fresh_vs_frozen_lost": drift_lost,
        }
        print(f"  {e['name']:<12} {len(full):>8} {len(c50):>4} {len(c100):>5} {len(new):>11}")

    (DATA / "cap_compare.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    g = report["categories"].get("20", {})
    print("\n=== 게임: 캡 상향 시 새로 들어오는 후보 (50<pos<=100) ===")
    for q in g.get("new_50_100", []):
        print("  +", q)
    print(f"\n게임 uncapped 총 {g.get('n_uncapped')}개 (cap50이면 {50 if g.get('n_uncapped',0)>=50 else g.get('n_uncapped')}개까지만 사용)")
    print("저장: data/cap_compare.json")


if __name__ == "__main__":
    main()
