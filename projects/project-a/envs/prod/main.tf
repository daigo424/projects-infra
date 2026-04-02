module "network" {
  source = "../../modules/network"

  name_prefix = var.name_prefix
  vpc_cidr    = var.vpc_cidr
}
