# Cost Analysis - LabSecure
> Los costos reales dependen de la región, uso real y descuentos de AWS.

## 1. Componentes principales de costo

### 1.1 EC2 (Portal y Worker)

- 2 instancias EC2 pequeñas (ej. t3.small):
  - `portal` → corre Flask + consultas ligeras a DynamoDB.
  - `worker` → procesa mensajes de SQS.
- Costos:
  - Por instancia, del orden de **decenas de USD/mes** si están 24/7.
- Optimización:
  - Apagar ambientes de desarrollo o usar instancias más pequeñas cuando sea posible.
  - Migrar a ECS Fargate si se quiere pagar solo por uso.

### 1.2 DynamoDB

Tablas:

- `lab_results` (lecturas/escrituras moderadas).
- `patients` (pocas escrituras, algunas lecturas).
- `access_audit` (muchas escrituras, algunas lecturas para dashboards).

Modelo de facturación: **On-Demand (PAY_PER_REQUEST)**.

- Ventajas:
  - Escala automático sin configurar capacidad.
  - Bueno para cargas variables.
- Costos típicos:
  - Para volúmenes de laboratorio moderados (miles o decenas de miles de resultados/mes), el costo suele ser moderado.

Optimización:

- Usar índices secundarios solo cuando sean necesarios.
- Ajustar TTL para no retener datos innecesarios fuera del período requerido.

### 1.3 S3

Bucket `lab_results`:

- Almacena:
  - JSON crudos (`raw/`).
  - JSON procesados (`processed/`).
  - PDFs (`reports/`).

Costos:

- Almacenamiento por GB/mes (muy barato).
- Requests `PUT/GET` también muy baratos en volumen moderado.

Optimización:

- Usar clases de almacenamiento más baratas (S3 Standard-IA, Glacier) para resultados muy viejos.
- Configurar lifecycle rules por prefijo si se quisieran migrar datos antiguos.

### 1.4 SQS

Colas:

- `lab_results_queue`, `lab_results_dlq`.
- `notify_queue`, `notify_dlq`.

Costos:

- Muy bajo costo por millón de requests.
- En un escenario de laboratorio/curso, prácticamente despreciable.

### 1.5 SNS

Topic `lab_results_ready`:

- Se factura por número de publicaciones y tipo de destino (email, SMS, etc.).

Optimización:

- Evitar notificaciones innecesarias.
- Agrupar notificaciones (ej. resumen diario) si el volumen es muy alto.

### 1.6 Lambda

Funciones:

- `ingest`
- `report`
- `notify`
- `data_lifecycle`

Costos:

- Dependen de:
  - Cantidad de invocaciones.
  - Duración de cada ejecución.
  - Memoria configurada.
- En este proyecto:
  - `ingest` y `notify` suelen ser rápidos (milisegundos).
  - `report` y `data_lifecycle` pueden tardar más, pero no son frecuentes.

Optimización:

- No sobredimensionar la memoria.
- Mantener el código eficiente (evitar loops pesados innecesarios).
- `data_lifecycle` se ejecuta 1 vez al día con un scan filtrado.

### 1.7 API Gateway

- REST API + HTTP API.
- Costos:
  - Por millón de llamadas.
- Optimización:
  - Usar HTTP API para endpoints sencillos (más barato).
  - Mantener REST API solo si se necesitan features avanzados.

---

## 2. Costo estimado mensual (muy aproximado)

### Ambiente de laboratorio (bajo tráfico)

Asumiendo:

- Decenas de miles de requests/mes.
- Pocas decenas de GB almacenados.

Orden de magnitud:

- EC2 (2 instancias pequeñas): **decenas de USD/mes**.
- DynamoDB: **bajo** (probablemente < 20–30 USD/mes en uso moderado).
- S3: **muy bajo**.
- Lambda, SQS, SNS, API Gateway: **bajo** en este escenario.

Total estimado: **del orden de decenas de USD/mes**, dependiendo de la región y del uso real.

---

## 3. Costo por resultado procesado

En un escenario de laboratorio moderado:

- Cada resultado toca:
  - 1 llamada a API Gateway + Lambda `ingest`.
  - 1 escritura en S3 (`raw/`).
  - 1 mensaje en SQS.
  - 1 procesamiento en EC2 worker.
  - 1 escritura en DynamoDB.
  - 1 mensaje en `notify_queue`.
  - 1 Lambda `notify` + 1 publicación en SNS.

Estos son recursos muy baratos por operación, por lo que el costo por resultado procesado suele ser una **fracción de centavo (USD)**.

---

## 4. Optimizaciones implementadas

- Uso de **DynamoDB On-Demand** → sencillo y eficiente para cargas variables.
- TTL en `lab_results` → evita almacenar datos eternamente.
- Versionado en S3 activado solo en el bucket principal (controlado).
- Reutilización de un solo worker EC2 en vez de un cluster completo.

---

## 5. Oportunidades de optimización futura

- Migrar el worker y el portal a **ECS Fargate** para pagar solo por tiempo de CPU/ RAM usado.
- Añadir **CloudFront** para el portal (si tuviera assets estáticos pesados).
- Ajustar niveles de **retention_in_days** en CloudWatch logs para reducir costo de logs.
- Usar **WAF** solo si el tráfico real lo justifica (es un costo extra).
