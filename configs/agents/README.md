# 신뢰하는 수집 에이전트 공개키

격리 환경 수집 번들(`src/agent/bundle.py`)은 **여기 등록된 공개키로 서명된 것만** 반입한다.

- 파일 이름: `<에이전트 이름>.pub.pem` (Ed25519 공개키 PEM). 반입 이력의 `triggered_by`에 이 이름이 남는다
- 공개키만 둔다. 비밀키는 에이전트가 설치된 현장에만 있다(환경변수 `AGENT_SIGNING_KEY`)
- 키 만들기(현장에서): `PYTHONPATH=. python scripts/package_dataset.py keygen --out <디렉터리>`
- 이미지 재빌드 없이 바꾸려면 `AGENT_TRUSTED_KEYS_DIR`로 다른 디렉터리(ConfigMap 마운트 등)를 지정한다
- 등록을 취소하려면 파일을 지운다 — 그 뒤로 해당 에이전트 번들은 403으로 거부된다
