variable "aws_region" {
  type = string
}

variable "workload_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "vpc_cidr" {
  type = string
}

variable "create_compute" {
  type    = bool
  default = true
}
