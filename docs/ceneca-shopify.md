# Ceneca + Shopify Integration Architecture

## Overview

This document outlines the technical architecture and authentication flow for integrating Shopify into the Ceneca adapter‑orchestration model. It covers:

* High‑level system architecture
* Setting up the Shopify app via CLI/npm
* OAuth2 authentication flow
* Adapter‑orchestration design
* Configuration and secrets management
* Webhook verification

---

## 1. High‑Level Architecture

```ascii
+----------------+         +--------------------+         +----------------------+         +-------------+
|  Shopify Store | <--Webhooks-- | Shopify Adapter   | <--HTTP-- | Orchestrator &       | <--Data-- | Ceneca AI &  |
| (Orders,       |         | (OAuth2, API calls) |         | Scheduler/Trigger    |         | Processing   |
|  Customers,    | --API--> |                    | --Normalized--> | (Cron, Events,       | --Insights--> | Pipelines    |
|  Products)     |         +--------------------+         | Manager)             |         +-------------+
+----------------+                                      +----------------------+                         
                                                                              |
                                                                              v
                                                                     +------------------+
                                                                     | Dashboard / UI   |
                                                                     | (Embedded in     |
                                                                     |  Shopify Admin   |
                                                                     +------------------+
```

* **Shopify Adapter**: Handles OAuth2, API communication, data parsing/order pagination, rate‑limiting, and error handling.
* **Orchestrator**: Manages triggers (scheduled or on‑demand), coordinates adapters, retries, and routes normalized data to Ceneca’s AI pipelines.
* **Ceneca AI & Processing**: Runs ML models for forecasting, segmentation, inventory optimization, and generates insights.
* **Dashboard/UI**: Displays insights to merchants via a Shopify embedded app or standalone UI.

---

## 2. Setting up the Shopify App (CLI & npm)

```bash
# Install Shopify CLI globally
npm install -g @shopify/cli

# Create a new Node.js Shopify app for Ceneca integration
shopify app create node --name ceneca-shopify-integration
cd ceneca-shopify-integration

# Install dependencies
npm install shopify-api-node dotenv express
```

* The CLI scaffolds the app, including `shopify.app.toml`, and sets up an Express server for your callback endpoints.
* Modify `shopify.app.toml` or `.env` to include your Ceneca domain and redirect URI once ready.

---

## 3. OAuth2 Authentication Flow

1. **App Registration** (via CLI above)

   * Scopes in `shopify.app.toml` or Partner Dashboard: `read_orders`, `read_products`, `read_customers`.
   * Redirect URI: `https://<YOUR_CENECA_DOMAIN>/shopify/callback`.

2. **Generate Install URL**

   ```js
   const installUrl = `https://${shopDomain}/admin/oauth/authorize`
     + `?client_id=${process.env.SHOPIFY_API_KEY}`
     + `&scope=read_products,read_orders,read_customers`
     + `&redirect_uri=${process.env.SHOPIFY_REDIRECT_URI}`
     + `&state=${nonce}`;
   ```

3. **Handle Callback** (`/shopify/callback`)

   ```js
   app.get('/shopify/callback', async (req, res) => {
     const { shop, code, state } = req.query;
     // Verify state
     const tokenResp = await axios.post(`https://${shop}/admin/oauth/access_token`, {
       client_id: process.env.SHOPIFY_API_KEY,
       client_secret: process.env.SHOPIFY_API_SECRET,
       code,
     });
     const accessToken = tokenResp.data.access_token;
     // Store in secrets manager
     await vaultClient.write(`secret/shops/${shop}`, { accessToken });
     res.redirect(`/app?shop=${shop}`);
   });
   ```

4. **API Calls**

   ```js
   const Shopify = require('shopify-api-node');
   const shopify = new Shopify({
     shopName: shop,
     accessToken: await vaultClient.read(`secret/shops/${shop}`).accessToken,
   });
   const orders = await shopify.order.list({ limit: 250, since_id: lastId });
   ```

5. **Uninstall Webhook**

   * Subscribe to `app/uninstalled` to clean up tokens.

---

## 4. Adapter‑Orchestration Design

### 4.1 Shopify Adapter

* **Responsibilities**:

  * OAuth2 handshake
  * Rate‑limited API calls
  * JSON parsing & data normalization
  * Error handling & retries
* **Libraries**: `shopify-api-node`, `axios`

### 4.2 Orchestrator

* **Responsibilities**:

  * Trigger adapters (cron jobs, on‑demand API)
  * Parallelize data pulls (orders, products, customers)
  * Aggregate & route data to ML models
  * Log & retry failures
* **Technologies**: Node.js, BullMQ (queues), Kubernetes Jobs/CronJobs or AWS Lambda + EventBridge

---

## 5. Configuration & Secrets Management

**.env**

```
SHOPIFY_API_KEY=<your_api_key>
SHOPIFY_API_SECRET=<your_api_secret>
SHOPIFY_REDIRECT_URI=https://<your-ceneca-domain>/shopify/callback
VAULT_ADDR=https://vault.your-domain.com
```

**Kubernetes Secret**

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: shopify-creds
type: Opaque
data:
  SHOPIFY_API_KEY: <base64>
  SHOPIFY_API_SECRET: <base64>
```

---

## 6. Webhook Verification

```js
app.post('/shopify/webhook', (req, res) => {
  const hmac = req.get('X-Shopify-Hmac-Sha256');
  const body = req.rawBody;
  const digest = crypto
    .createHmac('sha256', process.env.SHOPIFY_API_SECRET)
    .update(body, 'utf8')
    .digest('base64');
  if (digest !== hmac) return res.status(401).send('Unauthorized');
  // process webhook
  res.status(200).send('OK');
});
```

---

## 7. Next Steps

* Implement and test the `/shopify/callback` handler end‑to‑end.
* Wire up your secrets manager (Vault/K8s) for runtime credential access.
* Build and iterate on the orchestrator workflows for initial data sync.
* Develop the embedded dashboard to surface Ceneca insights within Shopify.

---

*Generated by Ceneca Integration Planning Guide*
