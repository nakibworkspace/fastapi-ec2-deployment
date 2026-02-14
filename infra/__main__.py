import pulumi
import pulumi_aws as aws
import json

# Configuration
config = pulumi.Config()
app_name = "fastapi-app"
database_url = config.get("database_url") or "postgresql://postgres:postgres@localhost:5432/postgres"

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

# 3. ECR Repository
repo = aws.ecr.Repository(
    f"{app_name}-repo",
    force_delete=True,
    image_scanning_configuration=aws.ecr.RepositoryImageScanningConfigurationArgs(
        scan_on_push=True,
    ),
)

# ECR Lifecycle Policy
aws.ecr.LifecyclePolicy(
    f"{app_name}-lifecycle",
    repository=repo.name,
    policy=json.dumps({
        "rules": [{
            "rulePriority": 1,
            "description": "Keep last 10 images",
            "selection": {
                "tagStatus": "any",
                "countType": "imageCountMoreThan",
                "countNumber": 10
            },
            "action": {
                "type": "expire"
            }
        }]
    }),
)

# 4. IAM Role for EC2
ec2_role = aws.iam.Role(
    f"{app_name}-ec2-role",
    assume_role_policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {
                "Service": "ec2.amazonaws.com"
            }
        }]
    }),
)

# Attach ECR read policy
aws.iam.RolePolicyAttachment(
    f"{app_name}-ecr-policy",
    role=ec2_role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
)

# Attach SSM policy for Session Manager
aws.iam.RolePolicyAttachment(
    f"{app_name}-ssm-policy",
    role=ec2_role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
)

# Instance Profile
instance_profile = aws.iam.InstanceProfile(
    f"{app_name}-instance-profile",
    role=ec2_role.name,
)

# 5. User Data Script
user_data = pulumi.Output.all(repo.repository_url, database_url).apply(
    lambda args: f"""#!/bin/bash
set -e

# Install Docker
yum update -y
yum install -y docker
systemctl start docker
systemctl enable docker
usermod -a -G docker ec2-user

# Install AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
./aws/install

# Login to ECR
aws ecr get-login-password --region ap-southeast-1 | docker login --username AWS --password-stdin {args[0].split('/')[0]}

# Pull and run the container
docker pull {args[0]}:latest
docker stop fastapi-app || true
docker rm fastapi-app || true
docker run -d --name fastapi-app --restart unless-stopped \
  -p 80:8000 \
  -e DATABASE_URL="{args[1]}" \
  {args[0]}:latest

echo "Deployment complete!"
"""
)

# 6. EC2 Instance
instance = aws.ec2.Instance(
    f"{app_name}-instance",
    instance_type="t3.small",
    ami="ami-01811d4912b4ccb26",  # Amazon Linux 2023 in ap-southeast-1
    subnet_id=public_subnet.id,
    vpc_security_group_ids=[security_group.id],
    iam_instance_profile=instance_profile.name,
    user_data=user_data,
    tags={"Name": f"{app_name}-instance"},
)

# Exports
pulumi.export("instance_id", instance.id)
pulumi.export("instance_public_ip", instance.public_ip)
pulumi.export("instance_public_dns", instance.public_dns)
pulumi.export("ecr_repository_url", repo.repository_url)
pulumi.export("application_url", instance.public_dns.apply(lambda dns: f"http://{dns}"))