module "network" {
  source = "../modules/network"

  name_prefix = "${var.project_name}-${var.environment}"
  vpc_cidr    = var.vpc_cidr
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
