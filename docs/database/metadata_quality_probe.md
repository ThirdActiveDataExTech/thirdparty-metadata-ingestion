# 메타데이터 품질 실측 (P0-5)

> **Last Updated:** 2026-11-02
> **목적:** B1(특징 추출)·B2(관계 분석)의 **최소선 구성을 데이터로 결정**한다.
> [development/04_Implementation_Methods.md §1.5](../development/04_Implementation_Methods.md)가
> "결과에 따라 최소선 구성이 바뀐다"고 적어 둔 그 측정이다.
> 측정 대상: 데이터셋 25건 / 수집 아이템 8,273건 (2026-11-02 기준)

---

## 결론 먼저

| 질문 | 답 |
|---|---|
| B2 **키워드 자카드** 엣지가 가능한가 | 🟡 **성립하나 너무 성기다.** 300쌍 중 22쌍(7.3%)만 키워드를 공유 |
| B2 **시계열 공변동**이 가능한가 | 🔴 **발견형 3종은 불가.** 관측일이 **1일**뿐 |
| 왜 시계열이 없는가 | **수집이 돌고 있지 않다.** 18개 데이터셋이 예정일을 2~3일 넘겼다 |

---

## ① 키워드·설명 채움률

| source_type | 데이터셋 | 키워드 있음 | 평균 개수 | 최대 | 설명 평균 길이 |
|---|---|---|---|---|---|
| blog | 5 | 5 | 1.6 | 3 | 24자 |
| news | 5 | 5 | 1.6 | 3 | 26자 |
| persona_insight | 5 | 5 | 3.0 | 3 | 27자 |
| shopping_insight | 5 | 5 | 3.0 | 3 | 28자 |
| video | 5 | 5 | 3.2 | 4 | 36자 |

**채움률은 100%다. 문제는 양이다.**

- 키워드가 **평균 2~3개, 최대 4개**다. 자카드 계수가 `0 / 1/3 / 1/2 / 1` 같은 거친
  이산값만 나와 순위를 매길 해상도가 없다.
- `description`이 **평균 24~36자**다. 한 줄 제목 수준이라 텍스트 특징 추출의
  입력으로 쓸 수 없다.

### 실제 엣지 밀도

```
키워드를 1개 이상 공유하는 데이터셋 쌍 :  22쌍 / 가능한 300쌍  (7.3%)
2개 이상 데이터셋에 걸친 키워드        :  10종
   4건  패션 · 페르소나 · 검색트렌드
   3건  고객군
   2건  치질 · 식품 · 디지털가전 · HBM · 화장품 · 반도체
```

25노드 그래프에 엣지 22개. **고립 노드가 다수 나온다.**

### 처방 — B1이 B2보다 먼저여야 하는 이유가 데이터로 확인됐다

데이터셋 레벨 키워드는 사람이 등록 시 손으로 적은 2~3개가 전부다. 반면
**아이템 레벨에는 신호가 훨씬 많다** — `meta_video.tags`, 뉴스·블로그 본문,
그리고 지금은 아무도 안 쓰는 YouTube 자막(P0-2).

따라서 B2의 입력은 **등록 키워드가 아니라 B1이 아이템에서 집계한 특징**이어야 한다.
로드맵의 `B1 → B2` 의존 순서가 추측이 아니라 측정으로 뒷받침된다.

> 04_Implementation_Methods.md §1.5가 예고한 대로, **"고립 노드 = 메타데이터 품질
> 문제"라는 제시 자체가 과제 산출물**이 될 수 있다. 다만 그건 B1을 돌려 본 뒤에
> 할 말이다 — 지금 고립된 것은 "등록 키워드가 적어서"이지 "관계가 없어서"가 아니다.

---

## ② 관측 기간 겹침 (시계열 공변동)

| source_type | 데이터셋 | 관측일 수 | 기간 |
|---|---|---|---|
| video | 5 | **1일** | 2026-10-29 |
| news | 5 | **1일** | 2026-10-29 |
| blog | 5 | **1일** | 2026-10-29 |
| shopping_insight | 5 | 15~59일 | 2026-09-01 ~ 10-29 |
| persona_insight | 5 | 15~58일 | 2026-09-01 ~ 10-28 |

**발견형 3종(video·news·blog)은 관측일이 1일이라 시계열이 없다.** 상관도 공변동도
정의되지 않는다. 선언형 2종만 겹치는 구간(2026-10-14 ~ 10-28, 15일 공통)이 있으나
`n=15`로는 상관계수의 신뢰구간이 거의 전 구간을 덮는다.

### 왜 1일인가 — 수집이 멈춰 있다

`active_meta_*`는 수집할 때마다 스냅샷을 쌓는 구조인데, **수집이 돌지 않는다.**

```
data_registry 기준 (2026-11-02)
  18개 데이터셋  next_collect_at 2026-10-30~10-31  →  2~3일 경과
   7개 데이터셋  next_collect_at 2026-11-05 이후   →  아직 도래 안 함
```

발견형 3종의 시계열이 10-29 하루뿐인 것은
[migration_2026_10_29_vec_chunking.sql](../../sql/migration_2026_10_29_vec_chunking.sql)에서
샘플 데이터를 비우고 재수집한 날이기 때문이고, **그 이후로 한 번도 안 돌았다.**
`k8s/`에 CronJob이 없고(디렉터리 자체가 없다) Airflow도 미도입이라, 지금은
사람이 `python -m src.main run <dataset_id>`를 직접 쳐야만 수집된다.

### 처방 — 스케줄러를 앞당겨야 한다

로드맵은 C4(동적 변화 파이프라인)를 **3단계**에 두고 있다. 의존성상으로는 맞다.
그러나 **시계열은 벽시계 시간으로만 쌓인다.** 지금 돌려놓지 않으면 B2 시계열
공변동은 몇 달 뒤에도 같은 자리에 있다.

C4 최소선은 Airflow가 필요 없다 —
`scripts/scheduler_tick.py`(due 조회 → 수집 호출 → `next_collect_at` 갱신) +
K8s CronJob 하나다. **의존성 순서와 무관하게 지금 착수할 값어치가 있는 유일한
3단계 항목이다.**

---

## 재현

```bash
PYTHONPATH=. python - <<'EOF'
from src.database.db import get_conn
cur = get_conn().cursor()
# ① 키워드 채움률
cur.execute("""SELECT source_type, count(*),
  count(*) FILTER (WHERE keywords IS NOT NULL AND jsonb_array_length(keywords)>0),
  ROUND(AVG(COALESCE(jsonb_array_length(keywords),0))::numeric,1),
  ROUND(AVG(COALESCE(length(description),0))::numeric)
  FROM dcat_dataset GROUP BY source_type ORDER BY 1""")
print(cur.fetchall())
# ② 수집 지연
cur.execute("""SELECT count(*) FROM data_registry
               WHERE next_collect_at < now()""")
print("예정일 경과:", cur.fetchone()[0])
EOF
```
