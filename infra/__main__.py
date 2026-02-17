import pulumi
import pulumi_aws as aws

# Configuration
config = pulumi.Config()
app_name = "fastapi-app"
database_url = config.require("database_url")  # Must be set via: pulumi config set database_url <value>
docker_image = config.require("docker_image")  # Must be set via: pulumi config set docker_image <value>
ssh_public_key = config.get("ssh_public_key")  # Optional: your public SSH key for EC2 access

# 1. VPC
vpc = aws.ec2.Vpc(
    f"{app_name}-vpc",
    cidr_block="10.0.0.0/16",
    enable_dns_hostnames=True,
    enable_dns_support=True,
    tags={"Name": f"{app_name}-vpc"},
)

# Internet Gateway
igw = aws.ec2.InternetGateway(
    f"{app_name}-igw",
    vpc_id=vpc.id,
    tags={"Name": f"{app_name}-igw"},
)

# Public Subnet
public_subnet = aws.ec2.Subnet(
    f"{app_name}-public-subnet",
    vpc_id=vpc.id,
    cidr_block="10.0.1.0/24",
    availability_zone="ap-southeast-1a",
    map_public_ip_on_launch=True,
    tags={"Name": f"{app_name}-public-subnet"},
)

# Route Table
route_table = aws.ec2.RouteTable(
    f"{app_name}-rt",
    vpc_id=vpc.id,
    tags={"Name": f"{app_name}-rt"},
)

# Route to Internet Gateway
route = aws.ec2.Route(
    f"{app_name}-route",
    route_table_id=route_table.id,
    destination_cidr_block="0.0.0.0/0",
    gateway_id=igw.id,
)

# Associate Route Table with Subnet
rta = aws.ec2.RouteTableAssociation(
    f"{app_name}-rta",
    subnet_id=public_subnet.id,
    route_table_id=route_table.id,
)

# 2. Security Group for EC2
security_group = aws.ec2.SecurityGroup(
    f"{app_name}-sg",
    vpc_id=vpc.id,
    description="Allow HTTP traffic",
    ingress=[
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
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=22,
            to_port=22,
            cidr_blocks=["0.0.0.0/0"],
        ),
    ],
    egress=[
        aws.ec2.SecurityGroupEgressArgs(
            protocol="-1",
            from_port=0,
            to_port=0,
            cidr_blocks=["0.0.0.0/0"],
        ),
    ],
    tags={"Name": f"{app_name}-sg"},
)

# 3. Use existing AWS Key Pair
# Note: Key pair must be created in AWS first with:
# aws ec2 create-key-pair --key-name fastapi-ec2-key --region ap-southeast-1 --query 'KeyMaterial' --output text > fastapi-ec2-key.pem

# 4. User Data Script - using Docker Hub (Ubuntu)
user_data = pulumi.Output.all(docker_image, database_url).apply(
    lambda args: f"""#!/bin/bash
set -e

# Update and install Docker
apt-get update
apt-get install -y docker.io

# Start Docker
systemctl start docker
systemctl enable docker

# Add ubuntu user to docker group
usermod -aG docker ubuntu

# Pull image from Docker Hub
echo "Pulling Docker image from Docker Hub: {args[0]}"
docker pull {args[0]}

# Stop and remove old container if exists
docker stop fastapi-app || true
docker rm fastapi-app || true

# Run the container
docker run -d --name fastapi-app --restart unless-stopped \
  -p 80:8000 \
  -e DATABASE_URL="{args[1]}" \
  {args[0]}

echo "Deployment complete!"
"""
)

# 5. EC2 Instance
instance = aws.ec2.Instance(
    f"{app_name}-instance",
    instance_type="t3.small",
    ami="ami-01811d4912b4ccb26",  # Amazon Linux 2023 in ap-southeast-1
    subnet_id=public_subnet.id,
    vpc_security_group_ids=[security_group.id],
    key_name="fastapi-ec2-key",  # Use the AWS key pair name
    user_data=user_data,
    tags={"Name": f"{app_name}-instance"},
)

# Exports
pulumi.export("instance_id", instance.id)
pulumi.export("instance_public_ip", instance.public_ip)
pulumi.export("instance_public_dns", instance.public_dns)
pulumi.export("application_url", instance.public_dns.apply(lambda dns: f"http://{dns}"))
pulumi.export("ssh_command", instance.public_ip.apply(lambda ip: f"ssh ec2-user@{ip}"))
pulumi.export("docker_image", docker_image)
