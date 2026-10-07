---
name: cicd-basics
version: "0.2.0"
description: "CI/CD Basics — Continuous Integration and Continuous Deployment fundamentals. GitHub Actions, Docker basics, deployment strategies (blue-green, canary), environment management. The minimum viable DevOps for solo developers and small teams."
---

# CI/CD Basics

> **Background and theory**: Read [references/foundation.md](references/foundation.md)


## One-Line Summary

**Automate the path from "code written" to "code running in production" — catching bugs earlier, deploying faster, and removing the terror of manual releases.**


## GitHub Actions — The Minimum Viable CI

GitHub Actions is the easiest starting point. It's free for public repos, and the free tier is generous for small projects.

### How it works

Create a file at `.github/workflows/ci.yml` in your repo. GitHub runs it automatically on every push.

### Basic workflow structure

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Run tests
        run: npm test

      - name: Run linter
        run: npm run lint
```

This runs on every push. If tests fail, the PR shows a red X. Simple and effective.

### Common additions

```yaml
      # Check for secrets accidentally committed
      - name: Secret scan
        uses: trufflesecurity/trufflehog@main

      # Build Docker image to verify it compiles
      - name: Build Docker image
        run: docker build -t my-app .

      # Deploy to staging after tests pass on main
      - name: Deploy to staging
        if: github.ref == 'refs/heads/main'
        run: ./deploy.sh staging
        env:
          DEPLOY_TOKEN: ${{ secrets.DEPLOY_TOKEN }}
```

---


## Docker Basics — Why Containers?

### The problem Docker solves

"It works on my machine" → Docker makes "your machine" and "the server" identical.

### Key concepts

**Dockerfile** = recipe for building your app's environment

```dockerfile
# Start from an official base image
FROM node:20-alpine

# Set working directory inside the container
WORKDIR /app

# Copy dependency files first (Docker caches this layer)
COPY package*.json ./
RUN npm ci --only=production

# Copy the rest of the code
COPY . .

# What to run when the container starts
CMD ["node", "server.js"]
```

**Image** = the built result of a Dockerfile (a snapshot)
**Container** = a running instance of an image

```bash
# Build an image
docker build -t my-app:v1.0 .

# Run a container from the image
docker run -p 3000:3000 -e NODE_ENV=production my-app:v1.0
```

### Why bother with Docker for a solo project?

| Without Docker | With Docker |
|---|---|
| Works locally, breaks on server | Same environment everywhere |
| "Install Node 18, not 20" in README | Just `docker run` |
| Manual rollback = redeploy old code | Rollback = run previous image tag |
| Can't test on a fresh machine easily | `docker run` is a clean slate |

For Vercel/Netlify (frontend), you don't need Docker — they handle it. Docker matters when you have a backend server you're running yourself.

---


## Deployment Strategies

### 1. Manual Deploy (Stage 0)
```bash
ssh user@server
git pull
npm ci
pm2 restart app
```
Downtime during deploy. No rollback except re-SSH-ing. Fine for early experiments, not for production users.

### 2. Automated Deploy (Stage 1)
GitHub Actions pushes to your server on every merge to `main`. Still some downtime, but no manual steps.

### 3. Blue-Green Deployment (Stage 2)
Run two identical environments. Route traffic to one ("blue"). Deploy to the other ("green"). Switch traffic when green is healthy. Rollback = switch back to blue.

```
                 ┌─────────────┐
Load Balancer ──►│ Blue (live) │ ← current traffic
                 └─────────────┘
                 ┌─────────────┐
                 │ Green (new) │ ← deploy here, test, then switch
                 └─────────────┘
```

**When to use**: When you can afford two environments (e.g., 2× server cost) and zero-downtime matters.

### 4. Canary Deployment (Stage 3)
Route 5% of traffic to the new version. Watch metrics. If healthy, increase to 20%, 50%, 100%. If not, route all traffic back to old version.

**When to use**: Large user base where even a brief outage has significant impact. Overkill for < 10,000 users.

### 5. Feature Flags (Stage 4)
Deploy code to 100% of servers, but only activate features for specific users. Decouple deployment from release.

Tools: LaunchDarkly, Unleash, Flagsmith, or simple DB-backed flags.

---


## Environment Management

Three environments is the classic setup:

| Environment | Purpose | Who deploys? | Data |
|---|---|---|---|
| **dev** (local) | Active development | Individual dev | Fake/test data |
| **staging** | QA, pre-release testing | CI on merge to `develop` | Anonymized copy of prod |
| **prod** | Real users | CI on merge to `main` (or manual) | Real data |

### Environment parity (from 12-Factor)
Staging should mirror production as closely as possible. "It worked in staging" failures usually mean staging and prod diverged.

### Config per environment
```bash
# .env.staging
DATABASE_URL=postgres://staging-db/myapp
STRIPE_KEY=sk_test_...
LOG_LEVEL=debug

# .env.production
DATABASE_URL=postgres://prod-db/myapp
STRIPE_KEY=sk_live_...
LOG_LEVEL=warn
```

Never commit `.env` files. Use platform environment variable settings (Vercel, Railway, Heroku, etc.) for production secrets.

---


## PaaS Options (The Vibe Coder's Real Choice)

For solo developers and small teams, managed platforms eliminate most DevOps complexity:

| Platform | Best for | Free tier | Notes |
|---|---|---|---|
| **Vercel** | Next.js, React frontends | Generous | Zero-config deploys from GitHub |
| **Netlify** | Static sites, JAMstack | Generous | Great for Hugo, Gatsby |
| **Railway** | Full-stack apps, backends | Limited | Simple Postgres + Node/Python |
| **Render** | Web services, workers | Generous | Good Docker support |
| **Fly.io** | Containers globally | Moderate | More control than Railway |
| **Heroku** | Classic PaaS | Paid only | No longer free, but mature ecosystem |

These platforms handle: SSL certificates, HTTPS, auto-deploys from GitHub, environment variables, and basic scaling. You don't need to set up nginx, configure firewalls, or manage servers.

**Recommendation for < 5-person teams**: Start with Vercel/Railway/Render. Only move to self-managed when you have a specific reason (cost at scale, compliance, unusual architecture).

---


## Health Check Endpoint

Every deployed app needs a `/health` or `/healthz` endpoint:

```javascript
// Minimum viable health check
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Better: check dependencies
app.get('/health', async (req, res) => {
  const dbOk = await checkDatabase();
  const status = dbOk ? 200 : 503;
  res.status(status).json({ status: dbOk ? 'ok' : 'degraded', db: dbOk });
});
```

Why it matters:
- CI/CD needs it to know if deployment succeeded
- Load balancers use it to route traffic
- Monitoring tools use it for uptime alerts
- PaaS platforms (Vercel, Railway) use it for auto-restart decisions

---


## Connecting to 12-Factor

CI/CD operationalizes the 12-Factor principles:

| 12-Factor | CI/CD connection |
|---|---|
| V. Build, Release, Run | Pipeline stages = build → release → deploy |
| III. Config | Env vars in pipeline secrets, not code |
| XI. Logs | Pipeline streams logs to centralized store |
| X. Dev/Prod Parity | Staging = prod mirroring in pipeline config |
| IX. Disposability | Blue-green relies on fast startup/shutdown |

---


## Stage-Default Recommendations

| Team size | Default setup |
|---|---|
| **1 person** | GitHub Actions for tests + Vercel/Railway auto-deploy |
| **2–5 people** | Above + staging environment + basic Docker for backend |
| **5–20 people** | Above + blue-green deploys + feature flags + Slack notifications |
| **20+ people** | Above + Docker Compose or managed Kubernetes (EKS, GKE) |

---


## DORA Metrics — How to Measure

The four metrics that correlate most with organizational performance (Forsgren et al., *Accelerate*):

| Metric | Elite | High | Medium | Low |
|---|---|---|---|---|
| Deployment Frequency | On-demand (multiple/day) | Weekly | Monthly | Quarterly |
| Lead Time (commit → prod) | < 1 hour | 1 day | 1 week | 1 month |
| Change Failure Rate | < 5% | 10% | 15% | > 15% |
| Recovery Time | < 1 hour | < 1 day | < 1 week | > 1 week |

You don't need to be "elite" immediately. Moving from monthly to weekly is already significant.

---


## Anti-Patterns

- **"Manual deploy is faster"** — true for the 10th deploy, false for the 100th. Automate before you regret it.
- **"We'll add tests later"** — CI without tests is just "faster manual deploy". Tests come first.
- **Staging is always broken** — means staging isn't actually being used. Fix or remove it.
- **Long-lived feature branches** — the longer you wait to merge, the more painful integration is. Merge at least weekly.
- **K8s for a 3-person startup** — Kubernetes adds 20–40 hours of ops overhead per month. Justify it first.
- **Skipping staging** — deploying straight to prod with no testing environment. Fine for personal projects, dangerous with real users.


## Over-Application Warning

CI/CD has a setup cost. Prioritize appropriately:

- **Personal project**: A GitHub Actions test run is enough. Don't build a full pipeline before you have users.
- **1-person startup**: Vercel auto-deploy from GitHub is a complete CI/CD setup. Spend time on product.
- **Kubernetes**: The threshold is ~50+ engineers with independent deployment needs across services. Almost no team under 20 engineers actually needs K8s. The operational overhead (YAML configuration, networking, monitoring, debugging) is significant.

The goal of CI/CD is confidence and speed, not infrastructure complexity.

---


## Limitations

1. **Tests are the hard part** — CI is only as good as your test suite. No tests = CI just checks "does it compile?"
2. **Culture must change** — CI/CD doesn't work in teams where "QA" is a separate gate happening weeks later
3. **Not a substitute for monitoring** — deploys can succeed and still have bugs in production (observability still needed)
4. **Database migrations** — the hardest part of CI/CD for stateful apps; blue-green breaks if migrations aren't backward-compatible


## Related Frameworks

- `twelve-factor` — V (Build/Release/Run), III (Config), XI (Logs) are directly CI/CD-relevant
- `observability` — what you monitor after a deployment
- `resilience-patterns` — blue-green and feature flags are resilience tools too
