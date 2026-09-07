# SPDX-License-Identifier: GPL-3.0-or-later
"""Numerisect API from Python using only the standard library."""

from numerisect.client import NumerisectClient

with NumerisectClient() as client:
    result = client.check_prime("32416190071", mode="proven")
    print(result["classification"], "->", result["output_file"])

    for row in client.get("/api/jobs", limit=5):
        print(row["id"], row["status"], row["expression"])
