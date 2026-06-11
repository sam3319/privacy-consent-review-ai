from scripts.deployment_smoke_test import run


def test_deployment_smoke_check():
    result = run()
    assert result["ready"]
    assert result["model_size_mb"] < 100
