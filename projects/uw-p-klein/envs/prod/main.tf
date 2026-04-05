module "network" {
  source = "../../modules/network"

  name_prefix = var.name_prefix
  vpc_cidr    = var.vpc_cidr
}

module "whatsapp_webhook" {
  source = "../../modules/whatsapp-webhook"

  project           = "whatsapp-webhook-prod"
  verify_token      = var.verify_token
  whatsapp_token    = var.whatsapp_token
  phone_number_id   = var.phone_number_id
  app_secret        = var.app_secret
  graph_api_version = "v23.0"
}
