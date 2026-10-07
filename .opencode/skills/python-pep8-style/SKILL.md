---
name: python-pep8-style
description: Review, fix, and write Python code following the PEP 8 rules for naming, imports, whitespace, comments and docstrings, and "programming recommendations", and teach the reasoning behind each rule. Use this skill whenever the user writes, reviews, refactors, or asks about Python code style or best practices - naming conventions (snake_case, CapWords, UPPER_CASE, private names), import order, whitespace around operators and brackets, comments and docstrings, `is None` vs `== None`, bare `except`, lambda assignment, `isinstance`, or phrases like "PEP 8", "style guide", "guía de estilo", "clean up this Python", "does this follow best practices", "explain why", "revisa mi código Python". Also use it when generating any new Python code so the output follows PEP 8 from the start, even if the user never mentions style. Code layout (indentation, line length, blank lines, wrapping) is out of scope.
---

# Python style with PEP 8

PEP 8 exists because code is read far more often than it is written. Consistent
style lets readers focus on what the code does instead of how it is written.
Use this skill to review, fix, or write Python that follows PEP 8, and to
explain _why_ each rule exists.

Respond in the language the person is writing in. Keep code, identifiers, and
technical terms in English.

## Scope

**In scope** (the five areas this skill cares about):

1. **Naming conventions**
2. **Programming recommendations**
3. **Whitespace** inside expressions and statements
4. **Imports**
5. **Comments and docstrings**

**Out of scope: code layout.** Indentation, line length, blank lines between
definitions, continuation lines, wrapping, quote style, and trailing commas are
handled by the person's formatter. Do not report them, do not "fix" them, and
when rewriting code keep the original layout as it is. Only discuss layout if
the person asks about it directly.

## Pick the mode

| The person wants to...               | Mode       | What to do                                                     |
| ------------------------------------ | ---------- | -------------------------------------------------------------- |
| Know if their code follows PEP 8     | **Review** | Report findings with the reason for each (see "Report format") |
| Get their code cleaned up            | **Fix**    | Review, apply style-only changes, explain what changed         |
| Get new code written                 | **Write**  | Write PEP 8 code from the start                                |
| Understand a rule or learn the guide | **Teach**  | Explain the rule, why it exists, and show a before/after       |

## Review and fix workflow

1. **Read the code category by category:** naming, programming
   recommendations, whitespace, imports, comments and docstrings. Note line
   numbers. The detailed rules are in `references/pep8-rules.md`.
2. **Look beyond the mechanical rules.** Check for misleading or stale comments,
   comments that restate the code instead of explaining why, vague names that
   technically follow the convention (`data2`, `tmp`), and missing docstrings on
   public functions and classes.
3. **Report** using the format below.
4. **Fix with style-only changes.** Behavior must stay identical, and two kinds
   of change need an explicit flag:
   - Renaming a public name (module-level function, class, constant, anything in
     `__all__`, or anything used from other files) can break callers. Flag it
     instead of renaming silently. Local variables and `_private` names are safe.
   - Narrowing a bare `except:` to specific exceptions changes behavior, because
     other exceptions will now propagate. That is the point of the fix, but say
     so, and say which exception you chose and why.
5. **Re-read the fixed code** against the same checklist before answering.

## Report format

Every finding carries its reason, because understanding the rule is what lets
the person avoid the mistake next time. Group findings by category and cite the
line. Lead with what matters most for correctness and readability.

```
## PEP 8 review: <file or snippet>

**Summary:** <one sentence: overall state and number of findings>

### Naming
- line 12: `myFunction` -> `my_function`
  - Why: functions use lowercase_with_underscores so that CapWords is reserved
    for classes, which lets a reader tell the two apart at a glance.

### Programming recommendations
- line 30: `if x == None` -> `if x is None`
  - Why: ...

(Imports / Whitespace / Comments and docstrings, only if they have findings)

### Fixed version
<the corrected code>

### What to remember
1. <takeaway>
2. <takeaway>
```

Omit empty categories. If the code is already clean, say so briefly instead of
inventing findings.

## Write workflow

Apply the core rules below while writing. Before answering, check naming,
import order, whitespace, and that every public function and class has a
docstring.

## Core rules at a glance

The complete list, with reasons and examples, is in
`references/pep8-rules.md`.

**Naming**

- `lowercase_with_underscores`: functions, methods, variables, modules.
- `CapWords`: classes and exceptions (exceptions end in `Error`).
  Acronyms stay uppercase: `HTTPServerError`.
- `UPPER_CASE_WITH_UNDERSCORES`: constants.
- `_leading_underscore`: internal use. `trailing_underscore_`: avoids a keyword
  clash (`class_`). Never name a variable `l`, `O`, or `I`.
- First argument is `self` in instance methods and `cls` in class methods.

**Programming recommendations**

- Compare to `None` (and other singletons) with `is` / `is not`.
- Write `is not`, never `not ... is`.
- Use `def`, not `name = lambda ...`, when binding a function to a name.
- Never use a bare `except:`; catch specific exceptions and keep the `try` body
  small.
- Do not compare booleans with `==`; use `if flag:`. Empty sequences are falsy,
  so use `if not items:`.
- Use `isinstance()` instead of comparing `type()`; use `startswith()` and
  `endswith()` instead of slicing.
- Use `with` for files and other resources.
- Be consistent with `return`: either every path returns a value or none does.

**Whitespace**

- Single space around assignment, comparison, and boolean operators:
  `x = 1`, `a == b`.
- No spaces around `=` in keyword arguments and defaults: `f(x=1)`. With an
  annotation, use spaces: `def f(x: int = 1)`.
- No space just inside brackets, before a comma, or between a function name and
  its `(`: `f(a, b)`, `items[0]`.
- No extra spaces to line up assignments; no trailing whitespace.

**Imports**

- One import per line, at the top of the file, after the module docstring.
- Three groups separated by a blank line: standard library, third-party, local.
- Prefer absolute imports; avoid `from module import *`.

**Comments and docstrings**

- Comments are complete sentences that explain _why_, not _what_. Block comments
  start with `# `; inline comments sit two spaces after the code.
- Public modules, functions, classes, and methods get docstrings, written with
  triple double quotes, a one-line summary in the imperative mood ("Return the
  total.", not "Returns the total.").
- A comment that contradicts the code is worse than none: update both together.

## Teaching mode

Teaching is a core part of this skill, not an optional extra. The person using
it is learning, so the goal is that they understand the rule well enough to
apply it alone next time, not just that the code gets fixed.

- **Explain every finding.** In reviews and fixes, each finding includes a
  one-sentence reason (see "Report format"). When the person asks to learn or
  asks "why", go deeper using the structure below.
- **Structure of a good explanation:** the rule, then why it exists, then a short
  before/after, then a way to remember it (a question to ask yourself while
  writing, such as "does this name tell me whether it is a class or a function?").
- **Separate convention from correctness.** Say honestly which rules are shared
  conventions that make code predictable (`snake_case`, import grouping) and which
  prevent real bugs (`is None`, bare `except`, `with` for files). Learners
  prioritize better when they know which ones can bite.
- **Define terms on first use:** identity vs equality, falsy, name mangling,
  dunder, docstring vs comment, context manager. Do not assume the vocabulary.
- **Group repeated violations.** If the same mistake appears ten times, teach it
  once and list the lines, instead of ten identical explanations.
- **Order by impact.** Teach naming and programming recommendations first;
  whitespace details last.
- **Close with 2 or 3 takeaways** ("What to remember"). When the person is clearly
  learning, offer a short practice snippet with a few violations to fix, and
  review their answer.
- **Be encouraging and accurate.** Do not invent violations to look thorough, and
  do not present a style preference as if it were a PEP 8 rule.

## References

- `references/pep8-rules.md`: the full rule set for the five in-scope areas, each
  with the reason behind it and do/don't examples. Read it when a case is not
  covered above or when you need to justify a rule in a teaching explanation.
