import os
import json
import time
import boto3

# === CONFIGURACIÓN DESDE ENV ===
REGION_NAME = os.environ.get("REGION_NAME", "us-east-1")
NOTIFY_QUEUE_URL = os.environ.get("NOTIFY_QUEUE_URL")

print("=== CONFIG NOTIFY WORKER ===")
print("REGION_NAME      :", REGION_NAME)
print("NOTIFY_QUEUE_URL :", NOTIFY_QUEUE_URL)
print("=============================\n")

if not NOTIFY_QUEUE_URL:
    raise RuntimeError("NOTIFY_QUEUE_URL no está definido en las variables de entorno.")

sqs = boto3.client("sqs", region_name=REGION_NAME)


def handle_notify_message(body: str):
    msg = json.loads(body)
    print("\n=== NOTIFICACIÓN RECIBIDA ===")
    print(f"patient_id : {msg.get('patient_id')}")
    print(f"result_id  : {msg.get('result_id')}")
    print("Mensaje completo:", msg)
    print("================================\n")


def main():
    print("Notify worker iniciado, escuchando notificaciones...\n")
    while True:
        # Hacemos long polling y además logeamos la respuesta cruda
        resp = sqs.receive_message(
            QueueUrl=NOTIFY_QUEUE_URL,
            MaxNumberOfMessages=5,
            WaitTimeSeconds=10,   # long polling
            VisibilityTimeout=30,
        )

        print("Respuesta cruda de receive_message:", resp)

        messages = resp.get("Messages", [])
        if not messages:
            print("No hay notificaciones nuevas en este ciclo...\n")
        else:
            print(f"Se recibieron {len(messages)} notificación(es).\n")

        for m in messages:
            try:
                handle_notify_message(m["Body"])
                sqs.delete_message(
                    QueueUrl=NOTIFY_QUEUE_URL,
                    ReceiptHandle=m["ReceiptHandle"],
                )
                print("✅ Notificación procesada y eliminada.\n")
            except Exception as e:
                print("❌ Error procesando notificación:", e)

        time.sleep(1)


if __name__ == "__main__":
    main()

