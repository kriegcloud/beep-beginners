from {{package}} import hello


def test_hello() -> None:
    assert hello().endswith("is set up.")
