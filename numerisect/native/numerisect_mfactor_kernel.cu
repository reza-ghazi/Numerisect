/* SPDX-License-Identifier: GPL-3.0-or-later
 *
 * The Mersenne trial-factoring device kernel, and nothing else.
 *
 * This file is deliberately free of #include directives and host code so that it can be
 * compiled two ways from one source: by nvcc, when a CUDA toolkit is installed, and by
 * NVRTC at run time, when only the driver and the pip CUDA runtime are present. NVRTC
 * has no standard headers, so anything it cannot see must not appear here.
 *
 * MONTGOMERY ARITHMETIC AND THE 2^63 LIMIT
 * ----------------------------------------
 * A 128-bit division per multiply would waste the device. Montgomery multiplication
 * replaces it with two 64-bit multiplies and a shift. The usual REDC bound applies: the
 * intermediate sum must not overflow 64 bits, so q < 2^63. Wider candidates are the
 * caller's problem and must be sent to the CPU helper, which handles them with GMP.
 *
 * WHAT A HIT MEANS
 * ----------------
 * 2^order = 1 (mod q) makes q a divisor of 2^order - 1. It does NOT make q prime, and
 * composite divisors do occur: 2047 = 23 * 89 divides 2^11 - 1 and the kernel reports it
 * correctly. The pipeline sieves those out beforehand and PARI/GP confirms primality
 * afterwards. This kernel is a filter, not an authority.
 */

typedef unsigned long long numerisect_u64;

__device__ __forceinline__ numerisect_u64 numerisect_mont_inv(numerisect_u64 q) {
  /* -q^-1 mod 2^64 by Newton iteration; exact after six doublings from 3 bits. */
  numerisect_u64 inv = 1;
  for (int i = 0; i < 6; i++) inv *= 2 - q * inv;
  return (numerisect_u64)0 - inv;
}

__device__ __forceinline__ numerisect_u64 numerisect_mont_mul(
    numerisect_u64 a, numerisect_u64 b, numerisect_u64 q, numerisect_u64 qinv) {
  const numerisect_u64 lo = a * b;
  const numerisect_u64 hi = __umul64hi(a, b);
  const numerisect_u64 m = lo * qinv;
  const numerisect_u64 mq_hi = __umul64hi(m, q);
  /* lo + m*q vanishes in the low word by construction, so only the carry survives. */
  const numerisect_u64 carry = (lo != 0) ? 1ULL : 0ULL;
  numerisect_u64 t = hi + mq_hi + carry;
  if (t >= q) t -= q;
  return t;
}

__device__ __forceinline__ bool numerisect_divides(numerisect_u64 q,
                                                   numerisect_u64 order) {
  const numerisect_u64 qinv = numerisect_mont_inv(q);
  /* R mod q with R = 2^64, computed as (2^64 - q) % q to stay inside 64 bits. */
  const numerisect_u64 one = ((numerisect_u64)0 - q) % q;
  numerisect_u64 base = (one << 1) % q;   /* 2 in the Montgomery domain; q < 2^63 */
  numerisect_u64 result = one;
  numerisect_u64 e = order;
  while (e) {
    if (e & 1) result = numerisect_mont_mul(result, base, q, qinv);
    base = numerisect_mont_mul(base, base, q, qinv);
    e >>= 1;
  }
  return result == one;
}

extern "C" __global__ void numerisect_mfactor_kernel(
    const numerisect_u64 *ks, unsigned int count, numerisect_u64 order,
    numerisect_u64 *hits, unsigned int *hit_count, unsigned int capacity) {
  const unsigned int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i >= count) return;
  const numerisect_u64 k = ks[i];
  const numerisect_u64 q = 2ULL * k * order + 1ULL;
  if (numerisect_divides(q, order)) {
    const unsigned int slot = atomicAdd(hit_count, 1u);
    if (slot < capacity) {
      hits[2 * slot] = q;
      hits[2 * slot + 1] = k;
    }
  }
}


/* ---------------------------------------------------------------------------------
 * DEVICE-SIDE SIEVING
 *
 * The first GPU build sieved on the host, gathered the survivors, and copied them to
 * the device. Benchmarked against the C helper it came out slower, and parallelising
 * the host sieve only narrowed the gap: the cost was never the arithmetic, it was
 * moving candidates across the bus. Roughly thirty 64-bit Montgomery squarings is not
 * enough work to pay for the transfer.
 *
 * These two kernels remove the transfer entirely. The segment bitmap is created on the
 * device, marked on the device, and consumed on the device; nothing but the small prime
 * table and the handful of hits ever crosses PCIe.
 * ------------------------------------------------------------------------------- */

/* Precompute, for each small prime r, the residue k0 with q = 2*k0*d + 1 = 0 (mod r).
 *
 * One thread per prime, and each does one Fermat inverse. Splitting this out means the
 * sieve kernel never repeats the inversion, which matters once the sieve is decomposed
 * across many more threads than there are primes. */
extern "C" __global__ void numerisect_residue_kernel(
    const unsigned int *primes, unsigned int prime_count, numerisect_u64 order,
    unsigned int *residues) {
  const unsigned int index = blockIdx.x * blockDim.x + threadIdx.x;
  if (index >= prime_count) return;
  const numerisect_u64 r = primes[index];
  const numerisect_u64 a = (2ULL % r) * (order % r) % r;
  if (a == 0) {                     /* r divides 2d; no k is ever hit */
    residues[index] = 0xFFFFFFFFu;
    return;
  }
  numerisect_u64 inv = 1, b = a % r, e = r - 2;
  while (e) {
    if (e & 1) inv = (inv * b) % r;
    b = (b * b) % r;
    e >>= 1;
  }
  residues[index] = (unsigned int)((r - inv) % r);
}

/* Mark every k in [base, base+length) whose q = 2kd+1 is divisible by a small prime.
 *
 * WHY THE WORK IS SPLIT BY (PRIME, CHUNK) AND NOT BY PRIME
 * -------------------------------------------------------
 * The obvious decomposition gives each thread one prime and lets it walk the whole
 * segment. That is catastrophically unbalanced: in a 67-million-entry segment the thread
 * holding r = 3 performs 22 million serialized global writes while the thread holding a
 * prime near the bound performs about seventy. Measured, that version ran at 0.42x the
 * CPU helper, worse than sieving on the host.
 *
 * Here each thread owns one (prime, chunk) pair, so a small prime's work is spread over
 * every chunk instead of landing on one thread, and writes stay inside a narrow window.
 * Threads write only the value 1, so overlapping progressions race benignly. */
extern "C" __global__ void numerisect_sieve_kernel(
    unsigned char *dead, numerisect_u64 base, numerisect_u64 length,
    numerisect_u64 order, const unsigned int *primes, const unsigned int *residues,
    unsigned int prime_count, numerisect_u64 chunk, numerisect_u64 chunk_count,
    numerisect_u64 montgomery_k) {
  const numerisect_u64 total = (numerisect_u64)prime_count * chunk_count;
  const numerisect_u64 stride = (numerisect_u64)gridDim.x * blockDim.x;
  for (numerisect_u64 item = (numerisect_u64)blockIdx.x * blockDim.x + threadIdx.x;
       item < total; item += stride) {
    const unsigned int pi = (unsigned int)(item / chunk_count);
    const numerisect_u64 ci = item % chunk_count;
    const unsigned int residue = residues[pi];
    if (residue == 0xFFFFFFFFu) continue;
    const numerisect_u64 r = primes[pi];
    const numerisect_u64 from = ci * chunk;
    if (from >= length) continue;
    numerisect_u64 to = from + chunk;
    if (to > length) to = length;

    /* First index at or after `from` that is congruent to the residue modulo r. */
    const numerisect_u64 offset = (base + from) % r;
    numerisect_u64 first = residue >= offset ? residue - offset : residue + r - offset;
    for (numerisect_u64 j = from + first; j < to; j += r) {
      const numerisect_u64 k = base + j;
      /* q may itself be the sieving prime, and that q is a genuine candidate. */
      if (k <= montgomery_k && 2ULL * k * order + 1ULL == r) continue;
      dead[j] = 1;
    }
  }
}

/* Test every surviving k in the segment, reading the bitmap in place.
 *
 * Candidates at or above the Montgomery bound are counted as deferred rather than
 * tested, because REDC cannot cover them. They are never silently dropped: an untested
 * range must not be reported as an absence of factors. */
extern "C" __global__ void numerisect_scan_kernel(
    const unsigned char *dead, numerisect_u64 base, numerisect_u64 length,
    numerisect_u64 order, numerisect_u64 montgomery_k, numerisect_u64 *hits,
    unsigned int *hit_count, unsigned int capacity, unsigned long long *deferred,
    unsigned long long *tested) {
  const numerisect_u64 stride = (numerisect_u64)gridDim.x * blockDim.x;
  for (numerisect_u64 j = (numerisect_u64)blockIdx.x * blockDim.x + threadIdx.x;
       j < length; j += stride) {
    if (dead[j]) continue;
    const numerisect_u64 k = base + j;
    /* Wider candidates are not skipped: the two-limb kernel takes them. */
    if (k > montgomery_k) continue;
    const numerisect_u64 q = 2ULL * k * order + 1ULL;
    const numerisect_u64 residue = q & 7ULL;
    if (residue != 1 && residue != 7) continue;
    atomicAdd(tested, 1ULL);
    if (numerisect_divides(q, order)) {
      const unsigned int slot = atomicAdd(hit_count, 1u);
      if (slot < capacity) {
        hits[2 * slot] = q;
        hits[2 * slot + 1] = k;
      }
    }
  }
}


/* ---------------------------------------------------------------------------------
 * WIDE CANDIDATES: 128-BIT MONTGOMERY
 *
 * Montgomery REDC on a single 64-bit limb needs q < 2^63, and at a Mersenne exponent
 * near 10^9 that ceiling is reached around k = 4.6 billion. Past it the device had
 * nothing to offer and the range fell back to GMP on the CPU, roughly a hundred times
 * slower per candidate.
 *
 * These routines carry the same algorithm on two limbs, so the device covers q < 2^127.
 * At the same exponent that is k up to about 8*10^28, which is not a practical limit.
 *
 * The arithmetic is CIOS Montgomery multiplication for a two-limb odd modulus, the
 * standard formulation. R = 2^128, and R mod n is built by doubling 1 a hundred and
 * twenty-eight times rather than by reducing 2^128, because repeated subtraction there
 * runs about 2^128/n times and does not terminate in practice for a small n.
 * ------------------------------------------------------------------------------- */

typedef struct { numerisect_u64 lo, hi; } numerisect_u128;

/* (carry, sum) = a*b + c + carry_in, on 64-bit limbs. */
__device__ __forceinline__ void numerisect_muladd(
    numerisect_u64 a, numerisect_u64 b, numerisect_u64 c, numerisect_u64 cin,
    numerisect_u64 *carry, numerisect_u64 *sum) {
  const numerisect_u64 lo = a * b;
  const numerisect_u64 hi = __umul64hi(a, b);
  const numerisect_u64 s1 = lo + c;
  const numerisect_u64 c1 = (s1 < lo) ? 1ULL : 0ULL;
  const numerisect_u64 s2 = s1 + cin;
  const numerisect_u64 c2 = (s2 < s1) ? 1ULL : 0ULL;
  *sum = s2;
  *carry = hi + c1 + c2;
}

__device__ __forceinline__ bool numerisect_ge128(numerisect_u128 a, numerisect_u128 b) {
  return a.hi > b.hi || (a.hi == b.hi && a.lo >= b.lo);
}

__device__ __forceinline__ numerisect_u128 numerisect_sub128(numerisect_u128 a,
                                                             numerisect_u128 b) {
  numerisect_u128 out;
  const numerisect_u64 borrow = (a.lo < b.lo) ? 1ULL : 0ULL;
  out.lo = a.lo - b.lo;
  out.hi = a.hi - b.hi - borrow;
  return out;
}

/* CIOS Montgomery multiply for a two-limb odd modulus n, with np = -n^-1 mod 2^64. */
__device__ __forceinline__ numerisect_u128 numerisect_mont_mul128(
    numerisect_u128 a, numerisect_u128 b, numerisect_u128 n, numerisect_u64 np) {
  numerisect_u64 t[4] = {0ULL, 0ULL, 0ULL, 0ULL};
  const numerisect_u64 av[2] = {a.lo, a.hi};
  const numerisect_u64 bv[2] = {b.lo, b.hi};
  const numerisect_u64 nv[2] = {n.lo, n.hi};
  for (int i = 0; i < 2; i++) {
    numerisect_u64 C = 0, S;
    for (int j = 0; j < 2; j++) {
      numerisect_muladd(av[j], bv[i], t[j], C, &C, &S);
      t[j] = S;
    }
    numerisect_u64 sum = t[2] + C;
    numerisect_u64 c2 = (sum < t[2]) ? 1ULL : 0ULL;
    t[2] = sum;
    t[3] = c2;
    C = 0;
    const numerisect_u64 m = t[0] * np;
    numerisect_muladd(m, nv[0], t[0], 0, &C, &S);   /* S is zero by construction */
    for (int j = 1; j < 2; j++) {
      numerisect_muladd(m, nv[j], t[j], C, &C, &S);
      t[j - 1] = S;
    }
    sum = t[2] + C;
    c2 = (sum < t[2]) ? 1ULL : 0ULL;
    t[1] = sum;
    t[2] = t[3] + c2;
  }
  numerisect_u128 out;
  out.lo = t[0];
  out.hi = t[1];
  /* The result is below 2n, so at most one conditional subtraction is needed. */
  if (t[2] || numerisect_ge128(out, n)) out = numerisect_sub128(out, n);
  return out;
}

/* Is 2^order = 1 (mod q), for odd q < 2^127 given as two limbs? */
__device__ __forceinline__ bool numerisect_divides128(numerisect_u128 q,
                                                      numerisect_u64 order) {
  numerisect_u64 np = 1;
  for (int i = 0; i < 6; i++) np *= 2 - q.lo * np;
  np = (numerisect_u64)0 - np;

  /* R mod q, by doubling 1 exactly 128 times. */
  numerisect_u128 one;
  one.lo = 1ULL;
  one.hi = 0ULL;
  for (int i = 0; i < 128; i++) {
    const numerisect_u64 top = one.hi >> 63;
    one.hi = (one.hi << 1) | (one.lo >> 63);
    one.lo <<= 1;
    if (top || numerisect_ge128(one, q)) one = numerisect_sub128(one, q);
  }

  /* 2 in the Montgomery domain is 2R mod q. */
  numerisect_u128 base = one;
  const numerisect_u64 carry = (base.lo + base.lo < base.lo) ? 1ULL : 0ULL;
  base.lo = one.lo + one.lo;
  base.hi = one.hi + one.hi + carry;
  if (numerisect_ge128(base, q)) base = numerisect_sub128(base, q);

  numerisect_u128 result = one;
  numerisect_u64 e = order;
  while (e) {
    if (e & 1) result = numerisect_mont_mul128(result, base, q, np);
    base = numerisect_mont_mul128(base, base, q, np);
    e >>= 1;
  }
  return result.lo == one.lo && result.hi == one.hi;
}

/* Test the survivors whose candidate exceeds the single-limb bound.
 *
 * Hits are written as (q low, q high, k) triples. Nothing is deferred here: this kernel
 * exists precisely so that no part of a requested range goes untested. */
extern "C" __global__ void numerisect_scan_wide_kernel(
    const unsigned char *dead, numerisect_u64 base, numerisect_u64 length,
    numerisect_u64 order, numerisect_u64 narrow_k, numerisect_u64 wide_k,
    numerisect_u64 *hits, unsigned int *hit_count, unsigned int capacity,
    unsigned long long *tested, unsigned long long *deferred) {
  const numerisect_u64 stride = (numerisect_u64)gridDim.x * blockDim.x;
  for (numerisect_u64 j = (numerisect_u64)blockIdx.x * blockDim.x + threadIdx.x;
       j < length; j += stride) {
    if (dead[j]) continue;
    const numerisect_u64 k = base + j;
    if (k <= narrow_k) continue;              /* the single-limb kernel took this one */
    if (k > wide_k) {                         /* beyond 2^127; nothing here can test it */
      atomicAdd(deferred, 1ULL);
      continue;
    }
    /* q = 2*k*order + 1 as a 128-bit value. */
    const numerisect_u64 two_k = k << 1;      /* k < 2^63 here, so this cannot overflow */
    numerisect_u128 q;
    q.lo = two_k * order;
    q.hi = __umul64hi(two_k, order);
    const numerisect_u64 low = q.lo;
    q.lo += 1ULL;
    if (q.lo < low) q.hi += 1ULL;
    const numerisect_u64 residue = q.lo & 7ULL;
    if (residue != 1 && residue != 7) continue;
    atomicAdd(tested, 1ULL);
    if (numerisect_divides128(q, order)) {
      const unsigned int slot = atomicAdd(hit_count, 1u);
      if (slot < capacity) {
        hits[3 * slot] = q.lo;
        hits[3 * slot + 1] = q.hi;
        hits[3 * slot + 2] = k;
      }
    }
  }
}
