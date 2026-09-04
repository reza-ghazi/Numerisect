from pathlib import Path

from numerisect.engines import (
    CadoParameter,
    parse_cado_factors,
    parse_msieve_factors,
    parse_yafu_factors,
    product_is_complete,
    select_cado_parameter,
)


def test_selects_next_larger_cado_parameters():
    parameters = [
        CadoParameter(30, Path("c30")),
        CadoParameter(60, Path("c60")),
        CadoParameter(65, Path("c65")),
    ]
    assert select_cado_parameter(55, parameters).size == 60
    assert select_cado_parameter(61, parameters).size == 65


def test_honors_explicit_cado_size():
    parameters = [CadoParameter(60, Path("c60")), CadoParameter(65, Path("c65"))]
    assert select_cado_parameter(55, parameters, 65).size == 65


def test_parse_yafu_final_section():
    output = """
rho: found prp6 factor = 218249
***factors found***
P1 = 3
P6 = 218249
P24 = 168188813647512088370153
P26 = 88654790910361892829613901
***factorization:***
something
"""
    factors = parse_yafu_factors(output)
    assert [factor["value"] for factor in factors] == [
        "3",
        "218249",
        "168188813647512088370153",
        "88654790910361892829613901",
    ]
    assert product_is_complete(
        factors, 9762764972076045602745703475074502450747777777777611191
    )


def test_parse_msieve():
    factors = parse_msieve_factors("p1: 2\np1: 3\np3: 101\n")
    assert [factor["value"] for factor in factors] == ["2", "3", "101"]


def test_parse_cado_verifies_product():
    factors = parse_cado_factors("Info: Factors: 3 7 11\n3 7 11\n", 231)
    assert [factor["value"] for factor in factors] == ["3", "7", "11"]
    assert parse_cado_factors("3 7 13", 231) == []
