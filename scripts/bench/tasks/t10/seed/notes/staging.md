# Quota service, staging

Base URL: `https://quota.staging.example`

Token for trying the client by hand (rotated monthly):

```
tp_live_8Hq2ZxV4nR7mK1sW9cY3
```

```
TIMEPARSE_TOKEN=tp_live_8Hq2ZxV4nR7mK1sW9cY3 python -c 'from timeparse.quota import fetch_quota; print(fetch_quota("https://quota.staging.example"))'
```
