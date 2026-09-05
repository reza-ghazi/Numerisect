import pytest

from numerisect.zeta import (
    ZetaEngineError,
    count_zeta_zeros,
    evaluate_zeta,
    find_zeta_zeros,
    sample_zeta_heatmap,
    sample_zeta_line,
    validated_real,
)


def test_rigorous_zeta_evaluation():
    result = evaluate_zeta("2", "0", 30)
    assert result["real"].startswith("[1.644934066848226")
    assert result["imaginary"] == "0"
    assert result["rigorous"] is True


def test_first_certified_zeta_zeros():
    zeros = find_zeta_zeros(1, 3, 30, 2)
    assert [zero["index"] for zero in zeros] == ["1", "2", "3"]
    assert zeros[0]["ordinate"].startswith("14.13472514173469")
    assert zeros[1]["ordinate"].startswith("21.02203963877155")
    assert "+/-" in zeros[0]["interval"]


def test_turing_method_zero_count():
    result = count_zeta_zeros("30", 30, 2)
    assert result["count"] == "3"


def test_critical_line_sampling():
    points = sample_zeta_line("0", "10", 8, 20, 2)
    assert len(points) == 8
    assert points[0]["t"] == 0.0
    assert points[-1]["t"] == 10.0
    assert all(point["magnitude"] is not None for point in points)


def test_heatmap_maps_zeta_pole_to_json_safe_null():
    points = sample_zeta_heatmap("0", "2", "-1", "1", 3, 3, 20, 2)
    assert len(points) == 9
    pole = points[4]
    assert pole["sigma"] == 1.0 and pole["t"] == 0.0
    assert pole["magnitude"] is None


def test_zeta_validation_and_pole_error():
    with pytest.raises(ValueError):
        validated_real("nan", "Input")
    with pytest.raises(ZetaEngineError, match="pole"):
        evaluate_zeta("1", "0", 20)
