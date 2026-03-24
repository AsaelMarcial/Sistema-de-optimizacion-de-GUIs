# ARCHITECTURE.md

## Purpose of this document

This document defines the **target architecture and coding conventions** for this project going forward.

It does **not** claim that every current file already matches this structure. Instead, it tells Codex how the project **must be organized from now on**, how each folder is expected to behave, which design patterns are preferred for each kind of file, and how common Python file types should be modeled.

If Codex finds code that does not clearly fit this architecture, it must:

1. **ask before moving or redesigning it**, or
2. **preserve it under a `legacy/` space** without breaking references.

This document is intentionally:
- architectural, not feature-specific,
- generic, not tied to a single implementation detail,
- strict about responsibilities,
- permissive only where architectural judgment is truly needed.

---

## Official project structure

```txt
engine/
├── domain/                         # Hexagon core: domain objects, rules, internal logic
│   ├── utils/
│   ├── models/
│   │   └── environmental_assessment/
│   ├── enums/
│   │   ├── types/
│   │   └── scope/
│   └── data/
│
├── pipeline/                       # Use cases: orchestration of domain logic
│   └── pipelines/
│
├── adapters/                       # External world: browser, file system, parsers, formatters
│   ├── browser/
│   ├── file_system/
│   └── utils/
│
└── main.py                         # Entry point
```

---

# 1. Folder responsibilities

## `domain/`

### What it is
The **core of the system**. It contains the project’s internal concepts and business meaning.

### What belongs here
- entities and models,
- internal structures,
- token-like objects,
- palettes, colors, styles, transformations,
- assessment objects,
- enums that define closed semantic domains,
- static datasets used by the domain,
- pure utilities used by the domain.

### What must NOT happen here
- direct browser access,
- direct filesystem access,
- direct Playwright/OpenCV/Pillow orchestration,
- HTML report rendering,
- parsing raw external formats unless the parsing is fully internal and pure,
- infrastructure-driven side effects.

### Architectural rule
Everything in `domain/` should still make sense if browser, filesystem, or UI adapters were replaced.

---

## `pipeline/`

### What it is
The **use-case orchestration layer**.

### What belongs here
- step-by-step workflows,
- sequencing of analysis, reconstruction, transformation, evaluation, reporting,
- coordination between domain and adapters,
- high-level execution order.

### What must NOT happen here
- heavy business rules that belong in models or domain helpers,
- raw external API handling,
- code that bypasses the domain model and manipulates loose data everywhere.

### Architectural rule
A pipeline orchestrates. It should read like a use case, not like a utility module.

---

## `adapters/`

### What it is
The **translation layer** between this system and the outside world.

### What belongs here
- browser wrappers,
- file system wrappers,
- external parser bridges,
- formatter bridges,
- source code readers/writers,
- screenshot/snapshot translators.

### What must NOT happen here
- business decisions,
- semantic token rules,
- domain policy,
- architectural ownership of core entities.

### Architectural rule
Adapters translate and isolate external tools. They should not define the project’s semantics.

---

## `domain/utils/` and `adapters/utils/`

### What they are
Shared helper modules. These are valid and intentional.

### What belongs here
- pure helper functions,
- lightweight formatters,
- lightweight parsers,
- sorting/grouping helpers,
- color math helpers,
- tree traversal helpers,
- validation helpers.

### What must NOT happen here
- an entire feature disguised as “helper code”,
- orchestration,
- hidden business logic that should live in models or pipelines,
- infrastructure side effects in `domain/utils`.

### Architectural rule
Utilities are reusable support code, not a replacement for architectural layers.

---

# 2. Allowed design patterns by file category

These rules are **guidelines with preference**, not blind obligations. A file may combine more than one pattern when justified.

---

## `domain/models/*.py`

### Typical purpose
Represent meaningful system objects such as elements, colors, styles, tokens, palettes, transformations, and assessments.

### Preferred patterns
- **Builder**: when the object is assembled step by step from multiple sources.
- **Iterator**: when the object contains a traversable internal structure.
- **Composite**: when the model is naturally tree-shaped.
- **Factory Method**: when there are multiple valid creation paths.
- **Strategy**: when the object delegates one interchangeable algorithm.
- **Command**: when the object represents an executable operation.
- **Observer**: only if the object truly publishes meaningful state changes.
- **Decorator**: only if optional behavior layers are needed without subclass explosion.

### What Codex should assume
A model file is not “just a dataclass by default”. It may be rich, typed, iterable, buildable, and behavior-bearing.

---

## `domain/enums/**/*.py`

### Typical purpose
Represent **closed symbolic sets** such as:
- token categories,
- transformation kinds,
- CSS property groups,
- HTML element kinds,
- semantic scopes.

### Preferred Python constructs
- `Enum`
- `StrEnum`
- `Flag` or `IntFlag` only if bitwise composition is actually needed

### Pattern note
Enums are **not** builders or services. They are closed vocabularies with optional helper behavior.

---

## `domain/data/*.py`

### Typical purpose
Static or read-only domain data:
- lookup tables,
- model coefficients,
- mappings,
- named color registries,
- thresholds,
- constant datasets.

### Pattern note
This is data, not orchestration. Keep it read-only and explicit.

---

## `domain/utils/*.py`

### Typical purpose
Pure or near-pure reusable helpers for the core.

### Preferred patterns
- plain functions first,
- **Strategy** only when multiple algorithms must be selected cleanly,
- no forced pattern when a function is enough.

---

## `pipeline/stages/*.py`

### Typical purpose
High-level workflows such as analysis, inventory building, token setup, transformation execution, and report generation.

### Preferred patterns
- **Facade**: expose a clear use-case entry point.
- **Template Method**: if multiple pipelines share the same execution skeleton.
- **Command**: only if a pipeline step must become an executable object with controlled execution/undo.

### Rule
Pipelines orchestrate domain behavior. They do not replace it.

---

## `adapters/browser/*.py`, `adapters/file_system/*.py`, `adapters/utils/*.py`

### Typical purpose
Bridge external systems into this architecture.

### Preferred pattern
- **Adapter** (primary)
- **Facade** may be layered on top if the external API is noisy
- **Context Manager** is preferred when external resources must be acquired/released safely

---

# 3. Generic file templates for Codex

These examples are intentionally **generic**. They are not tied to this project’s implementation details. Their purpose is to show Codex the **expected structural format** for each category.

---

## 3.1 Generic model file

Use this when creating a core entity or rich domain object.

```python
from __future__ import annotations

from typing import ClassVar, Iterator, Self


class GenericModel:
    """
    Responsibility:
        Represent one meaningful core entity.

    Allowed patterns:
        - Builder
        - Iterator
        - Composite (if tree-shaped)
        - Strategy (if delegating variable behavior)

    Notes:
        - Keep external I/O out of the model.
        - Use typed attributes.
        - Use classmethods for controlled construction.
    """

    DEFAULT_NAME: ClassVar[str] = "unnamed"

    def __init__(self, name: str, items: list[str] | None = None) -> None:
        self.name = name
        self.items = items or []

    @classmethod
    def build(cls, raw: object) -> "GenericModel":
        """
        Builder-style constructor.

        Use when the object needs normalization, validation,
        or assembly from multiple pieces of input.
        """
        normalized_name = str(raw).strip()
        return cls(name=normalized_name)

    def add_item(self, value: str) -> Self:
        self.items.append(value)
        return self

    def __iter__(self) -> Iterator[str]:
        """
        Iterator pattern when the model wraps a collection
        or exposes internal traversal.
        """
        return iter(self.items)

    def validate(self) -> bool:
        return bool(self.name)
```

### Why this format is good
- typed constructor,
- builder-style controlled construction,
- optional iterator,
- room for behavior,
- no side effects,
- no hidden infrastructure dependencies.

---

## 3.2 Generic composite model file

Use this when the model represents a tree or parent-child structure.

```python
from __future__ import annotations

from typing import Iterator


class Node:
    """
    Composite pattern:
        A node can contain other nodes and still be treated uniformly.
    """

    def __init__(self, label: str) -> None:
        self.label = label
        self.children: list[Node] = []

    def add_child(self, child: "Node") -> None:
        self.children.append(child)

    def remove_child(self, child: "Node") -> None:
        self.children.remove(child)

    def __iter__(self) -> Iterator["Node"]:
        """
        Shallow iteration over children.
        """
        return iter(self.children)

    def walk_depth_first(self) -> Iterator["Node"]:
        """
        Iterator pattern over a recursive structure.
        """
        yield self
        for child in self.children:
            yield from child.walk_depth_first()
```

### Why this format is good
- clearly expresses Composite,
- pairs naturally with Iterator,
- keeps traversal logic close to the structure.

---

## 3.3 Generic strategy-enabled model file

Use this when behavior varies by algorithm.

```python
from __future__ import annotations

from typing import Protocol


class ProcessorStrategy(Protocol):
    def execute(self, value: str) -> str: ...


class UppercaseStrategy:
    def execute(self, value: str) -> str:
        return value.upper()


class PrefixStrategy:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix

    def execute(self, value: str) -> str:
        return f"{self.prefix}{value}"


class Processor:
    """
    Strategy pattern:
        The object delegates one variable algorithm to a strategy object.
    """

    def __init__(self, strategy: ProcessorStrategy) -> None:
        self.strategy = strategy

    def set_strategy(self, strategy: ProcessorStrategy) -> None:
        self.strategy = strategy

    def process(self, value: str) -> str:
        return self.strategy.execute(value)
```

### Why this format is good
- uses `Protocol` for structural typing,
- keeps algorithm choices interchangeable,
- avoids giant conditionals.

---

## 3.4 Generic command file

Use this when a file represents an executable operation.

```python
from __future__ import annotations

from typing import Protocol


class CommandContext(Protocol):
    def log(self, message: str) -> None: ...


class Command:
    """
    Command pattern:
        Encapsulate an operation as an object.
    """

    name = "generic"

    def execute(self, context: CommandContext) -> None:
        raise NotImplementedError

    def undo(self, context: CommandContext) -> None:
        """
        Optional.
        Only implement if reversibility is meaningful.
        """
        pass


class PrintCommand(Command):
    name = "print"

    def __init__(self, message: str) -> None:
        self.message = message

    def execute(self, context: CommandContext) -> None:
        context.log(self.message)
```

### Why this format is good
- explicit executable behavior,
- supports optional `undo`,
- compatible with action-like execution systems.

---

## 3.5 Generic enum file

Use this for closed vocabularies.

```python
from enum import StrEnum, unique


@unique
class Status(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

    @classmethod
    def terminal_states(cls) -> tuple["Status", ...]:
        return (cls.COMPLETED, cls.FAILED)
```

### Why this format is good
- closed symbolic set,
- readable string values,
- behavior stays lightweight and local.

### Enum rules for Codex
- prefer `StrEnum` when values must round-trip to text,
- use `@unique` unless aliases are intentional,
- do not hide business workflows inside enums,
- do not use enums when a `Literal` union is enough and no behavior is needed.

---

## 3.6 Generic flag enum file

Use this only when composition is truly needed.

```python
from enum import Flag, auto


class Permission(Flag):
    READ = auto()
    WRITE = auto()
    EXECUTE = auto()
```

### Why this format is good
- supports composable flags,
- clearer than inventing integer bit masks manually.

### Rule
Do not use `Flag` or `IntFlag` unless bitwise composition is a real domain need.

---

## 3.7 Generic type alias file

Use this for lightweight type-level meaning.

```python
type HexColor = str
type FilePath = str
type Percentage = float
```

### Why this format is good
- makes signatures more readable,
- preserves semantics without overengineering.

### Rule
Use aliases when a primitive type has domain meaning.

---

## 3.8 Generic `TypedDict` file

Use this when the data shape matters but a full model class is unnecessary.

```python
from typing import NotRequired, TypedDict


class UserRecord(TypedDict):
    id: int
    name: str
    email: str
    phone: NotRequired[str]
```

### Why this format is good
- better than `dict[str, object]` for structured payloads,
- explicit required/optional fields,
- useful for raw records, parsed payloads, and adapter outputs.

### Rule
If a dictionary has a stable schema, prefer `TypedDict` over untyped dicts.

---

## 3.9 Generic discriminated union type file

Use this when records come in variants.

```python
from typing import Literal, TypedDict


class TextBlock(TypedDict):
    kind: Literal["text"]
    value: str


class ImageBlock(TypedDict):
    kind: Literal["image"]
    src: str


type Block = TextBlock | ImageBlock
```

### Why this format is good
- enables safe narrowing,
- cleaner than loose dict inspection,
- useful for parsed structures and report blocks.

---

## 3.10 Generic protocol file

Use this for structural interfaces that should not force inheritance.

```python
from typing import Iterable, Protocol


class SupportsBuild(Protocol):
    @classmethod
    def build(cls, raw: object) -> object: ...


class SupportsChildren(Protocol):
    def __iter__(self) -> Iterable[object]: ...
```

### Why this format is good
- enables structural subtyping,
- works well for builders, iterables, adapters, strategies, commands.

### Rule
Prefer `Protocol` for lightweight architectural contracts over deep abstract hierarchies unless inheritance is really needed.

---

## 3.11 Generic dataset file

Use this for static mappings and read-only domain constants.

```python
from types import MappingProxyType
from typing import Final

RAW_LEVELS: Final[dict[str, int]] = {
    "low": 1,
    "medium": 2,
    "high": 3,
}

LEVELS = MappingProxyType(RAW_LEVELS)
```

### Why this format is good
- explicit constant ownership,
- read-only public mapping,
- avoids silent mutation.

### Rule
Static reference data belongs in `data/`, not in utility modules or pipelines.

---

## 3.12 Generic utility file

Use this for pure reusable support code.

```python
def normalize_whitespace(value: str) -> str:
    """
    Pure helper:
        - deterministic
        - no side effects
        - reusable
    """
    return " ".join(value.split())


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
```

### Why this format is good
- simple,
- testable,
- no architectural confusion.

### Rule
If a helper starts carrying business meaning, move it out of `utils`.

---

## 3.13 Generic pipeline file

Use this for one use case or one major system step.

```python
from __future__ import annotations


class GenericPipeline:
    """
    Facade-style use case orchestrator.

    Responsibilities:
        - call domain objects
        - call adapters
        - preserve execution order
        - return an aggregated result

    Non-responsibilities:
        - defining core business rules
        - wrapping external API details directly if an adapter exists
    """

    def run(self, source: object) -> object:
        parsed = self._read_input(source)
        built = self._build_domain_state(parsed)
        result = self._evaluate(built)
        return result

    def _read_input(self, source: object) -> object:
        return source

    def _build_domain_state(self, parsed: object) -> object:
        return parsed

    def _evaluate(self, built: object) -> object:
        return built
```

### Why this format is good
- reads like a use case,
- keeps orchestration explicit,
- pushes core meaning into domain code.

---

## 3.14 Generic adapter file

Use this for browser, filesystem, parser, formatter, or external tool integration.

```python
from __future__ import annotations


class ExternalClient:
    def fetch(self, path: str) -> str:
        return f"raw:{path}"


class ResourceAdapter:
    """
    Adapter pattern:
        Translate an external interface into one that the project can use safely.
    """

    def __init__(self, client: ExternalClient) -> None:
        self.client = client

    def load_resource(self, path: str) -> dict[str, str]:
        raw = self.client.fetch(path)
        return {"content": raw}
```

### Why this format is good
- isolates external API shape,
- prevents leaking infrastructure into the domain,
- keeps translation logic in one place.

---

## 3.15 Generic context-managed adapter file

Use this when external resources need safe acquisition and release.

```python
from __future__ import annotations

from contextlib import AbstractContextManager


class SessionAdapter(AbstractContextManager["SessionAdapter"]):
    def __init__(self) -> None:
        self.connected = False

    def __enter__(self) -> "SessionAdapter":
        self.connected = True
        return self

    def request(self, payload: str) -> str:
        if not self.connected:
            raise RuntimeError("Session is not open")
        return f"response:{payload}"

    def __exit__(self, exc_type, exc, tb) -> None:
        self.connected = False
```

### Why this format is good
- clear lifecycle,
- safe cleanup,
- ideal for filesystem handles, browser sessions, temporary resources.

### Rule
Prefer context managers for adapters that manage external resources.

---

## 3.16 Generic `main.py` file

Use this as the application entry point.

```python
from __future__ import annotations


def main() -> None:
    """
    Entry point responsibilities:
        - build top-level dependencies
        - choose pipeline/use case
        - trigger execution
        - report success/failure

    It should NOT contain domain logic.
    """
    print("Starting application...")


if __name__ == "__main__":
    main()
```

### Why this format is good
- keeps bootstrapping explicit,
- avoids mixing startup with business rules.

---

# 4. Python typing guidance for Codex

These rules are important. Codex must follow them unless there is a strong reason not to.

## Prefer explicit typing
- use `list[str]`, `dict[str, int]`, `tuple[int, ...]`,
- avoid leaving public APIs untyped,
- annotate constructor arguments and return values.

## Prefer domain-friendly aliases
If a primitive value has meaning, use a type alias.

## Use `TypedDict` for structured records
If a dict has a stable schema, do not use `dict[str, object]` by default.

## Use `Protocol` for structural contracts
Use protocols for:
- strategies,
- builders,
- command-like executables,
- iterable/visitable structures,
- adapter-facing lightweight interfaces.

## Avoid `Any` by default
Use `Any` only as a deliberate escape hatch, not as convenience.

## Use `Self` for fluent or subclass-preserving returns
Use it in model methods such as `add_*()` or builder-like instance methods.

## Use `ClassVar` only for class-level state
Do not use it for normal instance attributes.

## Use `Final` for true constants
Good for immutable mappings, defaults, and reference data.

---

# 5. Construction rules by file category

## Models
A model file should usually contain:
- one main class,
- typed attributes,
- optional builder-style construction,
- optional iteration,
- business-relevant methods,
- no infrastructure side effects.

## Enums
An enum file should usually contain:
- one enum,
- symbolic members,
- optional lightweight helper methods,
- no workflow orchestration.

## Types
A type file should usually contain:
- aliases,
- `TypedDict`,
- `Protocol`,
- `Literal` unions,
- generic type helpers.

## Data
A data file should usually contain:
- constants,
- read-only mappings,
- static tables,
- no orchestration,
- no side effects.

## Pipelines
A pipeline file should usually contain:
- one main pipeline class or top-level callable,
- a clear `run()`-style entry point,
- ordered orchestration of steps,
- no domain logic duplication.

## Adapters
An adapter file should usually contain:
- one adapter or wrapper,
- translation from external shape to internal shape,
- resource management if needed,
- no domain semantics.

## Utilities
A utility file should usually contain:
- pure functions,
- deterministic helpers,
- reusable support logic,
- no hidden coupling.

---

# 6. What Codex must do when code does not fit

If existing or generated code does not clearly fit the architecture:

1. **Do not invent a new folder immediately.**
2. **Do not relocate files just because another arrangement looks cleaner.**
3. **Ask first if the move changes responsibility.**
4. If preservation is safer than guessing, place it under:

```txt
engine/legacy/
```

with a comment like:

```python
# TODO: preserve for compatibility; refactor into proper layer later
```

### Legacy rules
- preserve imports or compatibility bridges when possible,
- do not break references,
- do not silently delete old code during architectural cleanup,
- legacy is temporary preservation, not a dumping ground for new code.

---

# 7. What Codex must NOT do

Codex must NOT:

- create new architectural layers without justification,
- mix domain semantics into adapters,
- move business logic into pipelines,
- turn every helper into a class just to force a pattern,
- use patterns performatively,
- replace typed structures with loose dicts,
- leak external client objects into the domain,
- bypass the domain model with raw intermediate data everywhere,
- remove `utils/` just because some helpers could be inlined,
- over-normalize the repo into a different architecture without instruction.

---

# 8. What Codex SHOULD do before writing code

Before generating or changing code, Codex should answer internally:

1. **Which layer does this belong to?**
   - domain
   - pipeline
   - adapters
   - utils

2. **Which file category is it?**
   - model
   - enum
   - type
   - data
   - pipeline
   - adapter
   - util
   - entry point

3. **Which pattern is most appropriate here?**
   - Builder
   - Iterator
   - Composite
   - Strategy
   - Command
   - Adapter
   - Facade
   - plain function / no GoF pattern needed

4. **What should this file explicitly avoid?**

If the answer is unclear, Codex should ask.

---

# 9. Practical summary for Codex

## Short version
- `domain/` = meaning
- `pipeline/` = orchestration
- `adapters/` = translation to/from the outside world
- `utils/` = reusable support code

## Pattern summary
- models: rich objects, builders, iterators, composite if tree-like
- enums: closed symbolic sets
- types: aliases, protocols, typed dicts
- data: read-only mappings and static reference structures
- pipelines: facades for use cases
- adapters: wrappers for external systems
- utils: pure helpers first

## Safety summary
If unsure:
- ask, or
- preserve in `legacy/`

Do not improvise architecture.

---

# 10. Final instruction to Codex

Follow this architecture as a **guiding specification**.

Do not optimize it away.
Do not replace it with a cleaner architecture of your own.
Do not assume missing files already exist.
Do not fill architectural gaps by guessing if the responsibility is unclear.

Use this document to:
- place new code,
- judge refactors,
- choose suitable Python constructs,
- preserve structural consistency over time.


---

# 11. Pipeline Context Architecture

The system uses a structured **PipelineContext** instead of a flat context object.

## Principles

- The context MUST be hierarchical (composite structure)
- Data MUST be grouped by semantic domain:
  - session.*
  - inventory.*
  - color.*
  - environmental.*
- No flat attribute explosion is allowed

---

## Context Access

All stages MUST use:

- context.get("path.to.value")
- context.set("path.to.value", value)

Direct attribute mutation should be avoided unless inside context models.

---

## Context Evolution

The context is built progressively across pipeline stages.

Each stage:
- reads required data
- produces new data
- enriches the context

---

## Stage Contract

Every stage MUST:

1. Declare:

   requires = [...]
   produces = [...]

2. Validate inputs before execution

3. Use context.get/set for interaction

---

## Example

requires = ["inventory.elements"]
produces = ["inventory.elements_with_color"]

---

## Forbidden

- Writing random attributes into context
- Bypassing declared paths
- Mutating unrelated context branches
