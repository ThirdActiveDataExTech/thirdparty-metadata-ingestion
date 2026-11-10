"""로그인이 안 될 때 원인을 확인한다 — 비밀번호는 출력하지 않는다 (ADR-021).

    PYTHONPATH=. .venv/bin/python scripts/auth_check_login.py

아이디와 비밀번호(화면에 안 보임)를 받아 계정 파일과 대조한 결과만 알려 준다.
"""
import getpass
import sys

from src.api.auth import load_accounts, users_file, verify_password
from src.common.hangul_keys import has_hangul, to_keys


def main() -> None:
    path = users_file()
    if not path.exists():
        sys.exit(f"계정 파일이 없습니다: {path.name} — scripts/auth_setup_users.py를 먼저 실행해 주세요.")
    users = load_accounts()["users"]
    uid = input("아이디: ").strip()
    acc = users.get(uid)
    if not acc:
        print(f"  [X] 계정 파일에 없는 아이디입니다. 등록된 아이디 {len(users)}개 중 하나를 입력해 주세요.")
        return
    if not acc.get("password_hash"):
        print("  [X] 이 계정은 비밀번호가 설정되지 않았습니다. auth_setup_users.py로 다시 설정해 주세요.")
        return
    pw = getpass.getpass("비밀번호(화면에 보이지 않음): ")
    if has_hangul(pw):
        if verify_password(pw, acc["password_hash"]):
            print("  [!] 비밀번호가 한글로 저장되어 있습니다(설정할 때 한글 입력 상태였습니다).")
            print("      브라우저에서는 로그인할 수 없으니 auth_setup_users.py로 다시 설정해 주세요.")
            print("      이제 한글 상태로 입력해도 영문 키 기준으로 자동 변환해 저장합니다.")
            return
        pw = to_keys(pw)
        print("  한글 입력 상태라 누른 영문 키 기준으로 바꿔 대조합니다.")
    if verify_password(pw, acc["password_hash"]):
        print("  [O] 비밀번호가 일치합니다. 브라우저에서도 같은 값으로 로그인됩니다.")
        print("      그래도 안 되면 Caps Lock과 아이디 자동 완성 값을 확인해 주세요.")
        return
    print("  [X] 비밀번호가 일치하지 않습니다. 흔한 원인:")
    print("      - 비밀번호를 설정할 때 한글 입력 상태였을 수 있습니다(터미널은 한글 그대로 저장).")
    print("        한글 상태로 바꿔 같은 키를 눌러 다시 확인해 보세요.")
    print("      - Caps Lock이 켜져 있습니다.")
    print("      해결: 영문 입력 상태에서 auth_setup_users.py를 다시 실행해 주세요(이제 한글 입력은 영문 키로 자동 변환합니다).")

if __name__ == "__main__":
    main()
