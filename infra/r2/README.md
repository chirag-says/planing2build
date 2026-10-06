# R2 bucket CORS (launch gate N-01)

Browsers upload straight to the private bucket with presigned PUT URLs: homeowners their requirement files, professionals their evidence and portfolio photos. The bucket's CORS rule allows exactly those two hosts and nothing else (SLICE3_3_READINESS N-01, replacing S-01's "homeowner host only").

| File | Bucket | Allowed origins |
|---|---|---|
| `cors.production.json` | `p2b-prod-private` | `https://plan2build.in`, `https://professionals.plan2build.in` |
| `cors.staging.json` | `p2b-staging-private` | `https://staging.plan2build.in`, `https://staging-professionals.plan2build.in` |
| `cors.local.json` | local SeaweedFS (`infra/local/compose.yml`, `-s3.allowedOrigins`) | `http://ihb.localhost:8080`, `http://pro.localhost:8080` |

Every rule: method `PUT` only (presigned uploads); header `content-type` only (the only header the upload URL signs); no wildcard origin, method or header. The `www` host redirects to the apex and serves no pages. The admin host is not listed: operations never upload from the browser.

Apply the rule in the Cloudflare dashboard (R2, bucket, Settings, CORS policy) or with `wrangler r2 bucket cors set <bucket> --file infra/r2/cors.production.json`, then verify from a machine with internet access:

```bash
python apps/api/scripts/check_r2_cors.py --policy infra/r2/cors.production.json --endpoint https://<account-id>.r2.cloudflarestorage.com/p2b-prod-private --refuse https://admin.plan2build.in --refuse https://example.com
```

The check fails if the policy has a wildcard or any origin, method or header beyond the above, if an allowed origin's preflight is not answered with that exact origin, or if a refused origin's preflight is allowed. `tests/test_r2_cors.py` runs the same checks against the policies and against local storage.
