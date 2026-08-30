variable "region" {
    default = "ap-south-1"
}

variable "instance_type" {
    default = "t3.micro"
}

variable "project" {
    default = "agentic-qa"
}

variable "ecr_image_uri" {
    description = "357941178362.dkr.ecr.ap-south-1.amazonaws.com/agentic-qa:latest"
}

variable "my_ip" {
    description = "49.36.193.245"
}

variable "key_name" {
  description = "agentic-qa-key"
}

variable "openai_api_key" {
  description = "string"
  sensitive   = true
}

variable "tavily_api_key" {
  description = "string1"
  sensitive   = true
}