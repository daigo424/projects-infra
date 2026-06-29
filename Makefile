cidr-list:
	python .\scripts\allocate_cidr.py list

set-vpn-key:
	aws ssm put-parameter --name "/vpn/tailscale-auth-key" --type SecureString --value "$(TS_AUTHKEY)" --region ap-northeast-1

terraform-fmt:
	terraform fmt -recursive ./