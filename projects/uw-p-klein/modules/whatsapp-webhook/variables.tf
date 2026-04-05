variable "project" {
  type    = string
  default = "whatsapp-webhook"
}

variable "verify_token" {
  type      = string
  sensitive = true
}

variable "whatsapp_token" {
  type      = string
  sensitive = true
}

variable "phone_number_id" {
  type = string
}

variable "app_secret" {
  type      = string
  sensitive = true
}

variable "graph_api_version" {
  type    = string
  default = "v23.0"
}