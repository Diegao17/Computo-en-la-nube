# SECURITY GROUP PARA WORKER
resource "aws_security_group" "ec2_worker_sg" {
  name        = "${var.project_name}-ec2-worker-sg"
  description = "Security group for worker EC2 instance"
  vpc_id      = aws_vpc.main.id

  # SSH (para debug, aunque no lo uses)
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Salida a internet
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-ec2-worker-sg"
  }
}

# SECURITY GROUP PARA PORTAL
resource "aws_security_group" "ec2_portal_sg" {
  name        = "${var.project_name}-ec2-portal-sg"
  description = "Security group for portal EC2 instance"
  vpc_id      = aws_vpc.main.id

  # HTTP para el portal (Flask en 8080)
  ingress {
    description = "HTTP portal (8080)"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # SSH (opcional)
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Salida a internet
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-ec2-portal-sg"
  }
}

# KEY PAIR PARA ACCESO A EC2
resource "aws_key_pair" "worker_key" {
  key_name   = "${var.project_name}-worker-key"
  public_key = file("${path.module}/worker_key.pub")
}

# INSTANCIA EC2 DEL WORKER
resource "aws_instance" "worker" {
  ami                    = "ami-06aa3f7caf3a30282" # AMI Ubuntu/Amazon Linux en us-east-1 (ya vimos que sale Ubuntu)
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.public_1.id
  vpc_security_group_ids = [aws_security_group.ec2_worker_sg.id]
  key_name               = aws_key_pair.worker_key.key_name

  # Si cambia el user_data, recrea la instancia
  user_data_replace_on_change = true

  user_data = <<-EOF
    #!/bin/bash
    set -e
    export DEBIAN_FRONTEND=noninteractive

    # Actualizar e instalar dependencias en UBUNTU
    apt-get update -y
    apt-get install -y python3 python3-venv python3-pip git

    cd /opt

    # Clonar el repo correcto
    if [ ! -d "Computo-en-la-nube" ]; then
      git clone https://github.com/Diegao17/Computo-en-la-nube.git
    fi
    cd Computo-en-la-nube

    # Crear venv e instalar requirements del worker
    python3 -m venv venv
    . venv/bin/activate
    pip install --upgrade pip
    pip install -r services/processor/requirements.txt

    # Exportar variables de entorno que usa worker.py
    export REGION_NAME="${var.region}"
    export LAB_RESULTS_QUEUE_URL="${aws_sqs_queue.lab_results_queue.id}"
    export NOTIFY_QUEUE_URL="${aws_sqs_queue.notify_queue.id}"
    export RAW_BUCKET="${var.raw_bucket_name}"
    export LAB_RESULTS_TABLE="${aws_dynamodb_table.lab_results.name}"
    export ACCESS_AUDIT_TABLE="${aws_dynamodb_table.access_audit.name}"

    # Lanzar worker como módulo (importante para que encuentre 'services')
    nohup python3 -m services.processor.worker > /var/log/worker.log 2>&1 &
  EOF

  tags = {
    Name = "${var.project_name}-ec2-worker"
  }
}

# INSTANCIA EC2 DEL PORTAL
resource "aws_instance" "ec2_portal" {
  ami                    = "ami-06aa3f7caf3a30282"
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.public_1.id
  vpc_security_group_ids = [aws_security_group.ec2_portal_sg.id]
  key_name               = aws_key_pair.worker_key.key_name

  user_data_replace_on_change = true

  user_data = <<-EOF
    #!/bin/bash
    set -e
    export DEBIAN_FRONTEND=noninteractive

    # Actualizar e instalar dependencias en UBUNTU
    apt-get update -y
    apt-get install -y python3 python3-venv python3-pip git

    cd /opt

    # Clonar el repo correcto
    if [ ! -d "Computo-en-la-nube" ]; then
      git clone https://github.com/Diegao17/Computo-en-la-nube.git
    fi
    cd Computo-en-la-nube

    # Crear venv e instalar requirements del portal
    python3 -m venv venv
    . venv/bin/activate
    pip install --upgrade pip
    pip install -r services/portal/requirements.txt

    # Variables de entorno para el portal
    export REGION_NAME="${var.region}"
    export LAB_RESULTS_TABLE="${aws_dynamodb_table.lab_results.name}"
    export PATIENTS_TABLE="${aws_dynamodb_table.patients.name}"
    export ACCESS_AUDIT_TABLE="${aws_dynamodb_table.access_audit.name}"
    export REPORT_LAMBDA_NAME="${aws_lambda_function.report.function_name}"

    # Levantar portal como módulo, escuchando en 0.0.0.0:8080
    nohup python3 -m services.portal.app > /var/log/portal.log 2>&1 &
  EOF

  tags = {
    Name = "${var.project_name}-ec2-portal"
  }
}
