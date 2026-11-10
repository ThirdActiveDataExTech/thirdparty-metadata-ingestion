from src.common.hangul_keys import has_hangul, to_keys


def test_syllables_and_jamo():
    assert to_keys("ㅁㅇ") == "ad"
    assert to_keys("관리자") == "rhksflwk"          # ㅘ = h+k
    assert to_keys("ㅁ으ㅑㅜ") == "admin"            # a d m i n 을 한글 상태로
    assert to_keys("맏ㄴ") == "akes"                # 받침 ㄷ


def test_double_and_compound():
    assert to_keys("ㄲㅆ") == "RT"                  # 쌍자음은 Shift
    assert to_keys("ㅒㅖ") == "OP"
    assert to_keys("닭") == "ekfr"                  # 겹받침 ㄺ = f+r
    assert to_keys("의") == "dml"                   # ㅢ = m+l


def test_non_hangul_kept():
    assert to_keys("abc123!@") == "abc123!@"
    assert to_keys("ㅁ1ㅇ!") == "a1d!"


def test_round_trip_typical_password():
    # "Mobigen2026!"를 한글 상태로 치면 대문자 M은 ㅡ가 되고 Shift 정보는 사라진다
    typed = "ㅡㅐㅠㅑㅎ두2026!"
    assert to_keys(typed) == "mobigen2026!"


def test_has_hangul():
    assert has_hangul("ㅁㅇ") and has_hangul("가") and not has_hangul("abc!")
