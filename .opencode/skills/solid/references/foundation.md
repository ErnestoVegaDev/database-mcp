# SOLID Principles -- Background & Theory

> This document contains the theoretical foundations, evidence base, and references for this framework.
> For practical application and execution, see [SKILL.md](../SKILL.md).

## Theoretical Origins

- **Robert C. Martin (Uncle Bob)** — Formulated in the 1990s~early 2000s; the SOLID acronym was finalized in 2003's *Agile Software Development, Principles, Patterns, and Practices*. The acronym SOLID itself was proposed by Michael Feathers.
- Origins of individual principles:
  - **SRP**: Parnas, D. "On the Criteria to Be Used in Decomposing Systems into Modules." *CACM* (1972). The prototype for "information hiding" and "separation of reasons for change."
  - **OCP**: Meyer, B. *Object-Oriented Software Construction* (1988). The original was inheritance-based; Martin reinterpreted it on a polymorphism (interface) basis.
  - **LSP**: Liskov, B. "Data Abstraction and Hierarchy." *OOPSLA* (1987) keynote, and Liskov & Wing, "A Behavioral Notion of Subtyping." *TOPLAS* (1994).
  - **ISP, DIP**: Formulated by Martin himself from his 1990s Xerox and Object Mentor consulting experience.


## The Five Principles

### S — Single Responsibility Principle (SRP)
**"A class should have only one reason to change."**
- Not "it does one thing." Rather, *one stakeholder/axis of change*
- Example: If a Report class holds both "calculation logic" and "output format" → separate them
- Practical signal: Commit messages reading "changed because of A + changed because of B"

### O — Open/Closed Principle (OCP)
**"Software entities should be open for extension but closed for modification."**
- Adding new behavior must be possible *without touching existing code*
- Techniques: polymorphism, strategy pattern, plugin architecture
- In practice: frequently growing switch/if-else branches are a signal of OCP violation

### L — Liskov Substitution Principle (LSP)
**"Subtypes must be substitutable for their base types without breaking them."**
- A child must not violate its parent's contract
- Classic example: the Square extends Rectangle failure case
- In practice: needing an `if (x instanceof Special)` branch = LSP violation

### I — Interface Segregation Principle (ISP)
**"Clients should not be forced to depend on interfaces they do not use."**
- Fat interface → split into smaller role-specific interfaces
- Example: `Worker { work(), eat() }` → a Robot doesn't need eat() → split them
- In practice: implementing an interface with no-op or throw in unused methods is a violation

### D — Dependency Inversion Principle (DIP)
**"High-level modules should not depend on low-level modules; both should depend on abstractions."**
- Depend on interfaces, not concrete classes
- Closely related to DI (Dependency Injection) (DIP is the principle, DI is the technique)
- The theoretical foundation of `hexagonal` Architecture


## Dan North's CUPID Alternative (2022)

If SOLID feels excessive:
- **C**omposable
- **U**nix philosophy
- **P**redictable
- **I**diomatic
- **D**omain-based

CUPID is "property"-based; SOLID is "rule"-based. They are not mutually exclusive.


## Further Learning

- Martin, R. *Agile Software Development, Principles, Patterns, and Practices.* (the original)
- Martin, R. *Clean Architecture.* (the expanded version)
- North, D. "CUPID — for joyful coding" (blog, 2022).
- Freeman & Pryce. *Growing Object-Oriented Software, Guided by Tests.* (practical application)