# Plantilla estándar de README.md

Esta plantilla combina la estructura que el usuario definió como base
(título/subtítulo, párrafo introductorio, ayuda visual, instrucciones de
usuario, instrucciones de desarrollador) con buenas prácticas de
documentación de software confirmadas por investigación propia, y con el
estilo específico observado en el proyecto de referencia del usuario
(Spring Boot User Manager), que él mismo marcó como estándar a imitar
para: título, subtítulo, badges de stack, y sección About.

---

## 1. Título y subtítulo

```markdown
# Nombre del Proyecto

**Una línea en negrita que resume el problema que resuelve — no lo que es.**
```

- El subtítulo va en **negrita**, en una sola línea, inmediatamente debajo
  del título (sin encabezado propio).
- Enfócalo en el *problema resuelto*, no en una descripción técnica plana.
  Ejemplo del proyecto de referencia: no dice "API REST hecha con Spring
  Boot", dice qué gestiona y cómo lo entrega (*"REST API for managing
  users, roles, permissions, and API keys — with asynchronous event
  delivery via RabbitMQ."*).

## 2. Fila de badges (stack tecnológico)

Justo debajo del subtítulo, antes de cualquier otro contenido. Formato
estándar de [shields.io](https://shields.io), con logo de
[Simple Icons](https://simpleicons.org):

```markdown
[![Nombre](https://img.shields.io/badge/Label-Version-COLORHEX?logo=nombre-icono)](https://url-oficial-de-la-tecnologia)
```

Reglas:

- Un badge por cada pieza **central** del stack (lenguaje/runtime,
  framework principal, base de datos, message broker, etc.). No listar
  librerías secundarias aquí — eso va en la tabla de "Tech Stack" más
  abajo, no en los badges superiores.
- Cada badge enlaza a la web oficial de esa tecnología (`href` del link
  de Markdown que envuelve la imagen).
- Usa el color de marca oficial en hex (ej. Spring Boot `#6DB33F`, Java
  `#ED8B00`, PostgreSQL `#4169E1`, RabbitMQ `#FF6600`) — se puede
  consultar en Simple Icons o en la guía de marca de cada tecnología.
- Límite práctico: entre 3 y 6 badges. Más que eso empieza a diluir la
  señal y se ve como relleno.
- Solo se agregan badges de estado (build passing, cobertura de tests,
  versión de release) si existe el pipeline/proceso real detrás — nunca
  como decoración. **Siempre preguntar al usuario si aplica** antes de
  incluir este tipo de badge (ver SKILL.md, tabla de preguntas
  obligatorias).

Ejemplo real (tomado del proyecto de referencia del usuario):

```markdown
[![Spring Boot](https://img.shields.io/badge/Spring%20Boot-4.0.6-6DB33F?logo=springboot)](https://spring.io/projects/spring-boot)
[![Java](https://img.shields.io/badge/Java-25-ED8B00?logo=openjdk)](https://openjdk.org/projects/jdk/25/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18.3-4169E1?logo=postgresql)](https://www.postgresql.org/)
```

## 3. Sección `## About`

Encabezado fijo: `## About`. Estructura de 2-3 párrafos:

- **Párrafo 1 — el problema y su complejidad real.** Engancha explicando
  por qué el problema no es tan simple como suena a primera vista. Usa
  palabras clave del dominio (las mismas que un usuario buscaría) de
  forma natural, no forzada como relleno de SEO.
- **Párrafo 2 — la solución y el enfoque técnico central.** Aquí es
  donde se menciona el patrón arquitectónico principal (ej. Arquitectura
  Hexagonal, Clean Architecture, DDD) y cómo se refleja en el proyecto.
  Si hay un flujo importante (ej. un pipeline asíncrono), se describe en
  prosa aquí a alto nivel — el diagrama detallado va en la sección de
  Arquitectura más abajo.
- **Párrafo 3 (opcional) — disclaimer o contexto del proyecto.** Si es un
  proyecto personal, de aprendizaje, un MVP, o tiene alguna limitación de
  alcance relevante, usar un blockquote:

  ```markdown
  > **Disclaimer:** This is a **personal learning project**. ...
  ```

Después del About, si el dominio tiene conceptos propios que conviene
aclarar antes de seguir leyendo (ej. "Usuario", "Rol", "Permiso", "Webhook"
en el proyecto de referencia), agregar una tabla:

```markdown
### Key concepts

| Concept | Description |
|---------|-------------|
| **Users** | ... |
| **Roles** | ... |
```

Esta tabla es opcional y depende de si el dominio tiene terminología
propia que no es evidente por el nombre — no forzarla si el proyecto es
simple.

## 4. Ayuda visual

**Siempre preguntar al usuario cómo resolver esta sección — nunca
decidirlo por defecto.** Las opciones típicas son:

- Screenshot o GIF del proyecto en uso (lo más persuasivo según buenas
  prácticas de documentación, más que badges adicionales).
- Video/demo enlazado.
- Si el proyecto es una API sin interfaz visual (como suele ser un
  backend), una lista de los endpoints principales suele ser el
  reemplazo más útil — o un enlace directo a la documentación interactiva
  si existe (ej. Swagger UI).
- Si nada de esto existe todavía, usar un placeholder explícito y visible
  en vez de omitir la sección silenciosamente, para que quede como tarea
  pendiente clara:

  ```markdown
  ## Demo

  > 🚧 Demo/GIF pendiente de agregar.
  ```

## 5. Instrucciones para usuario final (Quick Start)

Encabezado sugerido: `## Quick Start` o `## Getting Started`. Dirigido a
quien solo quiere **usar** el proyecto ya construido, sin tocar el código:

- Prerequisitos (herramientas necesarias, con enlace a cada una).
- Opción recomendada primero (normalmente Docker/Docker Compose si el
  proyecto lo soporta) — es la vía con menos fricción.
- Opción manual como alternativa, para quien no usa contenedores.
- Cómo verificar que quedó funcionando (URL local, comando de prueba, o
  enlace a documentación interactiva como Swagger/OpenAPI si existe).

Todo comando debe ser el real del proyecto — copiado o verificado contra
el `docker-compose.yml`, `Dockerfile`, `package.json`/scripts, `pom.xml`,
Makefile, etc. según corresponda. Nunca un comando genérico "típico" del
framework si no se confirmó que es el que usa este proyecto.

## 6. Instrucciones para desarrollador (Developer Guide)

Encabezado sugerido: `## Developer Guide` o `## Development`. Dirigido a
quien va a **modificar** el código:

- Estructura de carpetas real del proyecto (árbol de directorios,
  reflejando la organización real — no una genérica del framework).
- Cómo correr el proyecto en modo desarrollo (hot reload si aplica,
  variables de entorno necesarias, servicios dependientes a levantar
  primero).
- Tabla de configuración si hay variables de entorno o propiedades
  relevantes:

  ```markdown
  | Property | Description | Example |
  |----------|-------------|---------|
  | `spring.datasource.url` | PostgreSQL JDBC URL | `jdbc:postgresql://localhost:5432/mydatabase` |
  ```

- Si hay un flujo de proceso interno importante (ej. cómo viaja un evento
  a través del sistema), un diagrama en bloque de texto ayuda más que un
  párrafo largo:

  ```
  Create user → WebhookPublisher (HTTP POST, @Async)
                     ↓
          SuscriptorController (/api/v1/webhook/delivery)
                     ↓
          ...
  ```

Esta separación (Quick Start vs. Developer Guide) no es solo estética:
son audiencias con necesidades opuestas — el usuario final no quiere leer
sobre compilación y estructura de paquetes, el desarrollador no se
conforma con solo "instala y corre". Mezclarlas obliga a ambos a escanear
contenido irrelevante para encontrar lo suyo.

## 7. Arquitectura (si aplica)

Si el proyecto sigue un patrón arquitectónico explícito (Hexagonal,
Clean Architecture, capas MVC estrictas, DDD, etc.), dedicar una sección
propia con:

- Diagrama ASCII de las capas y su relación de dependencia.
- La "regla de dependencia" explicada en una frase (qué capa puede
  conocer a cuál).
- Árbol de carpetas que refleje esa organización.

## 8. Secciones opcionales — SIEMPRE preguntar antes de incluir

Estas secciones son parte legítima del estándar, pero **nunca se agregan
por defecto**. Confirmar con el usuario si aplican a su proyecto:

### `## Contributing`

Solo si el proyecto acepta o busca colaboradores externos. Para
proyectos con flujo de contribución más elaborado, lo recomendado es un
`CONTRIBUTING.md` separado y enlazar a él desde el README, en vez de
saturar el README principal con reglas de PR, estándares de código, etc.
Esto mantiene el README enfocado en la audiencia más grande (los
usuarios), que es la práctica que consistentemente recomienda la
documentación actual sobre README.

```markdown
## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md)
before submitting a pull request.
```

### `## License`

Solo si el usuario ya definió una licencia. No se debe asumir MIT ni
ninguna otra por defecto — sin licencia declarada, aplica por defecto el
copyright cerrado (nadie puede legalmente usar/modificar/distribuir el
código), así que es una decisión que le corresponde únicamente al dueño
del proyecto.

```markdown
## License

MIT License. See [LICENSE](LICENSE) for details.
```

### Badges de estado (CI, cobertura, versión)

Solo si existe el pipeline/proceso real. Un badge de "build: passing" sin
un workflow de CI detrás es información falsa, no decoración.

## 9. Cierre (opcional)

El proyecto de referencia usa un footer discreto en `<sub>`:

```markdown
<sub>Built with Spring Boot, Java, RabbitMQ, and a lot of curiosity.</sub>
```

Es un detalle de estilo, no un estándar obligatorio — mantenerlo si el
usuario lo pide o si encaja con el tono del resto del documento.

---

## Checklist antes de entregar

- [ ] Título + subtítulo en negrita, enfocado en el problema resuelto.
- [ ] Badges de shields.io (3-6) con logo, color de marca, y enlace a la
      web oficial de cada tecnología.
- [ ] `## About` con 2-3 párrafos (problema → solución/arquitectura →
      disclaimer opcional).
- [ ] Ayuda visual resuelta **según lo que el usuario confirmó**, no por
      defecto.
- [ ] Instrucciones de usuario final y de desarrollador en secciones
      separadas, con comandos reales del proyecto.
- [ ] Contributing/License/badges de estado incluidos únicamente si el
      usuario confirmó que aplican.
- [ ] Todo el contenido verificado contra el código/README real — cero
      placeholders de relleno inventados.
