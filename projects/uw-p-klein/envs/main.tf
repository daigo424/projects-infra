resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.project_name}-${var.environment}-vpc"
  }
}

module "whatsapp_webhook" {
  source = "../modules/whatsapp-webhook"

  project           = "whatsapp-webhook-${var.environment}"
  graph_api_version = "v23.0"

  verify_token    = "dummy"
  whatsapp_token  = "dummy"
  phone_number_id = "dummy"
  app_secret      = "dummy"
}
