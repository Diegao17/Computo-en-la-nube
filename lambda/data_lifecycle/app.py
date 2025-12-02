import os
import json
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Attr

REGION_NAME = os.environ.get("REGION_NAME", "us-east-1")

LAB_RESULTS_TABLE = os.environ["LAB_RESULTS_TABLE"]
ACCESS_AUDIT_TABLE = os.environ["ACCESS_AUDIT_TABLE"]

dynamo = boto3.resource("dynamodb", region_name=REGION_NAME)
lab_results_table = dynamo.Table(LAB_RESULTS_TABLE)
access_audit_table = dynamo.Table(ACCESS_AUDIT_TABLE)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _put_audit_delete(result_id: str, patient_id: str, mode: str, details: str = ""):
    """
    Registra en access_audit que se hizo una acción de lifecycle
    (anonimización / marcado / etc.).
    """
    item = {
        "audit_id": f"lifecycle-{result_id}",
        "timestamp": _now_iso(),
        "action": f"DATA_{mode}_DELETE",
        "actor_id": "system_lifecycle",
        "patient_id": patient_id,
        "result_id": result_id,
        "details": details,
        "source": "lifecycle_lambda",
    }
    access_audit_table.put_item(Item=item)


def lambda_handler(event, context):
    """
    Ejecutado periódicamente por EventBridge (p.ej. diario).
    Maneja:
      - Solicitudes GDPR (gdpr_delete_requested = true)
      - Respeto a HIPAA con ttl_epoch (7 años) en DynamoDB
    Estrategia:
      - Si jurisdiction == "EU" y gdpr_delete_requested:
          -> anonimizar patient_id y notes
      - Si jurisdiction == "US" y gdpr_delete_requested:
          -> dejar que TTL borre físicamente, pero marcar gdpr_delete_requested = false
             y auditar la intención.
    """
    # Escanear items con gdpr_delete_requested = true
    resp = lab_results_table.scan(
        FilterExpression=Attr("gdpr_delete_requested").eq(True)
    )

    items = resp.get("Items", [])
    processed = 0

    for item in items:
        result_id = item["result_id"]
        patient_id = item["patient_id"]
        jurisdiction = item.get("jurisdiction", "US")
        ttl_epoch = item.get("ttl_epoch")

        if jurisdiction == "EU":
            # Anonimizar datos identificables pero dejar datos clínicos para estadísticas
            lab_results_table.update_item(
                Key={"result_id": result_id, "patient_id": patient_id},
                UpdateExpression=(
                    "SET patient_id = :anon, notes = :empty, "
                    "gdpr_delete_requested = :false"
                ),
                ExpressionAttributeValues={
                    ":anon": "ANONYMIZED",
                    ":empty": "",
                    ":false": False,
                },
            )
            _put_audit_delete(
                result_id,
                patient_id,
                mode="GDPR",
                details="Anonimización por solicitud GDPR (jurisdiction=EU)",
            )
        else:
            # US / HIPAA: la ley exige retención (7 años), así que no borramos duro
            # antes de tiempo. TTL se encargará de eliminar tras la retención.
            # Aquí solo marcamos la petición como atendida.
            lab_results_table.update_item(
                Key={"result_id": result_id, "patient_id": patient_id},
                UpdateExpression="SET gdpr_delete_requested = :false",
                ExpressionAttributeValues={
                    ":false": False,
                },
            )
            _put_audit_delete(
                result_id,
                patient_id,
                mode="HIPAA",
                details=f"Solicitud GDPR recibida pero sujeta a retención HIPAA, ttl_epoch={ttl_epoch}",
            )

        processed += 1

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "processed_items": processed,
                "message": "Lifecycle run complete",
            }
        ),
    }

