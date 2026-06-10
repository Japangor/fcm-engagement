# FCM Engagement Push

Scheduled engagement notifications for the app portfolio, sent via GitHub Actions.
Broadcasts a rotating message to the FCM topic `all` on each configured Firebase
project. Clients auto-subscribe to `all`, so no per-device token management is needed.

## Schedule

Mon / Wed / Fri / Sun at 13:30 UTC (~19:00 IST). See
[`.github/workflows/fcm-engagement.yml`](.github/workflows/fcm-engagement.yml).
You can also trigger it manually from the Actions tab (`Run workflow`), with options
for category, announcement pool, and dry-run.

## Secrets (Settings -> Secrets and variables -> Actions)

Each is the **base64-encoded** Firebase service-account JSON (with the
`cloudmessaging`/`firebase.messaging` scope). A project is skipped gracefully when
its secret is absent.

| Secret | Firebase project | Covers |
|--------|------------------|--------|
| `FCM_SA_CRICKET`  | `cricket-c7b8f` | Cricket apps + ~40 learning/calculator apps |
| `FCM_SA_JAPANGOR` | `japangor`      | `learn_ai`, `learn_llm` |

To produce a secret value from a service-account JSON:

```bash
base64 -i service_account.json | tr -d '\n' | pbcopy   # macOS, copies to clipboard
```

Then paste it as the secret value.

## Message bank

Edit [`fcm_messages.json`](fcm_messages.json). Pools: `education_code`,
`education_exam`, `finance`, `utility`, `general`, plus `announcements`.
The daily message rotates by day-of-year.

## Run locally

```bash
pip install -r requirements.txt
FCM_SA_CRICKET=./cricket_sa.json python3 fcm_engagement.py --dry-run
```
