# Exploración de la API de LLM Pulse

Repositorio de **exploración**, no de producción. Su único objetivo es responder a una pregunta
antes de empezar a construir el NAR:

> ¿Qué campos devuelve la API de LLM Pulse para cada respuesta de un modelo, cuáles vienen
> siempre rellenos y sobre qué se puede calcular?

Si has llegado aquí para desarrollar el NAR, **empieza por [`docs/ESQUEMA.md`](docs/ESQUEMA.md)**:
es el modelo de datos real, medido sobre una muestra, y te ahorra descubrirlo a base de llamadas.

Todo el código es **de solo lectura**: solo hace peticiones `GET`. No modifica proyectos, prompts
ni tags, y no ejecuta modelos.

## Requisitos

- **Python 3.10 o superior.** Nada más: el repositorio funciona con la biblioteca estándar.
- Una API key de LLM Pulse con permisos de lectura (plan Scale o superior, según la documentación).
- `pip install -r requirements.txt` es **opcional** y solo hace falta detrás de un proxy
  corporativo. Ver [Redes con inspección TLS](#redes-con-inspección-tls).

## Arranque en tres pasos

```bash
cp .env.example .env        # en PowerShell: Copy-Item .env.example .env
```

Abre `.env` y pon tu clave en `LLMPULSE_API_KEY`. **`.env` está ignorado por git y no debe
subirse nunca.** Después:

```bash
py scripts/01_ping.py
```

Si responde `ok=True`, ya estás conectado.

## Los seis pasos

Cada script se ejecuta por separado y en orden. Los pasos 2 y 3 **anotan tu elección en `.env`**,
así que no hay que repetir las llamadas en cada iteración.

| Script | Qué hace | Endpoints |
| --- | --- | --- |
| `01_ping.py` | Comprueba credencial y conectividad | `GET /ping` |
| `02_proyectos.py` | Lista los proyectos accesibles | `/dimensions/projects` |
| `03_tags_y_modelos.py` | Tags del proyecto y modelos con datos | `/dimensions/collections`, `/dimensions/models` |
| `04_prompts.py` | Prompts del tag elegido | `/dimensions/prompts` |
| `05_muestra.py` | Descarga la muestra de respuestas completas | `/answers`, `/answers/{id}` |
| `06_esquema.py` | Genera `docs/ESQUEMA.md` | ninguno (lee de `data/raw/`) |

Los pasos 2 y 3 aceptan un ID para fijar la elección:

```bash
py scripts/02_proyectos.py          # lista
py scripts/02_proyectos.py 123      # fija LLMPULSE_PROJECT_ID=123 en .env
py scripts/03_tags_y_modelos.py 7   # fija LLMPULSE_COLLECTION_ID=7
```

Antes del paso 5 hay que fijar la ventana temporal en `.env`:

```
LLMPULSE_FROM=2026-10-12
LLMPULSE_TO=2026-10-18
```

## Cómo se construye la muestra

El criterio **no** es un tope plano de respuestas, y esto importa. Si pides «las 20 primeras
respuestas», la API puede darte 20 ejecuciones del mismo prompt en días distintos, y entonces no
hay nada que comparar. Lo que interesa para el NAR es **el mismo prompt respondido por modelos
distintos**.

Por eso el paso 5:

1. Pide el listado de respuestas del tag en la ventana temporal.
2. Las **agrupa por prompt** y se queda con los `LLMPULSE_NUM_PROMPTS` (4 por defecto) que más
   respuestas tienen.
3. Descarga el detalle **completo** de todas las respuestas de esos prompts.

`LLMPULSE_MAX_ANSWERS` es solo una red de seguridad para no descargar de más, no el criterio de
selección.

Son **dos topes independientes** y conviene ajustar los dos. `NUM_PROMPTS` recorta *antes* de
descargar, descartando prompts enteros; `MAX_ANSWERS` corta *durante* la descarga, pase lo que
pase. Ejemplo real: un tag con 11 prompts y un proyecto con 5 modelos daría 55 respuestas por
ejecución. Con `NUM_PROMPTS=4` bajan a 20. Y conviene poner además `MAX_ANSWERS=20`, porque si
algún prompt se ejecutó dos veces dentro de la ventana saldrían 40 sin que nada lo advierta.

### Prueba exploratoria frente al NAR definitivo

El recorte a 4 prompts existe **solo para esta exploración**: permite ver el esquema completo con
pocas llamadas a la API. **El NAR definitivo analiza todos los prompts del tag**, no una muestra.

Para ese modo no hay que tocar código, basta con `.env`:

```
LLMPULSE_NUM_PROMPTS=all
LLMPULSE_MAX_ANSWERS=5000
```

Con `all` (o `0`) no se recorta nada: se descargan las respuestas de todos los prompts que
aparezcan en la ventana. Hay que subir `LLMPULSE_MAX_ANSWERS` en consecuencia, porque si no el
tope de seguridad corta la descarga a mitad.

El resto del flujo es idéntico, caché incluida: lo ya descargado no se vuelve a pedir, así que
pasar de la muestra a la extracción completa solo cuesta las respuestas nuevas.

El paso 3 te dice cuántos modelos con datos tiene el proyecto, que es lo que determina el tamaño
de la muestra: `LLMPULSE_NUM_PROMPTS` × número de modelos × número de ejecuciones que caigan
dentro de la ventana.

### La cadencia es semanal: la ventana tiene que cubrir una semana entera

**LLM Pulse no lanza los prompts a diario, sino una vez por semana, en la madrugada del lunes.**
Confirmado por el equipo y coherente con el campo `executed_at` de la muestra, que marca el lunes
12 de octubre a las 02:21 (+02:00).

La consecuencia es contraintuitiva y conviene no tropezar con ella: **una ventana de uno o dos
días puede devolver cero respuestas**, no porque haya un error de configuración, sino porque
ningún día de la ventana coincide con el de ejecución. Si el paso 5 dice que no hay respuestas,
lo primero que hay que descartar es esto, antes que el tag o la clave.

Por eso la ventana de ejemplo cubre siete días completos (lunes a domingo). Para una muestra
limpia conviene **una sola semana**: así hay una única ejecución por prompt y modelo, y la
comparación entre modelos no se mezcla con la evolución temporal. Ampliar la ventana a varias
semanas multiplica la muestra por el número de lunes que contenga.

### Por qué hay dos llamadas por respuesta

`GET /answers` **trunca el texto a 10.000 caracteres**. El NAR necesita la respuesta íntegra, así
que por cada ejecución se hace una segunda llamada a `GET /answers/{id}`. No elimines esa segunda
llamada: es la diferencia entre analizar la respuesta y analizar su principio.

Cada detalle se cachea en `data/raw/<execution_id>.json`. Reejecutar el paso 5 no vuelve a pedir
lo que ya está, y el paso 6 no cuesta ninguna llamada.

## Qué genera

```
docs/ESQUEMA.md              SÍ se versiona. Solo la forma de los campos.
data/raw/<id>.json           Respuesta cruda, tal cual la devuelve la API.
data/interim/muestra.json    Manifiesto: qué se descargó y con qué filtros.
data/interim/respuestas.csv  Tabla plana, una fila por (prompt × modelo × fecha).
```

`data/` **está ignorado por git** y contiene información confidencial de clientes.

`respuestas.csv` es la unidad de análisis del NAR: lleva el texto íntegro en una columna, más
`model`, `executed_at`, el número de fuentes y sus dominios.

## Redes con inspección TLS

En redes corporativas que inspeccionan el tráfico HTTPS, el certificado de `llmpulse.ai` no lo
firma una autoridad pública sino el proxy de la empresa. Python lo rechaza:

```
[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: certificate signature failure
```

No es un problema de la clave ni del plan: falla antes de enviar ninguna credencial. La autoridad
corporativa **sí** está en el almacén de certificados de Windows, pero OpenSSL no lo consulta. La
solución es `truststore`, que delega la verificación en el sistema operativo:

```bash
py -m pip install -r requirements.txt
```

El script `01_ping.py` indica al arrancar si la verificación está delegada en el sistema. Fuera de
esas redes no hace falta instalar nada: el código detecta que `truststore` no está y sigue con la
verificación normal.

## Tests

No necesitan clave ni conexión: simulan las respuestas de la API.

```bash
py -m unittest discover -s tests -v
```

Cubren la selección de prompts, la caché, el tope de seguridad, el aplanado a CSV y —importante—
que el informe de esquema **no filtre texto de respuestas ni nombres de cliente**.

## Seguridad

- **No compartas la API key.** Conviene generar una de solo lectura y restringida a los proyectos
  necesarios.
- **`data/` no sale del entorno aprobado.** Puede contener información confidencial de clientes:
  no va a repositorios, chats ni herramientas no autorizadas.
- `docs/ESQUEMA.md` sí se versiona porque solo describe la forma de los datos. Aun así,
  **revísalo antes del primer push**: los valores de ejemplo están filtrados por una lista de
  campos sensibles (ver `src/llmpulse/schema.py`) y conviene comprobar que esa lista cubre los
  campos de tu proyecto.
- Ningún script imprime la clave por pantalla ni la escribe en los ficheros exportados.

## Límites conocidos

- Es una **prueba de exploración**, no un pipeline: no hay programación semanal, base de datos ni
  checkpoints persistentes.
- **Las fechas significan cosas distintas según el endpoint**: en `/answers` se refieren a cuándo
  se generó la respuesta; en `/dimensions/prompts`, a cuándo se creó el prompt.
- La pertenencia de un prompt a un tag se expone de dos formas (`collection_ids` y `tags`). En el
  proyecto con el que se probó **sí viene rellena**, así que `/dimensions/prompts` basta para
  saber qué prompts lleva cada tag. El paso 4 avisa si alguna vez no fuera así; el paso 5
  funcionaría igualmente, porque filtra `/answers` por `collection_id`.
- Un prompt puede tener más de un tag.
- **Por convención del equipo, un tag nunca está vacío**: si un tag no devuelve prompts, es una
  señal de que algo va mal en la configuración del proyecto, no un caso normal a gestionar.
- La documentación oficial no se pudo consultar desde la red corporativa (mismo problema de
  certificado). Los endpoints usados aquí están comprobados contra la API real, pero puede haber
  parámetros adicionales sin documentar en este README.

## Documentación de referencia

- [Referencia oficial de la API](https://llmpulse.ai/api-docs)
- [Referencia técnica completa](https://llmpulse.ai/api-docs/llms-full.txt)
- [Endpoints de respuestas](https://llmpulse.ai/api-docs/answers)
- [Prompts](https://llmpulse.ai/api-docs/prompts)
- [Tags y collections](https://llmpulse.ai/api-docs/collections-and-tags)
