# Esquema de las respuestas de LLM Pulse

> Generado por `scripts/06_esquema.py` a partir de una muestra real.
> **No contiene datos de clientes**: solo la forma de los campos.
> Para regenerarlo, vuelve a ejecutar los scripts 05 y 06.

## Muestra analizada

- Respuestas inspeccionadas: **20**
- Prompts distintos: **4**
- Modelos distintos: **5**
- Ventana temporal: **2026-10-12 a 2026-10-18**

## Como leer la tabla

- **Relleno**: porcentaje de veces que el campo viene con valor no vacio,
  medido sobre la **base** indicada en la columna siguiente. Un campo al 100 %
  se puede dar por garantizado; por debajo, hay que tratarlo como opcional.
- **Base**: cuantas veces podia aparecer el campo. Para los de primer nivel es el
  numero de respuestas. Para los anidados es el numero de elementos de la lista que
  los contiene: `sources[].url` se mide sobre todas las fuentes de las 20
  respuestas, no sobre las respuestas.
- **Longitud**: numero de caracteres para cadenas, numero de elementos para listas.
- **Ejemplo**: solo para campos tecnicos sin rastro de origen (fechas, numeros,
  booleanos, nombres de modelo). Un guion significa que se omite, no que este
  vacio. **No se publican** ni textos, ni nombres, ni URL o dominios (identifican
  al cliente y a sus competidores), ni identificadores internos (son trazables
  contra la cuenta de origen). Para verlos, consulta `data/` en local.
- `sources[].url` se lee: campo `url` dentro de cada elemento de la lista `sources`.

## Campos

| Campo | Tipo | Relleno | Base | Longitud | Ejemplo |
| --- | --- | ---: | ---: | --- | --- |
| `app_url` | str | 100 % | 20 | 81 | - |
| `brand_entities` | list | 15 % | 20 | 0-6 (med. 1) | - |
| `brand_entities[].category` | str | 100 % | 13 | 5-7 (med. 7) | - |
| `brand_entities[].competitor_id` | int? | 8 % | 13 | - | - |
| `brand_entities[].competitor_name` | str? | 8 % | 13 | 8 | - |
| `brand_entities[].domain` | null | 0 % | 13 | - | - |
| `brand_entities[].id` | int | 100 % | 13 | - | - |
| `brand_entities[].is_owned` | bool | 100 % | 13 | - | False |
| `brand_entities[].markdown` | str | 100 % | 13 | 4-33 (med. 15) | - |
| `brand_entities[].model` | str | 100 % | 13 | 7 | chatgpt |
| `brand_entities[].title` | str | 100 % | 13 | 8-57 (med. 42) | - |
| `brand_entities[].urls` | list | 0 % | 13 | 0 | - |
| `citations` | list | 10 % | 20 | 0-1 (med. 0) | - |
| `citations[].id` | int | 100 % | 2 | - | - |
| `citations[].position` | int | 100 % | 2 | - | 2 |
| `citations[].url` | str | 100 % | 2 | 53 | - |
| `competitor_citations` | list | 20 % | 20 | 0-2 (med. 0) | - |
| `competitor_citations[].competitor_id` | int | 100 % | 7 | - | - |
| `competitor_citations[].competitor_name` | str | 100 % | 7 | 7-15 (med. 9) | - |
| `competitor_citations[].id` | int | 100 % | 7 | - | - |
| `competitor_citations[].position` | int | 100 % | 7 | - | 6 |
| `competitor_citations[].url` | str | 100 % | 7 | 22-52 (med. 42) | - |
| `competitor_mentions` | list | 45 % | 20 | 0-2 (med. 1) | - |
| `competitor_mentions[].competitor_id` | int | 100 % | 14 | - | - |
| `competitor_mentions[].competitor_name` | str | 100 % | 14 | 5-15 (med. 8) | - |
| `competitor_mentions[].id` | int | 100 % | 14 | - | - |
| `competitor_mentions[].keywords` | list | 100 % | 14 | 1-2 (med. 1) | - |
| `competitor_mentions[].position` | int | 100 % | 14 | - | 1 |
| `duration_ms` | float | 100 % | 20 | - | 33.4 |
| `executed_at` | str | 100 % | 20 | 29 | 2026-10-12T02:21:14.075+02:00 |
| `fan_out_queries` | list? | 20 % | 20 | 2-4 (med. 2) | - |
| `id` | int | 100 % | 20 | - | - |
| `local_businesses` | list | 0 % | 20 | 0 | - |
| `locale` | object | 100 % | 20 | - | - |
| `locale.country_code` | str | 100 % | 20 | 2 | - |
| `locale.language_code` | str | 100 % | 20 | 2 | - |
| `mentions` | list | 15 % | 20 | 0-1 (med. 0) | - |
| `mentions[].id` | int | 100 % | 3 | - | - |
| `mentions[].keywords` | list | 100 % | 3 | 1 | - |
| `mentions[].position` | int | 100 % | 3 | - | 2 |
| `model` | str | 100 % | 20 | 6-11 (med. 8) | perplexity |
| `no_result` | bool | 100 % | 20 | - | False |
| `plan_required_fields` | list | 0 % | 20 | 0 | - |
| `prompt_id` | int | 100 % | 20 | - | - |
| `prompt_text` | str | 100 % | 20 | 85-109 (med. 94) | - |
| `request_id` | str | 100 % | 20 | 36 | - |
| `response` | str | 100 % | 20 | 1647-17361 (med. 5152) | - |
| `sentiments` | list | 100 % | 20 | 1-3 (med. 2) | - |
| `sentiments[].analysis` | str? | 49 % | 35 | 7-13 (med. 8) | - |
| `sentiments[].comment` | str | 100 % | 35 | 10-195 (med. 76) | - |
| `sentiments[].competitor_id` | int? | 43 % | 35 | - | - |
| `sentiments[].id` | int | 100 % | 35 | - | - |
| `sentiments[].is_brand_sentiment` | bool | 100 % | 35 | - | False |
| `sentiments[].score` | float? | 49 % | 35 | - | 0.5 |
| `sentiments[].topics` | str? | 49 % | 35 | 20-63 (med. 47) | - |
| `shopping_products` | list | 10 % | 20 | 0-4 (med. 0) | - |
| `shopping_products[].competitor_id` | null | 0 % | 7 | - | - |
| `shopping_products[].competitor_name` | null | 0 % | 7 | - | - |
| `shopping_products[].currency` | null | 0 % | 7 | - | - |
| `shopping_products[].domain` | str | 100 % | 7 | 10-22 (med. 13) | - |
| `shopping_products[].id` | int | 100 % | 7 | - | - |
| `shopping_products[].images` | list | 100 % | 7 | 1 | - |
| `shopping_products[].is_owned` | bool | 100 % | 7 | - | False |
| `shopping_products[].merchants` | null | 0 % | 7 | - | - |
| `shopping_products[].model` | str | 100 % | 7 | 7 | chatgpt |
| `shopping_products[].price` | null | 0 % | 7 | - | - |
| `shopping_products[].product_id_external` | null | 0 % | 7 | - | - |
| `shopping_products[].rank_group` | int | 100 % | 7 | - | 1 |
| `shopping_products[].rating_max` | float | 100 % | 7 | - | 5.0 |
| `shopping_products[].rating_value` | null | 0 % | 7 | - | - |
| `shopping_products[].rating_votes_count` | null | 0 % | 7 | - | - |
| `shopping_products[].tag` | str? | 14 % | 7 | 18 | - |
| `shopping_products[].title` | str | 100 % | 7 | 12-33 (med. 19) | - |
| `shopping_products[].url` | str | 100 % | 7 | 37-99 (med. 60) | - |
| `sources` | list | 90 % | 20 | 0-35 (med. 12) | - |
| `sources[].domain` | str | 100 % | 233 | 6-27 (med. 11) | - |
| `sources[].id` | int | 100 % | 233 | - | - |
| `sources[].is_competitor` | bool | 100 % | 233 | - | True |
| `sources[].is_owned` | bool | 100 % | 233 | - | False |
| `sources[].normalized_url` | str | 100 % | 233 | 16-347 (med. 83) | - |
| `sources[].position` | int | 100 % | 233 | - | 1 |
| `sources[].url` | str | 100 % | 233 | 16-347 (med. 83) | - |
| `sources[].url_sha256` | str | 100 % | 233 | 64 | - |
| `success` | bool | 100 % | 20 | - | True |

## Notas para el desarrollo del NAR

- **El texto integro esta en `response`.** El listado `/answers` lo trunca a
  10.000 caracteres, por eso el script 05 hace una segunda llamada a
  `/answers/{id}` por cada respuesta. No prescindas de esa llamada.
- **`sources[]` es la via para atribucion y share of voice**: contiene las
  referencias que el modelo cita. Comprueba arriba su relleno antes de
  construir metricas que dependan de el.
- **La unidad de analisis es (prompt x modelo x fecha)**, que es como esta
  aplanado `data/interim/respuestas.csv`. Un mismo prompt se ejecuta contra
  varios modelos: ahi es donde se compara la narrativa.
- **Ojo con las fechas**: los filtros de `/answers` se refieren a cuando se
  genero la respuesta; los de `/dimensions/prompts`, a cuando se creo el prompt.
- **La cadencia de ejecucion es semanal**, en la madrugada del lunes, no diaria.
  Cualquier ventana temporal mas corta que una semana puede devolver cero
  respuestas sin que nada falle: es el primer fallo a descartar.
