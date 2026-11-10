"""시제품 로그인 계정 파일을 만든다 — 비밀번호를 물어 **해시만** 저장한다 (ADR-021).

    PYTHONPATH=. .venv/bin/python scripts/auth_setup_users.py            # 계정마다 따로
    PYTHONPATH=. .venv/bin/python scripts/auth_setup_users.py --same-user-password
        # 관리자는 따로, 사용자 5명은 비밀번호 하나로

- 입력은 화면에 보이지 않는다(getpass). 비밀번호는 어디에도 출력·기록하지 않는다.
- 결과: configs/auth_users.local.yaml (권한 600, git·이미지 제외). 이미 있으면 덮어쓸지 묻는다.
- 계정 목록·기관은 configs/auth_users.example.yaml에서 가져온다.
- 서명 키(AUTH_SIGNING_KEY)는 이 스크립트가 만들지 않는다 — .env에 직접 넣는다.
"""
import argparse
import getpass
import os
import sys
from pathlib import Path

import yaml

from src.api.auth import hash_password
from src.common.hangul_keys import has_hangul, to_keys

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "configs" / "auth_users.example.yaml"
OUT = REPO / "configs" / "auth_users.local.yaml"
MIN_LEN = 8


def _normalize(pw: str) -> str:
    """한글 입력 상태로 친 비밀번호를 실제로 누른 영문 키로 바꾼다(브라우저는 영문으로 입력되므로)."""
    return to_keys(pw) if has_hangul(pw) else pw


def ask(label: str) -> str:
    while True:
        raw = getpass.getpass(f"{label} 비밀번호({MIN_LEN}자 이상): ")
        pw = _normalize(raw)
        if len(pw) < MIN_LEN:
            print(f"  {MIN_LEN}자 이상이어야 합니다.")
            continue
        if not pw.isascii():
            print("  영문·숫자·기호만 쓸 수 있습니다.")
            continue
        if pw != pw.strip():
            print("  앞뒤 공백은 쓸 수 없습니다.")
            continue
        if _normalize(getpass.getpass("  한 번 더: ")) != pw:
            print("  두 번 입력한 값이 다릅니다.")
            continue
        if pw != raw:
            # macOS 터미널은 한글 입력 상태면 비밀번호를 한글로 받는다 — 누른 키 기준으로 저장한다
            print("  한글 입력 상태로 입력되어, 누른 영문 키 기준으로 바꿔 저장합니다.")
            print("  (한글 상태에서는 대문자를 구분할 수 없어 소문자로 저장됩니다. 대문자를 쓰려면 영문 상태에서 다시 입력해 주세요.)")
        return pw


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--same-user-password", action="store_true",
                    help="사용자(role=user) 계정은 비밀번호 하나로 (관리자는 따로)")
    a = ap.parse_args()
    if OUT.exists() and input(f"{OUT.relative_to(REPO)}가 이미 있습니다. 덮어쓸까요? [y/N] ").lower() != "y":
        sys.exit("그만둡니다.")
    data = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    shared = None
    for u in data["users"]:
        if a.same_user_password and u["role"] == "user":
            shared = shared or ask("사용자 공통")
            pw = shared
        else:
            pw = ask(f"{u['id']} ({u['name']})")
        u["password_hash"] = hash_password(pw)
    fd = os.open(OUT, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("# 자동 생성 — scripts/auth_setup_users.py. 커밋하지 말 것(.gitignore)\n")
        yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False)
    print(f"저장했습니다: {OUT.relative_to(REPO)} (계정 {len(data['users'])}개, 해시만)")


if __name__ == "__main__":
    main()
