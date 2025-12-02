import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def process_lab_result(data: Dict[str, Any], result_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Normaliza un resultado de laboratorio para guardarlo en DynamoDB.

    - Asegura que haya un result_id consistente en todo el flujo.
    - Agrega campos de auditoría (status, created_at, updated_at).
    - Calcula has_abnormal si algún resultado viene marcado como is_abnormal = True.
    """

    # Usa el result_id que venga del caller, o el que venga en data,
    # y si no hay ninguno, genera uno nuevo.
    rid = result_id or data.get("result_id") or str(uuid.uuid4())

    # Fecha/hora en UTC con timezone-aware (evita warning en Python 3.13+)
    now = datetime.now(timezone.utc).isoformat()

    item: Dict[str, Any] = {
        "result_id": rid,
        "patient_id": data["patient_id"],
        "lab_id": data["lab_id"],
        "lab_name": data["lab_name"],
        "test_type": data["test_type"],
        "test_date": data.get("test_date"),
        "results": data.get("results", []),
        "notes": data.get("notes", ""),
        "status": "PROCESSED",
        "created_at": now,
        "updated_at": now,
    }

    results = item["results"]

    # has_abnormal = True si cualquier resultado viene con is_abnormal = True
    if isinstance(results, list) and results:
        item["has_abnormal"] = any(bool(r.get("is_abnormal")) for r in results)
    else:
        item["has_abnormal"] = False

    return item

