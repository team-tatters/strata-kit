# El principio de la estructura prepagada

> Fuente canónica: strata-kit `core/docs/es/architecture/prepaid-structure.md` — migrado desde strata `docs/03-architecture/prepaid-structure.md` (orden 2026.10.29-06, 2026-10-29). El YAML de reglas está en `core/rules/`.

> Fuente canónica legible por máquina de las reglas de capas: `core/rules/layer-rules.yaml` / descripción por capa: `core/docs/es/architecture/backend-cqrs.md`
> Este documento es el principio de nivel superior que explica "por qué se construye esta estructura desde el principio". (DEC-2026-09-30-01, strata)

## Resumen

- **Principio:** si el coste de estructura que se paga ahora compensa de sobra el coste de cambios posteriores, esa estructura se construye desde el principio. Una estructura que no lo compensa no se construye hasta que haga falta.
- **Hay tres criterios de decisión:** el coste ahora, el coste cuando ese cambio sea necesario más adelante, y la probabilidad de que el cambio ocurra de verdad.
- **No se reducen las capas según la escala.** Los roles de las capas y la dirección de dependencia son los mismos a toda escala. Lo único que varía con la escala es el número de dominios y las unidades de despliegue.
- **El objetivo es que las capas casi no cambien al pasar de un monolito a MSA.** Los costes que las capas no cubren se concentran en tres puntos — la propiedad de los datos, las escrituras entre dominios y las lecturas entre dominios —, así que las reglas de estos tres también se fijan de antemano.
- **Una estructura prepagada solo se mantiene si se aplica.** Una frontera que ni el compilador ni la CI bloquean se va filtrando poco a poco con el tiempo, y con ello desaparece el valor pagado por adelantado.

## Lista de veredictos

### Estructuras que siempre se establecen

| Estructura | Coste ahora | Coste de cambio que compensa |
|---|---|---|
| Roles de capa y dependencia en una sola dirección | El esfuerzo de ajustar la ubicación de archivos y las rutas de llamada a las reglas | El coste de no poder predecir qué arrastra consigo una funcionalidad al moverla o separarla |
| Servicios separados en comando y consulta (CQS) | Los archivos de servicio se duplican y hay que tener presente dónde está la transacción | El coste de tener que desmontar el código de escritura al separar el modelo de lectura o moverlo a una caché o una réplica |
| Módulos de build separados en módulos de entidad y módulos de servicio | Configuración del build, declaración de dependencias entre módulos, y la complejidad del procesamiento transaccional, síncrono y asíncrono | El coste de trazar de nuevo los límites del código al separar servicios. Los propios módulos pasan a ser candidatos a unidad de despliegue |
| Puertos y adaptadores en los límites con sistemas externos (BD, mensajería, APIs externas) | Una interfaz y una implementación por límite | El coste de sustituir un sistema externo, o de convertir una llamada dentro del proceso en una llamada de red |

### Estructuras que se establecen solo cuando hacen falta

| Estructura | Cuándo se establece |
|---|---|
| Event sourcing (variante `es-cqrs`) | Cuando se confirma como requisito la pista de auditoría, la reconstrucción de momentos pasados o la reproducción de eventos |
| Almacén de lectura separado | Cuando la carga de consultas o el modelo de consulta se ha separado realmente del modelo de escritura |

### Estructuras que no se establecen

| Estructura | Motivo |
|---|---|
| Abstracciones de interfaz en cada capa interna | Las implementaciones internas rara vez se sustituyen, así que no hay coste de cambio que compensar. La regla de dirección de capas basta por sí sola para lograr el mismo efecto |
| Una arquitectura hexagonal completa | Los puertos y adaptadores aportan valor solo en las fronteras externas. Extenderlos al interior solo aumenta el coste |

## Tres fronteras que las capas no cubren

Al separar un servicio de un monolito, el código de las capas se traslada casi sin cambios. El coste restante surge en los tres puntos siguientes. Estos tres se fijan como reglas desde el principio.

### Propiedad de los datos

- Una tabla pertenece a un módulo de entidad. El historial de cambios de esquema de la tabla (changelog) también pertenece a ese módulo.
- Los demás módulos no escriben directamente en esa tabla. La escritura pasa por el servicio de comandos del módulo propietario.
- Motivo: al separar servicios, el coste de dividir la BD crece cuanto más dispersa esté la respuesta a "quién escribe en qué tabla".

### Escrituras entre dominios

- No se unen las escrituras de dos dominios en una sola transacción. Cuando termina la escritura de un dominio se publica un evento, y el otro dominio recibe ese evento y realiza su propia escritura.
- El registro de publicación se guarda junto con la transacción (enfoque outbox, p. ej. la tabla de publicación de eventos de Spring Modulith). Así, el punto que cambia de entrega dentro del proceso en un monolito a entrega por bróker en MSA es un único lugar.
- Motivo: dos dominios unidos en una transacción se convierten en un problema de transacción distribuida en cuanto se separan en servicios.

### Lecturas entre dominios

- La ruta para leer los datos de otro dominio se fija en un solo lugar por dominio. Se elige una de estas dos: una ventana de solo consulta (un servicio de consulta o una capa de coordinación) o una consulta de tablas externas a nivel de BD (FDW, etc.), y no se mezclan.
- No se usan directamente los tipos de entidad de otro dominio. El resultado de la consulta se recibe en tipos del propio dominio.
- Motivo: si la ruta de lectura es un solo lugar, al separar los servicios basta con cambiar ese único lugar a una consulta de red.

## Escala y unidades de despliegue

- Incluso un proyecto pequeño tiene la misma estructura de capas y módulos. Si solo hay un dominio, simplemente hay un módulo de dominio.
- La diferencia entre un monolito y MSA se ve como "cuántos módulos se agrupan en un proceso para desplegarlos". Mover un módulo a otro proceso equivale a cambiar el método de entrega de las tres fronteras anteriores.
- Según el presupuesto y las condiciones de operación, las unidades de despliegue pueden fusionarse o dividirse en cualquier momento. Mientras se respeten las fronteras de capas y módulos, esta elección no es una decisión de rehacer la estructura del código.

## Fronteras de compilación baratas por lenguaje

La forma de reducir al máximo el coste prepagado es usar las fronteras que el lenguaje y sus herramientas de build ya ofrecen. Cada binding de lenguaje indica "con qué se crea la frontera de módulo y con qué se bloquea la dirección de capas dentro del módulo".

| Lenguaje | Frontera de módulo (impuesta por el compilador) | Dirección de capas dentro del módulo | Ciclos |
|---|---|---|---|
| Kotlin / Java | Gradle multimódulo (`implementation` por defecto) | ArchUnit (bloquea en CI) | Gradle rechaza los ciclos entre módulos |
| Go | Módulos y paquetes `internal/` | Reglas de import como depguard | Los ciclos de import entre paquetes son error de compilación |
| Rust | Crates del workspace de cargo | Separación en crates o visibilidad de módulo (`pub(crate)`) | cargo rechaza los ciclos entre crates |
| TypeScript / JavaScript | Paquetes del workspace (superficie pública limitada con `exports`) | dependency-cruiser, eslint-plugin-boundaries | El gestor de paquetes los permite, por lo que es imprescindible una regla `no-circular` |
| Swift | Paquetes y targets de SwiftPM | Separación de targets + verificador (`profiles/frontend.swiftui/enforcement/`) | SwiftPM rechaza los ciclos entre targets |

Los documentos de binding están en `profiles/<id>/docs/es/`. Un nuevo binding de lenguaje se añade cuando aparezca un proyecto real.

## Un ejemplo de aplicar el mismo principio al frontend

- Los tres niveles de tokens (valor primitivo → alias → componente) pagan por adelantado la capa de alias, de modo que el coste de cambiar de tema o de marca se reduce a una sola definición de alias. Detalles: `core/docs/es/architecture/frontend-design-contract.md`
- La jerarquía de componentes solo se usa de arriba hacia abajo. Detalles: `core/docs/es/architecture/frontend-web.md`

## Conservar lo prepagado

- Las fronteras de módulo las bloquea la herramienta de build, y la dirección de capas dentro del módulo la bloquean las pruebas de arquitectura de la CI. Los hooks en el momento de edición son solo una retroalimentación rápida, no el veredicto canónico.
- Si se han acumulado infracciones en el código existente, se fijan como línea base y se bloquean solo las infracciones nuevas. La línea base se actualiza únicamente en el sentido de reducirse.

## Caso de evidencia (un proyecto backend, 2026-09)

- Al trasladar el diseño 3.0 del módulo de pedidos al módulo de facturación (billing), el trabajo terminó con la creación de nuevos módulos de entidad, documento y servicio y con ejecutar la ruta del gateway. Las reglas de capas y la forma del código de servicio no cambiaron (decisión de ese proyecto del 2026-09-08).
- El coste que de verdad costó resolver fue el mecanismo para que dos módulos convivieran en la misma BD, y el traslado de datos. Esta experiencia es el fundamento para elevar a regla la frontera de "propiedad de los datos".
- En la medición de ArchUnit de 2026-07 aparecieron casi 1.500 infracciones de capas dentro de los módulos. La frontera de módulo la mantuvo el compilador, pero la frontera dentro del módulo dependía solo de advertencias. Es el fundamento de la sección "Conservar lo prepagado".
