import os
import json
import time
import logging
from typing import Optional
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from services.processor.process_utils import process_lab_result

def _convert_floats_to_decimal(obj):
    """
    Convierte todos los float de un dict/list anidado a Decimal,
    porque DynamoDB no acepta floats de Python nativos.
    """
    if isinstance(obj, dict):
        return {k: _convert_floats_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_floats_to_decimal(v) for v in obj]
    if isinstance(obj, float):
        # Usar str() evita problemas de representación binaria tipo 0.3000000004
        return Decimal(str(obj))
    return obj


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [worker] %(message)s",
)

REGION_NAME = os.environ.get("REGION_NAME", "us-east-1")

LAB_RESULTS_QUEUE_URL = os.environ["LAB_RESULTS_QUEUE_URL"]
NOTIFY_QUEUE_URL = os.environ["NOTIFY_QUEUE_URL"]
RAW_BUCKET = os.environ["RAW_BUCKET"]
LAB_RESULTS_TABLE = os.environ["LAB_RESULTS_TABLE"]
ACCESS_AUDIT_TABLE: Optional[str] = os.environ.get("ACCESS_AUDIT_TABLE")

sqs = boto3.client("sqs", region_name=REGION_NAME)
s3 = boto3.client("s3", region_name=REGION_NAME)
dynamo = boto3.resource("dynamodb", region_name=REGION_NAME)

lab_results_table = dynamo.Table(LAB_RESULTS_TABLE)
audit_table = dynamo.Table(ACCESS_AUDIT_TABLE) if ACCESS_AUDIT_TABLE else None


def put_audit_event(action: str, result_id: str, patient_id: str, details: str = ""):
    """
    Registra en la tabla de auditoría que el worker procesó algo.
    Si no hay tabla configurada, no hace nada (escenario dev).
    """
    if not audit_table:
        return

    import uuid
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    audit_id = str(uuid.uuid4())

    item = {
        "audit_id": audit_id,
        "timestamp": now,
        "action": action,  # e.g. WORKER_PROCESSED, WORKER_FAILED
        "actor_id": "processor_worker",
        "patient_id": patient_id,
        "result_id": result_id,
        "details": details,
        "source": "worker_ec2",
    }

    audit_table.put_item(Item=item)


def process_message(message: dict) -> None:
    """
    Procesa un mensaje de la cola lab_results_queue:
      1. Lee el body (result_id, s3_key, patient_id).
      2. Descarga JSON raw de S3.
      3. Normaliza usando process_lab_result.
      4. Guarda en DynamoDB lab_results.
      5. Envía notificación a notify_queue.
    """
    body_str = message.get("Body", "{}")
    body = json.loads(body_str)

    result_id = body["result_id"]
    s3_key = body["s3_key"]
    patient_id = body["patient_id"]

    logging.info(f"Procesando mensaje result_id={result_id} patient_id={patient_id}")

    # 1) Descargamos el JSON raw de S3
    try:
        obj = s3.get_object(Bucket=RAW_BUCKET, Key=s3_key)
        raw_str = obj["Body"].read().decode("utf-8")
        raw_data = json.loads(raw_str)
    except ClientError as e:
        logging.error(f"Error al leer de S3 {RAW_BUCKET}/{s3_key}: {e}")
        put_audit_event(
            "WORKER_FAILED",
            result_id=result_id,
            patient_id=patient_id,
            details=f"S3 read failed: {e}",
        )
        # NO borramos el mensaje para que DLQ lo capture tras varios intentos
        raise

    # 2) Normalizar usando process_lab_result (usa lógica del proyecto)
    try:
        item = process_lab_result(raw_data, result_id=result_id)
    except Exception as e:
        logging.error(f"Error en process_lab_result para {result_id}: {e}")
        put_audit_event(
            "WORKER_FAILED",
            result_id=result_id,
            patient_id=patient_id,
            details=f"process_lab_result failed: {e}",
        )
        raise

    # 3) Guardar en DynamoDB
    try:
        item = _convert_floats_to_decimal(item)
        lab_results_table.put_item(Item=item)

    except ClientError as e:
        logging.error(f"Error al guardar en DynamoDB lab_results: {e}")
        put_audit_event(
            "WORKER_FAILED",
            result_id=result_id,
            patient_id=patient_id,
            details=f"DynamoDB put_item failed: {e}",
        )
        raise

    # 4) Enviar mensaje a cola de notificación (para Lambda notify)
    notify_msg = {
        "result_id": result_id,
        "patient_id": patient_id,
        "has_abnormal": item.get("has_abnormal", False),
        "test_type": item.get("test_type"),
        "test_date": item.get("test_date"),
    }

    try:
        sqs.send_message(
            QueueUrl=NOTIFY_QUEUE_URL,
            MessageBody=json.dumps(notify_msg),
        )
    except ClientError as e:
        logging.error(f"Error al enviar mensaje a NOTIFY_QUEUE: {e}")
        put_audit_event(
            "WORKER_FAILED",
            result_id=result_id,
            patient_id=patient_id,
            details=f"SQS send to notify failed: {e}",
        )
        # No es crítico para el status, pero lo dejamos registrado
        # No hacemos raise aquí para no reintentar todo el mensaje.
    else:
        logging.info(
            f"Notificación encolada correctamente para result_id={result_id}, queue={NOTIFY_QUEUE_URL}"
        )

    # 5) Auditoría de éxito
    put_audit_event(
        "WORKER_PROCESSED",
        result_id=result_id,
        patient_id=patient_id,
        details="Resultado procesado y almacenado en lab_results",
    )

    logging.info(f"Procesamiento completado para result_id={result_id}")


def main_loop():
    logging.info("Iniciando worker LabSecure (cola de resultados)...")
    logging.info(f"REGION_NAME={REGION_NAME}")
    logging.info(f"LAB_RESULTS_QUEUE_URL={LAB_RESULTS_QUEUE_URL}")
    logging.info(f"NOTIFY_QUEUE_URL={NOTIFY_QUEUE_URL}")
    logging.info(f"RAW_BUCKET={RAW_BUCKET}")
    logging.info(f"LAB_RESULTS_TABLE={LAB_RESULTS_TABLE}")
    logging.info(f"ACCESS_AUDIT_TABLE={ACCESS_AUDIT_TABLE}")

    while True:
        try:
            resp = sqs.receive_message(
                QueueUrl=LAB_RESULTS_QUEUE_URL,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=20,   # long polling
                VisibilityTimeout=60,
            )
        except ClientError as e:
            logging.error(f"Error recibiendo mensajes de SQS: {e}")
            time.sleep(5)
            continue

        messages = resp.get("Messages", [])

        if not messages:
            logging.info("No hay mensajes en la cola, esperando...")
            continue

        for msg in messages:
            receipt_handle = msg["ReceiptHandle"]

            try:
                process_message(msg)
            except Exception as e:
                logging.error(f"Error procesando mensaje, se mantendrá en la cola: {e}")
                # NO borramos el mensaje → SQS + DLQ se encargan
                continue

            # Si todo fue bien, borramos el mensaje
            try:
                sqs.delete_message(
                    QueueUrl=LAB_RESULTS_QUEUE_URL,
                    ReceiptHandle=receipt_handle,
                )
            except ClientError as e:
                logging.error(f"Error al borrar mensaje de la cola: {e}")

        # pequeña pausa entre lotes
        time.sleep(1)


if __name__ == "__main__":
    main_loop()
