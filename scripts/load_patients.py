#!/usr/bin/env python3
"""
Carga pacientes de ejemplo en la tabla DynamoDB de patients.
Usa los datos del enunciado del proyecto.
"""

import os
import boto3

REGION_NAME = os.environ.get("REGION_NAME", "us-east-1")
PATIENTS_TABLE = os.environ["PATIENTS_TABLE"]

dynamo = boto3.resource("dynamodb", region_name=REGION_NAME)
table = dynamo.Table(PATIENTS_TABLE)

SAMPLE_PATIENTS = [
    {
        "patient_id": "P123456",
        "first_name": "John",
        "last_name": "Smith",
        "date_of_birth": "1985-03-15",
        "email": "john.smith@example.com",
        "phone": "+1-555-0101",
    },
    {
        "patient_id": "P234567",
        "first_name": "Maria",
        "last_name": "Garcia",
        "date_of_birth": "1990-07-22",
        "email": "maria.garcia@example.com",
        "phone": "+1-555-0102",
    },
    {
        "patient_id": "P345678",
        "first_name": "James",
        "last_name": "Wilson",
        "date_of_birth": "1978-11-08",
        "email": "james.wilson@example.com",
        "phone": "+1-555-0103",
    },
    {
        "patient_id": "P456789",
        "first_name": "Li",
        "last_name": "Chen",
        "date_of_birth": "1995-02-14",
        "email": "li.chen@example.com",
        "phone": "+1-555-0104",
    },
    {
        "patient_id": "P567890",
        "first_name": "Sarah",
        "last_name": "Johnson",
        "date_of_birth": "1982-09-30",
        "email": "sarah.johnson@example.com",
        "phone": "+1-555-0105",
    },
]


def main():
    print(f"REGION_NAME={REGION_NAME}")
    print(f"PATIENTS_TABLE={PATIENTS_TABLE}")
    print("Cargando pacientes de ejemplo...\n")

    for p in SAMPLE_PATIENTS:
        print(f" - Insertando {p['patient_id']} ({p['first_name']} {p['last_name']})")
        table.put_item(Item=p)

    print("\n✅ Carga completa.")


if __name__ == "__main__":
    main()
