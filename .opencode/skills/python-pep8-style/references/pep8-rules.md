# PEP 8 rules reference

Covers the five areas of this skill, each rule with the reason behind it so it
can be used in teaching explanations. Code layout (indentation, line length,
blank lines, wrapping) is deliberately not included.
Source: https://peps.python.org/pep-0008/ and https://peps.python.org/pep-0257/

## Contents

1. A foolish consistency
2. Naming conventions
3. Programming recommendations
4. Whitespace in expressions and statements
5. Imports
6. Comments and docstrings

## 1. A foolish consistency

PEP 8 itself says that a style guide is about consistency, and that the most
important kind is consistency within a module or function. Break a rule when
following it would make the code _less_ readable, or when it would clash with
the surrounding code. Do not rewrite old code only to apply PEP 8.

_Why it matters for teaching:_ the rules serve readability. A learner who
understands this treats the rules as tools, not as commandments.

## 2. Naming conventions

| Kind                     | Convention                                | Example           |
| ------------------------ | ----------------------------------------- | ----------------- |
| Packages                 | short, lowercase, underscores discouraged | `utils`           |
| Modules                  | short, lowercase, underscores allowed     | `data_loader.py`  |
| Classes                  | `CapWords`                                | `OrderProcessor`  |
| Exceptions               | `CapWords`, ending in `Error` for errors  | `ValidationError` |
| Type variables           | short `CapWords`                          | `T`, `AnyStr`     |
| Functions, methods       | `lowercase_with_underscores`              | `load_orders`     |
| Variables, arguments     | `lowercase_with_underscores`              | `total_price`     |
| Constants (module level) | `UPPER_CASE_WITH_UNDERSCORES`             | `MAX_RETRIES`     |

**Why these conventions exist:** the casing tells the reader what a name _is_
before reading its definition. `CapWords` means "a class, so calling it builds
an object". `UPPER_CASE` means "a constant, do not reassign it". Lowercase means
"a function or a variable". The convention makes code predictable.

**Acronyms in CapWords stay fully uppercase:** `HTTPServerError`, not
`HttpServerError`.

**Exceptions end in `Error`** when they represent an error (`ValueError`,
`TimeoutError`). Why: it makes `except SomethingError` read naturally and tells
the reader the class is an exception, not a data class.

**First arguments:** `self` for instance methods, `cls` for class methods. Why:
every Python programmer reads these two names as "the instance" and "the class".
A different name works, but it forces the reader to stop and check.

**Leading and trailing underscores**

- `_name`: internal use. A signal to other programmers ("do not depend on this"),
  not enforced by the language. `from module import *` also skips these names.
- `name_`: trailing underscore avoids a clash with a keyword or builtin:
  `class_`, `type_`, `id_`.
- `__name` (two leading, none trailing) inside a class: _name mangling_. Python
  rewrites it to `_ClassName__name` so a subclass cannot accidentally replace it.
  It is a guard against name collisions in inheritance, not a way to make things
  private or secure.
- `__name__` (dunder): reserved for Python itself (`__init__`, `__all__`). Do not
  invent new ones.

**Names to avoid:** never use `l` (lowercase L), `O` (uppercase o), or `I`
(uppercase i) as single-character names. Why: in many fonts they look identical
to `1` and `0`, so `l = 1` can be read as `1 = 1`.

**Public and internal interfaces:** document public names and declare them in
`__all__`. Anything with a leading underscore is internal and may change without
notice. Why: users of a module need to know which names are safe to depend on.

**Related good practice (not stated in PEP 8):** do not shadow builtins such as
`list`, `dict`, `id`, `type`, `input`, or `max`. Why: after `list = [1, 2]`, the
call `list(range(3))` fails with a confusing error.

```python
# Do
class OrderProcessor:
    MAX_ITEMS = 100

    def total_price(self, tax_rate):
        item_totals = []
        return sum(item_totals)

# Don't
class order_processor:
    maxItems = 100

    def TotalPrice(self, taxRate):
        l = []
        return sum(l)
```

## 3. Programming recommendations

**Write code that does not depend on one Python implementation.** For example,
do not rely on CPython's fast in-place string concatenation; build strings with
`''.join(parts)`. Why: the trick can be slow or unavailable in other
implementations, and `join` is clear everywhere.

**Compare singletons with `is` / `is not`.**

```python
if x is None: ...        # Do
if x == None: ...        # Don't
```

Why: `==` calls the object's `__eq__` method, which a class can customize to
return surprising results. `is` checks _identity_ (is this the same object?),
which cannot be overridden, and there is only one `None`. Also be careful with
`if x:` when you mean `if x is not None:`: `0`, `''`, and `[]` are falsy but are
valid values.

**Prefer `is not` over `not ... is`.**

```python
if foo is not None: ...      # Do
if not foo is None: ...      # Don't
```

Why: the first reads as one operator, the second as a negated test and is easier
to misread.

**Use `def`, not an assigned lambda.**

```python
def double(x):               # Do
    return 2 * x

double = lambda x: 2 * x     # Don't
```

Why: a `def` gives the function a real name, which appears in tracebacks
(`double`) instead of `<lambda>`, and it can have a docstring. A lambda is fine
when passed inline, for example `sorted(items, key=lambda i: i.price)`.

**Derive custom exceptions from `Exception`, not `BaseException`.** Why:
`BaseException` includes `KeyboardInterrupt` and `SystemExit`, which a normal
`except Exception:` should not catch.

**Catch specific exceptions; never use a bare `except:`.**

```python
try:
    value = collection[key]
except KeyError:             # Do
    return key_not_found(key)

try:
    value = collection[key]
except:                      # Don't
    return None
```

Why: a bare `except:` also catches `KeyboardInterrupt` (Ctrl+C) and `SystemExit`,
so the program cannot be stopped, and it hides real bugs such as a typo that
raises `NameError`. PEP 8 allows it in two cases: logging the traceback, or
cleaning up and then re-raising.

**Use the explicit OS exception classes** (`FileNotFoundError`,
`PermissionError`) rather than checking `errno` numbers. Why: they are readable
and portable.

**Keep the `try` body minimal.**

```python
try:
    value = collection[key]          # Do: only the line that can fail
except KeyError:
    return key_not_found(key)
else:
    return handle_value(value)       # runs only if no exception occurred
```

Why: a long `try` block can catch an exception raised by a line you did not
intend to protect, which hides the bug.

**Chain exceptions explicitly** when raising a different one: `raise
ValueError("bad input") from exc`. Why: the traceback then shows the original
cause instead of "During handling of the above exception, another exception
occurred".

**Use `with` for resources.**

```python
with open('data.txt') as handle:     # Do
    contents = handle.read()

handle = open('data.txt')            # Don't: never closed if read() fails
contents = handle.read()
```

Why: `with` (a _context manager_) guarantees the file is closed even when an
exception is raised.

**Be consistent with `return`.** Either every `return` in a function returns an
expression, or none does. If any path returns a value, make the others
`return None` explicitly. Why: a function that returns a value on some paths and
silently falls off the end on others is easy to misuse.

```python
def first_positive(numbers):         # Do
    for number in numbers:
        if number > 0:
            return number
    return None

def first_positive(numbers):         # Don't: implicit None on one path
    for number in numbers:
        if number > 0:
            return number
```

**Use `startswith()` / `endswith()` instead of slicing.** `name.startswith('foo')`
beats `name[:3] == 'foo'` because there is no magic number to get wrong.

**Use `isinstance()` for type checks.** `isinstance(obj, int)` beats
`type(obj) is type(1)` because it also accepts subclasses.

**Do not compare booleans with `==`, and use the truthiness of sequences.**

```python
if greeting: ...             # Do
if greeting == True: ...     # Don't (and `is True` is worse)

if not items: ...            # Do: empty sequences are falsy
if len(items) == 0: ...      # Don't
```

Why: `greeting == True` is redundant, since `greeting` is already a condition.
_Falsy_ means "treated as False in a condition": empty lists, strings, and
dictionaries, plus `0` and `None`.

## 4. Whitespace in expressions and statements

**Avoid extraneous whitespace** in these situations. Why: extra spaces add visual
noise and make the same code look different from one author to the next.

```python
# Do
spam(ham[1], {eggs: 2})
foo = (0,)
x, y = y, x
spam(1)
dct['key'] = lst[index]

# Don't
spam( ham[ 1 ], { eggs: 2 } )     # spaces just inside brackets
foo = (0, )                       # space before closing bracket
if x == 4 : print(x , y)          # space before colon and comma
spam (1)                          # space before the call's parenthesis
dct ['key'] = lst [index]         # space before an index bracket
```

**Do not align with extra spaces.**

```python
# Do
x = 1
y = 2
long_variable = 3

# Don't
x             = 1
y             = 2
long_variable = 3
```

Why: aligning means that adding one longer name forces you to re-edit every other
line, which creates noisy diffs and fragile formatting.

**Binary operators: exactly one space on each side** of assignment (`=`, `+=`),
comparisons (`==`, `<`, `in`, `is`), and booleans (`and`, `or`, `not`).

```python
count = count + 1        # Do
count=count+1            # Don't
```

When operators of different priority are mixed, you may drop spaces around the
higher-priority ones. Why: the spacing mirrors how the expression is evaluated.

```python
hypot2 = x*x + y*y
c = (a+b) * (a-b)
```

**Keyword arguments and default values: no spaces around `=`**, except when the
parameter has an annotation.

```python
def complex(real, imag=0.0):                 # Do
    return magic(r=real, i=imag)

def munge(sep: AnyStr = None): ...           # Do: annotation, so spaces

def complex(real, imag = 0.0):               # Don't
    return magic(r = real, i = imag)
```

Why: without an annotation the `=` binds a name to a value and should look
tight; with an annotation the extra tokens need room to stay readable.

**Function annotations:** no space before the colon, one after; spaces around
`->`: `def total(items: list) -> float:`. Variable annotations: `count: int = 0`.

**Slices:** the colon works like a binary operator, so give it equal spacing on
both sides when the bounds are complex expressions, and none for simple slices.
When a part of the slice is omitted, omit its space too.

```python
# Do
ham[1:9]
ham[lower+offset : upper+offset]
ham[: upper_fn(x) : step_fn(y)]
ham[::step_fn(y)]

# Don't
ham[lower + offset:upper + offset]    # unequal spacing around the colon
ham[1: 9]
ham[1 :9]
ham[lower : : step]
```

Why: consistent spacing shows that the colon separates the bounds the same way an
operator separates operands.

**One statement per line.** Do not write `if x: do_something()` or
`first(); second()`. Why: the body of a conditional on its own line is easier to
scan and to step through in a debugger.

**No trailing whitespace.** Why: it is invisible, and it shows up as noise in
version-control diffs.

## 5. Imports

**One import per line.**

```python
import os                      # Do
import sys

import os, sys                 # Don't
```

`from subprocess import Popen, PIPE` is fine: several names from one module on a
single line is allowed. Why: one module per line makes additions and removals
clean in diffs.

**Place imports at the top of the file**, after the module docstring and any
module-level dunders (`__all__`, `__version__`), and before module globals and
constants. Why: a reader sees every dependency in one place.

**Group imports in this order**, with a blank line between groups:

1. Standard library (`os`, `sys`, `json`)
2. Related third-party packages (`requests`, `numpy`)
3. Local application or library modules

```python
"""Module docstring."""

import os
import sys

import requests

from myproject import utils
```

Why: the groups tell you at a glance what ships with Python, what must be
installed, and what lives in your own code. Alphabetical order inside each group
is a common extra convention that PEP 8 does not require.

**Prefer absolute imports** (`from myproject import utils`). Explicit relative
imports (`from . import sibling`) are acceptable inside packages. Why: absolute
imports keep working if the file moves and read the same everywhere.

**Avoid wildcard imports** (`from module import *`).

```python
from math import sqrt, pi      # Do
from math import *             # Don't
```

Why: the reader cannot tell where a name comes from, and tools cannot detect a
misspelled or unused name. A wildcard can also silently overwrite names you
already defined.

## 6. Comments and docstrings

### Comments

**Keep them accurate.** A comment that contradicts the code is worse than no
comment. Update comments whenever the code changes.

**Explain why, not what.** Code already says what it does; a comment adds the
reason behind it.

```python
# Do: explains a decision the code cannot show
# Retry once: the API occasionally drops the first request after idling.
response = fetch(url, retries=1)

# Don't: restates the code
x = x + 1  # increment x
```

**Write complete sentences.** Capitalize the first word unless it is an
identifier, and end with a period for sentence-style comments.

**Block comments** describe the code that follows. Indent them to the same level
as that code, start each line with `# ` (hash and one space), and separate
paragraphs with a line containing only `#`.

**Inline comments** go on the same line as a statement. Use them sparingly, with
at least two spaces between the code and `#`, and one space after it.

```python
timeout = 30  # Seconds; the server closes idle connections at 60.
```

**Language:** PEP 8 asks for comments in English unless you are certain nobody who
does not read your language will ever see the code. Teams may agree on another
language; consistency within the project wins.

### Docstrings (PEP 257)

A _docstring_ is a string literal that is the first statement of a module,
function, class, or method. Unlike a comment, Python keeps it at runtime
(`help(func)`, `func.__doc__`), so tools and IDEs can show it. Comments are for
maintainers; docstrings are for users of the code.

**Write docstrings for all public modules, functions, classes, and methods.**
Non-public methods do not need a docstring, but they should have a comment
explaining their purpose, placed after the `def` line.

**Use triple double quotes** (`"""`), even for one-liners. Why: it is the
universal convention, and a one-liner can grow into several lines without
changing the quotes.

**One-line docstring:** the quotes and text on one line, no blank line before or
after.

```python
def kelvin_to_celsius(kelvin):
    """Return the temperature in degrees Celsius."""
    return kelvin - 273.15
```

**Multi-line docstring:** a one-line summary, a blank line, then the details; the
closing quotes go on their own line.

```python
def total_by_customer(csv_path):
    """Return a dict mapping each customer to the sum of their orders.

    The CSV must have the columns ``customer`` and ``amount``.

    Args:
        csv_path: Path to the CSV file.

    Returns:
        A dict of customer name to total amount.

    Raises:
        KeyError: If a required column is missing.
        ValueError: If an ``amount`` value is not a number.
    """
```

**The summary line:** a short phrase ending with a period, in the _imperative
mood_ ("Return the total.", "Parse the file."), not the descriptive mood
("Returns the total."). Why: it describes what calling the function _does_, like
a command, and it stays consistent from one docstring to the next.

**Document arguments, return values, and exceptions** when they are not obvious.
PEP 257 does not prescribe a format for these sections. The common styles are
Google (`Args:`, `Returns:`, `Raises:`), NumPy, and reStructuredText. Pick one and
use it everywhere in the project.

**Classes:** the docstring summarizes the class's purpose and, for larger
classes, its public attributes and methods.

**Modules:** a docstring at the very top of the file says what the module is for.

**Backslashes:** use a raw docstring (`r"""..."""`) if the text contains
backslashes, so they are not interpreted as escapes.
