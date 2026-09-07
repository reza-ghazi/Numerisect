# Riemann zeta tools

Numerisect provides native, arbitrary-precision Riemann-zeta analysis through
a compiled C helper linked to FLINT/Arb. Python validates requests and parses
tagged native output; JavaScript renders results and charts. Neither interface
layer evaluates the zeta function.

## Opening the workspace

Start the source checkout with `./run.sh` and select **Riemann zeta**, or open
<http://127.0.0.1:8765/#zeta>. Zeta uses its own workspace, separate from the
133 individually routed Prime Tools pages. Zeta itself has 22 individually
routed operations. Choose an operation, enter its
precision and any available thread settings, then submit it. The zeta result
panel contains the native result, exact report path, and download control.
Restart the server and refresh the browser after source updates.

The twelve explicit-formula, zero-statistics, and L-function operations are
documented separately in [Zeta lab](ZETA_LAB.md).

The versioned user installer and Linux/WSL/macOS prerequisites are documented
in [Installation and versioning](INSTALLATION.md). FLINT development headers
are required for the zeta helper.

## Available operations

| Tool | Native operation | Result semantics |
|---|---|---|
| Evaluate `ζ(s)` | `acb_zeta` | Rigorous Arb enclosures for real part, imaginary part, magnitude, and argument |
| Hardy/Riemann–Siegel `Z(t)` | `acb_dirichlet_hardy_z` | Rigorous real enclosure on the critical line |
| Completed xi / Dirichlet eta | `acb_dirichlet_xi`, `acb_dirichlet_eta` | Rigorous complex enclosures and analytic continuation |
| Functional equation | Independent FLINT/Arb evaluation of both sides | Verified only when the resulting complex balls overlap |
| Stieltjes constants | `acb_dirichlet_stieltjes` | Rigorous enclosure for `γ_n` in the Laurent expansion at 1 |
| Gram point | `acb_dirichlet_gram_point` | Rigorous enclosure for one requested `g_n` |
| Consecutive zeros | `acb_dirichlet_hardy_z_zeros` | Rigorous intervals for consecutive Hardy Z zeros on `Re(s)=1/2` |
| Count zeros through T | `acb_dirichlet_zeta_nzeros` | Exact uniquely isolated count using FLINT's Turing method |
| Critical-line plot | Parallel `acb_zeta` samples | Exploratory chart of enclosure midpoints |
| Argand plot | The same native critical-line samples | Exploratory complex trace of enclosure midpoints |
| Complex heatmap | Parallel `acb_zeta` grid samples | Exploratory magnitude/phase colors from enclosure midpoints |

The evaluation endpoint rejects `s=1`, where zeta has a pole. A heatmap that
contains that point preserves it as JSON `null` and draws it black instead of
emitting a non-standard NaN value.

## Certification boundaries

The imported research prototype included an incomplete custom approximation
described as Riemann–Siegel and a configurable zero-count comparison described
as Turing certification. Numerisect does not expose those claims. The omitted
remainder in an asymptotic formula and user-chosen heuristic bounds do not
constitute a proof.

Instead, Numerisect delegates certified work to FLINT/Arb. Evaluation values
are printed as explicit balls, such as `[midpoint +/- radius]`. Zero ordinates
include their radius and interval. The zero-count endpoint succeeds only when
FLINT isolates a unique integer count; otherwise it asks the user to increase
precision or move the endpoint.

Plots are intentionally labeled exploratory. Native Arb arithmetic computes
each point, but a finite chart displays only midpoint samples and cannot prove
behavior between pixels.

## Threads, precision, and limits

Thread controls default to all detected logical CPUs. FLINT's zero routines use
its thread pool; line and heatmap sampling use OpenMP with independent Arb
objects per worker. The request accepts 16–1,000 decimal digits of precision,
up to 1,000 zero intervals, up to 10,000 line samples, and heatmap dimensions
up to 500 × 500. These are interface/resource limits, not mathematical
fixed-precision limits in FLINT.

Every successful operation is saved automatically in `output/`; the result
panel shows the exact `output/<filename>.txt` path and a download button.

## API examples

First create the local session cookie described in
[the security model](SECURITY_MODEL.md).

```bash
curl --cookie numerisect.cookies -X POST http://127.0.0.1:8765/api/zeta/evaluate \
  -H 'Content-Type: application/json' \
  -d '{"sigma":"0.5","ordinate":"14.134725","precision":50}'

curl --cookie numerisect.cookies -X POST http://127.0.0.1:8765/api/zeta/zeros \
  -H 'Content-Type: application/json' \
  -d '{"start_index":"1","count":10,"precision":50,"threads":8}'

curl --cookie numerisect.cookies -X POST http://127.0.0.1:8765/api/zeta/count \
  -H 'Content-Type: application/json' \
  -d '{"height":"100","precision":50,"threads":8}'

curl --cookie numerisect.cookies -X POST http://127.0.0.1:8765/api/zeta/functional-equation \
  -H 'Content-Type: application/json' \
  -d '{"sigma":"0.25","ordinate":"12","precision":50}'
```

Plot endpoints are `/api/zeta/line` and `/api/zeta/heatmap`. Their output
reports contain the native samples used by the browser.

## Implementation map

| File | Responsibility |
|---|---|
| `numerisect/native/numerisect_zeta.c` | FLINT/Arb evaluation, zero isolation/counting, OpenMP sampling, tagged output |
| `numerisect/native_tools.py` | Detect FLINT and compile the helper into the managed tools directory |
| `numerisect/zeta.py` | Validation, subprocess boundary, and strict result parsing |
| `numerisect/main.py` | HTTP models, endpoints, error mapping, and report persistence |
| `numerisect/static/index.html` | Zeta workspace and precision/thread controls |
| `numerisect/static/app.js` | Result presentation and canvas drawing only |
| `tests/test_zeta.py` | Known values, certified zeros/count, sampling, pole, and validation tests |
