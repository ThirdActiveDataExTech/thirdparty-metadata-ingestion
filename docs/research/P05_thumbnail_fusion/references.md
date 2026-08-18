# P05 References

인용하는 모든 문헌을 여기 기록한다. 논문 본문에 넣기 전에 **반드시 여기 먼저 추가**하고,
서지정보 + 확인 경로(URL/DOI/arXiv ID) + 우리 논문에서 어떻게 쓰는지 한 줄 메모를 남긴다.

> ⚠️ novelty 주장(초안 §2.1)은 2026-07-08 검색 기준 — 제출 전 최신 arXiv/ACL
> Anthology/DBLP 재검색으로 최근 6개월 유사연구 재확인 필요. 재검색 결과도 여기 기록.

## 핵심 인용 (번호 = 논문 최종본과 동일한 인용 순서; 상세 한국어 요약은 `references_summary_ko.md`)

| # | 서지정보 | 확인 경로 | 우리 논문에서의 용도 |
|---|---|---|---|
| 1 | Fang et al. (2021). CLIP2Video: Mastering Video-Text Retrieval via Image CLIP. | arXiv:2106.11097 | 프레임 집계 방식 대비 썸네일 단일프레임의 위치(§2.1) |
| 2 | Liu, Quan, Zhou, et al. (2026). M2HF: Multi-branch Multi-modal Hybrid Fusion for Text–Video Retrieval. *Computational Visual Media*, 12(2):449–471. | DOI:10.26599/CVM.2025.9450444 (프리프린트: arXiv:2208.07664, 'Multi-level') | 멀티모달 하이브리드 융합 대비 late fusion 단순성(§2.1). **정식 저널본 인용 확정**. 저자 = Shuo Liu 외(이전 'Gao' 오기 수정) |
| 3 | Radford et al. (2021). Learning Transferable Visual Models From Natural Language Supervision (CLIP). *ICML*. | arXiv:2103.00020 | 썸네일 이미지 인코더(ViT-B/32)의 기반 모델·CLIP 공동공간(§2.1) |
| 4 | Reimers & Gurevych (2019). Sentence-BERT. *EMNLP*. | arXiv:1908.10084 | 다국어 텍스트 임베딩(mpnet 계열) 근거(§2.1) |
| 5 | Hessel et al. (2021). CLIPScore: A Reference-free Evaluation Metric for Image Captioning. *EMNLP*. | arXiv:2104.08718 | gap 지표의 계산식 출처(용도는 재해석)(§2.2) |
| 6 | Li et al. (2022). BLIP. *ICML*. | arXiv:2201.12086 | 이미지-텍스트 통합모델 관련연구(§2.2) |
| 7 | Naveed, Uzmi & Qazi (2025). ThumbnailTruth: A Multi-Modal LLM Approach for Detecting Misleading YouTube Thumbnails Across Diverse Cultural Settings. | arXiv:2509.04714 [cs.SI] | 썸네일 축 최근접. **멀티모달 LLM(GPT-4o·Claude 3.5·Gemini)** 으로 오도성 썸네일 **탐지**. 우리와 차이: 검색 랭킹 기여 조건이 아니라 misleading 분류(§2.3) |
| 8 | Ma, Chen, Liu, Zhou & Cai (2024). Query-Adaptive Late Fusion for Hierarchical Fine-Grained Video-Text Retrieval. *IEEE TNNLS*, 35(5):7150–7161. | DOI:10.1109/TNNLS.2022.3214208 (early access 2022-10, 정식 게재 2024-05) | §2.3 "쿼리 적응 모달 활용" 축. 쿼리별 다중레벨 유효성 추정→late fusion 가중 적응(QAMF). 우리와 차이: **성능 최적화 메커니즘** vs 우리는 정합차이-기여 **연관 분석** |
| 9 | Loweimi, Qian, Knill, et al. (2026). To Be Multimodal or Not to Be: Query-Adaptive Audio-Visual Person Retrieval via Active Modality Detection. *INTERSPEECH*. | arXiv:2606.05931 | §2.3 동일 축. cross-modal agreement로 쿼리별 모달 능동 선택. 우리와 차이: **성능용 모달 선택 메커니즘** vs **기여 조건 기술 분석** |
| 10 | Mu & Viswanath (2018). All-but-the-Top: Simple and Effective Postprocessing for Word Representations. *ICLR*. | arXiv:1702.01417 | gap 계산 전 모달별 mean-centering(이방성/modality-gap offset 제거)의 근거(§3.2) |
| 11 | Ethayarajh (2019). How Contextual are Contextualized Word Representations? *EMNLP*. | arXiv:1909.00512 | 임베딩 이방성(anisotropy) 현상 근거 — raw cosine이 좁게 뭉치는 이유(§3.2) |
| 12 | Liang et al. (2022). Mind the Gap: Understanding the Modality Gap in Multi-modal Contrastive Representation Learning. *NeurIPS*. | arXiv:2203.02053 | modality gap(우리 gap과 구별) — centering으로 제거하는 대상(§3.2) |

## 사용 모델·도구 (방법 재현용 — 논문에 명시)

| 항목 | 정확한 식별자 | 비고 |
|---|---|---|
| 썸네일 이미지 인코더 | `sentence-transformers/clip-ViT-B-32` | 512-dim. ⚠️ **OCR 미수행** — 썸네일 내 한국어 자막 텍스트 판독 못 함(시각 신호=시각적 장면·비문자적 시각 정보에 국한, 한계·후속) |
| gap용 정렬 텍스트 인코더 | `sentence-transformers/clip-ViT-B-32-multilingual-v1` | CLIP 이미지 공간 정렬(distillation), 512-dim |
| 검색용 텍스트 인코더 | `paraphrase-multilingual-mpnet-base-v2` | 768-dim (평가 파이프라인은 PCA 없이 사용; 운영 플랫폼은 512로 PCA) |

## 재검색 로그 (제출 전)

- [x] **2026-08-18 재검색 실시** (WebSearch, 4각도: CLIPScore-랭킹, gap-late fusion, 썸네일-검색기여, query-adaptive fusion)
  - **[7] ThumbnailTruth의 "가장 가까운" 표현은 부정확** 판정 → 본문 "관련된 연구로는…"으로 약화, §2.3 두 축으로 재구성.
  - 연구질문(시각이 언제 검색에 기여?) 축에서 [7]보다 가까운 계열 발견 → **[8] QAMF(IEEE TNNLS 2022)**, **[9] Active Modality Detection(INTERSPEECH 2026)** 추가 인용. 둘 다 **성능용 적응 메커니즘**이라 우리(연관 분석)와 차별점 성립 → 오히려 §2.4 공백 선명화.
  - 참고: Cross the Gap(arXiv:2502.04263, CLIP intra-modal misalignment), YouTube thumbnail design rec(Springer 2024)는 도메인/과제가 멀어 미인용.
- [x] **2026-08-18 본문 참고문헌 번호를 인용(등장) 순서로 재정렬**. references_summary_ko.md 신설(한국어 요약집, 동일 번호).
- [x] **2026-08-18 KIICE 발표문 양식(2025) 규정 확인 완료**: "참고 문헌은 본문에서 인용된 것만을 **인용 순서에 따라** 작성", "모든 문헌 **영문** 원칙", "영문 Time new roman 9pt". → 우리 인용순서 재정렬이 규정과 **일치**(되돌릴 필요 없음). 서지 형식(저자, "제목," 논문지명, Vol., No., pp., 년월)에 맞춰 목록 보강 완료.
  - 확인된 서지: [6] BLIP = PMLR Vol.162, pp.12888–12900, Jul.2022 / [12] Mind the Gap = NeurIPS Vol.35, pp.17612–17625, Dec.2022.
  - **분량 규정: 3페이지 이내(초과 시 페이지당 1만원)** — 저자 결정: **5페이지 유지, 초과분 부담 감수**(내용 충실 우선).
- [x] **2026-08-18 서지 확정**: [8] QAMF = *IEEE TNNLS* 35(5):7150–7161, May 2024 (DOI 10.1109/TNNLS.2022.3214208). [2] M2HF = 정식 저널본 *Computational Visual Media* 12(2):449–471, 2026 (DOI 10.26599/CVM.2025.9450444, 'Multi-branch')로 인용 확정. [9] = INTERSPEECH 2026(arXiv:2606.05931), 저자 10인 확인, 프로시딩 페이지는 행사 특성상 미부여(현 표기 유지).
- [ ] **제출 직전 최종 재확인**: 최근 6개월(2026-03~) 신규 arXiv에서 "gap↔retrieval contribution 상관 분석" 직접 경쟁 연구 유무 재검색. [8][9]가 여전히 최인접인지 재확인.
- [ ] [9] INTERSPEECH 2026 정식 프로시딩 페이지가 나오면 갱신(현재 미부여).
