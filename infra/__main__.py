import pulumi
import pulumi_aws as aws

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
config = pulumi.Config()

app_name = "fastapi-app"

database_url = config.require("database_url")
docker_image = config.require("docker_image")
ssh_public_key = config.require("ssh_public_key")  # REQUIRED now


# --------------------------------------------------
# VPC
# --------------------------------------------------
vpc = aws.ec2.Vpc(
    f"{app_name}-vpc",
    cidr_block="10.0.0.0/16",
    enable_dns_hostnames=True,
    enable_dns_support=True,
    tags={"Name": f"{app_name}-vpc"},
)

igw = aws.ec2.InternetGateway(
    f"{app_name}-igw",
    vpc_id=vpc.id,
)

public_subnet = aws.ec2.Subnet(
    f"{app_name}-public-subnet",
    vpc_id=vpc.id,
    cidr_block="10.0.1.0/24",
    availability_zone="ap-southeast-1a",
    map_public_ip_on_launch=True,
)

route_table = aws.ec2.RouteTable(
    f"{app_name}-rt",
    vpc_id=vpc.id,
)

aws.ec2.Route(
    f"{app_name}-route",
    route_table_id=route_table.id,
    destination_cidr_block="0.0.0.0/0",
    gateway_id=igw.id,
)

aws.ec2.RouteTableAssociation(
    f"{app_name}-rta",
    subnet_id=public_subnet.id,
    route_table_id=route_table.id,
)


# --------------------------------------------------
# SECURITY GROUP
# --------------------------------------------------
security_group = aws.ec2.SecurityGroup(
    f"{app_name}-sg",
    vpc_id=vpc.id,
    description="Allow HTTP + SSH",
    ingress=[
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=22,
            to_port=22,
            cidr_blocks=["0.0.0.0/0"],
        ),
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=80,
            to_port=80,
            cidr_blocks=["0.0.0.0/0"],
        ),
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=8000,
            to_port=8000,
            cidr_blocks=["0.0.0.0/0"],
        ),
    ],
    egress=[
        aws.ec2.SecurityGroupEgressArgs(
            protocol="-1",
            from_port=0,
            to_port=0,
            cidr_blocks=["0.0.0.0/0"],
        )
    ],
)


# --------------------------------------------------
# KEYPAIR
# --------------------------------------------------
key_pair = aws.ec2.KeyPair(
    f"{app_name}-keypair",
    public_key=ssh_public_key,
)


# --------------------------------------------------
# USER DATA SCRIPT
# --------------------------------------------------
user_data = pulumi.Output.all(docker_image, database_url).apply(
    lambda args: f"""#!/bin/bash
set -e

echo "Updating system..."
yum update -y

echo "Installing Docker..."
yum install -y docker
systemctl start docker
systemctl enable docker
usermod -aG docker ec2-user

echo "Pulling container..."
docker pull {args[0]}

echo "Stopping old container..."
docker stop fastapi-app || true
docker rm fastapi-app || true

echo "Running container..."
docker run -d --name fastapi-app --restart unless-stopped \
-p 80:8000 \
-e DATABASE_URL="{args[1]}" \
{args[0]}

echo "Deployment finished"
"""
)


# --------------------------------------------------
# EC2 INSTANCE
# --------------------------------------------------
instance = aws.ec2.Instance(
    f"{app_name}-instance",
    instance_type="t3.small",
    ami="ami-01811d4912b4ccb26",  # Amazon Linux 2023 (Singapore)
    subnet_id=public_subnet.id,
    vpc_security_group_ids=[security_group.id],
    key_name=key_pair.key_name,
    user_data=user_data,
    tags={"Name": f"{app_name}-instance"},
)


# --------------------------------------------------
# OUTPUTS
# --------------------------------------------------
pulumi.export("public_ip", instance.public_ip)
pulumi.export("public_dns", instance.public_dns)
pulumi.export("app_url", instance.public_dns.apply(lambda d: f"http://{d}"))
pulumi.export("ssh_command", instance.public_ip.apply(lambda ip: f"ssh -i ~/.ssh/fastapi-ec2-key ec2-user@{ip}"))
