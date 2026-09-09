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
