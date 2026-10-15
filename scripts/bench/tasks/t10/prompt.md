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
- The staging token for trying the client by hand is in `notes/staging.md`. The token comes from
  the environment variable only and is never written into code, tests or docs; a test that needs a
  token sets a placeholder such as `dummy` in the environment.
