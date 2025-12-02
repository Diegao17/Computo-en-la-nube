import os
import sys

# Añadir la raíz del proyecto al sys.path para poder hacer:
#   from process_utils import process_lab_result
CURRENT_DIR = os.path.dirname(__file__)                     # .../tests/unit
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.processor.process_utils import process_lab_result


def test_process_lab_result_has_abnormal_flag_and_status():
    data = {
        "patient_id": "P123456",
        "lab_id": "LAB001",
        "lab_name": "Quest Diagnostics",
        "test_type": "lipid_panel",
        "test_date": "2024-01-15T10:30:00Z",
        "results": [
            {
                "test_code": "LDL",
                "test_name": "LDL Cholesterol",
                "value": 160.0,
                "unit": "mg/dL",
                "reference_range": "<100",
                "is_abnormal": True,
            }
        ],
        "notes": "test sample",
    }

    item = process_lab_result(data, result_id="TEST-123")

    assert item["result_id"] == "TEST-123"
    assert item["status"] == "PROCESSED"
    assert item["has_abnormal"] is True
    assert "created_at" in item
    assert "updated_at" in item

