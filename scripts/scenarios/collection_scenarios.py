"""수집 파이프라인 점검용 등록 시나리오 정의.

사용자가 등록 화면에서 넣을 법한 입력을 소스별로 경우를 갈라 모았다.
목적은 큰 코퍼스를 만드는 것이 아니라 **등록~수집 경로가 경우마다 제대로 도는지,
어느 컬럼이 비는지**를 보는 것이다. 그래서 대상은 작은 채널·좁은 검색어로 고른다.

각 항목은 register_dataset.py의 CLI 인자와 1:1로 대응한다 — 프론트엔드 등록 API가
받을 입력과 같은 모양이다(docs/api/01_Dataset_Registration_Scenario.md).
"""

# (시나리오명, source_type, CLI 인자 dict)
SCENARIOS = [
    # ── video ────────────────────────────────────────────────────────────
    ("V1 채널 1개", "video", {
        "title": "대항병원 대장항문 질환 정보",
        "description": "대항병원 유튜브 채널의 대장항문 질환 관련 영상을 수집한다.",
        "keywords": "대장항문,치질,치핵,의료",
        "subjects": "UCf3ZZpHjdWbCplbPQigtNvw",
        "periodicity": "P7D",
    }),
    ("V2 채널 2개", "video", {
        "title": "외과 전문의 채널 모음",
        "description": "외과 전문의가 운영하는 두 채널의 수술·질환 설명 영상을 함께 수집한다.",
        "keywords": "외과,수술,의료상담",
        "subjects": "UCmJW9F42VJe4mnZksLKNOmA,UCLofzxZxuSQV0Som_vlDBfg",
        "periodicity": "P7D",
    }),
    ("V3 채널+개별영상 혼합", "video", {
        "title": "암 정보 큐레이션",
        "description": "국가암지식정보센터 채널 전체에 대항병원 영상 2건을 더해 구성한 큐레이션.",
        "keywords": "암,위암,건강정보",
        "subjects": "UCnHq2L1NAGMpb_VE_4wiSUQ",
        "videos": "7RsnUNIjjq0,cYMWgUbQ3ls",
        "periodicity": "P7D",
    }),
    ("V4 개별영상만", "video", {
        "title": "치질 수술 안내 영상 모음",
        "description": "채널 전체가 아니라 관리자가 직접 고른 치질 관련 영상만 모은 데이터셋.",
        "keywords": "치질,치핵,수술안내",
        "videos": "7RsnUNIjjq0,I8rBCDvcVFA,cYMWgUbQ3ls",
        "periodicity": "P30D",
    }),
    ("V5 사용자 등록", "video", {
        "title": "내가 보는 반도체 채널",
        "description": "사용자가 직접 등록한 반도체 기술 채널 수집.",
        "keywords": "반도체,HBM,메모리",
        "subjects": "UCltyil2FaQZZ4kUNinKkKmw",
        "origin": "user", "owner_id": "demo-user-0001",
        "periodicity": "P7D",
    }),

    # ── news ─────────────────────────────────────────────────────────────
    ("N1 검색어 1개", "news", {
        "title": "HBM 뉴스",
        "description": "고대역폭 메모리(HBM) 관련 뉴스 기사를 수집한다.",
        "subjects": "HBM",
    }),
    ("N2 검색어 여러 개", "news", {
        "title": "양자컴퓨팅 뉴스",
        "description": "양자컴퓨팅 기술 동향 뉴스를 여러 검색어로 수집한다.",
        "subjects": "양자컴퓨팅,큐비트",
    }),
    ("N3 키워드 별도 지정", "news", {
        "title": "온디바이스 AI 뉴스",
        "description": "단말기에서 직접 추론하는 AI 기술 관련 뉴스.",
        "subjects": "온디바이스AI",
        "keywords": "인공지능,엣지컴퓨팅,반도체",   # 검색어와 다르게 지정
    }),
    ("N4 주간 수집", "news", {
        "title": "로봇 산업 주간 뉴스",
        "description": "로봇 산업 동향을 주 1회 수집한다.",
        "subjects": "휴머노이드로봇",
        "periodicity": "P7D",
    }),
    ("N5 사용자 등록", "news", {
        "title": "내가 보는 바이오 뉴스",
        "description": "사용자가 직접 등록한 바이오 산업 뉴스 수집.",
        "subjects": "바이오시밀러",
        "origin": "user", "owner_id": "demo-user-0002",
    }),

    # ── blog ─────────────────────────────────────────────────────────────
    ("B1 검색어 1개", "blog", {
        "title": "전기차 충전 블로그",
        "description": "전기차 충전 관련 블로그 게시물을 수집한다.",
        "subjects": "전기차충전",
    }),
    ("B2 검색어 여러 개", "blog", {
        "title": "홈트레이닝 블로그",
        "description": "홈트레이닝 루틴과 기구 후기 게시물을 수집한다.",
        "subjects": "홈트레이닝,홈짐",
    }),
    ("B3 키워드 별도 지정", "blog", {
        "title": "제로웨이스트 블로그",
        "description": "쓰레기를 줄이는 생활 방식을 다룬 게시물.",
        "subjects": "제로웨이스트",
        "keywords": "환경,친환경,지속가능성",
    }),
    ("B4 주간 수집", "blog", {
        "title": "캠핑 장비 주간 블로그",
        "description": "캠핑 장비 후기를 주 1회 수집한다.",
        "subjects": "캠핑장비",
        "periodicity": "P7D",
    }),
    ("B5 사용자 등록", "blog", {
        "title": "내가 보는 반려동물 블로그",
        "description": "사용자가 직접 등록한 반려동물 정보 블로그 수집.",
        "subjects": "반려견건강",
        "origin": "user", "owner_id": "demo-user-0003",
    }),

    # ── shopping_insight ─────────────────────────────────────────────────
    ("S1 카테고리 1개", "shopping_insight", {
        "title": "패션의류 검색 트렌드",
        "description": "패션의류 대분류의 성별·연령별 검색량 지수를 수집한다.",
        "keywords": "패션,의류,검색트렌드",
        "categories": "50000148:패션의류",
    }),
    ("S2 카테고리 여러 개", "shopping_insight", {
        "title": "패션 전체 검색 트렌드",
        "description": "패션의류와 패션잡화를 함께 보는 검색량 지수.",
        "keywords": "패션,잡화,검색트렌드",
        "categories": "50000148:패션의류,50000204:패션잡화",
    }),
    ("S3 소급 수집", "shopping_insight", {
        "title": "화장품 검색 트렌드 (소급)",
        "description": "화장품·미용 카테고리를 과거 시점부터 소급해 수집한다.",
        "keywords": "화장품,미용,검색트렌드",
        "categories": "50000002:화장품/미용",
        "temporal_start": "2026-09-01",
    }),
    ("S4 광고 관점", "shopping_insight", {
        "title": "디지털가전 광고 트렌드",
        "description": "광고 집행에 참고할 디지털/가전 카테고리 검색 트렌드.",
        "keywords": "광고,제품트렌드,디지털가전",
        "categories": "50000003:디지털/가전",
    }),
    ("S5 사용자 등록", "shopping_insight", {
        "title": "내가 보는 식품 트렌드",
        "description": "사용자가 직접 등록한 식품 카테고리 검색 트렌드.",
        "keywords": "식품,먹거리,검색트렌드",
        "categories": "50000006:식품",
        "origin": "user", "owner_id": "demo-user-0004",
    }),

    # ── persona_insight ──────────────────────────────────────────────────
    ("P1 카테고리 1개", "persona_insight", {
        "title": "패션의류 페르소나",
        "description": "패션의류 카테고리의 성별×연령 교차 추정 지표.",
        "keywords": "패션,페르소나,고객군",
        "categories": "50000148:패션의류",
    }),
    ("P2 카테고리 여러 개", "persona_insight", {
        "title": "패션 전체 페르소나",
        "description": "패션의류와 패션잡화의 성별×연령 교차 추정.",
        "keywords": "패션,잡화,페르소나",
        "categories": "50000148:패션의류,50000204:패션잡화",
    }),
    ("P3 소급 수집", "persona_insight", {
        "title": "화장품 페르소나 (소급)",
        "description": "화장품·미용 카테고리를 과거 시점부터 소급 분석한다.",
        "keywords": "화장품,페르소나,고객군",
        "categories": "50000002:화장품/미용",
        "temporal_start": "2026-09-01",
    }),
    ("P4 광고 관점", "persona_insight", {
        "title": "디지털가전 구매층 분석",
        "description": "광고 타겟팅에 쓸 디지털/가전 구매층 성별·연령 분포.",
        "keywords": "광고,타겟팅,디지털가전",
        "categories": "50000003:디지털/가전",
    }),
    ("P5 사용자 등록", "persona_insight", {
        "title": "내가 보는 식품 구매층",
        "description": "사용자가 직접 등록한 식품 카테고리 구매층 분석.",
        "keywords": "식품,페르소나,고객군",
        "categories": "50000006:식품",
        "origin": "user", "owner_id": "demo-user-0005",
    }),
]
