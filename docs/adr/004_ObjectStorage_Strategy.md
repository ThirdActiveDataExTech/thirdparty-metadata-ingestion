# ADR-004: Object Storage — MinIO → SeaweedFS 전환

> **Date:** 2026-07-03
> **Status:** Accepted

---

## 배경

초기 설계에서 오브젝트 스토리지로 MinIO를 선택했다. 그러나 MinIO Community Edition 정책 변화로 인해
대안 검토 후 SeaweedFS로 전환하기로 결정했다.

---

## MinIO CE 전환 배경 (결정 이유)

| 이슈 | 상세 |
|------|------|
| 배포 정책 변경 | 공식 바이너리/Docker 이미지 배포 중단, 소스 직접 빌드 방식으로 전환 |
| 기능 분리 | Console 관리 기능 일부가 유료 AIStor(Enterprise)로 이동 |
| 라이선스 방향성 | AGPL-3.0이나 상업적 경계 불명확, 미래 변경 가능성 |

---

## 검토한 대안

| 대안 | 라이선스 | 아키텍처 복잡도 | S3 호환 | 결정 |
|------|----------|----------------|---------|------|
| SeaweedFS | Apache 2.0 | 중간 (Pod 3개) | 좋음 | **채택** |
| Garage | AGPL-3.0 | 낮음 (Pod 1개) | 좋음 | 커뮤니티 작아 기각 |
| Ceph RGW | LGPL-2.1 | 매우 높음 | 완벽 | 단일 노드에 과함 |

---

## 결정

**SeaweedFS** 채택.

### 선택 근거

1. **라이선스**: Apache 2.0 — 영구 무료, 정책 변경 위험 없음
2. **S3 API 호환**: boto3/s3 SDK 그대로 사용 가능, 향후 AWS S3 이전 시 코드 변경 없음
3. **커뮤니티**: MinIO 대안 중 self-hosted 커뮤니티에서 가장 많이 검증된 선택
4. **규모 적합성**: 소규모 파일(API JSON, 수KB~수십KB) 다수 처리에 적합

---

## 영향 범위

- `data_registry` 테이블: `minio_raw_prefix` → `s3_raw_prefix`, `minio_jsonld_prefix` → `s3_jsonld_prefix`
- `.env` 환경변수: `MINIO_*` → `S3_*`
- K8s: MinIO Service 대신 SeaweedFS StatefulSet 3개 + NodePort Service 배포
- 수집 코드: S3 엔드포인트만 교체 (API 호환으로 로직 변경 없음)

---

## 향후 마이그레이션 경로

SeaweedFS → AWS S3 또는 다른 S3 호환 스토리지 전환 시:
- 엔드포인트, 자격증명만 교체
- 코드 변경 없음
- 기존 데이터: `aws s3 sync` 또는 `rclone` 으로 이전
