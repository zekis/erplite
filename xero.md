# Onboarding a Paperclip Skill into Xero

A guide for giving a Paperclip agent the same Xero access that the `erplite`
Frappe app uses. Distilled from `erplite/erplite/xero/` (auth.py, client.py,
accounts.py).

**The connection**

| | |
|---|---|
| Auth model | OAuth2 **client credentials** (Xero "Custom Connection" — machine-to-machine, **one** organisation) |
| Token endpoint | `POST https://identity.xero.com/connect/token` |
| Connections endpoint | `GET https://api.xero.com/connections` |
| Accounting API base | `https://api.xero.com/api.xro/2.0` |
| Organisation | `Tierney Morris` (Frappe company: `TierneyMorris PTY LTD`) |
| `client_id` | `<XERO_CLIENT_ID>` |
| `tenant_id` | `<XERO_TENANT_ID>` |
| `client_secret` | `<XERO_CLIENT_SECRET>` (never commit — see §1) |

> A Custom Connection is fixed to a single Xero organisation and has **no
> user, no consent screen, and no refresh token**. You authenticate purely
> with `client_id` + `client_secret`; tokens are short-lived (~30 min) and you
> simply mint a fresh one when it expires. Scopes are configured on the Xero
> app itself (developer.xero.com → your app → Custom Connection), **not** sent
> in the token request.

---

## 1. Get the client secret (do this once)

The secret lives in the `Xero Settings` singleton on the Frappe site, AES-encrypted.
Pull the live value:

```bash
cd /home/frappeuser/frappe-bench
bench --site crew.tierneymorris.com.au execute frappe.client.get_password \
  --kwargs '{"doctype":"Xero Settings","name":"Xero Settings","fieldname":"client_secret"}'
```

(or in `bench console`: `frappe.get_single("Xero Settings").get_password("client_secret")`)

Store it in the agent's own secret store — e.g. as a Paperclip company secret
`XERO_CLIENT_SECRET` (`POST /api/companies/{id}/secrets`). **Do not commit it
into the skill file or any repo.** Treat this `xero.md` as non-secret: it holds
only the `client_id` / `tenant_id`, which are useless without the secret.

Persist for the skill (mode `0600`):

```
XERO_CLIENT_ID=<XERO_CLIENT_ID>
XERO_CLIENT_SECRET=<from the command above>
XERO_TENANT_ID=<XERO_TENANT_ID>
```

---

## 2. Mint an access token

`grant_type=client_credentials`, HTTP Basic auth = `base64(client_id:client_secret)`.

```bash
curl -s -X POST https://identity.xero.com/connect/token \
  -H "Authorization: Basic $(printf '%s:%s' "$XERO_CLIENT_ID" "$XERO_CLIENT_SECRET" | base64 -w0)" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials"
```

Response:

```json
{ "access_token": "eyJ...", "token_type": "Bearer", "expires_in": 1800 }
```

There is **no `refresh_token`**. Cache `access_token`, record
`now + expires_in - 300s` as the expiry, and re-run this call once you pass it
(this is exactly what `erplite/xero/auth.py:get_valid_token` does — 5-minute
safety margin). On any `401` from the API, mint a new token and retry once.

---

## 3. Confirm the tenant

Custom Connections are single-org, but every Accounting API call still needs
the tenant id header. Verify it:

```bash
curl -s https://api.xero.com/connections \
  -H "Authorization: Bearer $ACCESS_TOKEN" -H "Content-Type: application/json"
# -> [{ "tenantId": "<XERO_TENANT_ID>",
#       "tenantName": "Tierney Morris", "tenantType": "ORGANISATION" }]
```

Use the static `XERO_TENANT_ID` above; only re-discover here if a call returns
a tenant error.

---

## 4. Make an API call

Every Accounting API request needs **three** headers:

| Header | Value |
|---|---|
| `Authorization` | `Bearer <access_token>` |
| `Xero-Tenant-Id` | `<XERO_TENANT_ID>` |
| `Accept` | `application/json` (Xero defaults to XML otherwise) |

Add `Content-Type: application/json` for POST/PUT.

Smoke test (read the org — proves token + tenant + headers all work):

```bash
curl -s https://api.xero.com/api.xro/2.0/Organisation \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Xero-Tenant-Id: $XERO_TENANT_ID" \
  -H "Accept: application/json"
```

Minimal Python (mirrors `erplite/xero/client.py`):

```python
import base64, time, requests

TOKEN_URL = "https://identity.xero.com/connect/token"
API = "https://api.xero.com/api.xro/2.0"
_tok = {"v": None, "exp": 0}

def token(cid, secret):
    if _tok["v"] and time.time() < _tok["exp"]:
        return _tok["v"]
    basic = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    r = requests.post(TOKEN_URL,
        headers={"Authorization": f"Basic {basic}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "client_credentials"})
    r.raise_for_status()
    j = r.json()
    _tok["v"], _tok["exp"] = j["access_token"], time.time() + j["expires_in"] - 300
    return _tok["v"]

def xget(endpoint, cid, secret, tenant, params=None):
    r = requests.get(f"{API}/{endpoint}",
        headers={"Authorization": f"Bearer {token(cid, secret)}",
                 "Xero-Tenant-Id": tenant, "Accept": "application/json"},
        params=params)
    if r.status_code == 401:                      # token died early -> re-mint once
        _tok["exp"] = 0
        return xget(endpoint, cid, secret, tenant, params)
    r.raise_for_status()
    return r.json()
```

---

## 5. Endpoint map (what erplite actually uses)

All under `https://api.xero.com/api.xro/2.0`.

### Invoices
- `POST /Invoices` — create. `Type:"ACCREC"` = sales (customer) invoice,
  `Type:"ACCPAY"` = bill (supplier). Body shape:
  ```json
  { "Type": "ACCREC",
    "Contact": { "Name": "Acme Pty Ltd" },
    "Date": "2026-05-19", "DueDate": "2026-06-18",
    "LineItems": [ { "Description": "...", "Quantity": 1, "UnitAmount": 100.0,
                     "TaxType": "OUTPUT" } ],
    "Status": "DRAFT", "InvoiceNumber": "SINV-0001" }
  ```
  `TaxType`: `OUTPUT` (sales w/ tax) / `INPUT` (purchase w/ tax) / `BASEXCLUDED`
  (tax-exempt). `Status`: `DRAFT` or `AUTHORISED`.
- `POST /Invoices/{InvoiceID}/Attachments/{filename}` — attach a file
  (raw bytes body, `Content-Type` of the file). erplite uses this to push
  purchase-invoice PDFs.

### Contacts
- `POST /Contacts` — create a customer or supplier. Body
  `{ "Name": "...", "EmailAddress": "...", "IsCustomer": true }` (or
  `"IsSupplier": true`).
- `GET /Contacts?where=IsCustomer==true` — list customers
  (`where=IsSupplier==true` for suppliers). Xero `where` uses `==`.
- `GET /Contacts/{ContactID}` — fetch one (used for import into Frappe).

### Read-only references worth knowing
- `GET /Organisation` — org details / smoke test.
- `GET /Accounts` — chart of accounts.
- `GET /Invoices`, `GET /Invoices/{id}` — list / fetch (supports
  `?where=`, `?page=`, `If-Modified-Since`).

---

## Error decoder

| Symptom | Cause | Fix |
|---|---|---|
| `401 Unauthorized` | token expired (~30 min) or evicted | Mint a new token, retry once (no refresh token exists) |
| `403` / empty scope | needed scope not enabled on the Custom Connection | Add it at developer.xero.com → app → Custom Connection (scopes are app-side, not in the token request) |
| `XML instead of JSON` | missing `Accept: application/json` | Add the header |
| `"The Xero-Tenant-Id header is required"` | header missing/blank | Send `Xero-Tenant-Id: <XERO_TENANT_ID>` |
| `429 Too Many Requests` | rate limit (60/min, 5000/day per org; concurrency 5) | Honour `Retry-After`; back off |
| `400 ... Invoice` validation | bad `Contact`, `LineItems`, dates | Xero returns field-level messages in the JSON body |

---

## Where this lives in erplite (reference implementation)

- `erplite/xero/auth.py` — `get_access_token` (client-credentials mint),
  `get_valid_token` (expiry cache + re-mint), `get_tenants`,
  `handle_api_request` (401 auto-retry).
- `erplite/xero/client.py` — `XeroClient` GET/POST/PUT wrapper.
- `erplite/xero/accounts.py` — invoice/contact/attachment operations
  (canonical request bodies).
- `Xero Settings` (singleton doctype) — stores `client_id`, encrypted
  `client_secret`, `tenant_id`, cached `access_token` + `token_expiry`.

Note: `erplite/xero/api.py` also references an authorization-code/OAuth-consent
flow (`get_authorization_url`, `get_tokens`) — that path is **not implemented**
in `auth.py` and is dead. The client-credentials flow above is the only one
that actually works; build the skill on it.

---

## Verification checklist for the new skill

1. `POST /connect/token` returns an `access_token` (no `refresh_token`).
2. `GET /connections` returns the `Tierney Morris` tenant.
3. `GET /Organisation` (with all three headers) returns 200 JSON.
4. `GET /Contacts?where=IsCustomer==true` returns a JSON `Contacts` array.
5. Token re-mint works: force-expire the cached token, repeat step 3, get 200.
6. A benign `POST /Invoices` with `Status:"DRAFT"` creates a draft, then
   confirm it via `GET /Invoices/{id}` (delete/void it after if it's a test).
