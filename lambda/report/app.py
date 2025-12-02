import os
import json
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

REGION_NAME = os.environ.get("REGION_NAME", "us-east-1")

LAB_RESULTS_TABLE = os.environ["LAB_RESULTS_TABLE"]
PATIENTS_TABLE = os.environ["PATIENTS_TABLE"]
REPORT_BUCKET = os.environ["REPORT_BUCKET"]

dynamo = boto3.resource("dynamodb", region_name=REGION_NAME)
lab_results_table = dynamo.Table(LAB_RESULTS_TABLE)
patients_table = dynamo.Table(PATIENTS_TABLE)
s3 = boto3.client("s3", region_name=REGION_NAME)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _generate_fake_pdf_bytes(patient: dict, result: dict) -> bytes:
    """
    Para no meter librerías externas (reportlab, etc.), generamos un "PDF"
    muy simple. Para el proyecto basta con que sea un archivo descargable
    que el navegador trate como PDF.

    En un sistema real, aquí usarías una librería de PDFs.
    """
    lines = [
        "LabSecure Report",
        "================",
        "",
        f"Generated at: {_now_iso()}",
        "",
        f"Patient: {patient.get('first_name', '')} {patient.get('last_name', '')}",
        f"Patient ID: {patient.get('patient_id')}",
        "",
        f"Result ID: {result.get('result_id')}",
        f"Test Type: {result.get('test_type')}",
        f"Test Date: {result.get('test_date')}",
        f"Status: {result.get('status')}",
        f"Has abnormal: {result.get('has_abnormal')}",
        "",
        "Detailed Results:",
        "",
    ]

    for r in result.get("results", []):
        line = (
            f"- {r.get('test_code')} | {r.get('test_name')} | "
            f"{r.get('value')} {r.get('unit')} "
            f"(ref: {r.get('reference_range')}) "
            f"{'(ABNORMAL)' if r.get('is_abnormal') else ''}"
        )
        lines.append(line)

    content = "\n".join(lines)
    # Lo codificamos como bytes; el navegador lo descargará como PDF aunque no sea un PDF real.
    return content.encode("utf-8")


def lambda_handler(event, context):
    """
    Este handler espera:
      - Ser invocado por API Gateway o por otra Lambda (portal)
      - Recibe patient_id y result_id en queryStringParameters:
        {
          "queryStringParameters": {
            "patient_id": "...",
            "result_id": "..."
          }
        }

    Devuelve:
      {
        "statusCode": 200,
        "body": "{\"download_url\": \"https://...\"}"
      }
    """
    params = (event.get("queryStringParameters") or {}) if isinstance(event, dict) else {}

    patient_id = params.get("patient_id")
    result_id = params.get("result_id")

    if not patient_id or not result_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "patient_id and result_id are required"}),
        }

    # Obtener paciente
    resp_p = patients_table.get_item(Key={"patient_id": patient_id})
    patient = resp_p.get("Item")
    if not patient:
        return {
            "statusCode": 404,
            "body": json.dumps({"error": "patient_not_found"}),
        }

    # Obtener resultado
    resp_r = lab_results_table.get_item(
        Key={"result_id": result_id, "patient_id": patient_id}
    )
    result = resp_r.get("Item")
    if not result:
        return {
            "statusCode": 404,
            "body": json.dumps({"error": "result_not_found"}),
        }

    # Generar contenido "PDF"
    pdf_bytes = _generate_fake_pdf_bytes(patient, result)

    # Guardar en S3, prefijo por paciente
    key = f"reports/{patient_id}/{result_id}.pdf"

    s3.put_object(
        Bucket=REPORT_BUCKET,
        Key=key,
        Body=pdf_bytes,
        ContentType="application/pdf",
        ServerSideEncryption="AES256",
        Metadata={
            "generated_at": _now_iso(),
            "patient_id": patient_id,
            "result_id": result_id,
        },
    )

    # Generar URL firmada (1 hora)
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": REPORT_BUCKET, "Key": key},
            ExpiresIn=3600,
        )
    except ClientError as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "presign_failed", "details": str(e)}),
        }

    return {
        "statusCode": 200,
        "body": json.dumps({"download_url": url}),
    }
