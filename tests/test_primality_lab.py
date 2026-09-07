"""Tests for the PARI/GP primality laboratory boundary, routes, and reports.

Every success case cites the mathematical fact it pins down. Nothing in this
file recomputes mathematics in Python; it only asserts what PARI/GP returned.
"""

import pytest
from fastapi.testclient import TestClient

from numerisect import outputs
from numerisect.main import app
from numerisect.primality_lab import (
    bitwin_chain_search,
    carmichael_analysis,
    chernick_search,
    compare_primality_tests,
    constrained_prime,
    covering_set_check,
    deterministic_witness_test,
    ecpp_steps,
    lucas_lehmer_steps,
    lucas_sequence_proof,
    pocklington_proof,
    pratt_certificate,
    prime_ladder,
    proth_search,
    proth_test,
    pseudoprime_taxonomy,
    repunit_search,
    sierpinski_riesel_search,
    verify_certificate,
)
from numerisect.primes import PRIMESIEVE_TUPLE_PATTERNS, PrimeEngineError, prime_tuples_in_range

# nextprime(10^80); N - 1 cannot be factored inside a one-second budget.
LARGE_PRIME_80 = (
    "100000000000000000000000000000000000000000000000000000000000000000000000000000129"
)
# M127 = 2^127 - 1, proven prime by Lucas in 1876 and the largest Mersenne prime
# found before the computer era.
MERSENNE_127 = "170141183460469231731687303715884105727"
POCKLINGTON_CERTIFICATE = "[104729,1007,[[53, 1, 3], [19, 1, 2]]]"


def local_client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    client.headers["X-Numerisect-Token"] = client.get("/api/session").json()["request_token"]
    return client


# ---------------------------------------------------------------------------
# Item 14: primesieve k-tuplet enumeration
# ---------------------------------------------------------------------------
def test_primesieve_and_pari_tuple_searches_agree(monkeypatch):
    # The prime quadruplets below 2000 are {5,7,11,13}, {11,13,17,19},
    # {101,103,107,109}, {191,193,197,199}, {821,823,827,829} and
    # {1481,1483,1487,1489} (OEIS A007530).
    quadruplets, truncated, _ = prime_tuples_in_range(1, 2000, [0, 2, 6, 8], 100)
    assert quadruplets[0] == [5, 7, 11, 13]
    assert quadruplets[-1] == [1871, 1873, 1877, 1879]
    assert truncated is False

    import numerisect.primes as primes_module

    real_which = primes_module.shutil.which
    monkeypatch.setattr(
        primes_module.shutil, "which",
        lambda name: None if name == "primesieve" else real_which(name),
    )
    assert prime_tuples_in_range(1, 2000, [0, 2, 6, 8], 100)[0] == quadruplets


def test_ambiguous_tuple_sizes_stay_on_pari():
    # primesieve emits both admissible triplet shapes together, so separating
    # them would need offset arithmetic outside the engines; PARI/GP filters
    # those natively instead. Sextuplets have a unique shape and use primesieve.
    assert (0, 2, 6) not in PRIMESIEVE_TUPLE_PATTERNS
    assert (0, 2, 6, 8, 12) not in PRIMESIEVE_TUPLE_PATTERNS
    assert (0, 4, 6, 10, 12, 16) in PRIMESIEVE_TUPLE_PATTERNS
    assert prime_tuples_in_range(1, 60, [0, 2, 6], 100)[0] == [[5, 7, 11], [11, 13, 17],
                                                               [17, 19, 23], [41, 43, 47]]
    assert prime_tuples_in_range(1, 60, [0, 4, 6], 100)[0] == [[7, 11, 13], [13, 17, 19],
                                                               [37, 41, 43]]
    # The first prime sextuplet is {7, 11, 13, 17, 19, 23} (OEIS A022008).
    assert prime_tuples_in_range(1, 100, [0, 4, 6, 10, 12, 16], 10)[0] == [
        [7, 11, 13, 17, 19, 23]
    ]


def test_prime_tuple_limit_reports_a_continuation_point():
    tuples, truncated, next_start = prime_tuples_in_range(1, 100, [0, 2], 3)
    assert tuples == [[3, 5], [5, 7], [11, 13]]
    assert truncated is True and next_start == 17


@pytest.mark.parametrize("offsets", [[], [1, 3], [0], [0, 2_000_000]])
def test_prime_tuple_offsets_are_validated(offsets):
    with pytest.raises(ValueError):
        prime_tuples_in_range(1, 100, offsets, 10)


# ---------------------------------------------------------------------------
# Item 21: comparison laboratory
# ---------------------------------------------------------------------------
def test_comparison_laboratory_separates_probable_from_proven():
    # 3215031751 = 151 * 751 * 28351 is the smallest strong pseudoprime to all of
    # 2, 3, 5 and 7 (Jaeschke 1993), so Miller-Rabin only fails at base 11.
    result = compare_primality_tests("3215031751", ["2", "3", "5", "7", "11"], 30)
    assert result["verdict"] == "proven composite"
    strong = [row for row in result["rows"] if row[0] == "Miller-Rabin"]
    assert [row[1] for row in strong] == ["pass", "pass", "pass", "pass", "fail"]
    assert {row[4] for row in result["rows"]} == {"probable", "proof"}
    aprcl = [row for row in result["rows"] if row[0] == "APR-CL"]
    assert aprcl[0][1] == "fail" and aprcl[0][4] == "proof"


def test_comparison_laboratory_proves_a_prime():
    # 104729 is the 10,000th prime.
    result = compare_primality_tests("104729", ["2"], 30)
    assert result["verdict"] == "proven prime"
    assert all(row[1] in {"pass", "skipped"} for row in result["rows"])


def test_comparison_laboratory_reports_an_exhausted_budget_as_inconclusive():
    # A one-second ECPP budget cannot finish for a 301-digit prime, so the row is
    # inconclusive rather than a failure.
    result = compare_primality_tests(LARGE_PRIME_80, ["2"], 1)
    outcomes = {row[0]: row[1] for row in result["rows"]}
    assert outcomes["Baillie-PSW"] == "pass"
    assert result["verdict"] in {"proven prime", "inconclusive"}
    assert "fail" not in outcomes.values()


@pytest.mark.parametrize(
    ("number", "bases", "budget"),
    [("1", ["2"], 30), ("101", [], 30), ("101", ["0"], 30), ("101", ["2"], 0)],
)
def test_comparison_laboratory_rejects_invalid_input(number, bases, budget):
    with pytest.raises(ValueError):
        compare_primality_tests(number, bases, budget)


# ---------------------------------------------------------------------------
# Item 22: deterministic Miller-Rabin witness sets
# ---------------------------------------------------------------------------
def test_deterministic_witness_set_matches_the_published_bound():
    # 3215031751 < 2152302898747, so bases 2, 3, 5, 7, 11 are sufficient
    # (Jaeschke 1993); the first four are liars and 11 is the witness.
    result = deterministic_witness_test("3215031751")
    assert result["deterministic"] is True
    assert result["metrics"]["Witness bases"] == "2, 3, 5, 7, 11"
    assert result["metrics"]["Proven below"] == "2152302898747"
    assert [row[1] for row in result["rows"]] == ["pass", "pass", "pass", "pass", "fail"]
    assert result["verdict"] == "proven composite"


def test_deterministic_witness_set_proves_a_prime():
    # 32416190071 is prime and below the five-base bound.
    result = deterministic_witness_test("32416190071")
    assert result["verdict"] == "proven prime"
    assert all(row[1] == "pass" for row in result["rows"])


def test_deterministic_witness_set_is_inconclusive_above_the_largest_bound():
    # 3317044064679887385961981 is exactly the largest tabulated bound, so no
    # published sufficient set covers it.
    result = deterministic_witness_test("3317044064679887385961981")
    assert result["deterministic"] is False
    assert result["verdict"] == "inconclusive"
    assert result["rows"] == []


def test_deterministic_witness_set_rejects_invalid_input():
    with pytest.raises(ValueError):
        deterministic_witness_test("1")


# ---------------------------------------------------------------------------
# Items 23 and 24: Pocklington and Pratt certificates
# ---------------------------------------------------------------------------
def test_pocklington_proof_emits_a_verifiable_certificate():
    # 104729 - 1 = 2^3 * 13 * 19 * 53; F = 19 * 53 = 1007 already satisfies
    # (F + 1)^2 > 104729.
    result = pocklington_proof("104729", 60, 200)
    assert result["verdict"] == "proven prime"
    assert result["metrics"]["Factored part F"] == "1007"
    assert result["certificate"] == POCKLINGTON_CERTIFICATE
    assert all(row[3] == "yes" for row in result["rows"])


def test_pocklington_proof_detects_a_composite():
    # 561 = 3 * 11 * 17 fails the Fermat step at base 3.
    result = pocklington_proof("561", 60, 200)
    assert result["verdict"] == "proven composite"
    assert result["metrics"]["Fermat compositeness witness"] == "3"


def test_pocklington_proof_reports_a_factoring_timeout_as_inconclusive():
    result = pocklington_proof(LARGE_PRIME_80, 1, 50)
    assert result["metrics"]["Factorization of N−1"] == "timeout"
    assert result["verdict"] == "inconclusive"


def test_pocklington_certificate_verification_is_independent():
    valid = verify_certificate("pocklington", POCKLINGTON_CERTIFICATE)
    assert valid["valid"] is True
    assert valid["metrics"]["Conditions failed"] == "0"
    tampered = verify_certificate("pocklington", "[104729,1007,[[53, 1, 4], [19, 1, 2]]]")
    assert tampered["valid"] is False
    assert tampered["metrics"]["Conditions failed"] != "0"


def test_pratt_certificate_tree_is_complete_and_verifiable():
    # The Pratt tree of 104729 certifies 104729, 2, 13, 3, 19 and 53.
    result = pratt_certificate("104729", 500, 60)
    assert result["verdict"] == "proven prime"
    assert result["metrics"]["Certified primes in tree"] == "6"
    assert result["nodes"][0][2] == "104729" and result["nodes"][0][3] == "12"
    assert verify_certificate("pratt", result["certificate"])["valid"] is True


def test_pratt_certificate_tree_reports_truncation_as_inconclusive():
    result = pratt_certificate("104729", 3, 60)
    assert result["truncated"] is True
    assert result["verdict"] == "inconclusive"


def test_pratt_certificate_detects_a_composite():
    result = pratt_certificate("561", 500, 60)
    assert result["verdict"] == "proven composite"


@pytest.mark.parametrize(
    ("kind", "certificate"),
    [("pratt", "quit()"), ("unknown", POCKLINGTON_CERTIFICATE), ("pratt", "104729")],
)
def test_certificate_verification_rejects_invalid_input(kind, certificate):
    with pytest.raises(ValueError):
        verify_certificate(kind, certificate)


# ---------------------------------------------------------------------------
# Items 27 and 33: Proth and generalized Proth
# ---------------------------------------------------------------------------
def test_proth_theorem_proves_and_refutes():
    # 5 * 2^3 + 1 = 41 is prime; 11 * 2^4 + 1 = 177 = 3 * 59 is composite.
    prime = proth_test("5", 3, 2, 200, 60)
    assert prime["verdict"] == "proven prime"
    assert prime["metrics"]["Candidate"] == "41"
    composite = proth_test("11", 4, 2, 200, 60)
    assert composite["verdict"] == "proven composite"
    assert composite["metrics"]["Candidate"] == "177"


def test_generalized_proth_uses_the_n_minus_one_criterion():
    # 1 * 10^2 + 1 = 101 is prime; the criterion needs a witness for 2 and 5.
    result = proth_test("1", 2, 10, 200, 60)
    assert result["verdict"] == "proven prime"
    assert [row[0] for row in result["rows"]] == ["2", "5"]


def test_proth_criterion_is_inconclusive_for_a_perfect_square():
    # 5 * 2^4 + 1 = 81 = 3^4; no base has Jacobi symbol -1, so Proth's theorem
    # yields no verdict even though 81 is composite.
    result = proth_test("5", 4, 2, 200, 60)
    assert result["verdict"] == "inconclusive"
    assert result["metrics"]["Independent isprime cross-check"] == "proven composite"


def test_proth_search_finds_the_known_exponents():
    # 5 * 2^n + 1 is prime for n = 1, 3, 7, 13, 15 below 20 (OEIS A001770).
    result = proth_search("5", 2, 1, 20, 100)
    assert [row[0] for row in result["rows"]] == ["1", "3", "7", "13", "15"]
    assert [row[4] for row in result["rows"]] == ["11", "41", "641", "40961", "163841"]
    assert result["truncated"] is False


def test_proth_search_reports_its_result_limit():
    result = proth_search("5", 2, 1, 20, 2)
    assert result["truncated"] is True
    assert len(result["rows"]) == 2


@pytest.mark.parametrize(
    ("k", "exponent", "base"), [("0", 3, 2), ("5", 0, 2), ("5", 3, 1)]
)
def test_proth_rejects_invalid_input(k, exponent, base):
    with pytest.raises(ValueError):
        proth_test(k, exponent, base)


# ---------------------------------------------------------------------------
# Item 28: Lucas sequences and N+1
# ---------------------------------------------------------------------------
def test_lucas_sequence_proves_a_mersenne_prime():
    # 8191 = 2^13 - 1; 8191 + 1 = 2^13 factors completely, so the Morrison N+1
    # criterion applies and Lucas-Lehmer-Riesel also succeeds.
    result = lucas_sequence_proof("8191")
    assert result["verdict"] == "proven prime"
    criteria = {row[0]: row[1] for row in result["rows"]}
    assert criteria["Lucas–Lehmer–Riesel"] == "pass"
    assert criteria["Morrison N+1 proof"] == "proven prime"


def test_lucas_pseudoprime_stays_inconclusive():
    # 4181 = 37 * 113 is the classical Fibonacci (Lucas) pseudoprime for
    # P = 1, Q = -1: it passes the Lucas test but the Jacobi symbol is +1, so
    # no N+1 proof is available and the result must not be called composite.
    result = lucas_sequence_proof("4181", 1, -1, selfridge=False)
    criteria = {row[0]: row[1] for row in result["rows"]}
    assert criteria["Lucas probable prime"] == "pass"
    assert result["verdict"] == "inconclusive"


def test_lucas_selfridge_parameters_detect_the_same_composite():
    result = lucas_sequence_proof("4181")
    assert result["verdict"] == "proven composite"


@pytest.mark.parametrize(
    ("number", "p", "q", "selfridge"),
    [("8192", 1, -1, True), ("15", 2, 1, False), ("2", 1, -1, True)],
)
def test_lucas_sequence_rejects_invalid_input(number, p, q, selfridge):
    with pytest.raises((ValueError, PrimeEngineError)):
        lucas_sequence_proof(number, p, q, selfridge)


# ---------------------------------------------------------------------------
# Item 29: probable-prime taxonomy
# ---------------------------------------------------------------------------
def test_taxonomy_identifies_the_smallest_strong_pseudoprime_base_two():
    # 2047 = 23 * 89 is the smallest strong pseudoprime to base 2, and base 3
    # exposes it immediately.
    result = pseudoprime_taxonomy("2047", ["2", "3"])
    rows = {(row[0], row[1]): row[2] for row in result["rows"]}
    assert rows[("Strong", "a=2")] == "yes"
    assert rows[("Strong", "a=3")] == "no"
    assert rows[("Baillie-PSW", "PARI ispseudoprime")] == "no"
    assert "strong pseudoprime" in result["metrics"]["Pseudoprime families"]
    assert result["prime_status"] == "proven composite"


def test_taxonomy_of_a_carmichael_number_is_a_fermat_pseudoprime_only():
    # 1729 is a Carmichael number: a Fermat and Euler pseudoprime to base 2 but
    # not a strong pseudoprime.
    result = pseudoprime_taxonomy("1729", ["2"])
    rows = {(row[0], row[1]): row[2] for row in result["rows"]}
    assert rows[("Fermat", "a=2")] == "yes"
    assert rows[("Strong", "a=2")] == "no"


def test_taxonomy_of_a_prime_lists_no_pseudoprime_family():
    result = pseudoprime_taxonomy("104729", ["2", "3"])
    assert result["prime_status"] == "proven prime"
    assert result["metrics"]["Pseudoprime families"] == "not applicable to a prime"


@pytest.mark.parametrize("number", ["2048", "1", "2"])
def test_taxonomy_rejects_invalid_input(number):
    with pytest.raises((ValueError, PrimeEngineError)):
        pseudoprime_taxonomy(number, ["2"])


# ---------------------------------------------------------------------------
# Item 30: Carmichael analysis and Chernick construction
# ---------------------------------------------------------------------------
def test_carmichael_analysis_of_561():
    # 561 = 3 * 11 * 17 is the smallest Carmichael number; lambda(561) = 80 and
    # there are exactly gcd(2,560)*gcd(10,560)*gcd(16,560) = 2*10*16 = 320
    # Fermat liars.
    result = carmichael_analysis("561", 1000, 60)
    assert result["carmichael"] == "yes"
    assert [row[0] for row in result["rows"]] == ["3", "11", "17"]
    assert result["metrics"]["Carmichael function λ(n)"] == "80"
    assert result["metrics"]["Fermat liars in [1, n]"] == "320"
    assert result["metrics"]["Scan exhaustive"] == "yes"


def test_carmichael_analysis_rejects_a_non_carmichael_composite():
    result = carmichael_analysis("15", 100, 60)
    assert result["carmichael"] == "no"
    assert result["metrics"]["Korselt: (p − 1) | (n − 1) for every p"] == "no"


def test_carmichael_analysis_reports_a_factoring_timeout_as_inconclusive():
    result = carmichael_analysis(LARGE_PRIME_80 + "1", 100, 1)
    assert result["carmichael"] == "inconclusive"
    assert result["metrics"]["Factorization"] == "time budget exhausted"


def test_chernick_construction_starts_at_1729():
    # Chernick's k = 1 gives 7 * 13 * 19 = 1729, k = 6 gives 294409.
    result = chernick_search(1, 100, 100)
    assert result["rows"][0] == ["1", "7", "13", "19", "1729", "yes"]
    assert result["rows"][1][4] == "294409"
    assert len(result["rows"]) == 8


@pytest.mark.parametrize(
    ("start", "end", "limit"), [(0, 10, 10), (10, 1, 10), (1, 10, 0)]
)
def test_chernick_rejects_invalid_input(start, end, limit):
    with pytest.raises(ValueError):
        chernick_search(start, end, limit)


# ---------------------------------------------------------------------------
# Item 36: generalized repunits
# ---------------------------------------------------------------------------
def test_decimal_repunit_primes_have_the_known_indices():
    # Decimal repunit primes occur at n = 2, 19, 23, 317, 1031 (OEIS A004023).
    result = repunit_search(10, 1, 100, 100)
    assert [row[0] for row in result["rows"]] == ["2", "19", "23"]
    assert result["rows"][0][3] == "11"


def test_binary_repunits_are_the_mersenne_primes():
    # (2^n - 1)/(2 - 1) = 2^n - 1, so the hits are the Mersenne exponents.
    result = repunit_search(2, 1, 32, 100)
    assert [row[0] for row in result["rows"]] == ["2", "3", "5", "7", "13", "17", "19", "31"]


@pytest.mark.parametrize(("base", "start", "end"), [(1, 1, 10), (10, 0, 10), (10, 10, 1)])
def test_repunit_search_rejects_invalid_input(base, start, end):
    with pytest.raises(ValueError):
        repunit_search(base, start, end)


# ---------------------------------------------------------------------------
# Item 37: Sierpinski/Riesel explorer and covering sets
# ---------------------------------------------------------------------------
def test_sierpinski_candidate_search_is_inconclusive_when_exhausted():
    # 78557 is the smallest known Sierpinski number, so no n yields a prime.
    result = sierpinski_riesel_search("78557", "sierpinski", 60, 30)
    assert result["status"] == "exhausted"
    assert result["rows"] == []


def test_sierpinski_search_finds_a_prime_for_a_small_multiplier():
    # 3 * 2^1 + 1 = 7 is prime, so 3 is not a Sierpinski number.
    result = sierpinski_riesel_search("3", "sierpinski", 20, 30)
    assert result["status"] == "found"
    assert result["rows"][0][0] == "1" and result["rows"][0][3] == "7"


def test_selfridge_covering_set_proves_78557_is_sierpinski():
    # Selfridge's covering set {3, 5, 7, 13, 19, 37, 73} with period 36 covers
    # every exponent class of 78557 * 2^n + 1.
    result = covering_set_check("78557", "sierpinski", 36,
                                ["3", "5", "7", "13", "19", "37", "73"])
    assert result["covered"] is True
    assert len(result["rows"]) == 36
    assert all(row[1] != "uncovered" for row in result["rows"])
    assert result["metrics"]["Primes actually used"] == "3, 5, 7, 13, 19, 37, 73"


def test_riesel_covering_set_proves_509203_is_riesel():
    # Riesel's covering set {3, 5, 7, 13, 17, 241} with period 24 covers every
    # exponent class of 509203 * 2^n - 1 (Riesel 1956).
    result = covering_set_check("509203", "riesel", 24,
                                ["3", "5", "7", "13", "17", "241"])
    assert result["covered"] is True
    assert result["metrics"]["All primes have order dividing the period"] == "yes"


def test_covering_set_rejects_primes_whose_order_misses_the_period():
    # ord(2) is 8 modulo 17 and 24 modulo 241; neither divides 36.
    result = covering_set_check("509203", "riesel", 36,
                                ["3", "5", "7", "13", "17", "241"])
    assert result["covered"] is False
    assert result["metrics"]["Non-periodic candidates"] == "17, 241"


def test_incomplete_covering_set_leaves_classes_uncovered():
    result = covering_set_check("78557", "sierpinski", 36, ["3", "5"])
    assert result["covered"] is False
    assert any(row[1] == "uncovered" for row in result["rows"])


@pytest.mark.parametrize(
    ("k", "kind", "period"), [("0", "sierpinski", 36), ("78557", "other", 36),
                              ("78557", "sierpinski", 0)],
)
def test_covering_set_rejects_invalid_input(k, kind, period):
    with pytest.raises(ValueError):
        covering_set_check(k, kind, period, ["3"])


# ---------------------------------------------------------------------------
# Item 40: bi-twin chains and prime ladders
# ---------------------------------------------------------------------------
def test_bitwin_chains_start_at_six():
    # The first bi-twin chain of length 2 is 5/7, 11/13 (origin n = 6), followed
    # by 29/31, 59/61 (origin n = 30).
    result = bitwin_chain_search("2", "10000", 2, 100)
    assert result["rows"][0] == ["6", "2", "5/7 11/13"]
    assert result["rows"][1] == ["30", "2", "29/31 59/61"]


def test_bitwin_chain_limit_is_reported():
    result = bitwin_chain_search("2", "10000", 2, 2)
    assert result["truncated"] is True and len(result["rows"]) == 2


def test_prime_ladder_finds_a_shortest_path():
    result = prime_ladder("1373", "8017", 20)
    assert result["status"] == "found"
    assert result["rows"][0][1] == "1373"
    assert result["rows"][-1][1] == "8017"
    assert result["metrics"]["Ladder length (steps)"] == str(len(result["rows"]) - 1)


def test_prime_ladder_depth_limit_is_inconclusive():
    result = prime_ladder("1373", "8017", 2)
    assert result["status"] == "bound"
    assert result["rows"] == []


@pytest.mark.parametrize(
    ("start", "end"), [("11", "101"), ("1", "3"), ("1234567890123", "1234567890127")]
)
def test_prime_ladder_rejects_invalid_input(start, end):
    with pytest.raises(ValueError):
        prime_ladder(start, end, 10)


# ---------------------------------------------------------------------------
# Items 42 and 43: constrained and cryptographic prime construction
# ---------------------------------------------------------------------------
def test_constrained_prime_respects_a_residue_class():
    # 2147496031 is prime, has exactly 32 bits and satisfies p = 3 (mod 4).
    result = constrained_prime(32, "any", "4", "3", certificate=False, seed="12345")
    assert result["status"] == "proven"
    assert result["metrics"]["Prime"] == "2147496031"
    assert result["metrics"]["Residue condition satisfied"] == "yes"
    assert result["metrics"]["Actual bit length"] == "32"


def test_constrained_safe_prime_exposes_its_sophie_germain_prime():
    # 2147483783 = 2 * 1073741891 + 1 with both factors proven prime.
    result = constrained_prime(32, "safe", "1", "0", certificate=True, seed="7")
    assert result["metrics"]["Prime"] == "2147483783"
    assert result["metrics"]["Sophie Germain prime q = (p − 1)/2"] == "1073741891"
    assert result["metrics"]["Primality certificate"] == "valid"
    assert result["certificate"]


def test_constrained_strong_prime_uses_gordons_auxiliaries():
    # Gordon's algorithm builds p from auxiliary primes s, t and r = 2it + 1.
    result = constrained_prime(64, "strong", "1", "0", certificate=False, seed="123456789")
    assert result["status"] == "proven"
    assert result["metrics"]["Prime"] == "9224523765532005097"
    assert result["metrics"]["Actual bit length"] == "64"
    assert result["metrics"]["Gordon auxiliary prime r = 2it + 1"] == "18562009"


def test_constrained_prime_candidate_limit_is_inconclusive():
    result = constrained_prime(32, "any", "1", "0", seed="12345", candidate_limit=1)
    assert result["status"] == "bound"
    assert "Prime" not in result["metrics"]


def test_constrained_prime_uses_the_system_csprng_by_default():
    first = constrained_prime(24, "any", "1", "0")
    second = constrained_prime(24, "any", "1", "0")
    assert first["metrics"]["Search seed"] == "CSPRNG (secrets.randbits)"
    assert first["status"] == "proven" and second["status"] == "proven"


@pytest.mark.parametrize(
    ("bits", "kind", "modulus", "residue"),
    [(4, "any", "1", "0"), (64, "other", "1", "0"), (64, "any", "4", "7"),
     (16, "strong", "1", "0")],
)
def test_constrained_prime_rejects_invalid_input(bits, kind, modulus, residue):
    with pytest.raises(ValueError):
        constrained_prime(bits, kind, modulus, residue)


# ---------------------------------------------------------------------------
# Item 130: educational proof viewer
# ---------------------------------------------------------------------------
def test_lucas_sequence_rejects_a_zero_discriminant():
    # P = 2, Q = 1 gives D = 0; PARI/GP refuses the degenerate sequence.
    with pytest.raises(PrimeEngineError):
        pseudoprime_taxonomy("561", ["2"], 2, 1, selfridge=False)


def test_lucas_lehmer_steps_prove_m13_and_refute_m11():
    # M13 = 8191 is prime; the iteration starts 14, 194, 4870, 3953, 5970 and
    # ends at s_11 = 0.
    prime = lucas_lehmer_steps(13, 5)
    assert prime["verdict"] == "proven prime"
    assert [row[1] for row in prime["rows"][:5]] == ["14", "194", "4870", "3953", "5970"]
    assert prime["rows"][-1] == ["11", "0"]
    # M11 = 2047 = 23 * 89 is composite.
    composite = lucas_lehmer_steps(11, 20)
    assert composite["verdict"] == "proven composite"
    assert composite["rows"][-1][1] != "0"


@pytest.mark.parametrize(("exponent", "show_limit"), [(1, 10), (4, 10), (13, -1)])
def test_lucas_lehmer_steps_reject_invalid_input(exponent, show_limit):
    with pytest.raises((ValueError, PrimeEngineError)):
        lucas_lehmer_steps(exponent, show_limit)


def test_ecpp_steps_expand_a_certificate_chain():
    # M127 = 2^127 - 1 is prime and needs a genuine Atkin-Morain descent.
    result = ecpp_steps(MERSENNE_127, 120)
    assert result["verdict"] == "proven prime"
    assert int(result["metrics"]["Descent steps"]) >= 1
    assert result["metrics"]["Certificate re-verified"] == "yes"
    assert result["rows"][0][1] == MERSENNE_127


def test_ecpp_steps_report_small_inputs_without_a_chain():
    result = ecpp_steps("104729", 60)
    assert result["metrics"]["Below the 2^64 deterministic threshold"] == "yes"
    assert result["verdict"] == "proven prime"
    assert result["rows"] == []


def test_ecpp_steps_reject_invalid_input():
    with pytest.raises(ValueError):
        ecpp_steps("1", 60)


# ---------------------------------------------------------------------------
# HTTP API
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("endpoint", "payload", "expected"),
    [
        ("compare", {"number": "561", "bases": ["2"], "budget_seconds": 30},
         ("verdict", "proven composite")),
        ("deterministic-witnesses", {"number": "3215031751"},
         ("verdict", "proven composite")),
        ("pocklington", {"number": "104729"}, ("verdict", "proven prime")),
        ("pratt", {"number": "104729"}, ("verdict", "proven prime")),
        ("verify-certificate",
         {"kind": "pocklington", "certificate": POCKLINGTON_CERTIFICATE}, ("valid", True)),
        ("proth", {"k": "5", "exponent": 3, "base": 2}, ("verdict", "proven prime")),
        ("carmichael", {"number": "561", "base_limit": 1000}, ("carmichael", "yes")),
        ("covering-set", {"k": "78557", "period": 36,
                          "candidates": ["3", "5", "7", "13", "19", "37", "73"]},
         ("covered", True)),
        ("lucas-lehmer-steps", {"exponent": 13, "show_limit": 5},
         ("verdict", "proven prime")),
    ],
)
def test_primality_lab_api_saves_a_report(endpoint, payload, expected, tmp_path, monkeypatch):
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    response = local_client().post("/api/primality-lab/" + endpoint, json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result[expected[0]] == expected[1]
    report = (tmp_path / result["output_file"]).read_text()
    assert result["note"].split(".")[0] in report
    assert result["engine"] == "PARI/GP"


def test_primality_lab_api_report_is_downloadable(tmp_path, monkeypatch):
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    client = local_client()
    response = client.post("/api/primality-lab/chernick",
                           json={"k_start": 1, "k_end": 100, "limit": 10})
    assert response.status_code == 200
    result = response.json()
    assert "1729" in " ".join(result["rows"][0])
    download = client.get("/api/outputs/" + result["output_file"])
    assert download.status_code == 200
    assert download.text == (tmp_path / result["output_file"]).read_text()


@pytest.mark.parametrize(
    ("endpoint", "payload"),
    [
        ("compare", {"number": "1", "bases": ["2"]}),
        ("compare", {"number": "561", "bases": []}),
        ("deterministic-witnesses", {"number": "not an integer"}),
        ("pocklington", {"number": "2"}),
        ("verify-certificate", {"kind": "pratt", "certificate": "quit()"}),
        ("proth", {"k": "0", "exponent": 3, "base": 2}),
        ("taxonomy", {"number": "2048", "bases": ["2"]}),
        ("covering-set", {"k": "78557", "period": 0, "candidates": ["3"]}),
        ("prime-ladder", {"start_prime": "11", "end_prime": "101"}),
        ("constrained-prime", {"bits": 4}),
        ("constrained-prime", {"bits": 64, "seed": "-5"}),
        ("lucas-sequence", {"number": "8192"}),
        ("lucas-lehmer-steps", {"exponent": 4}),
        ("ecpp-steps", {"number": "1"}),
    ],
)
def test_primality_lab_api_failures_do_not_save(endpoint, payload, tmp_path, monkeypatch):
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    response = local_client().post("/api/primality-lab/" + endpoint, json=payload)
    assert response.status_code == 422, response.text
    assert list(tmp_path.iterdir()) == []


def test_primality_lab_routes_require_the_session_token():
    client = TestClient(app, base_url="http://127.0.0.1")
    response = client.post("/api/primality-lab/compare", json={"number": "13"})
    assert response.status_code == 403
