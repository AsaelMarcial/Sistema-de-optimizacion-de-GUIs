# Guía / plantilla para construir `models/*` con POO en Python

> **Uso de este archivo**
>
> Este documento es una **guía y plantilla de referencia** para revisar, diseñar o refactorizar los archivos dentro de `models/*`.
>
> **No debe usarse como instrucción para crear literalmente las clases de ejemplo.**
> Los ejemplos son genéricos y sirven como base conceptual para decidir cómo construir modelos reales del proyecto.
>
> Antes de crear una clase nueva, Codex debe revisar si ya existe un modelo, enum, value object, función, helper, type alias o estructura equivalente que pueda reutilizarse o extenderse sin duplicar responsabilidades.

---

## 1. Objetivo de los `models/*`

Los `models/*` deben representar conceptos del dominio mediante objetos con identidad, datos, reglas e invariantes.

Un modelo debe existir cuando:

- Representa un concepto estable del dominio.
- Necesita mantener estado propio.
- Tiene invariantes que deben protegerse.
- Tiene comportamiento asociado a sus datos.
- Se relaciona con otros modelos.
- Necesita validación, comparación, serialización o transformación controlada.

Un modelo **no** debe existir solo para envolver una función, agrupar constantes sin comportamiento o crear una clase artificial sin responsabilidad clara.

---

## 2. Términos base

### Clase

Una **clase** es una plantilla para crear objetos. Define atributos, métodos, restricciones e invariantes.

```python
class Item:
    pass
```

### Objeto / instancia

Un **objeto** o **instancia** es un elemento concreto creado a partir de una clase.

```python
item = Item()
```

En Python, todo objeto tiene:

- identidad: `id(obj)`
- tipo: `type(obj)`
- valor / estado: sus atributos internos

### Atributo

Dato asociado a un objeto o clase.

```python
class Item:
    category = "generic"  # atributo de clase

    def __init__(self, name: str) -> None:
        self.name = name  # atributo de instancia
```

### Método

Función asociada a una clase.

```python
class Item:
    def rename(self, name: str) -> None:
        self.name = name
```

### Invariante

Regla que siempre debe cumplirse para que el objeto sea válido.

Ejemplo: un porcentaje debe estar entre `0` y `100`.

---

## 3. Regla principal: no crear clases “a lo wey”

Antes de crear una clase, Codex debe responder:

1. ¿Qué concepto del dominio representa?
2. ¿Tiene estado propio?
3. ¿Tiene comportamiento propio?
4. ¿Tiene invariantes que proteger?
5. ¿Se usa en más de un lugar?
6. ¿Mejora la legibilidad o solo añade indirección?
7. ¿Ya existe algo equivalente en el proyecto?

Si la respuesta principal es “solo agrupa una función”, probablemente debe ser una función, no una clase.

---

## 4. Cuándo usar clase y cuándo usar función

### Usar clase cuando

- Hay estado que vive más de una llamada.
- Hay reglas de consistencia internas.
- Hay identidad o ciclo de vida.
- Hay varias operaciones sobre el mismo estado.
- Se necesita polimorfismo.
- Se requiere encapsular mutaciones.
- Se necesita modelar composición entre objetos.

```python
class Cart:
    def __init__(self) -> None:
        self._items: list[str] = []

    def add_item(self, item: str) -> None:
        if not item:
            raise ValueError("item cannot be empty")
        self._items.append(item)

    def get_items(self) -> tuple[str, ...]:
        return tuple(self._items)
```

### Usar función cuando

- No hay estado persistente.
- Solo transforma datos de entrada en salida.
- No necesita identidad.
- No necesita herencia ni polimorfismo.
- No protege invariantes internas.
- La operación es pura o casi pura.

```python
def normalize_name(value: str) -> str:
    return value.strip().lower()
```

### Usar módulo de funciones cuando

- Son helpers reutilizables.
- No pertenecen naturalmente a un único modelo.
- Son operaciones independientes.

```python
# utils/text.py

def slugify(value: str) -> str:
    return value.strip().lower().replace(" ", "-")
```

---

## 5. Estructura recomendada de un modelo

Orden sugerido dentro de una clase:

1. Docstring breve.
2. Constantes de clase.
3. Atributos tipados, si aplica.
4. `__init__` o `@dataclass`.
5. Properties de lectura.
6. Setters controlados, si realmente hacen falta.
7. Métodos de dominio.
8. Métodos de consulta.
9. Métodos de serialización.
10. Métodos especiales: `__repr__`, `__eq__`, `__hash__`, etc.

Ejemplo genérico:

```python
from __future__ import annotations


class Entity:
    """Generic entity with identity and controlled state."""

    def __init__(self, entity_id: str, name: str) -> None:
        self._id = self._validate_id(entity_id)
        self._name = self._validate_name(name)

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    def rename(self, name: str) -> None:
        self._name = self._validate_name(name)

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> Entity:
        return cls(
            entity_id=data["id"],
            name=data["name"],
        )

    @staticmethod
    def _validate_id(value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("id cannot be empty")
        return value

    @staticmethod
    def _validate_name(value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be empty")
        return value

    def __repr__(self) -> str:
        return f"Entity(id={self.id!r}, name={self.name!r})"
```

---

## 6. `__init__`, `__new__` y ciclo de creación

### `__init__`

Se usa para inicializar una instancia ya creada.

```python
class User:
    def __init__(self, name: str) -> None:
        self.name = name
```

Reglas:

- No debe devolver nada.
- Debe dejar el objeto en estado válido.
- Debe validar invariantes iniciales.
- Debe evitar hacer I/O pesado si el modelo pertenece a dominio puro.

### `__new__`

Se usa para controlar la creación real del objeto. Normalmente no se necesita.

Casos válidos:

- Subclases de tipos inmutables: `str`, `int`, `tuple`.
- Singletons muy justificados.
- Frameworks o metaprogramación avanzada.

Ejemplo genérico:

```python
from typing import Self


class Email(str):
    def __new__(cls, value: str) -> Self:
        value = value.strip().lower()
        if "@" not in value:
            raise ValueError("invalid email")
        return super().__new__(cls, value)
```

No usar `__new__` para lógica normal de negocio si `__init__`, `@classmethod` o una factory simple resuelven el caso.

---

## 7. Encapsulamiento

Python no usa getters y setters estilo Java para todo.

### Atributo público

Usar cuando no hay regla especial.

```python
class Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
```

### Atributo interno con `_`

Usar cuando no debe modificarse directamente desde fuera.

```python
class Counter:
    def __init__(self) -> None:
        self._value = 0
```

### `property`

Usar cuando se necesita exponer lectura o controlar escritura.

```python
class Percentage:
    def __init__(self, value: float) -> None:
        self._value = 0.0
        self.value = value

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, value: float) -> None:
        if not 0 <= value <= 100:
            raise ValueError("percentage must be between 0 and 100")
        self._value = float(value)
```

### Métodos `get_*` y `set_*`

Usarlos solo si representan una acción explícita o acceso semántico, no por costumbre.

Válido:

```python
class Registry:
    def get_by_id(self, item_id: str) -> object:
        return self._items[item_id]

    def set_default(self, item: object) -> None:
        self._default = item
```

Evitar:

```python
class User:
    def get_name(self) -> str:
        return self.name

    def set_name(self, name: str) -> None:
        self.name = name
```

Preferible:

```python
class User:
    def __init__(self, name: str) -> None:
        self.name = name
```

---

## 8. Validaciones

Las validaciones deben vivir cerca del lugar donde se protege la regla.

### En `__init__`

```python
class Age:
    def __init__(self, value: int) -> None:
        if value < 0:
            raise ValueError("age cannot be negative")
        self.value = value
```

### En `property`

```python
class Account:
    def __init__(self, balance: int) -> None:
        self._balance = 0
        self.balance = balance

    @property
    def balance(self) -> int:
        return self._balance

    @balance.setter
    def balance(self, value: int) -> None:
        if value < 0:
            raise ValueError("balance cannot be negative")
        self._balance = value
```

### En método de dominio

```python
class Account:
    def __init__(self, balance: int = 0) -> None:
        self._balance = balance

    def withdraw(self, amount: int) -> None:
        if amount <= 0:
            raise ValueError("amount must be positive")
        if amount > self._balance:
            raise ValueError("insufficient balance")
        self._balance -= amount
```

### En `__post_init__` con dataclass

```python
from dataclasses import dataclass


@dataclass(slots=True)
class Range:
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ValueError("start must be <= end")
```

---

## 9. `dataclass`

Usar `@dataclass` cuando el modelo es principalmente datos con comportamiento ligero o mediano.

```python
from dataclasses import dataclass, field


@dataclass(slots=True)
class Product:
    sku: str
    tags: list[str] = field(default_factory=list)
```

Reglas:

- Usar `field(default_factory=...)` para listas, diccionarios, sets u otros mutables.
- Usar `slots=True` si habrá muchas instancias o se quiere evitar atributos dinámicos.
- Usar `frozen=True` para value objects lógicamente inmutables.
- Usar `__post_init__` para validaciones cruzadas.
- No usar dataclass si la clase tiene un ciclo de vida complejo o demasiada lógica de mutación.

### Dataclass mutable

```python
from dataclasses import dataclass


@dataclass(slots=True)
class MutableItem:
    name: str
    count: int = 0

    def increment(self) -> None:
        self.count += 1
```

### Dataclass frozen

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Money:
    currency: str
    amount: int

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("amount cannot be negative")
```

`frozen=True` significa inmutabilidad lógica, no absoluta. Si contiene una lista interna, esa lista puede seguir siendo mutable.

---

## 10. `attrs`

Usar `attrs` cuando se necesitan validadores, converters o control más fuerte que `dataclass`.

```python
from attrs import define, field


def positive(instance, attribute, value: int) -> None:
    if value <= 0:
        raise ValueError(f"{attribute.name} must be positive")


@define
class Quantity:
    value: int = field(converter=int, validator=positive)
```

Reglas:

- Usar `attrs` si ya está permitido como dependencia del proyecto.
- No mezclar `dataclass` y `attrs` sin razón clara.
- Preferir una sola estrategia dominante para `models/*`.

---

## 11. `__slots__`

`__slots__` restringe atributos dinámicos y puede reducir memoria.

Manual:

```python
class SlottedItem:
    __slots__ = ("name", "count")

    def __init__(self, name: str, count: int) -> None:
        self.name = name
        self.count = count
```

Con dataclass:

```python
from dataclasses import dataclass


@dataclass(slots=True)
class SlottedItem:
    name: str
    count: int
```

Usar cuando:

- Habrá muchas instancias.
- No se necesitan atributos dinámicos.
- Se quiere una estructura más estricta.

Evitar cuando:

- El modelo requiere atributos agregados dinámicamente.
- Alguna librería depende de `__dict__`.
- Hay herencia múltiple compleja.

---

## 12. Herencia

Usar herencia solo cuando existe una relación real “es un tipo de”.

```python
class Shape:
    def area(self) -> float:
        raise NotImplementedError


class Square(Shape):
    def __init__(self, side: float) -> None:
        self.side = side

    def area(self) -> float:
        return self.side * self.side
```

Evitar herencia si solo se busca reutilizar código. En ese caso, preferir composición.

Malo:

```python
class Report(FileWriter):
    pass
```

Mejor:

```python
class Report:
    def __init__(self, writer: object) -> None:
        self._writer = writer
```

---

## 13. Composición

Preferir composición cuando un objeto está formado por otros objetos.

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Address:
    city: str
    country: str


class Customer:
    def __init__(self, name: str, address: Address) -> None:
        self.name = name
        self.address = address
```

Usar composición para:

- Evitar jerarquías rígidas.
- Reutilizar comportamiento sin herencia.
- Expresar relaciones “tiene un”.

---

## 14. Clases con clases como atributos

Un modelo puede tener otros modelos como atributos.

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Coordinates:
    x: float
    y: float


@dataclass(slots=True)
class Node:
    id: str
    position: Coordinates
```

Reglas:

- Si el atributo representa una parte del objeto, usar composición.
- Si puede existir por separado, usar agregación.
- Si solo se referencia temporalmente, usar asociación.

---

## 15. Inner classes / clases anidadas

Python permite declarar una clase dentro de otra, pero no es igual a Java.

Usar con moderación para conceptos muy internos y no reutilizables.

```python
class Workflow:
    class Status:
        PENDING = "pending"
        RUNNING = "running"
        DONE = "done"

    def __init__(self) -> None:
        self.status = self.Status.PENDING
```

Usar inner class cuando:

- Solo tiene sentido dentro de la clase contenedora.
- No debe reutilizarse desde otros módulos.
- Ayuda a expresar estados o estructuras internas pequeñas.

Evitar inner class cuando:

- La clase será importada en varios lugares.
- Tiene lógica propia significativa.
- Es un modelo del dominio por sí misma.

En esos casos, ponerla como clase normal en su propio archivo o módulo.

---

## 16. Abstracción

La abstracción oculta detalles internos y expone una interfaz clara.

### ABC

Usar `ABC` cuando se quiere un contrato nominal.

```python
from abc import ABC, abstractmethod


class Exporter(ABC):
    @abstractmethod
    def export(self, data: dict[str, object]) -> str:
        raise NotImplementedError
```

### Protocol

Usar `Protocol` cuando se quiere tipado estructural sin obligar a heredar.

```python
from typing import Protocol


class Exporter(Protocol):
    def export(self, data: dict[str, object]) -> str:
        ...
```

Regla:

- Preferir `Protocol` para puertos, contratos y dependencias intercambiables.
- Usar `ABC` cuando se necesite herencia real, mixins o `isinstance` nominal.

---

## 17. Polimorfismo

Polimorfismo significa que distintos objetos pueden usarse mediante la misma interfaz.

```python
class JsonExporter:
    def export(self, data: dict[str, object]) -> str:
        import json
        return json.dumps(data)


class TextExporter:
    def export(self, data: dict[str, object]) -> str:
        return "\n".join(f"{key}: {value}" for key, value in data.items())


def export_data(exporter: object, data: dict[str, object]) -> str:
    return exporter.export(data)
```

Con `Protocol`:

```python
from typing import Protocol


class Exporter(Protocol):
    def export(self, data: dict[str, object]) -> str:
        ...


def export_data(exporter: Exporter, data: dict[str, object]) -> str:
    return exporter.export(data)
```

---

## 18. Colecciones en modelos

Usar colecciones tipadas y protegerlas si son internas.

### Lista interna mutable protegida

```python
class Group:
    def __init__(self) -> None:
        self._members: list[str] = []

    def add_member(self, name: str) -> None:
        if not name:
            raise ValueError("name cannot be empty")
        self._members.append(name)

    def get_members(self) -> tuple[str, ...]:
        return tuple(self._members)
```

### Diccionario interno

```python
class Registry:
    def __init__(self) -> None:
        self._items: dict[str, object] = {}

    def register(self, key: str, item: object) -> None:
        if key in self._items:
            raise ValueError(f"duplicated key: {key}")
        self._items[key] = item

    def get_by_key(self, key: str) -> object:
        return self._items[key]
```

### Set para unicidad

```python
class UniqueNames:
    def __init__(self) -> None:
        self._names: set[str] = set()

    def add_name(self, name: str) -> None:
        if name in self._names:
            raise ValueError("duplicated name")
        self._names.add(name)
```

Reglas:

- Usar `list` para orden y repetición.
- Usar `set` para unicidad.
- Usar `dict` para búsqueda por clave.
- Usar `tuple` para exponer vistas inmutables.
- No devolver colecciones internas mutables si eso rompe invariantes.

---

## 19. Igualdad, hash y representación

### `__repr__`

Debe ser útil para debugging.

```python
class Item:
    def __init__(self, item_id: str) -> None:
        self.item_id = item_id

    def __repr__(self) -> str:
        return f"Item(item_id={self.item_id!r})"
```

### `__eq__`

Usar cuando hay igualdad lógica.

```python
class Item:
    def __init__(self, item_id: str) -> None:
        self.item_id = item_id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Item):
            return NotImplemented
        return self.item_id == other.item_id
```

### `__hash__`

Solo usar si el objeto es lógicamente inmutable.

```python
class ItemId:
    def __init__(self, value: str) -> None:
        self._value = value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ItemId):
            return NotImplemented
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)
```

Regla:

- Si el objeto es mutable, normalmente no debe tener `__hash__`.
- Si se define `__eq__`, revisar explícitamente qué debe pasar con `__hash__`.

---

## 20. Classmethod, staticmethod y factory methods

### `@classmethod`

Usar para constructores alternativos.

```python
class User:
    def __init__(self, name: str, email: str) -> None:
        self.name = name
        self.email = email

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "User":
        return cls(name=data["name"], email=data["email"])
```

### `@staticmethod`

Usar para helpers ligados conceptualmente a la clase, pero que no usan `self` ni `cls`.

```python
class User:
    @staticmethod
    def normalize_email(value: str) -> str:
        return value.strip().lower()
```

No meter cualquier helper como `staticmethod`. Si no pertenece al modelo, debe vivir como función de módulo.

---

## 21. Serialización

Los modelos pueden exponer `to_dict` y `from_dict` si el proyecto lo necesita.

```python
class Item:
    def __init__(self, item_id: str, name: str) -> None:
        self.item_id = item_id
        self.name = name

    def to_dict(self) -> dict[str, str]:
        return {
            "item_id": self.item_id,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "Item":
        return cls(
            item_id=data["item_id"],
            name=data["name"],
        )
```

Reglas:

- No acoplar modelos de dominio a archivos, rutas o JSON físico si eso pertenece a adapters.
- `to_dict` debe devolver estructuras simples.
- `from_dict` debe validar y normalizar.
- Evitar `pickle` para datos externos o no confiables.

---

## 22. Excepciones de dominio

Crear excepciones propias solo si ayudan a distinguir errores.

```python
class DomainError(Exception):
    pass


class DuplicatedItemError(DomainError):
    pass
```

Usar:

```python
class Registry:
    def __init__(self) -> None:
        self._items: dict[str, object] = {}

    def register(self, key: str, item: object) -> None:
        if key in self._items:
            raise DuplicatedItemError(key)
        self._items[key] = item
```

No crear 20 excepciones si nadie las maneja distinto.

---

## 23. Restricciones recomendadas para `models/*`

Los modelos deben:

- Tener nombres claros y representativos.
- Usar `snake_case` en métodos y atributos.
- Usar `PascalCase` en clases.
- Tener type hints.
- Validar invariantes.
- Evitar dependencias de infraestructura.
- Evitar I/O directo.
- Evitar referencias innecesarias a frameworks.
- Evitar setters genéricos sin validación.
- Evitar clases vacías o wrappers artificiales.
- Exponer colecciones internas como `tuple` o copias si hay riesgo de mutación externa.
- Preferir composición sobre herencia.
- Usar `Protocol` para contratos intercambiables.
- Usar `dataclass(slots=True)` para value objects o modelos de datos simples.
- Usar `frozen=True` solo cuando el objeto debe ser lógicamente inmutable.

---

## 24. Plantilla base para value object

Un value object se identifica por su valor, no por identidad propia.

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ValueObject:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        if not normalized:
            raise ValueError("value cannot be empty")
        object.__setattr__(self, "value", normalized)
```

Usar para:

- IDs.
- Colores.
- Coordenadas.
- Medidas.
- Rangos.
- Tokens.
- Valores normalizados.

---

## 25. Plantilla base para entidad

Una entidad tiene identidad estable.

```python
class Entity:
    def __init__(self, entity_id: str, name: str) -> None:
        self._id = self._validate_id(entity_id)
        self._name = self._validate_name(name)

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    def rename(self, name: str) -> None:
        self._name = self._validate_name(name)

    @staticmethod
    def _validate_id(value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("id cannot be be empty")
        return value

    @staticmethod
    def _validate_name(value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be empty")
        return value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return self.id == other.id

    def __repr__(self) -> str:
        return f"Entity(id={self.id!r}, name={self.name!r})"
```

Si la entidad es mutable, evitar `__hash__`.

---

## 26. Plantilla base para catálogo / colección controlada

Usar cuando una clase gestiona unicidad, búsqueda y relación entre objetos.

```python
class Catalog:
    def __init__(self) -> None:
        self._items_by_id: dict[str, object] = {}

    def add_item(self, item_id: str, item: object) -> None:
        if item_id in self._items_by_id:
            raise ValueError(f"duplicated item: {item_id}")
        self._items_by_id[item_id] = item

    def get_item(self, item_id: str) -> object:
        return self._items_by_id[item_id]

    def has_item(self, item_id: str) -> bool:
        return item_id in self._items_by_id

    def get_items(self) -> tuple[object, ...]:
        return tuple(self._items_by_id.values())
```

---

## 27. Checklist para revisar un modelo existente

Codex debe revisar cada archivo de `models/*` con esta lista:

1. ¿La clase representa un concepto real del dominio?
2. ¿El nombre comunica su responsabilidad?
3. ¿Tiene una sola responsabilidad principal?
4. ¿Sus atributos tienen type hints?
5. ¿Sus invariantes se validan al crear y modificar?
6. ¿Hay setters innecesarios?
7. ¿Hay getters innecesarios?
8. ¿Expone listas/dicts internos que pueden romper el estado?
9. ¿Usa `dataclass` cuando sería suficiente?
10. ¿Usa clase manual cuando necesita más control?
11. ¿Usa `frozen=True` solo si corresponde?
12. ¿Usa `slots=True` si conviene restringir atributos o ahorrar memoria?
13. ¿Tiene `__repr__` útil para debug?
14. ¿Define `__eq__` correctamente?
15. ¿Define o evita `__hash__` correctamente?
16. ¿Usa composición antes que herencia?
17. ¿La herencia representa realmente “es un tipo de”?
18. ¿Hay inner classes que deberían salir a su propio módulo?
19. ¿Hay funciones convertidas en clases sin necesidad?
20. ¿Hay lógica de infraestructura dentro del modelo?
21. ¿Hay duplicación con otro modelo, enum, helper o type existente?
22. ¿Los métodos tienen nombres PEP8 claros?
23. ¿Los errores son claros y manejables?
24. ¿Los modelos pueden probarse sin I/O externo?
25. ¿El archivo mantiene cohesión y no mezcla demasiados conceptos?

---

## 28. Decisión rápida

| Necesidad | Recomendación |
|---|---|
| Solo transformar datos sin estado | Función |
| Agrupar constantes | `Enum`, `Literal`, módulo de constantes o diccionario controlado |
| Datos simples | `@dataclass(slots=True)` |
| Valor inmutable | `@dataclass(frozen=True, slots=True)` |
| Validaciones/converters fuertes | `attrs` si el proyecto lo permite |
| Objeto con identidad y comportamiento | Clase manual o dataclass con métodos |
| Relación “tiene un” | Composición |
| Relación “es un tipo de” | Herencia |
| Contrato flexible | `Protocol` |
| Contrato nominal | `ABC` |
| Colección con reglas de unicidad | Clase catálogo/registro |
| Helper sin estado | Función de módulo |

---

## 29. Instrucción especial para Codex

Cuando uses esta guía:

1. No copies los ejemplos como implementación final.
2. No inventes clases solo porque aparecen en la guía.
3. Analiza primero los modelos existentes.
4. Detecta equivalencias aunque no tengan el mismo nombre.
5. Reutiliza, renombra o refactoriza antes de crear algo nuevo.
6. Mantén los modelos libres de infraestructura.
7. Justifica cada clase nueva con su responsabilidad, invariantes y relaciones.
8. Si algo puede ser una función clara y pura, no lo conviertas en clase.
9. Si una clase solo tiene un método y no tiene estado, probablemente sobra.
10. Entrega cambios pequeños, coherentes y probables de probar.

