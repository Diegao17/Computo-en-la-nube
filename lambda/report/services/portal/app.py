from flask import Flask, request, jsonify, redirect
import boto3
import os
from datetime import datetime
import uuid

app = Flask(__name__)

dynamo = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")

LAB_RESULTS_TABLE = os.environ["LAB_RESULTS_TABLE"]
PATIENTS_TABLE = os.environ["PATIENTS_TABLE"]
ACCESS_AUDIT_TABLE = os.environ["ACCESS_AUDIT_TABLE"]
REPORT_LAMBDA_NAME = os.environ["REPORT_LAMBDA_NAME"]

lab_results_table = dynamo.Table(LAB_RESULTS_TABLE)
patients_table = dynamo.Table(PATIENTS_TABLE)
audit_table = dynamo.Table(ACCESS_AUDIT_TABLE)


@app.route("/health")
def health():
    return "ok", 200


@app.route("/results")
def list_results():
    """
    Lista resultados para un paciente.
    Para simplificar, recibimos ?patient_id=P123456
    (Más adelante esto vendría del token de Cognito).
    """
    patient_id = request.args.get("patient_id")
    if not patient_id:
        return jsonify({"error": "patient_id is required"}), 400

    resp = lab_results_table.scan(
        FilterExpression="patient_id = :pid",
        ExpressionAttributeValues={":pid": patient_id},
    )
    results = resp.get("Items", [])

    return jsonify({"patient_id": patient_id, "results": results})


@app.route("/results/<result_id>", methods=["GET", "POST"])
def view_result(result_id):
    """
    GET: muestra un formulario simple (texto) pidiendo reason.
    POST: recibe reason y registra auditoría + devuelve el resultado.
    """
    patient_id = request.args.get("patient_id")
    if not patient_id:
        return jsonify({"error": "patient_id is required"}), 400

    if request.method == "GET":
        return (
            f"""
        <html>
        <body>
        <h1>Justificación de acceso</h1>
        <form method="POST">
          <label>Reason (motivo):</label><br/>
          <input name="reason" placeholder="patient_request / routine / emergency"/><br/><br/>
          <button type="submit">Ver resultado</button>
        </form>
        </body>
        </html>
        """,
            200,
        )

    # POST: procesar motivo y registrar auditoría
    reason = request.form.get("reason", "").strip() or "unspecified"

    audit_table.put_item(
        Item={
            "audit_id": str(uuid.uuid4()),
            "action": "VIEW_RESULT",
            "patient_id": patient_id,
            "result_id": result_id,
            "timestamp": datetime.utcnow().isoformat(),
            "reason": reason,
        }
    )

    # Ahora sí podemos leer el resultado
    resp = lab_results_table.get_item(
        Key={"result_id": result_id, "patient_id": patient_id}
    )
    item = resp.get("Item")
    if not item:
        return jsonify({"error": "result_not_found"}), 404

    return jsonify(item)


@app.route("/results/<result_id>/report")
def download_report(result_id):
    """
    Llama a la Lambda de reportes y redirige al URL firmado.
    """
    patient_id = request.args.get("patient_id")
    if not patient_id:
        return jsonify({"error": "patient_id is required"}), 400

    # Invocamos la lambda como si fuera API Gateway (query params)
    payload = {
        "queryStringParameters": {
            "patient_id": patient_id,
            "result_id": result_id,
        }
    }
    response = lambda_client.invoke(
        FunctionName=REPORT_LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=__import__("json").dumps(payload),
    )
    body = __import__("json").loads(response["Payload"].read())

    if response.get("StatusCode") != 200 or body.get("statusCode", 200) != 200:
        return jsonify({"error": "report_lambda_failed", "details": body}), 500

    data = __import__("json").loads(body["body"])
    url = data.get("download_url")

    return redirect(url, code=302)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)

