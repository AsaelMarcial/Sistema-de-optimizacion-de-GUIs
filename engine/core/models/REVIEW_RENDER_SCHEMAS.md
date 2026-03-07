# Revisión técnica inicial: dictionaries + schemas del módulo render

## Veredicto rápido

La base conceptual **sí es buena** para arrancar un pipeline de reconstrucción de design system:
- inventario de colores únicos,
- inventario de reglas/declaraciones,
- inventario de nodos renderizados y su origen de estilo.

Pero había problemas estructurales que te iban a bloquear pronto:
1. referencias `$ref` rotas entre archivos,
2. mezcla de responsabilidades entre "diccionarios" y "schemas",
3. algunos nombres ambiguos/inconsistentes.

## Qué se corrigió en esta iteración

- Se corrigieron referencias de `scope-colors.json` hacia los diccionarios de colores (`named-colors.json`, `system-colors.json`).
- Se corrigieron referencias internas entre schemas:
  - `style.json` ahora referencia `declaration.json`.
  - `element.json` ahora referencia `property.json`.
- Se corrigieron referencias al esquema de espacios de color para que apunten al archivo real (`../../Dictionaries/scope-colors.json`).
- Se normalizó un nombre en `color.json`: `foundedFormattes` -> `foundFormats`.
- Se corrigió un typo de `scope-properties.json`: `<interger>` -> `<integer>`.

## Opinión honesta sobre el enfoque actual

### Lo que está bien

- El modelo orientado a inventarios por ID (`colorId`, `styleRuleId`, `colorDeclarationId`, `elementId`) es correcto para trazabilidad y incrementalidad.
- La separación Color / Style / Element / Property es compatible con reconstrucción de "design intent".
- Usar JSON Schema Draft 2020-12 es una buena decisión para validación y evolución gradual.

### Lo que hoy está flojo

1. **`scope-colors` no es un diccionario puro**, es un esquema de tipos/formats.
   - Recomendación: moverlo conceptualmente a `Schemas/Common/color-space.json`.
2. **`named-colors` y `system-colors` están como objetos con una propiedad string**.
   - Para reutilización, suele ser más limpio exponer también arrays estáticos (`colors: []`) o `$defs` reutilizables.
3. **Falta cerrar relaciones referenciales entre inventarios**.
   - JSON Schema no resuelve foreign keys por sí solo. Necesitas una validación de segunda fase para asegurar que los IDs referenciados sí existen.
4. **`Color` trae demasiada información de salida junto con entrada**.
   - Si el objetivo inicial es deduplicar color, arranca mínimo con: `colorId`, `normalized`, `usage`, `aliases`.

## Propuesta de organización (primer paso realista)

- `models/contracts/` → listas de scope (elementos, propiedades, atributos) que cambian poco.
- `models/dictionaries/` → catálogos puros (named colors, system colors).
- `models/schemas/` → validaciones de estructuras de pipeline.

Esto baja ruido semántico: "scope" (reglas del dominio) no es lo mismo que "dictionary" (catálogo cerrado).

## Cómo empezar en el pipeline de render (orden recomendado)

1. **Fase A: extracción**
   - Capturar `StyleRule[]`, `ElementNode[]`, declaraciones crudas y valores computados.
2. **Fase B: normalización**
   - Parsear color en cualquier formato permitido y producir `normalized` (sRGB canónico).
3. **Fase C: inventario**
   - Deduplicar por color normalizado y generar `Color[]`.
4. **Fase D: vínculos**
   - Resolver `winningStyleRef` y `resolvedInitialColorRef`.
5. **Fase E: validación**
   - Validación estructural (JSON Schema) + validación relacional (IDs existentes + conteos consistentes).

## Criterios mínimos de calidad para continuar

- Cero `$ref` rotos.
- Cero valores fuera de scope de propiedades/atributos definidos.
- Cero referencias a IDs inexistentes.
- Conteos de uso (`elementUsageCount`) consistentes con listas de uso reales.

## Próximo entregable sugerido

Crear un validador de dos etapas:
1. `schema-validation` (AJV u otra librería JSON Schema 2020-12),
2. `relational-validation` (script custom para foreign keys e invariantes).

Con eso ya puedes usar estos archivos como **contrato ejecutable** del pipeline.
