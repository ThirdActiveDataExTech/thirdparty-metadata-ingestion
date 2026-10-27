"""와이즈넛 「백엔드 설계 초안 v2」 별첨 테이블정의서 ↔ 실제 DB 대조 (읽기 전용).

스펙 출처: 별첨_테이블정의서_와이즈넛_의견(모비젠).pdf — 시트 1·2 기준 스냅샷.
와이즈넛이 DDL을 전달하면 SPEC을 갱신해 재실행한다.

사용법: PYTHONPATH=. python scripts/compare_wisenut_spec.py
"""
from src.database.db import get_conn

# 테이블 → (구분, 스펙 컬럼 순서)
SPEC = {
    "dcat_dataset": ("기존+신규6", [
        "dataset_id", "source", "title", "description", "publisher", "publisher_code",
        "source_type", "dataset_origin", "owner_id", "subjects", "keywords", "theme",
        "language", "spatial", "temporal_start", "temporal_end", "temporal_resolution",
        "accrual_periodicity", "license", "rights", "version", "item_count",
        "landing_page", "access_url", "external_ids", "party", "visibility",
        "created_at", "updated_at"]),
    "dcat_dataset_attr": ("신규", [
        "dataset_id", "next_registration_date", "list_type", "media_type", "provision_form",
        "api_type", "allowed_traffic", "review_type", "national_core_yn", "standard_data_yn",
        "cost_charged", "cost_basis", "dept_name", "dept_phone", "retention_basis",
        "collection_method", "data_limitation", "other_notes", "updated_at"]),
    "active_meta_dataset": ("신규", [
        "id", "dataset_id", "metric_code", "metric_value", "observed_at", "source"]),
    "dcat_dataset_relation": ("신규", [
        "id", "source_dataset_id", "target_dataset_id", "relation_type", "score",
        "method", "status", "evidence", "created_at"]),
    "meta_datagokr_file": ("신규", [
        "file_id", "dataset_id", "file_name", "display_name", "file_format", "byte_size",
        "content_sha256", "storage_key", "record_count", "column_count", "column_names",
        "column_profile", "coverage_start", "coverage_end", "domain", "table_summary",
        "created_at", "updated_at"]),
    "active_meta_file": ("신규", [
        "id", "file_id", "metric_code", "metric_value", "observed_at", "source"]),
    "meta_file_relation": ("신규", [
        "id", "source_file_id", "source_column", "target_file_id", "target_column",
        "relation_type", "score", "evidence", "status", "created_at"]),
    "dcat_dataset_vec": ("기존", [
        "dataset_id", "embedding", "embed_text", "model_name", "embedded_at"]),
    "meta_datagokr_file_vec": ("신규", [
        "file_id", "summary_embedding", "keywords_embedding", "embed_text",
        "model_name", "embedded_at"]),
    "dcat_provenance": ("기존", [
        "prov_id", "dataset_id", "activity_type", "agent", "triggered_by", "started_at",
        "ended_at", "status", "rows_affected", "params", "error_message"]),
    "data_registry": ("기존", [
        "dataset_id", "s3_raw_prefix", "s3_jsonld_prefix", "pg_meta_table",
        "pg_active_table", "vec_collection", "status", "last_collected_at",
        "next_collect_at", "last_error", "item_count", "row_count",
        "temporal_start", "temporal_end", "registered_at", "updated_at"]),
    "dcat_dataset_draft": ("신규", [
        "id", "source", "payload_sha256", "raw_storage_key", "mapping_version", "status",
        "content", "mapping_evidence", "auto_threshold", "reviewed_by", "reviewed_at",
        "created_at"]),
    "metadata_entry": ("기존", [
        "id", "metadata_id", "metadata_schema", "value", "ingested_at"]),
    "metric_registry": ("신규(모비젠 제안·와이즈넛 반영)", [
        "metric_code", "label", "layer", "value_type", "unit", "applies_to",
        "default_source", "description"]),
    "relation_type_registry": ("신규(모비젠 제안·와이즈넛 반영)", [
        "relation_type", "label", "scope", "applies_to", "required_fields", "description"]),
}


def main():
    conn = get_conn()
    conn.set_session(readonly=True)
    cur = conn.cursor()
    print("# 와이즈넛 테이블정의서 ↔ 실제 DB 대조\n")
    print("| 테이블 | 구분 | DB | 스펙 누락 컬럼 | DB에만 있는 컬럼 |")
    print("|---|---|---|---|---|")
    todo = []
    for t, (kind, spec_cols) in SPEC.items():
        cur.execute("""SELECT column_name FROM information_schema.columns
                        WHERE table_schema='public' AND table_name=%s
                        ORDER BY ordinal_position""", (t,))
        db_cols = [r[0] for r in cur.fetchall()]
        if not db_cols:
            print(f"| `{t}` | {kind} | ❌ **테이블 없음** | — | — |")
            todo.append(f"테이블 생성: {t}")
            continue
        missing = [c for c in spec_cols if c not in db_cols]
        extra = [c for c in db_cols if c not in spec_cols]
        mark = "✅" if not missing and not extra else "⚠️"
        print(f"| `{t}` | {kind} | {mark} {len(db_cols)}컬럼 | "
              f"{', '.join(f'`{c}`' for c in missing) or '—'} | "
              f"{', '.join(f'`{c}`' for c in extra) or '—'} |")
        if missing:
            todo.append(f"컬럼 추가 {t}: {', '.join(missing)}")
        if extra:
            todo.append(f"스펙 확인 필요 {t}: DB에만 {', '.join(extra)}")

    print("\n## 조치 목록\n")
    for i, x in enumerate(todo, 1):
        print(f"{i}. {x}")

    # dataset_id 실제 값 — URN 규칙 대조용
    print("\n## 현재 dataset_id 값 (URN 규칙 대조)\n")
    cur.execute("SELECT dataset_id, source_type FROM dcat_dataset ORDER BY 1")
    rows = cur.fetchall()
    print("```")
    for d, st in rows:
        print(f"{d:45s} {st}")
    print("```")
    print(f"- 총 {len(rows)}건, 최대 길이 {max(len(d) for d, _ in rows)}자 (스펙 상한 100자)")
    print(f"- URN 형식(`urn:` 접두) 사용: {sum(1 for d, _ in rows if d.startswith('urn:'))}건")
    conn.close()


if __name__ == "__main__":
    main()
