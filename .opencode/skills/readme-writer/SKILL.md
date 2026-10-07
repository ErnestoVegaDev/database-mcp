---
name: readme-writer
description: Crea o reescribe archivos README.md profesionales para proyectos de desarrollo de software, siguiendo un estándar con título+subtítulo, badges de stack (shields.io), sección About, tabla de conceptos clave, arquitectura, instrucciones separadas para usuario final y para desarrollador. Úsala siempre que el usuario pida "crear un README", "reescribir el README", "mejorar mi README", "documentar este proyecto", pregunte cómo estructurar un README, o comparta el código/estructura de un proyecto pidiendo que se le genere la documentación de portada. Aplica tanto si el usuario pega código o describe el proyecto en texto, como si adjunta un README existente para reescribir.
license: MIT
compatibility: opencode
metadata:
  audience: developers
  output_format: markdown
---

# README Writer

Skill para crear o reescribir archivos `README.md` con un estándar
profesional y consistente entre proyectos, basado en buenas prácticas de
documentación de software (GitHub Flavored Markdown, badges shields.io,
separación de audiencias usuario/desarrollador) y en la plantilla de
referencia que se detalla en `references/estructura-readme.md`.

## Principio rector: nunca asumas, pregunta primero

Esta skill trabaja con información real del proyecto, no con relleno
genérico. Dos reglas duras gobiernan todo el workflow:

1. **Nunca inventes contenido que no puedas verificar.** Nombre del
   proyecto, stack, comandos de instalación, estructura de carpetas,
   variables de entorno: todo debe salir del código real, del README
   existente que el usuario comparta, o de lo que el usuario responda
   directamente. Si falta un dato, pregúntalo — no lo completes con un
   placeholder inventado que suene plausible.
2. **Las secciones opcionales SIEMPRE se preguntan antes de incluirse.**
   Nunca agregues `## Contributing`, `## License`, badges de CI/build, o
   una sección de ayuda visual (demo/GIF/lista de endpoints) sin
   confirmar antes con el usuario si aplica a su caso. Ver el detalle de
   cada una en "Preguntas obligatorias" más abajo.

## Workflow

### 1. Reunir contexto del proyecto

Antes de escribir una sola línea, identifica:

- **Qué es el proyecto y qué problema resuelve.** Si el usuario pegó
  código, un README anterior, o describió el proyecto, extrae esto de
  ahí. Si es ambiguo o insuficiente para redactar el párrafo introductorio
  (ver `references/estructura-readme.md`, sección 2), pregunta.
- **Stack tecnológico real.** Lee archivos de dependencias si están
  disponibles (`pom.xml`, `package.json`, `requirements.txt`,
  `build.gradle`, `*.csproj`, etc.) en vez de asumir versiones. Si el
  usuario solo describe el proyecto sin dar acceso al código, pregunta
  las tecnologías y versiones exactas — no debes redondear ni escoger
  "una versión típica".
- **Estructura de carpetas real**, si vas a incluir un árbol de
  directorios (recomendado en la sección de Arquitectura). Debe reflejar
  la estructura real del repositorio, no una genérica de "cómo suele
  verse un proyecto de este framework".
- **Si ya existe un README**, léelo completo antes de reescribir: puede
  tener información valiosa (URLs, credenciales de ejemplo, variables de
  entorno, decisiones de arquitectura) que no debe perderse solo porque
  se está mejorando el formato.

### 2. Preguntas obligatorias (antes de redactar)

Estas preguntas **no son opcionales para la skill** — siempre deben
resolverse antes de producir el README final, incluso si el usuario no
las mencionó:

| Punto a confirmar | Por qué preguntar en vez de asumir |
|---|---|
| **Ayuda visual** (sección 3 de la plantilla): ¿hay demo, GIF, screenshot, video, o se prefiere listar los endpoints principales de la API? | Es contenido que no se puede fabricar — depende de si existe un asset visual real o si el usuario quiere documentar endpoints en su lugar. Si no hay nada disponible aún, pregunta si se deja como placeholder marcado (`> 🚧 Demo próximamente`) o si se omite la sección por ahora. |
| **`## Contributing`** | Solo aplica si el proyecto acepta colaboradores externos. Un proyecto personal/de aprendizaje normalmente no la necesita. |
| **`## License`** | Depende de si el usuario ya eligió una licencia. Sin ella, no se debe inventar una ni asumir MIT por defecto. |
| **Badges adicionales** (CI/build status, cobertura de tests, versión de release) | Solo tienen sentido si existe el pipeline o el proceso real detrás (Actions, cobertura, releases). Un badge que no refleja nada real es ruido, no información. |

No avances a redactar el documento final sin haber resuelto estos cuatro
puntos con el usuario (aunque sea con una sola pregunta agrupada).

### 3. Redactar siguiendo el estándar

Usa `references/estructura-readme.md` como plantilla — contiene la
estructura completa sección por sección (con el porqué de cada una) y el
formato exacto de badges. Dos secciones son **fijas y no negociables**
como estándar (así lo pidió el usuario explícitamente): el bloque de
título+subtítulo+badges, y la sección `## About`. Mantén ese formato
igual entre proyectos aunque cambie el contenido.

Respeta siempre:

- GitHub Flavored Markdown (tablas, bloques de código con lenguaje
  anotado, listas de tareas si aplica).
- Separación clara entre instrucciones para **usuario final** (cómo
  instalar y correr el proyecto ya construido, idealmente vía Docker si
  existe) e instrucciones para **desarrollador** (cómo compilar, correr
  en modo desarrollo, estructura de carpetas, variables de configuración).
  Esto no es un capricho de estilo: son audiencias con objetivos
  distintos y mezclar sus instrucciones obliga a ambas a leer contenido
  que no necesitan.
- Un tono profesional pero directo — sin relleno de marketing vacío
  ("solución innovadora de última generación"), y sin emojis salvo que
  el usuario los use en su ejemplo/proyecto.

### 4. Revisión final

Antes de entregar el archivo, verifica:

- ¿Todo comando de instalación/ejecución es el real del proyecto (no
  genérico de "un proyecto de este framework")?
- ¿Las cuatro preguntas obligatorias de la sección 2 quedaron resueltas
  y reflejadas (o explícitamente omitidas por decisión del usuario)?
- ¿Los badges usan el formato y colores de marca correctos? (ver
  `references/estructura-readme.md`, sección de badges).
- ¿La tabla de stack/dependencias coincide con lo que declara el
  proyecto real (versiones incluidas)?

## Entregable

Genera el archivo como `README.md` usando las herramientas de archivo
disponibles (no lo dejes solo en el chat como texto plano) cuando el
usuario tenga un proyecto real al que aplicarlo, para que pueda
descargarlo y colocarlo directamente en la raíz del repositorio.

## Referencias

- `references/estructura-readme.md` — plantilla completa sección por
  sección, con el formato exacto de badges de shields.io, ejemplos de
  cada bloque, y justificación de buenas prácticas basada en
  investigación sobre documentación de proyectos de software.
