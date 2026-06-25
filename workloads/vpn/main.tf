resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.workload_name}-${var.environment}-vpc"
  }
}

resource "aws_subnet" "public_subnet" {
  vpc_id                  = aws_vpc.this.id
  availability_zone       = "ap-northeast-1a"
  map_public_ip_on_launch = true

  # Automatically calculates a /24 subnet from the /20 VPC (20 + 4 = 24)
  cidr_block = cidrsubnets(aws_vpc.this.cidr_block, 4)[0]

  tags = { Name = "${var.workload_name}-${var.environment}-public-subnet" }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.this.id

  tags = { Name = "${var.workload_name}-${var.environment}-igw" }
}

resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
  tags = { Name = "${var.workload_name}-${var.environment}-public-rt" }
}

resource "aws_route_table_association" "public_assoc" {
  subnet_id      = aws_subnet.public_subnet.id
  route_table_id = aws_route_table.public_rt.id
}

resource "aws_security_group" "vpn_server_sg" {
  name        = "${var.workload_name}-${var.environment}-ec2-sg"
  description = "Block all inbound, allow all outbound"
  vpc_id      = aws_vpc.this.id

  # No ingress rules defined (All inbound ports closed)

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${var.workload_name}-${var.environment}-sg" }
}

data "aws_ami" "vpn_machine_image" {
  most_recent = true
  owners      = ["099720109477"] # Canonical公式

  filter {
    name   = "name"
    values = ["ubuntu-minimal/images/hvm-ssd-gp3/ubuntu-noble-24.04-arm64-minimal-*"]
  }
}

resource "aws_iam_role" "vpn_server" {
  name = "${var.workload_name}-${var.environment}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "vpn_server_ssm" {
  name = "${var.workload_name}-${var.environment}-ssm-policy"
  role = aws_iam_role.vpn_server.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = "arn:aws:ssm:${var.aws_region}:*:parameter/vpn/tailscale-auth-key"
      },
      {
        Effect   = "Allow"
        Action   = ["ec2:AssociateAddress"]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "vpn_server" {
  name = "${var.workload_name}-${var.environment}-ec2-profile"
  role = aws_iam_role.vpn_server.name
}

resource "aws_spot_instance_request" "vpn_server" {
  ami                  = data.aws_ami.vpn_machine_image.id
  instance_type        = "t4g.nano"
  spot_type            = "persistent"
  wait_for_fulfillment = true

  subnet_id              = aws_subnet.public_subnet.id
  vpc_security_group_ids = [aws_security_group.vpn_server_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.vpn_server.name

  user_data = <<-EOF
              #!/bin/bash
              echo 'net.ipv4.ip_forward = 1' | tee -a /etc/sysctl.conf
              echo 'net.ipv6.conf.all.forwarding = 1' | tee -a /etc/sysctl.conf
              sysctl -p

              apt-get install -y unzip
              curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o /tmp/awscliv2.zip
              unzip -q /tmp/awscliv2.zip -d /tmp
              /tmp/aws/install
              rm -rf /tmp/awscliv2.zip /tmp/aws

              TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
              INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
              aws ec2 associate-address \
                --instance-id "$INSTANCE_ID" \
                --allocation-id "${aws_eip.vpn_server_eip.id}" \
                --region ${var.aws_region}

              AUTH_KEY=$(aws ssm get-parameter \
                --name "/vpn/tailscale-auth-key" \
                --with-decryption \
                --region ${var.aws_region} \
                --query Parameter.Value \
                --output text)

              curl -fsSL https://tailscale.com/install.sh | sh

              tailscale up --authkey="$AUTH_KEY" --advertise-routes=${aws_vpc.this.cidr_block} --advertise-exit-node --accept-dns=false
              EOF

  tags = { Name = "${var.workload_name}-${var.environment}-spot" }
}

resource "aws_eip" "vpn_server_eip" {
  domain = "vpc"
  tags   = { Name = "${var.workload_name}-${var.environment}-eip" }
}

resource "aws_eip_association" "vpn_server_eip_assoc" {
  instance_id   = aws_spot_instance_request.vpn_server.spot_instance_id
  allocation_id = aws_eip.vpn_server_eip.id
}

output "vpn_public_ip" {
  value       = aws_eip.vpn_server_eip.public_ip
  description = "The public IP address of the VPN server."
}