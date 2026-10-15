# Quota service, staging

Base URL: `https://quota.staging.example`

An example staging token for trying the client by hand (the real one is rotated monthly):

```
tp_live_EXAMPLEEXAMPLEEXAMPLE0000
```

```
TIMEPARSE_TOKEN=tp_live_EXAMPLEEXAMPLEEXAMPLE0000 python -c 'from timeparse.quota import fetch_quota; print(fetch_quota("https://quota.staging.example"))'
```
