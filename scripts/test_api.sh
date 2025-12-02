#!/usr/bin/env bash
set -euo pipefail

# Cambia esto por tu URL real de API Gateway (sin la ruta final)
# Ejemplo: https://abc123.execute-api.us-east-1.amazonaws.com/prod
API_BASE_URL="${API_BASE_URL:-https://your-api-gateway-url}"

echo "== LabSecure API Smoke Test =="
echo "API_BASE_URL = ${API_BASE_URL}"
echo

if [[ "${API_BASE_URL}" == "https://your-api-gateway-url" ]]; then
  echo "ERROR: Debes exportar API_BASE_URL con tu URL real de API Gateway."
  echo "Ejemplo:"
  echo "  export API_BASE_URL='https://abc123.execute-api.us-east-1.amazonaws.com/prod'"
  exit 1
fi

# 1) Health check
echo "1) GET /api/v1/health"
curl -sS -X GET "${API_BASE_URL}/api/v1/health" | jq .
echo

# 2) POST /api/v1/ingest con un payload de ejemplo
echo "2) POST /api/v1/ingest"

REQUEST_BODY='{
  "patient_id": "P123456",
  "lab_id": "LAB001",
  "lab_name": "Quest Diagnostics",
  "test_type": "complete_blood_count",
  "test_date": "2024-01-15T10:30:00Z",
  "physician": {
    "name": "Dr. Sarah Johnson",
    "npi": "1234567890"
  },
  "results": [
    {
      "test_code": "WBC",
      "test_name": "White Blood Cell Count",
      "value": 7.5,
      "unit": "10^3/uL",
      "reference_range": "4.5-11.0",
      "is_abnormal": false
    },
    {
      "test_code": "RBC",
      "test_name": "Red Blood Cell Count",
      "value": 4.8,
      "unit": "10^6/uL",
      "reference_range": "4.5-5.5",
      "is_abnormal": false
    }
  ],
  "notes": "Fasting sample. Patient reported no recent illness."
}'

RESPONSE=$(curl -sS -X POST "${API_BASE_URL}/api/v1/ingest" \
  -H "Content-Type: application/json" \
  -d "${REQUEST_BODY}")

echo "Respuesta:"
echo "${RESPONSE}" | jq .
echo

RESULT_ID=$(echo "${RESPONSE}" | jq -r '.result_id')
STATUS=$(echo "${RESPONSE}" | jq -r '.status')

if [[ -z "${RESULT_ID}" || "${RESULT_ID}" == "null" ]]; then
  echo "ERROR: no se obtuvo result_id en la respuesta de ingest."
  exit 1
fi

echo "result_id = ${RESULT_ID}"
echo "status    = ${STATUS}"
echo

# 3) Polling /api/v1/status/{result_id}
echo "3) GET /api/v1/status/${RESULT_ID} (polling hasta PROCESSED o 10 intentos)"

ATTEMPTS=0
MAX_ATTEMPTS=10

while [[ "${ATTEMPTS}" -lt "${MAX_ATTEMPTS}" ]]; do
  ATTEMPTS=$((ATTEMPTS + 1))
  echo "Intento ${ATTEMPTS}/${MAX_ATTEMPTS}..."

  STATUS_RESPONSE=$(curl -sS -X GET "${API_BASE_URL}/api/v1/status/${RESULT_ID}")
  echo "Respuesta:"
  echo "${STATUS_RESPONSE}" | jq .

  CURR_STATUS=$(echo "${STATUS_RESPONSE}" | jq -r '.status')

  if [[ "${CURR_STATUS}" == "PROCESSED" ]]; then
    echo "✅ Resultado PROCESSED en intento ${ATTEMPTS}."
    exit 0
  fi

  echo "Estado actual = ${CURR_STATUS}, esperando 5 segundos..."
  sleep 5
done

echo "⚠️ Timeout esperando que el resultado se procese."
exit 1
