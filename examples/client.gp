\\ SPDX-License-Identifier: GPL-3.0-or-later
\\ Numerisect API from PARI/GP by shelling out to curl.
\\ Usage:  gp -q client.gp

numerisect_check(n) =
{
  my(jar = "/tmp/numerisect.cookies", base = "http://127.0.0.1:8765", cmd, out);
  system(Str("curl --silent --cookie-jar ", jar, " ", base, "/api/session > /dev/null"));
  cmd = Str("curl --silent --cookie ", jar,
            " --header 'Content-Type: application/json'",
            " --data '{\"expression\":\"", n, "\",\"mode\":\"proven\"}' ",
            base, "/api/primes/check");
  out = externstr(cmd);
  system(Str("rm -f ", jar));
  out;
};

print(numerisect_check(32416190071));
