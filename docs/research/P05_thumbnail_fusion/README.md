# P05 — 썸네일-텍스트 융합 임베딩 검색 실험 워크스페이스

논문 초안: [../paper_draft_P05_thumbnail_fusion.md](../paper_draft_P05_thumbnail_fusion.md)

이 폴더는 P05 논문의 **실험 코드·데이터·결과**를 재현 가능하게 보관한다. 논문의
`[DATA: ...]` 자리는 여기서 나온 결과로 채운다.

## 디렉토리 구조

```
P05_thumbnail_fusion/
├── README.md          # 이 파일 — 재현 가이드
├── references.md      # 레퍼런스 전체 기록 (인용 시 여기 먼저 추가)
├── code/              # 실험 스크립트 (번호 순서대로 실행)
├── data/              # corpus manifest, queries, qrels (임베딩 바이너리는 git 제외)
└── results/           # 표·그림·통계 출력물
```

## 실행 순서 (파이프라인)

> 아직 코드 미작성 — 아래는 계획된 순서. 각 스크립트는 앞 단계의 산출물만 입력으로
> 받고 결과를 `data/` 또는 `results/`에 남겨, 중간부터 재실행 가능하게 만든다.

| 순서 | 스크립트 | 입력 | 출력 |
|---|---|---|---|
| 01 | `code/01_build_corpus.py` | 채널 목록 | `data/corpus.jsonl` (video_id, title, description, thumbnail_url, channel) |
| 02 | `code/02_extract_embeddings.py` | corpus.jsonl | `data/embeddings/` (v_img, v_txt, g_txt) |
| 03 | `code/03_compute_gap.py` | embeddings | `data/gap.tsv` |
| 04 | `code/04_run_retrieval.py` | embeddings, queries, qrels | `results/retrieval_metrics.json` |
| 05 | `code/05_analyze.py` | 위 결과 전부 | `results/` (표·그림·통계) |

## 환경

- Python 3.9 (repo `.venv`)
- 주요 의존: `sentence-transformers`(clip-ViT-B-32 / clip-ViT-B-32-multilingual-v1 포함),
  `torch`, `Pillow`, `scikit-learn`, `scipy`, `numpy` — 모두 repo에 이미 설치됨
- 실행: 저장소 루트에서 `PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/0X_*.py`

## 재현성 원칙

- **데이터 매니페스트(corpus/queries/qrels)는 git에 커밋** — 코퍼스 구성이 고정돼야 재현 가능
- **임베딩 바이너리·다운로드 썸네일은 git 제외**(`.gitignore`) — 용량 크고 코드로 재생성 가능
- **모든 난수 시드 고정**, 사용한 모델명·버전을 결과 파일에 함께 기록
- 인용하는 모든 문헌은 `references.md`에 서지정보 + 확인 경로(URL/DOI)까지 기록

## 상태

- 2026-08-03: 워크스페이스 생성. 코퍼스 수집(01) 착수 예정 — 주제 다양성 확보를 위해
  여러 한국어 채널에서 표집(현재 운영 DB는 반도체 채널뿐이라 별도 수집 필요).
