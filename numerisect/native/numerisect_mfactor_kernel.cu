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
    if (k > montgomery_k) {
      atomicAdd(deferred, 1ULL);
      continue;
    }
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
