# P05 References

인용하는 모든 문헌을 여기 기록한다. 논문 본문에 넣기 전에 **반드시 여기 먼저 추가**하고,
서지정보 + 확인 경로(URL/DOI/arXiv ID) + 우리 논문에서 어떻게 쓰는지 한 줄 메모를 남긴다.

> ⚠️ novelty 주장(초안 §2.1)은 2026-07-08 검색 기준 — 제출 전 최신 arXiv/ACL
> Anthology/DBLP 재검색으로 최근 6개월 유사연구 재확인 필요. 재검색 결과도 여기 기록.

## 핵심 인용 (초안에서 이미 사용 중)

| # | 서지정보 | 확인 경로 | 우리 논문에서의 용도 |
|---|---|---|---|
| 1 | Radford et al. (2021). Learning Transferable Visual Models From Natural Language Supervision (CLIP). *ICML*. | arXiv:2103.00020 | 썸네일 이미지 인코더(ViT-B/32)의 기반 모델 |
| 2 | Hessel et al. (2021). CLIPScore: A Reference-free Evaluation Metric for Image Captioning. *EMNLP*. | arXiv:2104.08718 | gap 지표의 계산식 출처(용도는 재해석) |
| 3 | Fang et al. (2021). CLIP2Video: Mastering Video-Text Retrieval via Image CLIP. | arXiv:2106.11097 | 프레임 집계 방식 대비 썸네일 단일프레임의 위치 |
| 4 | Reimers & Gurevych (2019). Sentence-BERT. *EMNLP*. | arXiv:1908.10084 | 다국어 텍스트 임베딩(mpnet 계열) 근거 |
| 5 | Li et al. (2022). BLIP. *ICML*. | arXiv:2201.12086 | 이미지-텍스트 통합모델 관련연구 |
| 6 | Gao et al. (2022). M2HF: Multi-level Multi-modal Hybrid Fusion for Text-Video Retrieval. | arXiv:2208.07664 | 멀티레벨 융합 대비 late fusion 단순성 |
| 7 | ThumbnailTruth (2025). A Multi-Modal LLM Approach for Detecting Misleading YouTube Thumbnails. | arXiv:2509.04714 | ⚠️ 서지정보 미완 — 저자/베뉴 확인 필요. 가장 가까운 선행연구(클릭베이트 분류) |

## 사용 모델·도구 (방법 재현용 — 논문에 명시)

| 항목 | 정확한 식별자 | 비고 |
|---|---|---|
| 썸네일 이미지 인코더 | `sentence-transformers/clip-ViT-B-32` | 512-dim |
| gap용 정렬 텍스트 인코더 | `sentence-transformers/clip-ViT-B-32-multilingual-v1` | CLIP 이미지 공간 정렬(distillation), 512-dim |
| 검색용 텍스트 인코더 | `paraphrase-multilingual-mpnet-base-v2` | 768-dim → PCA 512 (운영 파이프라인과 동일) |

## 재검색 로그 (제출 전)

- [ ] "CLIPScore rank improvement retrieval" — ACL/SIGIR/CIKM 최근 프로시딩
- [ ] "image-text gap retrieval fusion" — arXiv 최근 6개월
- [ ] 결과 여기 기록
