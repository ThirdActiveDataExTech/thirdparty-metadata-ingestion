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

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "configs" / "auth_users.example.yaml"
OUT = REPO / "configs" / "auth_users.local.yaml"
MIN_LEN = 8


def ask(label: str) -> str:
    while True:
        pw = getpass.getpass(f"{label} 비밀번호({MIN_LEN}자 이상): ")
        if len(pw) < MIN_LEN:
            print(f"  {MIN_LEN}자 이상이어야 합니다.")
            continue
        if getpass.getpass("  한 번 더: ") != pw:
            print("  두 번 입력한 값이 다릅니다.")
            continue
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
