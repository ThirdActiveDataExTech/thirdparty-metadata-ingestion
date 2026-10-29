#!/usr/bin/env python3
"""시나리오를 register_dataset.py로 등록한다.

사용자가 등록 화면에서 넣을 입력을 그대로 CLI 인자로 넘긴다 — 등록 API가 생기면
이 호출부만 HTTP 요청으로 바뀐다.

사용:
    PYTHONPATH=. python scripts/scenarios/run_registration.py
    PYTHONPATH=. python scripts/scenarios/run_registration.py --only video
"""
import argparse
import subprocess
import sys

from scripts.scenarios.collection_scenarios import SCENARIOS


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="source_type 하나만")
    args = ap.parse_args()

    ok, fail = [], []
    for name, st, opts in SCENARIOS:
        if args.only and st != args.only:
            continue
        cmd = [sys.executable, "scripts/register_dataset.py", st]
        for k, v in opts.items():
            cmd += [f"--{k.replace('_', '-')}", str(v)]
        r = subprocess.run(cmd, capture_output=True, text=True,
                           env={"PYTHONPATH": ".", **__import__("os").environ})
        out = (r.stdout + r.stderr).strip()
        if r.returncode == 0:
            did = next((ln.split()[-1] for ln in out.split("\n")
                        if "urn:" in ln), out.split("\n")[-1] if out else "?")
            ok.append((name, st, did))
            print(f"  ✅ {name:<22} {st:<18} {did}")
        else:
            fail.append((name, st, out))
            print(f"  ❌ {name:<22} {st:<18} {out.splitlines()[-1][:70] if out else ''}")

    print(f"\n  성공 {len(ok)}건 / 실패 {len(fail)}건")
    for name, st, err in fail:
        print(f"\n  [{name}] 실패 상세:\n{err[-500:]}")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
