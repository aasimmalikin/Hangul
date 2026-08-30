data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_ecr.name
  key_name               = var.key_name

  user_data = <<-USERDATA
    #!/bin/bash
    yum update -y
    yum install -y docker
    systemctl start docker
    systemctl enable docker

    # Wait for IAM instance-profile credentials to become available (they can
    # lag a few seconds after boot). Retry sts until it succeeds.
    for i in $(seq 1 30); do
      if aws sts get-caller-identity --region ${var.region} >/dev/null 2>&1; then
        break
      fi
      echo "waiting for IAM credentials... ($i)"
      sleep 5
    done

    # ECR login, with retry
    for i in $(seq 1 10); do
      if aws ecr get-login-password --region ${var.region} | \
         docker login --username AWS --password-stdin ${split("/", var.ecr_image_uri)[0]}; then
        break
      fi
      echo "ecr login retry $i..."
      sleep 5
    done

    docker run -d --restart unless-stopped \
      -p 8501:8501 -p 8000:8000 \
      -e OPENAI_API_KEY="${var.openai_api_key}" \
      -e TAVILY_API_KEY="${var.tavily_api_key}" \
      ${var.ecr_image_uri}
  USERDATA

  tags = { Name = var.project }
}
