output "public_ip" {
  value       = aws_instance.app.public_ip
  description = "Public IP of the EC2 instance"
}

output "app_url" {
  value       = "http://${aws_instance.app.public_ip}:8501"
  description = "URL to open the Streamlit app"
}