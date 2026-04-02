# Especificación de requisitos de software (SRS)
## Refactor de preparación/extracción/estructuración del prototipo (v3 + complemento v4)

**Estado:** Propuesta técnica formal.  
**Fecha:** 2026-04-01.  
**Autoría:** Ingeniería de software (definición arquitectónica y de requisitos).

---
## 0. Gobierno y precedencia documental

Esta SRS es la especificación prioritaria del tramo en alcance.

Orden de precedencia:

1. esta SRS;
2. `docs/ARCHITECTURE_FINAL.md` como marco arquitectónico general;
3. implementación actual.

### Regla de conflicto

* Si existe conflicto entre esta SRS y `ARCHITECTURE_FINAL.md`, prevalece esta SRS para este tramo.
* Si existe conflicto entre esta SRS y la implementación actual, no se podrá cambiar el criterio por inferencia: se deberá detener el punto conflictivo, mostrar evidencia y solicitar aprobación explícita del usuario para continuar.

## 1. Propósito

Definir, de forma verificable y ejecutable, cómo refactorizar el tramo inicial del engine para:

1. usar el `PipelineContext` existente como única fuente de verdad por corrida,
2. eliminar por completo JSON intermedios de debug en la ruta principal,
3. simplificar el modelado interno del prototipo de alta fidelidad,
4. reducir duplicación, contradicciones y sobreprocesamiento,
5. mantener integración coherente con el resto del pipeline.

---

## 2. Alcance

### 2.1 En alcance

- Preparación de sesión.
- Extracción de estado inicial del prototipo de alta fidelidad.
- Estructuración en memoria para consumo downstream.
- Derivados inmediatos del estado estructurado (insumos para contraste, patrones, esquema de color y transformación).
- Definición de reglas de naming, SOLID/POO/PEP8 y clasificación de módulos.

### 2.2 Fuera de alcance (por ahora)

- Replanteamiento completo de módulos de assessment ambiental.
- Cambios de UI funcionales mayores en `results.html`.
- Rediseño total del pipeline de punta a punta en una sola iteración.

---

## 3. Términos y definiciones

- **Corrida (run):** ejecución completa del pipeline para un input.
- **SSoT (Single Source of Truth):** única representación autoritativa de estado por corrida.
- **Context:** `PipelineContext`, contenedor de estado en memoria de toda la corrida.
- **Prototype Structure:** estructura normalizada del DOM/cómputo de estilos por nodo para análisis.
- **JSON intermedio:** artefacto persistido sólo para debug/inspección temporal, no requerido por la lógica de negocio final.

---

## 4. Requisitos de negocio y de arquitectura

### RB-01 (SSoT por corrida)
Por cada corrida debe existir una única instancia semántica de:
- `session`
- `scheme`
- `prototype_structure`

### RB-02 (No duplicación semántica)
El mismo dato de negocio no puede vivir como verdad en dos ramas diferentes del `context`.

### RB-03 (Eliminación de JSON intermedio)
La ruta principal no debe leer ni escribir JSON intermedio en el tramo en alcance.

### RB-04 (Integración progresiva)
Los cambios deben conectarse con el pipeline existente sin ruptura de contrato funcional global.

### RB-05 (Observabilidad)
Se conserva trazabilidad por etapas mediante `trace`, sin reintroducir JSON debug como fuente primaria.

---

## 5. Modelo canónico de datos en `context`

## 5.1 Estructura obligatoria

```text
session.id
session.base_path
session.input_path
session.output_path
session.artifacts_path

scheme.colors
scheme.tonal_palettes
scheme.display_pixels

prototype_structure.nodes
prototype_structure.indexes.by_tag
prototype_structure.indexes.by_classification
prototype_structure.indexes.by_depth

environmental.inputs.original.raw_pixel_frequencies
environmental.inputs.output.raw_pixel_frequencies
```

## 5.2 Restricciones

- `session.id`: string no vacío, único por corrida.
- `nodes`: colección ordenada y estable por recorrido.
- `indexes.*`: siempre derivados de `nodes` (no dueños primarios de estado).
- `prototype_structure` sólo contiene estructura, relaciones y propiedades resueltas mínimas por nodo.
- `scheme.display_pixels` es evidencia visual complementaria para construir el scheme.
- `environmental.inputs.*.raw_pixel_frequencies` es input de assessment ambiental, no parte de `prototype_structure`.

---

## 6. Modelado interno (POO) — entidades mínimas

> El estado vivo permanece en `context`; los modelos encapsulan validación/operaciones de dominio.

### 6.1 Entidades recomendadas

#### Diagrama de dominio (objetos y conexiones)

```text
Session (1) ------------------------------> PrototypeStructure (1)
  id, base/input/output/artifacts paths        nodes
                                                indexes(by_tag, by_classification, by_depth)
                                                |
                                                | contiene (1..N)
                                                v
                                             Element (1..N)
                                             node_id, tag, xpath,
                                             parent_id, children_ids,
                                             classification
                                                |
                                                | contiene (1..N)
                                                v
                                             Property (1..N)
                                             name, value,
                                             classification(background|foreground|effect|other)

ColorScheme (1)
  colors, tonal_palettes, display_pixels
      |
      | contiene (1..N)
      v
   Color (1..N)
   color_id, value, normalized_value, source_role

Style (0..N rules) -----------------------> StyleDeclaration (1..N por rule)
  rule metadata                               name, value, important, declaration_id, ...

Style/StyleDeclaration <------------------> Element/Property (referencias mínimas)
                    (style_id, declaration_id, node_id para trazabilidad)
```

#### Entidades base

- `Session`
  - `id`, `base_path`, `input_path`, `output_path`, `artifacts_path`

- `ColorScheme`
  - `colors`, `tonal_palettes`

- `Color`
  - `color_id`, `value`

- `PrototypeStructure`
  - `nodes`
  - `indexes` (`by_tag`, `by_classification`, `by_depth`)

- `Element`
  - `node_id`, `tag`, `xpath`, `parent_id`, `children_ids`, `classification`, `properties`

- `Property` (**siempre dentro de `Element`**)
  - `name`, `value`, `classification` (`background|foreground|effect|other`)

- `Style` (modelo existente de reglas CSS)
  - reglas, origen, selector, source range, etc.

- `Declaration` (**siempre dentro de `Style`**)
  - `name`, `value`, `important`, `declaration_id`, uso/resolución.

### 6.2 Regla de simplificación clave

- `effect_color` **no** será modelo independiente: se representa como `Property` clasificada como `effect`.
- `contrast` **no** será modelo raíz: se calcula como derivado sobre `prototype_structure`.

### 6.3 Reglas de nomenclatura

- Preferir nombres cortos y semánticamente directos.
- Evitar sufijos redundantes (`*Model`) si no añaden información.
- Evitar nombres de etapa que sugieran unicidad/proceso irrepetible cuando no aplica.
  - Ejemplo recomendado: `build_color_scheme`.

---

## 7. Requisitos funcionales (RF)

### RF-01 Preparar sesión única
El sistema debe inicializar una única sesión por corrida y registrar rutas base una sola vez.

### RF-02 Crear un único PageBuilder
El sistema debe iniciar una única instancia de `page_builder` por corrida (1 sesión CDP + 1 página).

### RF-03 Capturar y estructurar prototipo
El sistema debe poblar `prototype_structure` con elementos ordenados, relaciones y propiedades clasificadas.

### RF-04 Construir esquema de color
El sistema debe construir `scheme` desde `prototype_structure` sin estructuras paralelas de verdad.

### RF-05 Derivar insumos de calidad
El sistema debe derivar contraste/patrones desde `prototype_structure` sin persistir reportes intermedios como fuente primaria.

### RF-06 Cerrar recursos de browser
El sistema debe cerrar `page_builder` al final del tramo.

### RF-07 Eliminar JSON intermedio
El sistema no debe usar serialización/lectura JSON intermedia en este tramo.

---

## 8. Requisitos no funcionales (RNF)

### RNF-01 Consistencia
Debe existir validación de invariantes por etapa (contratos).

### RNF-02 Mantenibilidad
Cada stage con responsabilidad única y acoplamiento controlado.

### RNF-03 Rendimiento
Reducir I/O innecesario eliminando artefactos intermedios.

### RNF-04 Trazabilidad
Mantener eventos de `trace` para diagnóstico técnico.

### RNF-05 Compatibilidad progresiva
Permitir migración por etapas sin romper el comportamiento final esperado.

---

## 9. Invariantes de datos por corrida

1. `session.id` único.
2. única rama `scheme`.
3. único `prototype_structure`.
4. `node_id` único global.
5. relaciones parent/children consistentes.
6. propiedad asociada a un único elemento.
7. prohibido duplicar verdad semántica en ramas distintas.

Si un invariante falla: la etapa debe abortar con error explícito de contrato.

---

## 10. Especificación de `page_builder` (adapter)

## 10.1 Restricción de instancia

- exactamente 1 `page_builder` por corrida.

## 10.2 API pública requerida

- `capture_screenshot()`
- `get_element(node_id)`
- `get_computed(node_id)`
- `get_xpath(node_id)`
- `get_relations()`
- `close()`

## 10.3 Criterio de diseño

`page_builder` encapsula infraestructura browser/CDP; no contiene reglas centrales de negocio.

---

## 11. Ubicación de datos de píxeles y estilos (mínimo viable)

### 11.1 `environmental.inputs.*.raw_pixel_frequencies`

```text
environmental.inputs.original.raw_pixel_frequencies
environmental.inputs.output.raw_pixel_frequencies
```

Regla: son inputs operativos del assessment ambiental y no forman parte de `prototype_structure`.

### 11.2 `scheme.display_pixels`

Debe incluir únicamente evidencia visual agregada del render visible:
- `matched_inventory_colors`
- `unmatched_visual_pixels`
- `total_pixels_considered`
- `excluded_regions_summary`

Regla: `scheme.display_pixels` es evidencia visual complementaria para cuantización/pesos visuales; no reemplaza `scheme.colors` ni forma parte de `prototype_structure`.

### 11.3 `prototype_structure.nodes[].properties`

Debe incluir únicamente:
- propiedades computadas necesarias para color/contraste/efectos,
- clasificación mínima (`background|foreground|effect|other`),
- trazabilidad mínima (`style_id`, `declaration_id`, `declared_property`, `inherited_from_element_id`, `resolution_status`).

Regla: no crear inventarios redundantes separados si ya existe la información resuelta por `Element/Property`.

---

## 12. Reglas SOLID/POO/Python/PEP8 y taxonomía de módulos

## 12.1 Reglas de ingeniería

- **SRP:** una responsabilidad por stage/archivo.
- **OCP/DIP:** extender vía interfaces/adapters; stages no dependen de detalles técnicos concretos.
- **POO útil:** invariantes y comportamiento en entidades, no en diccionarios sueltos.
- **PEP8:** naming consistente, módulos cohesionados, legibilidad prioritaria.

## 12.2 Definición por tipo de módulo

- **Model:** dominio + invariantes + comportamiento; sin I/O.
- **Stage:** orquesta un paso; I/O de negocio vía context e interfaces.
- **Adapter:** integra infra externa (browser/fs/red/lib).
- **Util:** helper puro transversal, sin estado de negocio.
- **Enum:** conjunto finito estable de valores semánticos.
- **Data:** datos estáticos/versionados de solo lectura.

---

## 13. Inventario de archivos: crear/modificar/eliminar

## 13.1 Crear

1. `engine/domain/models/prototype_structure.py`
   - **Razón:** centralizar estructura canónica del prototipo.
   - **Reemplaza:** dispersión entre inventarios/reportes intermedios.

2. `engine/adapters/browser/page_builder.py` (o consolidarlo en módulo browser existente)
   - **Razón:** garantizar singleton por corrida y API estable.
   - **Reemplaza:** inicializaciones browser dispersas.

## 13.2 Modificar

1. `engine/pipeline/stages/prepare_project_session.py`
   - **Razón:** retirar paths `*_json` intermedios.
   - **Reemplazo:** claves `session.*` canónicas.

2. `engine/pipeline/stages/capture_original_state.py`
   - **Razón:** poblar captura base y enrutar `raw_pixel_frequencies` al branch canónico correspondiente.
   - **Reemplazo:** `session.artifacts.original.capture` + `environmental.inputs.original.raw_pixel_frequencies`.

3. `engine/pipeline/stages/build_inventories.py`
   - **Razón:** construir `prototype_structure` como verdad primaria y proyectar legacy.
   - **Reemplazo:** `prototype_structure.nodes`, `prototype_structure.indexes` y derivaciones transicionales.

4. `engine/pipeline/stages/analyze_color_inventory.py`
   - **Razón:** construir `scheme.input` desde el canon nuevo.
   - **Reemplazo:** lectura primaria desde `prototype_structure` + `scheme.display_pixels`.

5. `engine/pipeline/stages/build_effect_color_report.py`
   - **Razón:** `effect` vive en `Property`.
   - **Reemplazo:** derivación puntual sin truth paralela.

6. `engine/pipeline/stages/build_contrast_report.py`
   - **Razón:** contraste es derivado.
   - **Reemplazo:** cálculo desde `prototype_structure` y salida final.

7. `engine/pipeline/stages/set_tokens.py` y `engine/pipeline/stages/check_tokens.py`
   - **Razón:** reducir doble procesamiento.
   - **Reemplazo:** unificación lógica efectiva (aunque transicionalmente permanezcan dos archivos).

8. `engine/pipeline/artifact_serializers.py`
   - **Razón:** serializers intermedios quedan obsoletos.
   - **Reemplazo:** mapeo directo a output final permitido.

## 13.3 Eliminar

1. Serialización JSON intermedia en el tramo en alcance.
2. Lectura interna dependiente de esos JSON intermedios.

**Reemplazo global:** consumo directo de `session/scheme/prototype_structure` desde `context`.

---

## 14. Orden de proceso recomendado (tramo en alcance)

1. `prepare_session`
2. `start_page_builder`
3. `capture_prototype_structure`
4. `build_color_scheme`
5. `derive_quality_inputs`
6. `close_page_builder`

> Nota: en compatibilidad transicional puede existir extracción previa de insumos para esquema, pero el objetivo final es evitar etapas redundantes/nombres engañosos.

---

## 15. Plan de migración incremental (obligatorio y secuencial)

Todas las iteraciones son obligatorias y deben ejecutarse en orden.
No se permite saltar etapas ni ejecutar cambios fuera de este flujo.

---

## 15.1 Estrategia de migración técnica obligatoria

La migración hacia el estado final descrito en esta SRS debe seguir el siguiente orden estricto:

1. introducir modelos y estructuras canónicas en paralelo, sin eliminar aún la implementación previa;
2. comenzar a poblar `context` con la nueva representación canónica;
3. migrar consumidores para leer desde `context`;
4. validar invariantes, contratos y compatibilidad funcional del tramo;
5. eliminar completamente JSON intermedio, serializers intermedios y dependencias legacy del tramo.

### Restricciones obligatorias

* Prohibido eliminar JSON intermedio antes de que todos los consumidores del tramo hayan sido migrados.
* Prohibido cambiar productores de datos si los consumidores downstream aún dependen del formato anterior, salvo que exista adaptador transicional explícito.
* Prohibido introducir doble source of truth funcional.
* Si existe coexistencia temporal entre representación legacy y canónica, la representación canónica en `context` será la fuente primaria y la representación legacy sólo podrá existir como compatibilidad transicional controlada.

### Criterio de seguridad de migración

Una iteración se considera segura únicamente si:

* el pipeline del tramo sigue siendo ejecutable,
* `context` aumenta su ownership real sobre el estado,
* disminuye la dependencia efectiva de JSON intermedio,
* no aumenta la duplicación semántica.

---

## 15.2 Iteración 1 — Introducción del modelo canónico

**Objetivo:** introducir la nueva representación sin romper el pipeline actual.

### Acciones

* introducir `PrototypeStructure` como estructura canónica;
* introducir `PageBuilder` como adapter único por corrida;
* poblar `context.session`, `context.scheme` y `context.prototype_structure`;
* mantener JSON intermedio como compatibilidad temporal;
* crear adaptadores transicionales si es necesario.

### Resultado esperado

* coexistencia controlada entre modelo legacy y modelo canónico;
* pipeline sigue funcionando sin cambios visibles;
* `context` comienza a ser fuente real de estado.

---

## 15.3 Iteración 2 — Migración de consumidores

**Objetivo:** mover toda la lectura hacia `context`.

### Acciones

* migrar stages consumidores para leer desde:

  * `context.prototype_structure`
  * `context.scheme`
  * `context.session`
* eliminar dependencias directas a JSON en lectura;
* validar contratos de stages;
* reforzar invariantes.

### Resultado esperado

* JSON deja de ser fuente de lectura;
* no hay consumidores dependiendo de formatos legacy;
* el sistema funciona usando `context` como fuente principal.

---

## 15.4 Iteración 3 — Eliminación de JSON intermedio

**Objetivo:** eliminar completamente la representación legacy.

### Acciones

* eliminar serializers JSON intermedios;
* eliminar lectura de JSON en el tramo en alcance;
* eliminar rutas `*_json` del `session`;
* limpiar código muerto y adaptadores transicionales.

### Resultado esperado

* no existe JSON intermedio en la ruta principal;
* no hay doble source of truth;
* todo el pipeline usa exclusivamente `context`.

---

## 15.5 Iteración 4 — Consolidación de dominio y derivaciones

**Objetivo:** cerrar duplicaciones semánticas y estabilizar el modelo.

### Acciones

* consolidar `effect` dentro de `Property`;
* eliminar `effect_color` como entidad independiente;
* convertir `contrast` en derivación (no modelo raíz);
* unificar lógica de tokens (`set_tokens` / `check_tokens`);
* integrar correctamente `style` con `prototype_structure`.

### Resultado esperado

* no existen modelos redundantes;
* todas las derivaciones nacen de `prototype_structure`;
* el dominio es coherente y consistente.

---

## 15.6 Iteración 5 — Endurecimiento y cierre

**Objetivo:** asegurar estabilidad, calidad y consistencia total.

### Acciones

* reforzar invariantes por stage;
* validar contratos de extremo a extremo;
* limpiar deuda técnica restante;
* validar criterios de aceptación completos.

### Resultado esperado

* pipeline estable y consistente;
* arquitectura alineada completamente al SRS;
* sin deuda técnica relevante en el tramo.

---

## 16. Criterios de aceptación

1. No existen lecturas/escrituras JSON intermedias en la ruta principal del tramo en alcance.
2. `context` contiene exactamente una instancia semántica de `session`, `scheme`, `prototype_structure` por corrida.
3. `page_builder` se crea una vez por corrida y se cierra correctamente.
4. `effect` y `contrast` se obtienen como derivaciones de la estructura canónica.
5. El resto del pipeline consume el estado canónico sin depender de artefactos intermedios.
6. No se observan duplicaciones semánticas en ramas de `context`.
7. Ningún stage del tramo puede depender de JSON intermedio si ya existe el dato canónico equivalente en `context`.

---

## 17. Riesgos y mitigaciones

- **Riesgo:** ruptura de stages existentes que esperan archivos JSON.
  - **Mitigación:** adaptadores transicionales de lectura desde context y eliminación gradual de dependencias.

- **Riesgo:** inconsistencias en relaciones de nodos durante migración.
  - **Mitigación:** validaciones de invariantes por etapa + abortos tempranos.

- **Riesgo:** regressions por cambio de ownership de datos.
  - **Mitigación:** pruebas de contrato por stage y pruebas de integración del tramo.

---

## 18. Resultado esperado

- arquitectura más simple y mantenible,
- menor I/O y menor costo operacional,
- reducción de contradicciones por doble source of truth,
- base sólida para evolucionar el resto del pipeline con menor riesgo.

---

## 19. Verificación de consistencia interna (checklist cerrada)

Esta sección cierra ambigüedades y fija interpretación única.

### VC-01 Unicidad semántica

- `session`, `scheme`, `prototype_structure` son los únicos dueños de verdad del tramo.
- Cualquier dato derivado debe referenciar estos dueños y no duplicarse como estado primario.

### VC-02 Orden y contratos

- El orden del tramo es normativo: `prepare_session -> start_page_builder -> capture_prototype_structure -> build_color_scheme -> derive_quality_inputs -> close_page_builder`.
- Ninguna etapa puede exigir JSON intermedio como precondición.

### VC-03 Ownership explícito de datos

- Relaciones de nodos y propiedades: `prototype_structure`.
- Esquema de color y paletas: `scheme`.
- Evidencia visual display: `scheme.display_pixels`.
- Inputs raw para assessment ambiental: `environmental.inputs.*.raw_pixel_frequencies`.
- Rutas y metadatos operativos: `session`.
- Reglas CSS/declaraciones ricas: `style` como subdominio especializado o compatibilidad transicional.

### VC-04 Terminología normalizada

- `effect`: clasificación de `Property`.
- `contrast`: derivación de calidad, no modelo raíz.
- `intermedio`: todo artefacto no requerido como salida final.

### VC-05 Compatibilidad transicional

* Se permite compatibilidad transicional únicamente si:

  * `context` ya es la representación canónica primaria;
  * los consumidores legacy están claramente identificados;
  * la adaptación no reintroduce JSON intermedio como dependencia principal;
  * no existe escritura de nueva verdad fuera de `session`, `scheme` y `prototype_structure`.

---

## 20. Puntos que podían dejar dudas (ahora cerrados)

1. **¿`nodes` reemplaza por completo a `elements_by_id`?**  
   Sí para la representación canónica del tramo. Si se requiere acceso O(1), se usa índice derivado en `prototype_structure.indexes`, no una segunda verdad primaria.

2. **¿Se pueden mantener serializers para debug?**  
   No en la ruta principal de este tramo. Si se requiere diagnóstico puntual, debe ser bajo mecanismo de inspección no persistente o tooling externo, nunca como dependencia funcional.

3. **¿`build_initial_color_scheme_input` sigue existiendo?**  
   No como etapa objetivo final. La extracción de insumo ocurre dentro de `build_color_scheme` o como detalle interno no expuesto como etapa pública separada.

4. **¿Dónde viven contrast/effect para resultados?**  
   Se derivan desde `prototype_structure` durante `derive_quality_inputs` y se materializan sólo en salida final consumible, sin crear una fuente primaria paralela.

5. **¿Qué evita contradicciones entre stages?**  
   Invariantes obligatorios + contratos de etapa + ownership único por rama de `context`.

---

## 21. Criterios de “Done” del refactor en este tramo

Un cambio se considera terminado únicamente si cumple todo:

1. No hay `save_json(...)` ni lectura de JSON intermedio en stages del tramo en alcance.
2. `prepare_project_session` no registra rutas `*_json` intermedias como dependencia operativa.
3. `prototype_structure` contiene nodos, índices y propiedades mínimas consistentes.
4. `page_builder` se instancia una vez y se libera siempre.
5. `effect` y `contrast` no existen como truth primaria separada.
6. Stages downstream inmediatos leen de `context` canónico.
7. Se mantienen resultados finales esperados por UI/bundle.
8. No existen consumidores nuevos construidos sobre rutas legacy si ya existe la ruta canónica en `context`.


---

## 22. Auditoría de naming (consistencia con esta especificación)

Resultado de revisión: los nombres usados en esta SRS quedan consistentes con las reglas declaradas (claros, cortos, snake_case para funciones/etapas, PascalCase para clases).

### 22.1 Nombres validados en esta especificación

- Etapas: `prepare_session`, `start_page_builder`, `capture_prototype_structure`, `build_color_scheme`, `derive_quality_inputs`, `close_page_builder`.
- Clases de dominio propuestas: `Session`, `ColorScheme`, `PrototypeStructure`, `Element`, `Property`.
- Claves de contexto: `session.*`, `scheme.*`, `prototype_structure.*`.

### 22.2 Nombres que se consideran transicionales o heredados

- `build_effect_color_report` y `build_contrast_report`: mantener temporalmente por compatibilidad, pero su rol objetivo es de derivación desde `prototype_structure`.
- `set_tokens` y `check_tokens`: pueden permanecer temporalmente separados por compatibilidad, pero deben converger a una lógica unificada sin duplicación semántica.

### 22.3 Regla ejecutable de naming para implementación

- Nuevas clases: sin sufijo `Model` salvo que exista conflicto real de semántica.
- Nuevos stages: verbo + objeto (`build_color_scheme`, `derive_quality_inputs`).
- Nuevas claves de context: `<raiz>.<subarbol>.<campo>` evitando aliases equivalentes para el mismo dato.

---

## 23. Mapa explícito de clases de dominio (nuevas, modificadas, eliminadas/absorbidas)

## 23.1 Nuevas clases propuestas

1. `PrototypeStructure` (nuevo archivo sugerido: `engine/domain/models/prototype_structure.py`)
   - Responsabilidad: estructura canónica del prototipo para análisis.
   - Contiene: `nodes`, `indexes`.

2. `PageBuilder` (adapter; archivo sugerido: `engine/adapters/browser/page_builder.py`)
   - Responsabilidad: encapsular sesión CDP/página única por corrida.

## 23.2 Clases existentes a modificar

1. `Session` (actualmente representada en `engine/domain/models/session.py`)
   - Ajuste: asegurar campos canónicos (`id`, `base_path`, `input_path`, `output_path`, `artifacts_path`) y constructor único por corrida.

2. `ColorScheme` / modelo de esquema (actualmente en `engine/domain/models/palette.py` y flujo asociado)
   - Ajuste: normalizar lectura/escritura en `scheme.colors`, `scheme.tonal_palettes` y `scheme.display_pixels`.

3. `Element` (actualmente en `engine/domain/models/element.py`)
   - Ajuste: consolidar `classification` y `properties` para que soporte explícitamente `effect`.

## 23.3 Clases/estructuras que dejan de existir como verdad primaria

1. `effect_color` como entidad raíz independiente.
   - **Absorción:** `Property(classification="effect")` dentro de `Element` en `PrototypeStructure`.

2. `contrast` como entidad raíz independiente.
   - **Absorción:** derivación calculada en `derive_quality_inputs` a partir de `PrototypeStructure`.

3. reportes intermedios serializados como fuente primaria.
   - **Absorción:** estado canónico en `context` + materialización final de salida.

---

## 24. Ubicación correcta del modelo de Style (CSS rules + declarations)

Actualmente ya existe un modelo de estilos en `engine/domain/models/style.py` que representa reglas, declaraciones y metadatos de resolución.

### 24.1 Decisión de arquitectura

- `style` **no** se elimina ni se duplica.
- `style` se mantiene como subdominio especializado para reglas CSS/declaraciones.

### 24.2 Relación correcta entre `style` y `prototype_structure`

1. `prototype_structure` no contiene inventario rico de reglas CSS.
2. `prototype_structure.nodes[].properties` conserva sólo estado resuelto mínimo y referencias de trazabilidad.
3. No tener instancias repetidas de un mismo `style` dentro de `prototype_structure`.

### 24.3 Regla de no-duplicación aplicada a style

- Fuente primaria de reglas CSS/declaraciones: `style` como subdominio especializado mientras exista compatibilidad transicional.
- Fuente primaria del estado estructural por nodo: `prototype_structure.nodes`.
- Puente permitido: referencias mínimas en cada property (`style_id`) para trazabilidad.

Con esta decisión, se evita conflicto entre “inventario CSS completo” y “estructura operativa del prototipo”.

