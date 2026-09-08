# GGNFS lattice sievers

*Numerisect 0.6.0*

YAFU performs the number field sieve by calling the GGNFS lattice sievers, the
`gnfs-lasieve4I<index>e` programs. It does not contain a lattice siever of its own. Without
them YAFU cannot sieve at all.

## The failure this page exists to prevent

A YAFU run with no siever directory does not say "sievers missing". It says this, once per
worker thread, and then exits non-zero having found nothing:

```text
nfs: could not open output file rels19_19.dat, possibly bad path to siever
nfs: could not open output file rels10_10.dat, possibly bad path to siever
...
Application error: YAFU exited with status 1
```

On a hundred-digit input that reads as an engine crash rather than a missing dependency.
Worse, the surrounding output prints a "factorization" of the input as itself, which is not
a factorization at all. Numerisect rejects that result because the returned factors do not
reconstruct the input, so it fails the job rather than reporting nonsense, but the
underlying cause is easy to misread.

Numerisect now discovers the sievers and passes the directory to YAFU on every run, so this
failure mode requires the binaries to be genuinely absent.

## lasieve4 and lasieve5

Two lines of these sievers are in circulation.

**lasieve4** is the long-standing GGNFS siever. Numerisect pins it in
`engine_manifest.toml` and the installer builds it from source at that commit, like every
other managed engine.

**lasieve5** is a newer line distributed with recent YAFU releases, including builds
targeting AVX-512 that are reported to sieve appreciably faster on hardware supporting
those instructions. It ships as prebuilt binaries. Numerisect will **use** a lasieve5
directory that is already present, and reports it as such, but never downloads it: the
project builds engines from pinned source and does not fetch unverified binaries.

Both lines use the same `gnfs-lasieve4I<index>e` file names, so the file name cannot tell
them apart. Numerisect reports the line from the directory the binaries were found in and
says that is what it is doing, rather than claiming to have fingerprinted the build.

## Why every siever is executed once

An AVX-512 siever on a CPU without AVX-512 dies with an illegal instruction the moment it
is asked to work. Nothing about the path or the file name reveals this; the configuration
looks correct and fails at run time.

Numerisect therefore runs each discovered siever once with no job file. A working siever
complains about the missing file and exits. One built for instructions this machine lacks
is killed by `SIGILL`, and is reported as unusable rather than handed to YAFU.

This is not hypothetical. A `yafu.ini` in the wild pointed `ggnfs_dir` at
`factor/lasieve5_64/bin/avx512/` on a machine whose CPU has no AVX-512, so the setting
would have failed twice over: the path did not exist, and the binaries could not have run
if it had.

## Search order

The first directory holding at least one siever that runs here is selected:

1. `NUMERISECT_GGNFS_DIR`, if set
2. Numerisect's managed tools directory, `data/tools/bin`
3. `~/ggnfs/bin`
4. `/usr/local/bin`
5. `/usr/bin`

Nothing outside that list is searched. A directory whose binaries all fail to run is
skipped rather than passed on, because YAFU would accept it and then fail mid-sieve.

## Which index gets used

The index is the lattice sieve area parameter; a larger index suits a harder
factorization. **YAFU chooses the index for a given difficulty, and Numerisect does not
override that choice.** The report lists which indices are available, because the largest
one present bounds the difficulty YAFU can attempt.

## If no siever is available

This disables the number field sieve in YAFU and nothing else. YAFU still performs trial
division, Pollard rho, P−1, P+1, ECM and the self-initializing quadratic sieve, which
covers inputs up to roughly a hundred digits comfortably. **CADO-NFS is a completely
independent implementation of the number field sieve and does not use these binaries**, so
large factorizations remain available through it.

## Route

```text
GET /api/factor-lab/sievers   what was found, what runs here, and what YAFU will be given
```

The report includes a SHA-256 prefix for each binary, so a siever set can be identified
across machines and a swapped build is visible.
