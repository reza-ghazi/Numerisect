// SPDX-License-Identifier: GPL-3.0-or-later
// Numerisect API from Node. The session cookie is captured and replayed.
const BASE = process.env.NUMERISECT_URL ?? "http://127.0.0.1:8765";

const session = await fetch(`${BASE}/api/session`);
const { request_token: token } = await session.json();

const response = await fetch(`${BASE}/api/primes/check`, {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-Numerisect-Token": token },
  body: JSON.stringify({ expression: "32416190071", mode: "proven" }),
});
console.log(await response.json());
