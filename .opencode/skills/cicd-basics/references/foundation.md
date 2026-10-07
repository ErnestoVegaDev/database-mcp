# CI/CD Basics -- Background & Theory

> This document contains the theoretical foundations, evidence base, and references for this framework.
> For practical application and execution, see [SKILL.md](../SKILL.md).

## Theoretical Origin

- **Continuous Integration** coined by Grady Booch (1991), popularized by Kent Beck and Extreme Programming (1999).
- **Continuous Delivery** formalized by Jez Humble and David Farley in *Continuous Delivery* (2010).
- **DORA research** (Forsgren et al., *Accelerate*, 2018) quantified the business impact: elite CI/CD teams deploy 208× more frequently with 2,604× faster recovery.
- **The Phoenix Project** (Kim et al., 2013) — fictional but influential narrative of a company transforming from quarterly releases to daily deploys.

---


## Core Concepts, Explained Simply

### What is CI?
**Continuous Integration** = Every time a developer pushes code, automated tests run immediately.

Without CI: "We'll integrate everyone's code on Friday." → Friday is a disaster.
With CI: Bad code is caught within minutes, not days.

### What is CD?
**Continuous Delivery** = After tests pass, the code is *ready* to deploy at any moment (a human clicks the button).
**Continuous Deployment** = After tests pass, code deploys *automatically* to production (no human button).

Most small teams want Continuous Delivery, not full Deployment. The distinction matters.

### Why does it matter for non-developers?
- "The app update we shipped last week broke login" → CI would have caught it before shipping
- "I'm scared to deploy" → automated pipeline makes deploys boring (which is good)
- "We deploy once a month" → DORA research shows quarterly deployments correlate with lower organizational performance

---


## Further Reading

- Humble, J. & Farley, D. *Continuous Delivery.* (Addison-Wesley, 2010) — the definitive text
- Kim, G. et al. *The Phoenix Project.* (IT Revolution, 2013) — narrative entry point
- Forsgren, N. et al. *Accelerate.* (IT Revolution, 2018) — the data behind DORA metrics
- **DORA State of DevOps Report**: dora.dev (annual, free)
- **GitHub Actions documentation**: docs.github.com/en/actions