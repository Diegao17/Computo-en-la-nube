import os
import json
import uuid
from datetime import datetime, timezone

import boto3

# Configuración desde variables de entorno
REGION_NAME = os.environ.get("REGION_NAME", "us-east-1")
RAW_BUCKET = os.environ["RAW_BUCKET"]
LAB_RESULTS_QUEUE_URL = os.environ["LAB_RESULTS_QUEUE_URL"]

s3 = boto3.client("s3", region_name=REGION_NAME)
sqs = boto3.client("sqs", region_name=REGION_NAME)


def main():
    # IDs y datos base
    lab_id = "lab-001"
    result_id = str(uuid.uuid4())
    patient_id = "patient-123"
    lab_name = "Lab Central"
    test_type = "glucose"
    value = 95.6
    unit = "mg/dL"
    risk_score = 0.18
    collected_at = datetime.now(timezone.utc).isoformat()

    # Key en S3 donde se guarda el JSON crudo
    s3_key = f"raw/{result_id}.json"

    # Estructura pensada para cubrir todo lo que nos ha pedido process_lab_result:
    #   raw_data["lab_id"]
    #   raw_data["patient_id"]
    #   raw_data["lab_name"]
    #   raw_data["test_type"]
    #   raw_data["value"]
    #   raw_data["unit"]
    #   raw_data["risk_score"]
    #   raw_data["result_id"]
    #   raw_data["collected_at"]
    #   raw_data["results"] -> lista con un resultado idéntico
    raw_data = {
        "lab_id": lab_id,
        "patient_id": patient_id,
        "lab_name": lab_name,
        "test_type": test_type,
        "value": value,
        "unit": unit,
        "risk_score": risk_score,
        "result_id": result_id,
        "collected_at": collected_at,
        "results": [
            {
                "result_id": result_id,
                "patient_id": patient_id,
                "test_type": test_type,
                "value": value,
                "unit": unit,
                "risk_score": risk_score,
                "lab_name": lab_name,
                "collected_at": collected_at,
            }
        ],
    }

    print("=== SUBIENDO RESULTADO CRUDO A S3 ===")
    print(f"Bucket: {RAW_BUCKET}")
    print(f"Key:    {s3_key}")

    s3.put_object(
        Bucket=RAW_BUCKET,
        Key=s3_key,
        Body=json.dumps(raw_data),
        ContentType="application/json",
    )
    print("✅ Archivo subido a S3.")

    # Mensaje que el worker espera
    message_body = {
        "result_id": result_id,
        "s3_key": s3_key,
    }

    print("\n=== ENVIANDO MENSAJE A SQS (LAB_RESULTS_QUEUE) ===")
    print(f"QueueUrl: {LAB_RESULTS_QUEUE_URL}")
    print(f"Body:     {json.dumps(message_body)}")

    sqs.send_message(
        QueueUrl=LAB_RESULTS_QUEUE_URL,
        MessageBody=json.dumps(message_body),
    )

    print("✅ Mensaje enviado a la cola de resultados.")
    print("\nAhora el worker debería procesar este resultado end-to-end ✨")


if __name__ == "__main__":
    main()

