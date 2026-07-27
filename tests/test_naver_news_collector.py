from src.collectors.naver_news_collector import (
    _strip_b_tags,
    normalize_article,
    parse_naver_hosted,
)


def test_parse_naver_hosted_true_for_mnews_format():
    is_hosted, oid, aid = parse_naver_hosted("https://n.news.naver.com/mnews/article/023/0003800000")
    assert is_hosted is True
    assert oid == "023"
    assert aid == "0003800000"


def test_parse_naver_hosted_true_for_plain_article_format():
    is_hosted, oid, aid = parse_naver_hosted("https://news.naver.com/article/001/0015300000")
    assert is_hosted is True
    assert oid == "001"
    assert aid == "0015300000"


def test_parse_naver_hosted_false_for_external_site():
    is_hosted, oid, aid = parse_naver_hosted("https://www.yna.co.kr/view/AKR20260706000000017")
    assert is_hosted is False
    assert oid is None
    assert aid is None


def test_strip_b_tags_removes_highlight_markup():
    assert _strip_b_tags("삼성전자, <b>HBM4</b> 개발 <b>본격화</b>") == "삼성전자, HBM4 개발 본격화"


def test_strip_b_tags_unescapes_html_entities():
    assert _strip_b_tags("보건의료 <b>R&amp;D</b> 우수성과") == "보건의료 R&D 우수성과"


def test_normalize_article_maps_fields_correctly():
    item = {
        "title": "<b>삼성전자</b> HBM4 개발",
        "originallink": "https://www.yna.co.kr/view/AKR001",
        "link": "https://n.news.naver.com/mnews/article/001/0015300000",
        "description": "<b>삼성전자</b>가 HBM4를 개발한다",
        "pubDate": "Mon, 27 Jul 2026 10:00:00 +0900",
    }
    article = normalize_article(item, search_keyword="HBM4")
    assert article["title"] == "삼성전자 HBM4 개발"
    assert article["description"] == "삼성전자가 HBM4를 개발한다"
    assert article["article_url"] == "https://www.yna.co.kr/view/AKR001"
    assert article["is_naver_hosted"] is True
    assert article["naver_oid"] == "001"
    assert article["naver_aid"] == "0015300000"
    assert article["publisher"] == "www.yna.co.kr"
    assert article["search_keyword"] == "HBM4"
    assert article["published_at"] is not None


def test_normalize_article_falls_back_to_naver_url_when_originallink_empty():
    item = {
        "title": "제목", "originallink": "", "link": "https://blog.naver.com/x/1",
        "description": "설명", "pubDate": "Mon, 27 Jul 2026 10:00:00 +0900",
    }
    article = normalize_article(item, search_keyword="k")
    assert article["article_url"] == "https://blog.naver.com/x/1"
