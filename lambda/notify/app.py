import json
import os
from datetime import datetime, timezone
import uuid

import boto3

REGION_NAME = os.environ.get("REGION_NAME", "us-east-1")

PATIENTS_TABLE = os.environ["PATIENTS_TABLE"]
ACCESS_AUDIT_TABLE = os.environ["ACCESS_AUDIT_TABLE"]
NOTIFY_TOPIC_ARN = os.environ["NOTIFY_TOPIC_ARN"]

dynamo = boto3.resource("dynamodb", region_name=REGION_NAME)
patients_table = dynamo.Table(PATIENTS_TABLE)
access_audit_table = dynamo.Table(ACCESS_AUDIT_TABLE)
sns = boto3.client("sns", region_name=REGION_NAME)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _put_audit_event(
    action: str,
    patient_id: str,
    result_id: str,
    status: str,
    details: str | None = None,
):
    item = {
        "audit_id": str(uuid.uuid4()),
        "timestamp": _now_iso(),
        "action": action,              # e.g. NOTIFICATION_SENT / NOTIFICATION_FAILED
        "actor_id": "system_notify",
        "patient_id": patient_id,
        "result_id": result_id,
        "notification_status": status,
        "details": details,
        "source": "notification_lambda",
    }
    item = {k: v for k, v in item.items() if v is not None}
    access_audit_table.put_item(Item=item)


def lambda_handler(event, context):
    """
    Event source: SQS notify_queue
    Records[i].body:
      {
        "result_id": "...",
        "patient_id": "...",
        "test_type": "...",
        "test_date": "...",
        "has_abnormal": true/false
      }
    """
    for record in event.get("Records", []):
        body_str = record.get("body", "{}")
        try:
            msg = json.loads(body_str)
        except json.JSONDecodeError:
            continue

        result_id = msg.get("result_id")
        patient_id = msg.get("patient_id")
        test_type = msg.get("test_type")
        test_date = msg.get("test_date")
        has_abnormal = msg.get("has_abnormal", False)

        if not result_id or not patient_id:
            continue

        # Obtener datos del paciente
        resp = patients_table.get_item(Key={"patient_id": patient_id})
        patient = resp.get("Item")
        if not patient:
            _put_audit_event(
                action="NOTIFICATION_FAILED",
                patient_id=patient_id,
                result_id=result_id,
                status="NO_PATIENT_RECORD",
                details="Paciente no encontrado en tabla patients",
            )
            continue

        email = patient.get("email")
        phone = patient.get("phone")

        subject = "Tus resultados de laboratorio están disponibles"
        status_line = "Uno o más valores fuera de rango." if has_abnormal else "Todos los valores dentro del rango."

        message = (
            f"Hola {patient.get('first_name', '')},\n\n"
            f"Tu resultado de laboratorio (ID: {result_id}) para el estudio '{test_type}' "
            f"del {test_date} ya está disponible en el portal LabSecure.\n\n"
            f"Resumen: {status_line}\n\n"
            f"Inicia sesión en el portal para revisarlo.\n\n"
            f"Este mensaje es automático, por favor no respondas."
        )

        try:
            sns.publish(
                TopicArn=NOTIFY_TOPIC_ARN,
                Subject=subject,
                Message=message,
            )
            _put_audit_event(
                action="NOTIFICATION_SENT",
                patient_id=patient_id,
                result_id=result_id,
                status="SUCCESS",
                details=f"Notification sent to SNS topic for email {email} / phone {phone}",
            )
        except Exception as e:
            _put_audit_event(
                action="NOTIFICATION_FAILED",
                patient_id=patient_id,
                result_id=result_id,
                status="ERROR_SNS",
                details=str(e),
            )

    return {
        "statusCode": 200,
        "body": json.dumps({"status": "ok"}),
    }
