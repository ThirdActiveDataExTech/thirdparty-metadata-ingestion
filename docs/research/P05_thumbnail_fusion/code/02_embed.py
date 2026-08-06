"""P05 02단계 — 임베딩 생성 (PREREGISTRATION.md §0.4·§0.5).

corpus.jsonl의 각 영상에 대해 3종 임베딩을 만든다:
  - img      : 썸네일 이미지  → `clip-ViT-B-32` (512d)               → gap 계산용
  - gap_txt  : 제목(한국어)   → `clip-ViT-B-32-multilingual-v1` (512d) → gap 계산용(이미지 공간 정렬)
  - ret_txt  : 제목(한국어)   → `paraphrase-multilingual-mpnet-base-v2` (768d) → retrieval 텍스트 채널

gap_i = 1 - cos(img_i, gap_txt_i) 는 03단계에서, 검색은 04단계에서 이 임베딩을 읽어 계산한다.

내구성:
  - 썸네일은 data/thumbnails/{video_id}.jpg에 캐시(재실행 시 재다운로드 안 함).
  - 임베딩은 data/embeddings/embeddings.npz (video_ids + 3행렬) + manifest에 저장.
    다운로드 실패(비공개/삭제 등)한 영상은 건너뛰고 embed_skipped.json에 기록.
  - 모든 임베딩은 정규화(normalize)되어 cos == dot.

쿼터 무관(로컬 추론). 최초 실행 시 모델 3종 다운로드(HF).

실행: 저장소 루트에서
  PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/02_embed.py [--limit N]
"""

import argparse
import io
import json
import time
from pathlib import Path

import numpy as np
import requests
from PIL import Image
from sentence_transformers import SentenceTransformer

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CORPUS_PATH = DATA_DIR / "corpus.jsonl"
THUMB_DIR = DATA_DIR / "thumbnails"
EMB_DIR = DATA_DIR / "embeddings"
EMB_PATH = EMB_DIR / "embeddings.npz"
MANIFEST_PATH = EMB_DIR / "embed_manifest.json"
SKIPPED_PATH = EMB_DIR / "embed_skipped.json"

IMG_MODEL = "clip-ViT-B-32"
GAP_TXT_MODEL = "sentence-transformers/clip-ViT-B-32-multilingual-v1"
RET_TXT_MODEL = "paraphrase-multilingual-mpnet-base-v2"

HEADERS = {"User-Agent": "Mozilla/5.0 (research thumbnail fetch)"}


def load_corpus(limit=None) -> list:
    rows = []
    with CORPUS_PATH.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
                if limit and len(rows) >= limit:
                    break
    return rows


def download_thumb(video_id: str, url: str, tries=3) -> Path:
    """썸네일을 캐시에 저장하고 경로 반환. 실패 시 None."""
    dst = THUMB_DIR / f"{video_id}.jpg"
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    for attempt in range(tries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
            img.save(dst, "JPEG", quality=90)
            return dst
        except Exception:
            if attempt < tries - 1:
                time.sleep(1.0 * (attempt + 1))
    return None


def main(limit=None):
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    EMB_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_corpus(limit)
    print(f"corpus {len(rows)}편 로드 (limit={limit})")

    # 1) 썸네일 다운로드(캐시) — 실패 건 제외
    ok_rows, skipped = [], []
    for i, r in enumerate(rows, 1):
        p = download_thumb(r["video_id"], r["thumbnail_url"])
        if p:
            ok_rows.append(r)
        else:
            skipped.append({"video_id": r["video_id"], "reason": "thumbnail_download_failed"})
        if i % 50 == 0:
            print(f"  다운로드 {i}/{len(rows)} (실패 {len(skipped)})")
    print(f"다운로드 완료: {len(ok_rows)}편 사용, {len(skipped)}편 실패")

    # 2) 인코딩
    video_ids = [r["video_id"] for r in ok_rows]
    titles = [r["title"] for r in ok_rows]
    images = [Image.open(THUMB_DIR / f"{v}.jpg").convert("RGB") for v in video_ids]

    print(f"이미지 인코더 로드: {IMG_MODEL}")
    img_model = SentenceTransformer(IMG_MODEL)
    img_emb = img_model.encode(images, batch_size=32, convert_to_numpy=True,
                               normalize_embeddings=True, show_progress_bar=True)

    print(f"gap 텍스트 인코더 로드: {GAP_TXT_MODEL}")
    gap_model = SentenceTransformer(GAP_TXT_MODEL)
    gap_txt_emb = gap_model.encode(titles, batch_size=64, convert_to_numpy=True,
                                   normalize_embeddings=True, show_progress_bar=True)

    print(f"retrieval 텍스트 인코더 로드: {RET_TXT_MODEL}")
    ret_model = SentenceTransformer(RET_TXT_MODEL)
    ret_txt_emb = ret_model.encode(titles, batch_size=64, convert_to_numpy=True,
                                   normalize_embeddings=True, show_progress_bar=True)

    # 3) 저장
    np.savez_compressed(
        EMB_PATH,
        video_ids=np.array(video_ids),
        img=img_emb.astype(np.float32),
        gap_txt=gap_txt_emb.astype(np.float32),
        ret_txt=ret_txt_emb.astype(np.float32),
    )
    MANIFEST_PATH.write_text(json.dumps({
        "n": len(video_ids), "img_model": IMG_MODEL, "gap_txt_model": GAP_TXT_MODEL,
        "ret_txt_model": RET_TXT_MODEL, "img_dim": int(img_emb.shape[1]),
        "gap_txt_dim": int(gap_txt_emb.shape[1]), "ret_txt_dim": int(ret_txt_emb.shape[1]),
        "corpus_rows": len(rows), "skipped": len(skipped),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    SKIPPED_PATH.write_text(json.dumps(skipped, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ 임베딩 저장 → {EMB_PATH}")
    print(f"   img {img_emb.shape} / gap_txt {gap_txt_emb.shape} / ret_txt {ret_txt_emb.shape}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="처리할 영상 수(테스트용)")
    main(ap.parse_args().limit)
