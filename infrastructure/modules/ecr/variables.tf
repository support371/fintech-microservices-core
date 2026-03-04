variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "repositories" {
  description = "List of ECR repository names"
  type        = list(string)
}
