---
name: solid
version: "0.2.0"
description: "SOLID Principles (Robert Martin) — SRP/OCP/LSP/ISP/DIP. Classic principles of OO design. Includes warnings against over-application. References Dan North's CUPID alternative."
---

# SOLID Principles

> **Background and theory**: Read [references/foundation.md](references/foundation.md)


## One-Line Summary

Five principles of object-oriented design. **A thinking tool for building code that is resilient to change.** However, forcing code to conform to the principles backfires. The principles are a *lens for reducing pain*, not a checklist.


## When to Use

- When writing long-lived maintenance codebases in an OO language
- As a common language during team onboarding
- As a *discussion tool* in code review
- When judging refactoring direction
- When cleaning up code that is hard to test


## Situations Where SOLID Becomes the *Primary* Framework (Not Architectural Level)

When larger structure (boundaries, teams, deployment) comes first, SOLID rightly takes a back seat. But the following cases center on SOLID:

1. **Refactoring at the legacy function/class level** — leave module/service boundaries intact, clean up internals only
2. **Breaking up God classes** — a 2000-line `OrderService.java` → split via SRP
3. **Payment routing where switch branches keep growing** — replace with OCP + strategy pattern
4. **Designing internal SDK/library interfaces** — ISP and DIP determine API quality
5. **Establishing a common language for code review** — onboarding new hires + PR review guide
6. **Redesigning inheritance hierarchies** — catching LSP violations
7. **Functions where "you have to spin up a DB to test"** — convert with DIP + `hexagonal`

### Concrete Scenario

```
Situation: 3-year-old order service, `OrderProcessor` at 2,400 lines
  - 22 branches of if (paymentType == ...)
  - Inventory, shipping, coupons, rewards, notifications all mixed together
  - Tests: only 2 integration tests
Signal mapping:
  - "Scared to touch it" → accumulated SRP/OCP violations
  - "Can't be tested" → no DIP + I/O coupling
Approach:
  1. SRP: separate payment routing / inventory deduction / coupon application / notifications
  2. OCP: paymentType switch → PaymentStrategy interface + implementations
  3. DIP: put DB/external APIs behind interfaces (→ naturally leads to hexagonal)
  4. Testing: unit tests for each separated responsibility
Result: 2,400 lines → 10 classes averaging 200 lines + interfaces + fakes
```


## Practical Tips

### Use as a Lens
- "Why am I afraid to touch this code?" → check SRP/OCP
- "Why is the test this long?" → check DIP/ISP
- "Should I use inheritance?" → does it pass LSP?

### Priority Order
- **DIP + SRP** first. Largest practical payoff.
- OCP applies only *after a pattern of change is visible*. Applied preemptively, it's over-engineering.
- LSP matters only when using inheritance.
- ISP triggers when a large interface has emerged and needs splitting.


## Anti-patterns & Over-application

- **Classes made extremely small** — SRP over-application. Dozens of 10-line files are harder to read
- **Making everything an interface** — DIP over-application. An interface with only one implementation is meaningless
- **Abstraction for abstraction's sake** — adding layers on "what if it changes later"
- **SOLID = the right refactor answer** — No. Tolerating duplication is often better (Rule of Three)
- **Name-dropping principles with vague application** — saying only "SRP violation" in code review ends the discussion. You must point to a concrete axis of change


## Limitations

1. **Only partially applicable outside OO paradigms** — functional and data-centric styles have different principles (immutability, purity)
2. **Knowing the names ≠ understanding** — reciting them verbally breeds misunderstanding
3. **Tempts the "solve with inheritance" trap** — the mistake of using inheritance because of LSP
4. **Not a business problem** — what the domain structure should be belongs to `ddd`


## Frameworks to Use Alongside This One

- `hexagonal` — the natural consequence of DIP
- `ddd` — the domain version of SRP (Aggregate boundaries)
- `solid` is at the *code level*; `hexagonal` and `ddd` are at the *structural level*


## When This Framework Is *Wrong*

- Short-term scripts/prototypes → over-application
- Procedural/functional code → different principles
- Domain boundary problems → `ddd`
