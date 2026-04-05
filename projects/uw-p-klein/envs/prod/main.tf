module "network" {
  source = "../../modules/network"

  name_prefix = var.name_prefix
  vpc_cidr    = var.vpc_cidr
}

module "whatsapp_webhook" {
  source = "../../modules/whatsapp-webhook"

  project           = "whatsapp-webhook-prod"
  graph_api_version = "v23.0"

  # These should be set to real values in a secure way in AWS console
  verify_token    = "dummy"
  whatsapp_token  = "dummy"
  phone_number_id = "dummy"
  app_secret      = "dummy"
}
