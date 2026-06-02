module "network" {
  source = "../modules/network"

  name_prefix = "${var.workload_name}-${var.environment}"
  vpc_cidr    = var.vpc_cidr
}
