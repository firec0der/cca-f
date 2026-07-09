from measure.errors import is_retryable


class FakeAPIError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


def test_rate_limit_is_retryable():
    assert is_retryable(FakeAPIError(429))


def test_overloaded_is_retryable():
    assert is_retryable(FakeAPIError(529))


def test_bad_request_is_not_retryable():
    assert not is_retryable(FakeAPIError(400))


def test_unauthorized_is_not_retryable():
    assert not is_retryable(FakeAPIError(401))


def test_a_plain_exception_is_not_retryable():
    assert not is_retryable(ValueError("boom"))
