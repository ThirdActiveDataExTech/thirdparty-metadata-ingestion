def pytest_configure(config):
    config.addinivalue_line("markers", "anonymous: 로그인하지 않은 상태로 부른다(tests/test_my_api.py)")
