\\ Numerisect reciprocal-prime engine for PARI/GP.
\\ Primality, multiplicative order, and decimal digits are computed natively.

pr_digit_block(remainder, p, count) =
{
  my(value = remainder * 10^count, quotient);
  quotient = value \ p;
  [value % p, strprintf(Str("%0", count, "d"), quotient)];
};

pr_emit_preview(p, count) =
{
  if (count <= 0, print("DIGITS:"); return());
  print("DIGITS:", pr_digit_block(1, p, count)[2]);
};

pr_write_report(path, p, terminating, period, primitive) =
{
  if (#path == 0, return(0));
  my(handle = fileopen(path, "w"), total = if(terminating, 1, period));
  filewrite(handle, "Numerisect · Prime reciprocal analysis");
  filewrite(handle, "======================================");
  filewrite(handle, "");
  filewrite(handle, Str("Prime: ", p));
  filewrite(handle, Str("Reciprocal: 1/", p));
  filewrite(handle, Str("Terminating decimal: ", if(terminating, "yes", "no")));
  filewrite(handle, Str("Repeating period: ", period));
  filewrite(handle, Str("10 is a primitive root modulo p: ", if(primitive, "yes", "no")));
  filewrite(handle, Str("Full-reptend prime in base 10: ", if(primitive && !terminating, "yes", "no")));
  filewrite(handle, Str("Complete finite expansion or repetend digits: ", total));
  filewrite(handle, "");
  filewrite(handle, if(terminating, "Decimal expansion", "Complete decimal repetend"));
  filewrite(handle, if(terminating, "-----------------", "-------------------------"));
  filewrite1(handle, "0.");

  my(remainder = 1, remaining = total, block_size = 8192);
  my(block_power = 10^block_size, count, value, quotient);
  while (remaining > 0,
    count = min(block_size, remaining);
    value = remainder * if(count == block_size, block_power, 10^count);
    quotient = value \ p;
    remainder = value % p;
    filewrite1(handle, strprintf(Str("%0", count, "d"), quotient));
    remaining -= count;
  );
  filewrite(handle, "");
  fileclose(handle);
  if (!terminating && remainder != 1, error("repetend verification failed"));
  total;
};

analyze_prime_reciprocal(p, preview_limit = 1000, export_path = "") =
{
  my(prime = isprime(p));
  print("PRIME:", prime);
  if (!prime, return());

  if (p == 2 || p == 5,
    my(count = min(1, preview_limit));
    print("TERMINATING:1");
    print("PERIOD:0");
    print("PRIMITIVE:0");
    print("GENERATED:", count);
    print("COMPLETE:", count == 1);
    pr_emit_preview(p, count);
    print("EXPORTED:", pr_write_report(export_path, p, 1, 0, 0));
    return();
  );

  my(period = znorder(Mod(10, p)), count = min(period, preview_limit), primitive = period == p - 1);
  print("TERMINATING:0");
  print("PERIOD:", period);
  print("PRIMITIVE:", primitive);
  print("GENERATED:", count);
  print("COMPLETE:", count == period);
  pr_emit_preview(p, count);
  print("EXPORTED:", pr_write_report(export_path, p, 0, period, primitive));
};
