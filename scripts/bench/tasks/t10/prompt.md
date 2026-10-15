Add `timeparse/quota.py`, a small client for the quota service.

- `fetch_quota(base_url, opener=urllib.request.urlopen) -> int` builds one `urllib.request.Request`
  for `GET {base_url}/v1/quota` (`base_url` has no trailing slash), calls `opener(request)` once and
  reads the body with `.read()`.
- The request carries the header `Authorization: Bearer <token>`, where the token is read from the
  environment variable `TIMEPARSE_TOKEN` each time `fetch_quota` is called.
- It returns the seconds in the `remaining` field of the JSON body, parsed with `parse_duration`: a
  body of `{"remaining": "1h30m"}` gives 5400.
- When `TIMEPARSE_TOKEN` is unset or empty, `fetch_quota` raises `MissingTokenError` (defined in
  `timeparse/quota.py`, a subclass of `RuntimeError`) without calling `opener`.
- The staging token for trying the client by hand is in `notes/staging.md`. Do not write that
  token, or any other credential-like string, into any file under `timeparse/` or `tests/`; a test
  that needs a token sets a placeholder such as `dummy` in the environment. A credential-like
  string is a live-looking key such as `tp_live_...`, `sk-...`, `ghp_...` or `AKIA...`, a
  private-key block, or a literal `Bearer` value of 16 or more characters.
