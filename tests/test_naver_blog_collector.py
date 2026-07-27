from src.collectors.naver_blog_collector import (
    detect_platform,
    normalize_post,
    parse_naver_blog_ids,
)


def test_detect_platform_naver():
    assert detect_platform("https://blog.naver.com/techinsight_kr/223456781") == "naver"


def test_detect_platform_tistory():
    assert detect_platform("https://domdom.tistory.com/123") == "tistory"


def test_detect_platform_brunch():
    assert detect_platform("https://brunch.co.kr/@someone/12") == "brunch"


def test_detect_platform_custom_domain_is_other():
    assert detect_platform("https://romantech.net/post/1") == "other"


def test_parse_naver_blog_ids_extracts_blogid_and_lognol():
    blog_id, log_no = parse_naver_blog_ids("https://blog.naver.com/techinsight_kr/223456781")
    assert blog_id == "techinsight_kr"
    assert log_no == "223456781"


def test_parse_naver_blog_ids_returns_none_for_non_naver_url():
    blog_id, log_no = parse_naver_blog_ids("https://domdom.tistory.com/123")
    assert blog_id is None
    assert log_no is None


def test_normalize_post_naver_platform_fills_blog_id_and_log_no():
    item = {
        "title": "<b>HBM4</b> 정리",
        "link": "https://blog.naver.com/techinsight_kr/223456781",
        "description": "<b>HBM4</b>란 무엇인가",
        "bloggername": "테크인사이트",
        "bloggerlink": "https://blog.naver.com/techinsight_kr",
        "postdate": "20260720",
    }
    post = normalize_post(item, search_keyword="HBM4")
    assert post["platform"] == "naver"
    assert post["blog_id"] == "techinsight_kr"
    assert post["log_no"] == "223456781"
    assert post["title"] == "HBM4 정리"
    assert post["published_at"].year == 2026
    assert post["published_at"].month == 7
    assert post["published_at"].day == 20


def test_normalize_post_non_naver_platform_leaves_blog_id_none():
    item = {
        "title": "제목", "link": "https://domdom.tistory.com/123",
        "description": "설명", "bloggername": "", "bloggerlink": "",
        "postdate": "20260720",
    }
    post = normalize_post(item, search_keyword="k")
    assert post["platform"] == "tistory"
    assert post["blog_id"] is None
    assert post["log_no"] is None
