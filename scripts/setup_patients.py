import boto3

dynamo = boto3.resource("dynamodb")
table = dynamo.Table("healthcare-lab-patients")  

PATIENTS = [
    {
        "patient_id": "P123456",
        "first_name": "John",
        "last_name": "Smith",
        "date_of_birth": "1985-03-15",
        "email": "john.smith@example.com",
        "phone": "+1-555-0101"
    },
    {
        "patient_id": "P234567",
        "first_name": "Maria",
        "last_name": "Garcia",
        "date_of_birth": "1990-07-22",
        "email": "maria.garcia@example.com",
        "phone": "+1-555-0102"
    },
    {
        "patient_id": "P345678",
        "first_name": "James",
        "last_name": "Wilson",
        "date_of_birth": "1978-11-08",
        "email": "james.wilson@example.com",
        "phone": "+1-555-0103"
    },
    {
        "patient_id": "P456789",
        "first_name": "Li",
        "last_name": "Chen",
        "date_of_birth": "1995-02-14",
        "email": "li.chen@example.com",
        "phone": "+1-555-0104"
    },
    {
        "patient_id": "P567890",
        "first_name": "Sarah",
        "last_name": "Johnson",
        "date_of_birth": "1982-09-30",
        "email": "sarah.johnson@example.com",
                "phone": "+1-555-0105"
    }
]

def main():
    for p in PATIENTS:
        print(f"Inserting {p['patient_id']}")
        table.put_item(Item=p)

if __name__ == "__main__":
    main()

