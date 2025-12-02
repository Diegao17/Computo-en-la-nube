########################################
# SECURITY GROUP PARA LA EC2 DEL PORTAL
########################################

resource "aws_security_group" "ec2_portal_sg" {
  name        = "${var.project_name}-ec2-portal-sg"
  description = "Allow HTTP traffic for portal"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

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

########################################
# INSTANCIA EC2 PARA EL PORTAL
########################################

resource "aws_instance" "ec2_portal" {
  ami                    = "ami-06aa3f7caf3a30282" # Amazon Linux 2 (ejemplo us-east-1)
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public_1.id
  vpc_security_group_ids = [aws_security_group.ec2_portal_sg.id]
  key_name               = var.key_name

  user_data = <<-EOF
    #!/bin/bash
    yum update -y
    yum install -y python3 git

    cd /opt
    git clone https://github.com/Diegao17/Computo-en-la-nube.git
    cd Cloud-Computing-main

    pip3 install -r services/portal/requirements.txt

    export LAB_RESULTS_TABLE="${aws_dynamodb_table.lab_results.name}"
    export PATIENTS_TABLE="${aws_dynamodb_table.patients.name}"
    export ACCESS_AUDIT_TABLE="${aws_dynamodb_table.access_audit.name}"
    export REPORT_LAMBDA_NAME="${aws_lambda_function.report.function_name}"

    # Levantar el portal en background
    python3 services/portal/app.py > /var/log/portal.log 2>&1 &
  EOF

  tags = {
    Name = "${var.project_name}-ec2-portal"
  }
}

