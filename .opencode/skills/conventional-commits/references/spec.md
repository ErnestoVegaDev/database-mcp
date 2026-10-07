# Conventional Commits v1.0.0 — Especificación completa (es)

Fuente oficial: https://www.conventionalcommits.org/es/v1.0.0/

## Estructura del mensaje

```
<tipo>[ámbito opcional]: <descripción>

[cuerpo opcional]

[nota(s) al pie opcional(es)]
```

## Elementos estructurales

1. **fix:** corrige un error en la base del código → se correlaciona con
   `PATCH` en SemVer.
2. **feat:** introduce una nueva funcionalidad → se correlaciona con
   `MINOR` en SemVer.
3. **BREAKING CHANGE:** (como nota al pie, o `!` tras el tipo/ámbito)
   introduce un cambio de ruptura de API → se correlaciona con `MAJOR` en
   SemVer. Puede combinarse con cualquier tipo (`feat!`, `fix!`, `refactor!`, etc.).
4. Tipos distintos a `fix`/`feat` están permitidos. `@commitlint/config-conventional`
   (basado en la convención de Angular) recomienda: `build`, `chore`, `ci`,
   `docs`, `style`, `refactor`, `perf`, `test`, entre otros.
5. Notas al pie distintas de `BREAKING CHANGE:` siguen una convención similar
   al formato git trailer.

## Tabla de tipos (convención Angular / commitlint)

| Tipo       | Cuándo usarlo                                                          | SemVer     |
|------------|-------------------------------------------------------------------------|------------|
| `feat`     | Nueva funcionalidad para el usuario final                              | MINOR      |
| `fix`      | Corrección de un bug                                                    | PATCH      |
| `build`    | Cambios en el sistema de build o dependencias externas                 | —          |
| `chore`    | Tareas de mantenimiento que no afectan src ni tests                     | —          |
| `ci`       | Cambios en configuración/scripts de integración continua                | —          |
| `docs`     | Cambios solo en documentación                                           | —          |
| `style`    | Cambios de formato (espacios, comas, etc.) sin afectar lógica           | —          |
| `refactor` | Cambio de código que no corrige un bug ni agrega funcionalidad          | —          |
| `perf`     | Cambio de código que mejora el rendimiento                              | —          |
| `test`     | Agregar o corregir tests                                                | —          |
| `revert`   | Revierte un commit anterior (usar nota al pie `Refs:` con los SHAs)      | depende    |

Cualquier tipo puede combinarse con `!` o una nota `BREAKING CHANGE:` para
indicar MAJOR, sin importar la tabla anterior.

## Las 16 reglas normativas

1. Los commits DEBEN iniciarse con un prefijo de tipo (sustantivo: `feat`,
   `fix`, etc.), seguido del ámbito OPCIONAL, `!` OPCIONAL, y `: ` (dos
   puntos + espacio) REQUERIDO.
2. El tipo `feat` DEBE usarse cuando el commit agrega una nueva
   funcionalidad a la aplicación o librería.
3. El tipo `fix` DEBE usarse cuando el commit corrige un bug.
4. Un ámbito PUEDE añadirse tras el tipo. DEBE ser un sustantivo entre
   paréntesis que describa una sección de la base del código, ej.
   `fix(parser):`.
5. La descripción DEBE ir inmediatamente después de `: `. Es un resumen
   corto del cambio, ej. *fix: array parsing issue when multiple spaces
   were contained in string.*
6. Un cuerpo más extenso PUEDE agregarse tras la descripción, dando
   contexto adicional. DEBE empezar tras una línea en blanco después de
   la descripción.
7. El cuerpo es de forma libre y PUEDE tener cualquier número de párrafos
   separados por líneas en blanco.
8. Una o más notas al pie PUEDEN añadirse tras una línea en blanco después
   del cuerpo. Cada nota DEBE consistir en una palabra clave + separador
   (`: ` o ` #`) + un valor string.
9. La palabra clave de una nota al pie DEBE usar `-` en vez de espacios,
   ej. `Acked-by` (excepción: `BREAKING CHANGE` sí puede llevar espacio).
10. Una nota al pie PUEDE contener espacios y líneas en blanco; el parseo
    DEBE terminar al observar el siguiente separador/clave.
11. Los cambios de ruptura DEBEN indicarse en el prefijo tipo/ámbito
    (`!`) o como entrada de nota al pie.
12. Si se incluye como nota al pie, un BREAKING CHANGE DEBE consistir del
    texto en mayúsculas `BREAKING CHANGE`, seguido de `:` y una
    descripción, ej. *BREAKING CHANGE: environment variables now take
    precedence over config files*.
13. Si se incluye en el prefijo, el BREAKING CHANGE DEBE indicarse con `!`
    inmediatamente después de `:`... espera, inmediatamente **antes** de
    `:`. Si se usa `!`, `BREAKING CHANGE:` en el footer PUEDE omitirse, y
    la descripción del commit DEBERÁ describir el cambio de ruptura.
14. Tipos distintos a `feat`/`fix` PUEDEN usarse, ej. *docs: updated ref
    docs.*
15. Las unidades estructurales NO DEBEN tratarse como sensibles a
    mayúsculas/minúsculas, con la excepción de `BREAKING CHANGE`, que DEBE
    ir en mayúsculas.
16. `BREAKING-CHANGE` DEBE tratarse como sinónimo de `BREAKING CHANGE`
    cuando se usa como nota al pie.

## Ejemplos oficiales

### Con descripción y BREAKING CHANGE en nota al pie
```
feat: allow provided config object to extend other configs

BREAKING CHANGE: `extends` key in config file is now used for extending other config files
```

### Con `!` para señalar el cambio de ruptura
```
refactor!: drop support for Node 6
```

### Con `!` y BREAKING CHANGE en nota al pie a la vez
```
refactor!: drop support for Node 6

BREAKING CHANGE: refactor to use JavaScript features not available in Node 6.
```

### Sin cuerpo
```
docs: correct spelling of CHANGELOG
```

### Con ámbito
```
feat(lang): added polish language
```

### Con cuerpo multi-párrafo y múltiples notas al pie
```
fix: correct minor typos in code

see the issue for details

on typos fixed.

Reviewed-by: Z
Refs #133
```

### Revert
```
revert: let us never again speak of the noodle incident

Refs: 676104e, a215868
```

## Por qué usar Conventional Commits

- Generación automática de CHANGELOGs.
- Determinación automática del salto de versión SemVer (según los tipos
  usados en el historial).
- Comunicar la naturaleza de los cambios al equipo y a otros interesados.
- Disparar procesos de build y publicación automatizados.
- Facilitar que otras personas contribuyan al tener un historial más
  estructurado y explorable.

## Preguntas frecuentes relevantes

- **¿Un commit encaja en más de un tipo?** → Sepáralo en varios commits.
  Parte del beneficio del estándar es lograr commits/PRs más organizados.
- **¿Mayúsculas o minúsculas en el tipo?** → Cualquiera es válido; lo
  importante es ser consistente en el proyecto.
- **¿Usé un tipo equivocado?** → Si el tipo existe en la especificación
  pero era el incorrecto (ej. `fix` en vez de `feat`) y aún no se ha hecho
  merge/release, usa `git rebase -i` para corregirlo. Si el tipo no existe
  en la especificación (ej. `feet`), no pasa nada grave: las herramientas
  basadas en el estándar simplemente lo ignorarán.

---

# Buenas prácticas de contenido (estilo kernel de Linux)

Esta sección **no** es parte de la especificación formal de Conventional
Commits. Es una capa complementaria de calidad, en la línea del estilo de
mensajes de commit que exige Linus Torvalds para el kernel de Linux: define
cómo escribir *bien* el contenido, más allá del formato `tipo(ámbito):
descripción`. Referencia: artículo "Los mensajes de commit son cartas a tu
futuro yo" (100cosas.dev, basado en ideas de *97 Things Every Programmer
Should Know*).

La idea central: **un mensaje de commit es la única explicación que
tendrás dentro de seis meses**. Un historial lleno de mensajes como `fix`,
`update`, `WIP` o `asdf` es, en la práctica, un historial sin
documentación — nadie podrá reconstruir el porqué de un cambio con
`git blame` si el mensaje no dice nada.

## Las 4 reglas de contenido

1. **Subject corto, como un titular.** Apunta a un máximo aproximado de 50
   caracteres — debe caber cómodo en un `git log --oneline`. Si el cambio
   necesita más que eso para describirse, probablemente son varios cambios
   lógicos mezclados (ver regla 4).
2. **Modo imperativo.** "Corrige memory leak", no "Corregido memory leak"
   ni "Corrigiendo memory leak". Es la misma convención que usa Git para
   sus propios mensajes autogenerados (merges, reverts), así que mantiene
   el historial estilísticamente consistente.
3. **El body explica el POR QUÉ, no el QUÉ.** El diff ya muestra, línea
   por línea, qué cambió — repetirlo en el mensaje es información
   redundante. Lo que el diff *no puede* decir es la motivación: qué
   problema había, qué pasaba antes del fix, por qué se decidió esta
   solución y no otra. Ejemplo de la diferencia:

   *Mensaje que solo describe el qué (poco útil, es redundante con el diff):*
   ```
   fix: null pointer en servicio de usuarios

   Se modificó la función getUser para validar null
   antes de acceder a las propiedades.
   ```

   *Mensaje que explica el porqué (sí aporta algo que el diff no dice):*
   ```
   fix: null pointer al consultar usuarios eliminados

   Los usuarios eliminados desde el panel de administración
   mantenían su token de sesión activo hasta por 30 minutos
   (TTL del token). Durante esa ventana, las llamadas a la API
   con un token válido referenciaban registros de usuario que
   ya no existían, causando null pointer exceptions en getUser().

   El fix agrega una validación null con un error específico
   que dispara la invalidación del token, evitando fallos en
   cascada en servicios dependientes.

   Reported-by: equipo de operaciones (incidente #4521)
   ```

4. **Commits atómicos: una idea, un commit.** Un commit debe representar
   un solo cambio lógico — no varias features, un fix y un refactor a la
   vez. Esto no es solo estética: es lo que hace útil a `git bisect` para
   encontrar en qué commit se introdujo un bug mediante búsqueda binaria.
   Con un commit "monstruo" de 40 archivos que mezcla de todo, `git bisect`
   señala el commit correcto pero no *qué parte* de ese commit causó el
   problema; con commits atómicos, señala la causa exacta.

## Checklist rápido antes de hacer commit

- ¿El subject cabe en ~50 caracteres y está en modo imperativo?
- ¿Hay una línea en blanco entre el subject y el body?
- ¿El body explica el motivo del cambio y no solo repite el diff?
- ¿Este commit representa una sola idea/cambio lógico, o debería dividirse?
- ¿Cumple además el formato de Conventional Commits (tipo, ámbito, `: `,
  BREAKING CHANGE si aplica)?
