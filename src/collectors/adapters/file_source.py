"""스펙(YAML)으로 동작하는 로컬 파일 수집 어댑터 (A1 · 3차년도 "수집 프로세스가 없는 환경").

연구계획서 3차년도: "네트워크로 격리되어 있거나, 수집 프로세스가 없는 환경에서 데이터의 수집을 지원".
API가 없는 현장은 데이터가 **파일**(CSV·JSON·JSONL 내보내기)로만 있다. REST 어댑터와 같은
스펙 형식(`fields`·`id_field`)으로 파일을 읽어, 파이프라인이 원천 종류를 몰라도 되게 한다.

    kind: file
    source: site_export
    path: /data/export/*.csv          # glob. 상대 경로는 스펙 파일 기준
    format: csv                        # csv | json | jsonl (생략하면 확장자로)
    items_path: items                  # json일 때 배열 위치(생략하면 최상위 배열)
    encoding: utf-8-sig
    fields: {id: 번호, title: 제목}
    id_field: 번호

- 파일은 이름순으로 읽는다(결과 순서가 재현돼야 표본·드리프트 판정이 흔들리지 않는다)
- 네트워크를 쓰지 않는다
"""

import csv
import glob
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import yaml

from src.collectors.adapters.rest_json import clean_text, dig
from src.collectors.base import BaseCollector, CollectorError, RemovalPolicy

logger = logging.getLogger(__name__)

FORMATS = ("csv", "json", "jsonl")


class FileCollector(BaseCollector):
    """로컬 파일을 원천으로 읽는 수집기."""

    def __init__(self, spec: Dict[str, Any], base_dir: Optional[Path] = None):
        self.spec = spec
        self.source = spec.get("source") or ""
        if not self.source:
            raise CollectorError("스펙에 source가 없다")
        if not spec.get("path"):
            raise CollectorError(f"{self.source}: 스펙에 path가 없다")
        fmt = spec.get("format")
        if fmt and fmt not in FORMATS:
            raise CollectorError(f"{self.source}: 모르는 format {fmt!r} (가능: {FORMATS})")
        self._format = fmt
        self._base = Path(base_dir or ".")
        self._fields: Dict[str, str] = spec.get("fields") or {}
        self._id_field: Optional[str] = spec.get("id_field")
        self._items_path: Optional[str] = spec.get("items_path")
        self._encoding: str = spec.get("encoding", "utf-8-sig")
        self._clean_text: bool = bool(spec.get("clean_text", True))
        # 파일은 스냅샷이다 — 이번 파일에 없다고 지워졌다고 볼 근거가 없다
        self.removal_policy = RemovalPolicy.UNSUPPORTED

    @classmethod
    def from_file(cls, path: str) -> "FileCollector":
        with open(path, encoding="utf-8") as f:
            return cls(yaml.safe_load(f), base_dir=Path(path).parent)

    def files(self) -> List[Path]:
        pattern = self.spec["path"]
        if not Path(pattern).is_absolute():
            pattern = str(self._base / pattern)
        found = sorted(Path(p) for p in glob.glob(pattern) if Path(p).is_file())
        if not found:
            raise CollectorError(f"{self.source}: 읽을 파일이 없다 ({self.spec['path']})")
        return found

    def _format_of(self, path: Path) -> str:
        fmt = self._format or path.suffix.lower().lstrip(".")
        if fmt not in FORMATS:
            raise CollectorError(f"{self.source}: {path.name}의 형식을 알 수 없다(format을 지정하라)")
        return fmt

    def _read(self, path: Path) -> Iterator[Dict[str, Any]]:
        fmt = self._format_of(path)
        with open(path, encoding=self._encoding, newline="" if fmt == "csv" else None) as fh:
            if fmt == "csv":
                yield from csv.DictReader(fh)
            elif fmt == "jsonl":
                for n, line in enumerate(fh, 1):
                    if line.strip():
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError as e:
                            raise CollectorError(f"{path.name} {n}행이 JSON이 아니다: {e}") from e
            else:
                data = json.load(fh)
                items = dig(data, self._items_path) if self._items_path else data
                if not isinstance(items, list):
                    raise CollectorError(f"{path.name}: 항목 배열을 찾지 못했다(items_path 확인)")
                yield from items

    def fetch(self, cursor: Optional[Any] = None, query: Optional[Dict[str, Any]] = None,
              **_: Any) -> Iterator[Dict[str, Any]]:
        for path in self.files():
            for item in self._read(path):
                if isinstance(item, dict):
                    yield item

    def normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        if not self._fields:
            return dict(raw)
        out = {target: dig(raw, src) for target, src in self._fields.items()}
        if self._clean_text:
            out = {k: clean_text(v) for k, v in out.items()}
        if self._id_field and out.get("id") is None:
            out["id"] = dig(raw, self._id_field)
        return out

    def item_id(self, normalized: Dict[str, Any]) -> str:
        value = normalized.get("id")
        if value is None or value == "":
            raise CollectorError(f"{self.source}: 식별자가 비었다(id_field 확인)")
        return str(value)


def adapter_from_file(path: str):
    """스펙의 `kind`로 어댑터를 고른다(기본 rest_json)."""
    with open(path, encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    kind = spec.get("kind", "rest_json")
    if kind == "file":
        return FileCollector(spec, base_dir=Path(path).parent)
    if kind == "rest_json":
        from src.collectors.adapters.rest_json import RestJsonCollector
        return RestJsonCollector(spec)
    raise CollectorError(f"모르는 어댑터 종류: {kind!r} (rest_json | file)")
