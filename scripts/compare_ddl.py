"""우리 정본 DDL(sql/*.sql) ↔ 와이즈넛 수신 DDL 대조 (파일만 읽는다, DB 접속 없음).

와이즈넛이 새 DDL을 보내면 sql/_received/<벤더>_<날짜>/ 에 원본을 넣고 이 스크립트를 돌린다.
컬럼 정의·제약·인덱스·뷰·시드를 비교해 통합이 필요한 지점을 뽑는다.

사용법: python scripts/compare_ddl.py [수신폴더]
        기본값은 sql/_received/ 하위에서 가장 최근 폴더
"""

import glob
import io
import os
import re
import sys


# 의도적으로 다르게 두기로 한 항목 — 사유를 함께 적는다.
# 여기에 없는 차이만 보고한다. 합의가 바뀌면 이 표를 먼저 고친다.
ACCEPTED = {
    ("dcat_dataset", "subjects"): "비정형 전용 — 수집 대상(채널·검색어·카테고리)",
    ("dcat_dataset", "owner_id"): "비정형 전용 — 등록 사용자",
    ("dcat_dataset", "version"): "비정형 전용 — 수집 방식 버전",
    ("dcat_dataset", "description"): "NOT NULL 유지 — SEMANTICALLY_RELATED 판정 근거라 비면 관계가 안 나온다",
    ("dcat_dataset", "publisher"): "NOT NULL 유지 — 비정형은 source와 같은 값이 항상 있다",
    ("dcat_dataset", "source_type"): "기본값 미설정 — 비정형이 실수로 structured_file이 되면 라우팅이 어긋난다",
    ("dcat_dataset", "spatial"): "DEFAULT 'KR' 유지 — 비정형은 국내 수집이 기본",
    ("dcat_dataset", "item_count"): "BIGINT 유지 — data_registry.item_count(BIGINT)의 미러라 타입을 맞춘다",
    ("dcat_dataset", "visibility"): "DEFAULT 'ORG' — 2026-10-28 합의. 와이즈넛 DDL 수정 요청 중",
    # FK·컬럼을 테이블 정의에 인라인으로 두느냐 별도 파일에서 ALTER로 거느냐의 차이.
    # 최종 DB 상태는 같다.
    ("active_meta_dataset", "metric_code"): "FK 위치 차이 — 그들은 DDL 4에서 건다",
    ("dcat_dataset_relation", "relation_type"): "FK 위치 차이 — 그들은 DDL 3에서 건다",
    ("dcat_dataset_relation", "relation_label"): "컬럼 추가 위치 차이 — 그들은 DDL 3에서 ALTER",
}


def strip_comments(t):
    return re.sub(r"--[^\n]*", "", t)


def norm(d):
    d = re.sub(r"::\w+", "", d)
    d = re.sub(r"\s+", " ", d).strip().upper().replace("( ", "(").replace(" )", ")")
    d = re.sub(r"REFERENCES (\w+) ?\(", r"REFERENCES \1(", d)
    d = re.sub(r"NUMERIC\((\d+), ?(\d+)\)", r"NUMERIC(\1,\2)", d)
    parts = re.findall(r"ON (?:DELETE|UPDATE) \w+", d)
    for p in parts:
        d = d.replace(p, "")
    return (re.sub(r"\s+", " ", d).strip() + " " + " ".join(sorted(parts))).strip()


def parse(text):
    """CREATE TABLE 블록 → {테이블: {컬럼: 정규화된 정의}}"""
    text = strip_comments(text)
    out = {}
    for m in re.finditer(r"CREATE TABLE (?:IF NOT EXISTS )?(\w+)\s*\((.*?)\n\s*\);", text, re.S | re.I):
        cols, depth, cur = {}, 0, ""
        for ch in m.group(2):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if ch == "," and depth == 0:
                _add(cols, cur)
                cur = ""
            else:
                cur += ch
        _add(cols, cur)
        out[m.group(1)] = cols
    return out


def _add(cols, frag):
    line = frag.strip()
    if not line or line.split()[0].upper() in (
            "CONSTRAINT", "UNIQUE", "PRIMARY", "FOREIGN", "CHECK"):
        return
    cols[line.split()[0]] = norm(" ".join(line.split()[1:]))


def load(files):
    tables, views = {}, set()
    for f in files:
        t = io.open(f, encoding="utf-8").read()
        tables.update(parse(t))
        views |= {m.group(1).lower()
                  for m in re.finditer(r"CREATE (?:OR REPLACE )?VIEW (\w+)", strip_comments(t), re.I)}
    return tables, views


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else None
    if not base:
        cands = sorted(glob.glob("sql/_received/*"))
        if not cands:
            print("sql/_received/ 에 수신 DDL이 없다")
            return 1
        base = cands[-1]
    ours, ov = load(glob.glob("sql/*.sql"))
    wn, wv = load(sorted(glob.glob(os.path.join(base, "*.sql"))))

    print(f"대조 대상: {base}\n우리 {len(ours)}개 테이블 / 수신 {len(wn)}개 / 공통 {len(set(ours) & set(wn))}\n")
    diffs = 0
    for t in sorted(set(ours) & set(wn)):
        o, w = ours[t], wn[t]
        only_o = [c for c in o if c not in w and (t, c) not in ACCEPTED]
        only_w = [c for c in w if c not in o and (t, c) not in ACCEPTED]
        chg = [(c, o[c], w[c]) for c in o
               if c in w and o[c] != w[c] and (t, c) not in ACCEPTED]
        if not (only_o or only_w or chg):
            print(f"✅ {t}")
            continue
        diffs += 1
        print(f"❗ {t}")
        for c in only_o:
            print(f"     우리만  {c}: {o[c]}")
        for c in only_w:
            print(f"     그들만  {c}: {w[c]}")
        for c, a, b in chg:
            print(f"     차이    {c}\n          우리 → {a}\n          그들 → {b}")

    missing_view = wv - ov
    if missing_view:
        diffs += 1
        print(f"\n❗ 수신 DDL에만 있는 뷰: {sorted(missing_view)}")
    print(f"\n차이 있는 테이블: {diffs}개")
    print(f"의도적 차이(허용 목록): {len(ACCEPTED)}건 — 사유는 compare_ddl.py의 ACCEPTED 참조")
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
