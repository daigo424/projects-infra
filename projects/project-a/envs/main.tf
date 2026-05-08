module "network" {
  source = "../modules/network"

  name_prefix = "${var.project_name}-${var.environment}"
  vpc_cidr    = var.vpc_cidr
}
