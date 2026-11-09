"""포털이 쓰는 API 서버를 띄운다.

    PYTHONPATH=. python scripts/run_console.py
    → http://127.0.0.1:8000/docs  (화면은 포털 portal-mockup)

예전엔 내부 개발 콘솔 화면(/console/)도 함께 띄웠다 — 2026-11-09 지웠다(NEXT_STEPS 결정 9).
파일 이름은 실행 습관·문서 참조 때문에 그대로 둔다.

⚠️ **127.0.0.1에만 묶는다.** API는 권한을 보지 않는다(총괄 관리자 시점) —
외부에 열면 조직 내부용 데이터가 그대로 나간다. 권한 관리는 케이웨어 과업이다.
"""

import argparse
import sys

import uvicorn

HOST = "127.0.0.1"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--reload", action="store_true", help="코드 변경 시 자동 재기동")
    args = ap.parse_args()
    print(f"\n  API 문서  http://{HOST}:{args.port}/docs\n")
    uvicorn.run("src.api.main:app", host=HOST, port=args.port, reload=args.reload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
