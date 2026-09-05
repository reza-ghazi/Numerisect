import subprocess

import pytest

from numerisect import prime_manipulation as pm
from numerisect.primes import PrimeEngineError


def test_batch_order_duplicates_and_nonpositive_integers():
    result = pm.batch_primality('13, 561; 1\n0 -7 13 170141183460469231731687303715884105727')
    assert [row[1] for row in result['rows']] == [
        'Proven prime', 'Composite', 'Neither prime nor composite',
        'Neither prime nor composite', 'Neither prime nor composite',
        'Proven prime', 'Proven prime',
    ]
    assert result['rows'][0] == result['rows'][5]
    assert pm.batch_primality('13', 'fast')['rows'] == [['13', 'Probable prime']]


@pytest.mark.parametrize('text', ['', '2^127-1', '2;quit()', '2,' , '1 ' * 1001])
def test_batch_invalid_input(text):
    with pytest.raises(ValueError):
        pm.batch_primality(text)


def test_progression_pagination_and_sum():
    first = pm.progression_primes('1', '30', '4', '-3', limit=2)
    assert first['rows'] == [['5'], ['13']]
    assert first['metrics']['Sum of returned primes'] == '18'
    assert first['metrics']['Normalized residue'] == '1'
    assert first['next_start'] == '17'
    second = pm.progression_primes(first['next_start'], '30', '4', '1')
    assert second['rows'] == [['17'], ['29']]
    assert second['next_start'] is None


@pytest.mark.parametrize('start,end,m,r,expected', [
    ('-10', '7', '1', '0', [['2'], ['3'], ['5'], ['7']]),
    ('1', '100', '6', '3', [['3']]),
    ('4', '100', '6', '3', []),
    ('1', '100', '8', '4', []),
    ('1', '100', '2', '0', [['2']]),
    ('-10', '-2', '1', '0', []),
    ('170141183460469231731687303715884105727',
     '170141183460469231731687303715884105727', '1', '0',
     [['170141183460469231731687303715884105727']]),
])
def test_progression_boundaries(start, end, m, r, expected):
    assert pm.progression_primes(start, end, m, r)['rows'] == expected


def test_progression_resource_limit():
    with pytest.raises(PrimeEngineError, match='1,000,000'):
        pm.progression_primes('2', '1000002', '1', '0')


@pytest.mark.parametrize('p,a,e,op,expected', [
    ('7', '2', '2', 'inverse', [['4']]),
    ('7', '-2', '2', 'inverse', [['3']]),
    ('7', '2', '-1', 'power', [['4']]),
    ('7', '2', '100000000000000000000', 'power', [['2']]),
    ('7', '0', '0', 'power', [['1']]),
    ('7', '2', '2', 'order', [['3']]),
    ('7', '2', '2', 'roots', [['3'], ['4']]),
    ('7', '3', '2', 'roots', []),
    ('7', '0', '2', 'roots', [['0']]),
    ('2', '1', '2', 'roots', [['1']]),
    ('2', '0', '2', 'roots', [['0']]),
    ('2', '1', '2', 'generator', [['1']]),
    ('170141183460469231731687303715884105727', '2', '2', 'inverse',
     [['85070591730234615865843651857942052864']]),
])
def test_modular_operations(p, a, e, op, expected):
    assert pm.prime_modular(p, a, e, op)['rows'] == expected


def test_primitive_root_order():
    root = pm.prime_modular('101', '1', operation='generator')['rows'][0][0]
    assert pm.prime_modular('101', root, operation='order')['rows'] == [['100']]


@pytest.mark.parametrize('p,a,e,op', [
    ('15', '2', '2', 'inverse'), ('-7', '2', '2', 'power'),
    ('1', '2', '2', 'roots'), ('7', '7', '2', 'inverse'),
    ('7', '0', '2', 'order'), ('7', '0', '-1', 'power'),
])
def test_modular_undefined_operations(p, a, e, op):
    with pytest.raises(PrimeEngineError):
        pm.prime_modular(p, a, e, op)


def test_incomplete_output_is_not_a_negative_result(monkeypatch):
    monkeypatch.setattr(pm, '_run_gp', lambda *a, **kw: ['ROW:13|1'])
    with pytest.raises(PrimeEngineError, match='incomplete'):
        pm.batch_primality('13')


def test_engine_timeout(monkeypatch):
    from numerisect import primes
    def timeout(*args, **kwargs):
        assert kwargs['timeout'] == 1
        raise subprocess.TimeoutExpired('gp', 1)
    monkeypatch.setattr(primes.subprocess, 'run', timeout)
    with pytest.raises(PrimeEngineError, match='1-second'):
        pm.prime_modular('7', '2', timeout=1)
