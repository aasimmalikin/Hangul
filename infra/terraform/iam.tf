# The role EC2 will assume
resource "aws_iam_role" "ec2_ecr" {
  name = "${var.project}-ec2-ecr"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

# Attach AWS's managed ECR read-only policy (least privilege)
resource "aws_iam_role_policy_attachment" "ecr_read" {
  role       = aws_iam_role.ec2_ecr.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

# Instance profile (what actually attaches to the EC2 instance)
resource "aws_iam_instance_profile" "ec2_ecr" {
  name = "${var.project}-ec2-ecr"
  role = aws_iam_role.ec2_ecr.name
}