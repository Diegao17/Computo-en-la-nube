import os
import json
from datetime import datetime, timezone
import uuid
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key, Attr
from flask import (
    Flask,
    request,
    jsonify,
    render_template_string,
    redirect,
    url_for,
    session,
)

app = Flask(__name__)

REGION_NAME = os.environ.get("REGION_NAME", "us-east-1")
LAB_RESULTS_TABLE = os.environ["LAB_RESULTS_TABLE"]
PATIENTS_TABLE = os.environ["PATIENTS_TABLE"]
ACCESS_AUDIT_TABLE = os.environ["ACCESS_AUDIT_TABLE"]
REPORT_LAMBDA_NAME = os.environ["REPORT_LAMBDA_NAME"]

dynamo = boto3.resource("dynamodb", region_name=REGION_NAME)
lab_results_table = dynamo.Table(LAB_RESULTS_TABLE)
patients_table = dynamo.Table(PATIENTS_TABLE)
access_audit_table = dynamo.Table(ACCESS_AUDIT_TABLE)
lambda_client = boto3.client("lambda", region_name=REGION_NAME)


# ===================== UTILIDADES =====================


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _put_audit_event(
    action: str,
    actor_id: str,
    patient_id: str | None = None,
    result_id: str | None = None,
    justification: str | None = None,
    break_glass: bool = False,
):
    """
    Registra un evento en la tabla access_audit.
    Se usa para:
      - RESULT_VIEW
      - REPORT_DOWNLOAD
      - PORTAL_HEALTH
      - PORTAL_LOGIN
    """
    item = {
        "audit_id": str(uuid.uuid4()),
        "timestamp": _now_iso(),
        "action": action,
        "actor_id": actor_id,
        "patient_id": patient_id,
        "result_id": result_id,
        "justification": justification,
        "break_glass": break_glass,
        "source": "portal",
    }
    # Quitar None
    item = {k: v for k, v in item.items() if v is not None}
    access_audit_table.put_item(Item=item)


def _get_patient(patient_id: str):
    resp = patients_table.get_item(Key={"patient_id": patient_id})
    return resp.get("Item")


# ===================== RUTAS =====================
@app.route("/admin/audit")
def admin_audit():
    """
    Security Dashboard básico:
    - Muestra los últimos eventos de auditoría de la tabla ACCESS_AUDIT_TABLE
    """
    table = dynamo.Table(ACCESS_AUDIT_TABLE)

    # Traemos hasta 100 eventos (para no cargar todo)
    resp = table.scan(Limit=100)
    events = resp.get("Items", [])

    # Plantilla HTML sencilla usando render_template_string para no crear archivos extra
    template = """
    <!doctype html>
    <html lang="es">
    <head>
        <meta charset="utf-8">
        <title>LabSecure - Security Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            h1 { margin-bottom: 10px; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ccc; padding: 6px 8px; font-size: 14px; }
            th { background-color: #f5f5f5; text-align: left; }
            tr:nth-child(even) { background-color: #fafafa; }
            .badge { padding: 2px 6px; border-radius: 4px; font-size: 12px; }
            .badge-break-glass { background-color: #b71c1c; color: #fff; }
            .badge-normal { background-color: #2e7d32; color: #fff; }
            .small { font-size: 12px; color: #555; }
        </style>
    </head>
    <body>
        <h1>Security Dashboard - Audit Trail</h1>
        <p class="small">
            Mostrando hasta 100 eventos recientes de la tabla de auditoría:
            <strong>{{ access_audit_table }}</strong>
        </p>
        <table>
            <thead>
                <tr>
                    <th>Timestamp</th>
                    <th>Action</th>
                    <th>Actor</th>
                    <th>Patient</th>
                    <th>Result</th>
                    <th>Break Glass</th>
                    <th>Justification</th>
                    <th>Source IP</th>
                </tr>
            </thead>
            <tbody>
            {% for e in events %}
                <tr>
                    <td>{{ e.get("timestamp", "") }}</td>
                    <td>{{ e.get("action", "") }}</td>
                    <td>{{ e.get("actor_id", "") }}</td>
                    <td>{{ e.get("patient_id", "") }}</td>
                    <td>{{ e.get("result_id", "") }}</td>
                    <td>
                        {% if e.get("break_glass", False) %}
                            <span class="badge badge-break-glass">YES</span>
                        {% else %}
                            <span class="badge badge-normal">NO</span>
                        {% endif %}
                    </td>
                    <td>{{ e.get("justification", "") }}</td>
                    <td>{{ e.get("source_ip", "") }}</td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
    </body>
    </html>
    """

    return render_template_string(template, events=events, access_audit_table=ACCESS_AUDIT_TABLE)

@app.route("/admin/compliance-report")
def admin_compliance_report():
    """
    Compliance Report:
    - Resumen de eventos de auditoría para evidenciar cumplimiento (HIPAA/GDPR)
    """
    table = dynamo.Table(ACCESS_AUDIT_TABLE)
    resp = table.scan(Limit=500)  # Traemos hasta 500 eventos para el reporte
    events = resp.get("Items", [])

    total_events = len(events)
    by_action = {}
    by_actor = {}
    break_glass_count = 0

    for e in events:
        action = e.get("action", "UNKNOWN")
        actor = e.get("actor_id", "UNKNOWN")
        if e.get("break_glass", False):
            break_glass_count += 1

        by_action[action] = by_action.get(action, 0) + 1
        by_actor[actor] = by_actor.get(actor, 0) + 1

    template = """
    <!doctype html>
    <html lang="es">
    <head>
        <meta charset="utf-8">
        <title>LabSecure - Compliance Report</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            h1 { margin-bottom: 10px; }
            h2 { margin-top: 24px; }
            table { border-collapse: collapse; width: 60%; margin-bottom: 20px; }
            th, td { border: 1px solid #ccc; padding: 6px 8px; font-size: 14px; }
            th { background-color: #f5f5f5; text-align: left; }
            .small { font-size: 12px; color: #555; }
        </style>
    </head>
    <body>
        <h1>Compliance Report - LabSecure</h1>
        <p class="small">
            Fuente: tabla de auditoría <strong>{{ access_audit_table }}</strong><br>
            Este reporte está pensado como evidencia de cumplimiento (HIPAA / GDPR)
            mostrando patrones de acceso, uso de "break glass" y trazabilidad completa.
        </p>

        <h2>Resumen general</h2>
        <table>
            <tr><th>Total de eventos registrados</th><td>{{ total_events }}</td></tr>
            <tr><th>Accesos con "break glass"</th><td>{{ break_glass_count }}</td></tr>
        </table>

        <h2>Eventos por tipo de acción</h2>
        <table>
            <thead>
                <tr><th>Action</th><th>Count</th></tr>
            </thead>
            <tbody>
            {% for action, count in by_action.items() %}
                <tr>
                    <td>{{ action }}</td>
                    <td>{{ count }}</td>
                </tr>
            {% endfor %}
            </tbody>
        </table>

        <h2>Eventos por usuario (actor)</h2>
        <table>
            <thead>
                <tr><th>Actor</th><th>Count</th></tr>
            </thead>
            <tbody>
            {% for actor, count in by_actor.items() %}
                <tr>
                    <td>{{ actor }}</td>
                    <td>{{ count }}</td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
    </body>
    </html>
    """

    return render_template_string(
        template,
        access_audit_table=ACCESS_AUDIT_TABLE,
        total_events=total_events,
        break_glass_count=break_glass_count,
        by_action=by_action,
        by_actor=by_actor,
    )


@app.route("/health")
def health():
    _put_audit_event(
        action="PORTAL_HEALTH",
        actor_id="system_healthcheck",
    )
    return jsonify({"status": "ok", "service": "portal"}), 200


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Para simplificar:
      - GET: muestra formulario de login con patient_id.
      - POST: recibe patient_id y redirige al dashboard.
    En producción, esto sería Cognito Hosted UI + tokens.
    """
    if request.method == "POST":
        patient_id = request.form.get("patient_id")
        if not patient_id:
            return "Missing patient_id", 400

        _put_audit_event(
            action="PORTAL_LOGIN",
            actor_id=f"portal_user:{patient_id}",
            patient_id=patient_id,
            justification="login",
        )
        return redirect(url_for("dashboard", patient_id=patient_id))

    return """
    <h1>LabSecure Portal - Login</h1>
    <form method="post">
      <label>Patient ID:</label>
      <input name="patient_id" />
      <button type="submit">Entrar</button>
    </form>
    """, 200


@app.route("/dashboard")
def dashboard():
    patient_id = request.args.get("patient_id")
    if not patient_id:
        return redirect(url_for("login"))

    patient = _get_patient(patient_id)
    if not patient:
        return f"Patient {patient_id} not found", 404

    # NOTA: la tabla tiene PK (result_id, patient_id).
    # No tenemos GSI por patient_id, así que usamos scan + filtro para demo.
    resp = lab_results_table.scan(
        FilterExpression=Attr("patient_id").eq(patient_id)
    )
    results = resp.get("Items", [])

    template = """
    <h1>LabSecure - Dashboard</h1>
    <p>Paciente: {{ patient.first_name }} {{ patient.last_name }} ({{ patient.patient_id }})</p>

    <h2>Resultados</h2>
    {% if not results %}
      <p>No hay resultados disponibles.</p>
    {% else %}
      <table border="1" cellpadding="4">
        <tr>
          <th>Result ID</th>
          <th>Tipo</th>
          <th>Fecha</th>
          <th>Estado</th>
          <th>Anomalías</th>
          <th>Acciones</th>
        </tr>
        {% for r in results %}
          <tr>
            <td>{{ r.result_id }}</td>
            <td>{{ r.test_type }}</td>
            <td>{{ r.test_date }}</td>
            <td>{{ r.status }}</td>
            <td>{% if r.has_abnormal %}<b style="color:red;">Sí</b>{% else %}No{% endif %}</td>
            <td>
              <a href="{{ url_for('result_detail', result_id=r.result_id, patient_id=patient.patient_id) }}">Ver</a>
            </td>
          </tr>
        {% endfor %}
      </table>
    {% endif %}
    """
    return render_template_string(template, patient=patient, results=results)


@app.route("/results/<result_id>", methods=["GET", "POST"])
def result_detail(result_id):
    """
    Escenario F:
      - El usuario debe justificar el acceso (reason).
      - Puede marcar break_glass en caso de emergencia.
      - Solo después se muestra el resultado.
    """
    patient_id = request.args.get("patient_id")
    if not patient_id:
        return redirect(url_for("login"))

    patient = _get_patient(patient_id)
    if not patient:
        return f"Patient {patient_id} not found", 404

    if request.method == "GET":
        # Mostrar formulario de justificación
        form_html = """
        <h1>Acceso a resultado {{ result_id }}</h1>
        <p>Paciente: {{ patient.first_name }} {{ patient.last_name }} ({{ patient.patient_id }})</p>

        <h2>Justificación de acceso</h2>
        <form method="post">
          <label>Reason:</label><br />
          <textarea name="reason" rows="4" cols="50" required></textarea><br /><br />
          <label>
            <input type="checkbox" name="break_glass" value="true" />
            Break glass (emergencia)
          </label><br /><br />
          <button type="submit">Ver resultado</button>
        </form>
        """
        return render_template_string(form_html, result_id=result_id, patient=patient)

    # POST: ya tenemos reason / break_glass
    reason = request.form.get("reason", "").strip()
    break_glass = request.form.get("break_glass") == "true"

    if not reason:
        return "Justification (reason) is required", 400

    # Obtener resultado de DynamoDB
    resp = lab_results_table.get_item(
        Key={"result_id": result_id, "patient_id": patient_id}
    )
    item = resp.get("Item")
    if not item:
        return "Result not found", 404

    # Registrar auditoría
    _put_audit_event(
        action="RESULT_VIEW",
        actor_id=f"portal_user:{patient_id}",
        patient_id=patient_id,
        result_id=result_id,
        justification=reason,
        break_glass=break_glass,
    )

    html = """
    <h1>Resultado {{ result_id }}</h1>
    <p>Paciente: {{ patient.first_name }} {{ patient.last_name }} ({{ patient.patient_id }})</p>
    <p>Test: {{ item.test_type }} ({{ item.test_date }})</p>
    <p>Status: {{ item.status }}</p>
    <p>Notas: {{ item.notes }}</p>
    <p>Anomalías: {% if item.has_abnormal %}<b style="color:red;">Sí</b>{% else %}No{% endif %}</p>

    <h2>Resultados detallados</h2>
    <table border="1" cellpadding="4">
      <tr>
        <th>Código</th>
        <th>Nombre</th>
        <th>Valor</th>
        <th>Unidad</th>
        <th>Rango ref.</th>
        <th>Abnormal</th>
      </tr>
      {% for r in item.results %}
        <tr>
          <td>{{ r.test_code }}</td>
          <td>{{ r.test_name }}</td>
          <td>{{ r.value }}</td>
          <td>{{ r.unit }}</td>
          <td>{{ r.reference_range }}</td>
          <td>{% if r.is_abnormal %}<b style="color:red;">Sí</b>{% else %}No{% endif %}</td>
        </tr>
      {% endfor %}
    </table>

    <h3>Reporte PDF</h3>
    <form method="post" action="{{ url_for('download_report', result_id=result_id, patient_id=patient.patient_id) }}">
      <input type="hidden" name="reason" value="{{ reason }}" />
      <input type="hidden" name="break_glass" value="{{ 'true' if break_glass else 'false' }}" />
      <button type="submit">Generar y descargar PDF</button>
    </form>
    """
    return render_template_string(
        html,
        result_id=result_id,
        patient=patient,
        item=item,
        reason=reason,
        break_glass=break_glass,
    )


@app.route("/report/<result_id>", methods=["POST"])
def download_report(result_id):
    patient_id = request.args.get("patient_id")
    if not patient_id:
        return redirect(url_for("login"))

    reason = request.form.get("reason", "").strip()
    break_glass = request.form.get("break_glass") == "true"

    if not reason:
        return "Justification (reason) is required", 400

    # Invocar Lambda de reportes (report_lambda)
    payload = {
        "queryStringParameters": {
            "patient_id": patient_id,
            "result_id": result_id,
        }
    }

    resp = lambda_client.invoke(
        FunctionName=REPORT_LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode("utf-8"),
    )

    raw_body = resp["Payload"].read().decode("utf-8") or "{}"
    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        body = {}

    # Se espera que la Lambda de report devuelva algo tipo:
    # { "statusCode": 200, "body": "{\"download_url\": \"...\"}" }
    if isinstance(body, dict) and "body" in body:
        try:
            inner = json.loads(body["body"])
        except Exception:
            inner = {}
    else:
        inner = body

    download_url = inner.get("download_url")

    # Auditoría de descarga
    _put_audit_event(
        action="REPORT_DOWNLOAD",
        actor_id=f"portal_user:{patient_id}",
        patient_id=patient_id,
        result_id=result_id,
        justification=reason,
        break_glass=break_glass,
    )

    if not download_url:
        return "Error generating report", 500

    html = f"""
    <h1>Reporte generado</h1>
    <p>Puedes descargar tu PDF aquí:</p>
    <p><a href="{download_url}" target="_blank">Descargar PDF</a></p>
    """
    return html, 200


@app.route("/profile")
def profile():
    patient_id = request.args.get("patient_id")
    if not patient_id:
        return redirect(url_for("login"))

    patient = _get_patient(patient_id)
    if not patient:
        return f"Patient {patient_id} not found", 404

    return jsonify(patient)


if __name__ == "__main__":
    # Para correr localmente: python services/portal/app.py
    app.run(host="0.0.0.0", port=8080, debug=True)
