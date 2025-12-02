import json
import uuid
import os
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

s3 = boto3.client("s3")
sqs = boto3.client("sqs")
dynamo = boto3.resource("dynamodb")

RAW_BUCKET = os.environ["RAW_BUCKET"]
LAB_RESULTS_QUEUE_URL = os.environ["LAB_RESULTS_QUEUE_URL"]
LAB_RESULTS_TABLE = os.environ.get("LAB_RESULTS_TABLE")
ACCESS_AUDIT_TABLE = os.environ.get("ACCESS_AUDIT_TABLE")


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def validate_payload(body: dict) -> tuple[bool, str | None]:
    required = ["patient_id", "lab_id", "lab_name", "test_type", "test_date", "results"]
    missing = [f for f in required if f not in body]
    if missing:
        return False, f"Missing fields: {', '.join(missing)}"

    if not isinstance(body.get("results"), list) or not body["results"]:
        return False, "Field 'results' must be a non-empty list"

    return True, None


def _put_audit_event(
    action: str,
    actor_id: str,
    source_ip: str | None = None,
    patient_id: str | None = None,
    result_id: str | None = None,
    justification: str | None = None,
    break_glass: bool = False,
) -> None:
    """
    Inserta un registro en la tabla access_audit (si está configurada).
    Si no hay tabla, simplemente no hace nada.
    """
    if not ACCESS_AUDIT_TABLE:
        return

    table = dynamo.Table(ACCESS_AUDIT_TABLE)

    now = datetime.now(timezone.utc)
    iso_now = now.isoformat()
    audit_id = str(uuid.uuid4())

    item = {
        "audit_id": audit_id,
        "timestamp": iso_now,
        "action": action,         # e.g. "INGEST_CREATE", "RESULT_STATUS_READ"
        "actor_id": actor_id,     # e.g. "external_lab:LAB001"
        "source_ip": source_ip or "unknown",
        "patient_id": patient_id,
        "result_id": result_id,
        "justification": justification,
        "break_glass": break_glass,
    }

    # quitar campos None
    item = {k: v for k, v in item.items() if v is not None}

    table.put_item(Item=item)


def handle_health(event, context):
    source_ip = _get_source_ip(event)
    _put_audit_event(
        action="INGEST_HEALTH_CHECK",
        actor_id="system",
        source_ip=source_ip,
    )
    return _response(200, {"status": "ok", "service": "ingest"})


def handle_status(event, context, path: str):
    if not LAB_RESULTS_TABLE:
        return _response(500, {"error": "LAB_RESULTS_TABLE not configured"})

    # path esperado: /api/v1/status/{result_id}
    result_id = path.rsplit("/", 1)[-1]

    table = dynamo.Table(LAB_RESULTS_TABLE)
    resp = table.query(KeyConditionExpression=Key("result_id").eq(result_id))
    items = resp.get("Items", [])

    source_ip = _get_source_ip(event)
    _put_audit_event(
        action="RESULT_STATUS_READ",
        actor_id="external_lab_or_monitor",
        source_ip=source_ip,
        result_id=result_id,
    )

    if not items:
        return _response(200, {"result_id": result_id, "status": "PENDING"})

    item = items[0]
    return _response(
        200,
        {
            "result_id": result_id,
            "status": item.get("status", "UNKNOWN"),
            "patient_id": item.get("patient_id"),
            "test_type": item.get("test_type"),
            "test_date": item.get("test_date"),
            "has_abnormal": item.get("has_abnormal", False),
        },
    )


def handle_ingest(event, context, path: str):
    try:
        raw_body = event.get("body") or "{}"
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        return _response(400, {"error": "invalid_json"})

    ok, error = validate_payload(body)
    if not ok:
        return _response(400, {"error": error})

    # result_id global para todo el flujo
    result_id = str(uuid.uuid4())
    body["result_id"] = result_id

    s3_key = f"raw/{result_id}.json"

    # guardar raw en S3 (cumplimiento / trazabilidad)
    s3.put_object(
        Bucket=RAW_BUCKET,
        Key=s3_key,
        Body=json.dumps(body).encode("utf-8"),
        ServerSideEncryption="AES256",
        Metadata={"received_at": datetime.now(timezone.utc).isoformat()},
    )

    # encolar para procesamiento
    msg = {
        "result_id": result_id,
        "s3_key": s3_key,
        "patient_id": body["patient_id"],
    }
    sqs.send_message(
        QueueUrl=LAB_RESULTS_QUEUE_URL,
        MessageBody=json.dumps(msg),
    )

    # auditoría
    source_ip = _get_source_ip(event)
    _put_audit_event(
        action="INGEST_CREATE",
        actor_id=f"external_lab:{body.get('lab_id')}",
        source_ip=source_ip,
        patient_id=body["patient_id"],
        result_id=result_id,
        justification="system_ingest",
    )

    return _response(202, {"result_id": result_id, "status": "QUEUED"})


def _get_method_and_path(event: dict) -> tuple[str, str]:
    """
    Soporta:
    - API Gateway REST (v1):  event["httpMethod"], event["path"]
    - HTTP API (v2):          event["requestContext"]["http"]["method"], event["rawPath"]
    """
    # v1
    method = event.get("httpMethod")
    path = event.get("path")

    # v2
    if not method:
        method = (
            event.get("requestContext", {})
            .get("http", {})
            .get("method")
        )
    if not path:
        path = event.get("rawPath") or (
            event.get("requestContext", {})
            .get("http", {})
            .get("path")
        )

    # fallback
    method = method or ""
    path = path or ""

    return method, path


def _get_source_ip(event: dict) -> str | None:
    # v1
    ip = (
        event.get("requestContext", {})
        .get("identity", {})
        .get("sourceIp")
    )
    if ip:
        return ip

    # v2
    ip = (
        event.get("requestContext", {})
        .get("http", {})
        .get("sourceIp")
    )
    return ip


def lambda_handler(event, context):
    """
    Envolvemos todo en try/except para devolver detalles del error
    en vez de solo "Internal Server Error".
    """
    try:
        method, path = _get_method_and_path(event)
        path = path or ""

        # GET /api/v1/health
        if method == "GET" and path.endswith("/api/v1/health"):
            return handle_health(event, context)

        # GET /api/v1/status/{result_id}
        if method == "GET" and "/api/v1/status/" in path:
            return handle_status(event, context, path)

        # POST /api/v1/ingest
        if method == "POST" and path.endswith("/api/v1/ingest"):
            return handle_ingest(event, context, path)

        return _response(
            404,
            {
                "error": "not_found",
                "path": path,
                "method": method,
            },
        )

    except Exception as e:
        # Log en CloudWatch y respuesta visible en el cliente
        print("ERROR in lambda_handler:", repr(e))
        return _response(
            500,
            {
                "error": "internal_error",
                "details": str(e),
            },
        )

