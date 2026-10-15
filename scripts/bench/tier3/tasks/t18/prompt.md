Simplify `parse_duration`: replace the token loop with one full-match regex. Its behaviour must not change for any input, and nothing else in the package may break.
