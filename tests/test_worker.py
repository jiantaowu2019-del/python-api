from api.worker import _can_retry


def test_retry_budget_counts_retries_after_initial_attempt():
    assert _can_retry(attempts=1, max_retries=1) is True
    assert _can_retry(attempts=2, max_retries=1) is False


def test_zero_retries_stops_after_initial_failure():
    assert _can_retry(attempts=1, max_retries=0) is False
