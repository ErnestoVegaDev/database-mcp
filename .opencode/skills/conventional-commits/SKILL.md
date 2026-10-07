---
name: conventional-commits
description: Genera, valida y explica mensajes de commit siguiendo el estándar Conventional Commits v1.0.0 (https://www.conventionalcommits.org/es/v1.0.0/), combinado con buenas prácticas de calidad de commits estilo kernel de Linux (subject imperativo y corto, body que explica el por qué, commits atómicos). Úsala siempre que el usuario pida "hacer un commit", "escribir un mensaje de commit", "redactar el commit", pida revisar/validar si un mensaje de commit cumple el estándar o es un buen commit, pregunte qué tipo de commit usar (feat, fix, chore, etc.), pida generar un CHANGELOG a partir del historial de commits, o mencione BREAKING CHANGE, SemVer, git blame, git bisect, o commits atómicos. Aplica también cuando el usuario pegue un `git diff` o describa cambios de código y quiera el mensaje de commit correspondiente.
license: MIT
compatibility: opencode
metadata:
  audience: developers
  spec_version: "1.0.0"
  spec_lang: es
---

# Conventional Commits

Skill para redactar y validar mensajes de commit combinando dos capas
complementarias:

1. **La estructura formal**: [Conventional Commits v1.0.0 (es)](https://www.conventionalcommits.org/es/v1.0.0/)
   — define el *formato* (`tipo(ámbito): descripción`, footers, BREAKING CHANGE).
2. **La calidad del contenido**: buenas prácticas de estilo kernel de Linux
   (popularizadas por Linus Torvalds) — definen *cómo escribir bien* lo que
   va dentro de ese formato, para que el commit realmente sea útil dentro
   de seis meses.

Un commit puede cumplir la estructura formal a la perfección (`fix(cart):
arregla bug`) y aun así ser inútil, porque no explica el porqué. Esta skill
busca que el resultado cumpla ambas capas.

## Formato base (regla de oro, capa 1)

```
<tipo>[ámbito opcional][!]: <descripción>

[cuerpo opcional]

[nota(s) al pie opcional(es)]
```

Ejemplo mínimo: `fix(auth): valida token expirado antes de refrescar sesión`

Para la tabla completa de tipos, las 16 reglas normativas (MUST/SHOULD/MAY) y
ejemplos extendidos con BREAKING CHANGE, ve `references/spec.md`.
Léelo **antes** de generar un commit si tienes dudas sobre una regla
específica (ámbitos, notas al pie, mayúsculas, etc.) — no la asumas de
memoria.

## Buenas prácticas de contenido (capa 2, estilo kernel de Linux)

Estas reglas no son parte de la especificación formal de Conventional
Commits, pero son el criterio real que separa un commit útil de uno inútil.
Aplícalas siempre además del formato:

1. **Subject corto y como titular.** Apunta a un máximo aproximado de 50
   caracteres en la descripción — debe caber cómodo en un `git log --oneline`.
   Si no cabe, probablemente el commit está intentando decir demasiado y
   convendría dividirlo (ver punto 4).
2. **Modo imperativo, no pasado ni gerundio.** "Corrige memory leak" o
   "agrega validación", no "Corregido memory leak" ni "Agregando validación".
   Es la misma convención que usa `git` para sus propios mensajes generados
   automáticamente (merges, reverts), así que mantiene el historial
   consistente.
3. **El body explica el POR QUÉ, no el QUÉ.** El `git diff` ya muestra qué
   cambió línea por línea; repetirlo en el body es redundante. El body debe
   responder: ¿qué problema motivó este cambio?, ¿qué pasaba antes?, ¿por
   qué esta solución y no otra? Si el usuario solo te da el diff sin
   contexto de motivación, pregúntale el porqué antes de inventar una
   justificación — no rellenes ese hueco con suposiciones.
4. **Commits atómicos: una idea, un commit.** Si el diff mezcla varios
   cambios lógicos independientes (una feature + un fix + un refactor),
   sugiere al usuario separarlos en varios commits en vez de generar un
   único mensaje que intente cubrirlo todo. Esto es lo que hace útil a
   `git bisect` para encontrar en qué commit se introdujo un bug: si cada
   commit es una sola unidad lógica, `git bisect` localiza el culpable
   exacto en vez de un commit "monstruo" con 40 archivos.

## Workflow al generar un commit

1. **Entender el cambio real.** Si el usuario pegó un `git diff` o describe
   el cambio, identifica: ¿qué se modificó?, ¿por qué?, ¿rompe
   compatibilidad? ¿Es en realidad más de un cambio lógico mezclado en un
   solo diff? Si falta contexto claro sobre el propósito del cambio,
   pregunta antes de inventar un tipo, un ámbito, o — sobre todo — el
   "porqué" del body.
2. **Si el diff mezcla varias ideas, dilo primero.** Antes de redactar el
   mensaje, indica al usuario que conviene dividirlo en commits atómicos
   y propone cómo agruparlos (ver punto 4 de buenas prácticas). Solo genera
   un mensaje único si el usuario confirma que prefiere mantenerlo así.
3. **Elegir el tipo correcto.** Usa la tabla de `references/spec.md`
   (sección "Tabla de tipos"). Como regla rápida:
   - ¿Agrega funcionalidad nueva visible para el usuario final? → `feat`
   - ¿Corrige un comportamiento incorrecto (bug)? → `fix`
   - ¿Solo reorganiza código sin cambiar comportamiento? → `refactor`
   - ¿Solo toca documentación? → `docs`
   - ¿Solo toca tests? → `test`
   - Si dudas entre dos tipos, prioriza cómo lo leerá alguien generando un
     CHANGELOG automático: ¿qué le importa a un consumidor de la librería?
4. **Definir el ámbito (scope), si aplica.** Un sustantivo entre paréntesis
   que ubique la zona del código afectada, ej. `feat(parser): ...`. Es
   opcional — si el cambio es transversal, omítelo.
5. **Detectar BREAKING CHANGE.** Si el cambio rompe compatibilidad hacia
   atrás (API pública, contrato de datos, firma de función expuesta, etc.),
   DEBE marcarse. Dos formas válidas (pueden combinarse):
   - `!` inmediatamente después del tipo/ámbito y antes de `:` → `refactor!: ...`
   - Nota al pie `BREAKING CHANGE: <descripción>` (siempre en mayúsculas).
6. **Redactar la descripción corta.** Modo imperativo, sin punto final,
   apuntando a ~50 caracteres, siendo específico sobre el qué — no el cómo.
7. **Redactar el cuerpo centrado en el porqué.** Línea en blanco tras la
   descripción, luego la motivación del cambio: qué problema había, qué
   pasaba antes, por qué se eligió esta solución. Evita simplemente
   parafrasear el diff.
8. **Añadir notas al pie, si aplica.** Línea en blanco tras el cuerpo.
   Formato `Palabra-Clave: valor` (guiones en vez de espacios), ej.
   `Refs: #133`, `Reported-by: ops-team`, o `BREAKING CHANGE: ...`.
9. **Revisar contra ambas capas antes de entregar.** Formato (capa 1: tipo,
   `: `, líneas en blanco, footers bien formados) y contenido (capa 2:
   subject corto e imperativo, body explica el porqué, es una sola idea).

## Cómo explicar tus decisiones al usuario

Cuando entregues un commit generado o el resultado de una revisión:

- Indica explícitamente el **tipo** elegido y **por qué** (a qué categoría
  de cambio corresponde y con qué parte de SemVer se correlaciona:
  `fix`→PATCH, `feat`→MINOR, BREAKING CHANGE→MAJOR).
- Si detectaste un BREAKING CHANGE, explica cuál es el cambio de contrato
  que lo rompe (qué deja de funcionar como antes).
- Si sugeriste dividir el cambio en varios commits, explica brevemente por
  qué (facilita `git bisect` y hace más legible el historial para quien
  revise el código después).
- Si el usuario no tiene experiencia con el estándar, apóyate en el resumen
  de "Formato base" de arriba antes de mostrar el resultado final — no
  asumas que conoce los términos "ámbito" o "nota al pie" sin una breve
  aclaración la primera vez que los uses en la conversación.

## Referencias

- `references/spec.md` — especificación completa de Conventional Commits en
  español (las 16 reglas normativas, tabla de tipos recomendados
  Angular/commitlint, todos los ejemplos oficiales) y el resumen de buenas
  prácticas de contenido estilo kernel de Linux con ejemplos de "antes/después".
