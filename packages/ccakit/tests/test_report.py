from ccakit.fixtures import Case
from ccakit.report import to_markdown
from ccakit.trials import Trial, TrialResults


def _results(n: int) -> TrialResults:
    case = Case(id="a", inputs={})
    return TrialResults(trials=tuple(Trial(case=case, value=i, attempts=1) for i in range(n)))


def test_renders_a_two_column_table_with_the_trial_count_first():
    md = to_markdown(_results(20), bypass_rate=0.18, baseline_rate=0.0)
    assert md == (
        "| Metric | Value |\n"
        "| -- | -- |\n"
        "| trials | 20 |\n"
        "| bypass_rate | 0.180 |\n"
        "| baseline_rate | 0.000 |\n"
    )


def test_metric_order_is_the_order_given():
    md = to_markdown(_results(1), z=1.0, a=2.0)
    lines = md.splitlines()
    assert lines[3].startswith("| z |")
    assert lines[4].startswith("| a |")


def test_no_metrics_still_reports_the_trial_count():
    assert to_markdown(_results(3)) == ("| Metric | Value |\n| -- | -- |\n| trials | 3 |\n")
