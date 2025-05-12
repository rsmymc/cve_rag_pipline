#!/bin/bash

### --- NETWORK SETUP --- ###

# VPC ID (using default VPC here)
aws ec2 describe-vpcs \
  --query "Vpcs[*].{ID:VpcId,CIDR:CidrBlock,Default:IsDefault}" \
  --output table

VPC_ID="vpc-0e23a80099b2d4ec2"

# Create public subnet
aws ec2 create-subnet \
  --vpc-id $VPC_ID \
  --cidr-block 172.31.50.0/24 \
  --availability-zone us-east-2a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=OllamaPublicSubnet}]'

# List subnet
SUBNET_ID=$(aws ec2 describe-subnets --filters Name=tag:Name,Values=OllamaPublicSubnet \
  --query 'Subnets[0].SubnetId' --output text)

aws ec2 describe-subnets \
  --query "Subnets[*].{ID:SubnetId,AZ:AvailabilityZone}" \
  --output table

# Enable auto-assign public IP for the subnet
aws ec2 modify-subnet-attribute \
  --subnet-id $SUBNET_ID \
  --map-public-ip-on-launch




### --- EFS File System for ChromaDB Persistence --- ###

# Create EFS File System

aws efs create-file-system \
  --performance-mode generalPurpose \
  --throughput-mode bursting \
  --tags Key=Name,Value=chroma-efs

# Create Mount Targets in Each Subnet
#1.create security group
aws ec2 create-security-group \
  --group-name chroma-efs-sg \
  --description "Allow NFS access for EFS" \
  --vpc-id vpc-0e23a80099b2d4ec2
#2.Allow NFS access from your VPC CIDR
aws ec2 authorize-security-group-ingress \
  --group-id sg-0d0bbf64e299c2955 \
  --protocol tcp \
  --port 2049 \
  --cidr 172.31.0.0/16
#3.Create EFS Mount Target in Subnet
aws efs create-mount-target \
  --file-system-id fs-0274164cec35300cc \
  --subnet-id subnet-06e4e5009a4f330ef \
  --security-groups sg-0d0bbf64e299c2955




### --- DOCKER + ECR SETUP ChromaDB --- ###

# Create Log Group
aws logs create-log-group --log-group-name /ecs/chromadb --region us-east-2 || true

# Register the Task
cat > chromadb-task-def.json <<EOF
{
  "family": "chromadb-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::959632173666:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "chromadb",
      "image": "ghcr.io/chroma-core/chroma:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        { "name": "IS_PERSISTENT", "value": "TRUE" },
        { "name": "PERSIST_DIRECTORY", "value": "/data" }
      ],
      "mountPoints": [
        {
          "sourceVolume": "chroma-efs-vol",
          "containerPath": "/data"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/chromadb",
          "awslogs-region": "us-east-2",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "essential": true
    }
  ],
  "volumes": [
    {
      "name": "chroma-efs-vol",
      "efsVolumeConfiguration": {
        "fileSystemId": "fs-0274164cec35300cc",
        "transitEncryption": "ENABLED",
        "rootDirectory": "/"
      }
    }
  ]
}
EOF

aws ecs register-task-definition --cli-input-json file://chromadb-task-def.json

#Allow HTTP access from your VPC CIDR
aws ec2 authorize-security-group-ingress \
  --group-id sg-0d0bbf64e299c2955 \
  --protocol tcp \
  --port 8080 \
  --cidr 0.0.0.0/0

# Run the ECS service
aws ecs create-service \
  --cluster cve_rag_pipline \
  --service-name chromadb-service \
  --task-definition chromadb-task \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration '{
    "awsvpcConfiguration": {
      "subnets": ["subnet-06e4e5009a4f330ef"],
      "securityGroups": ["sg-0d0bbf64e299c2955"],
      "assignPublicIp": "ENABLED"
    }
  }'

# Update the ECS service
aws ecs update-service   --cluster cve_rag_pipline   --service chromadb-service   --desired-count 1





### --- DOCKER + ECR SETUP Chroma-indexer --- ###

# Build Docker image
docker build -t chroma-indexer ./chroma-indexer

# Tag image for ECR Public
docker tag chroma-indexer:latest public.ecr.aws/x6i8o2b8/chroma-indexer:latest

# Authenticate with ECR Public
aws ecr-public get-login-password --region us-east-1 | \
docker login --username AWS --password-stdin public.ecr.aws/x6i8o2b8

# Create public ECR repo (no error if it exists)
aws ecr-public create-repository \
  --repository-name chroma-indexer \
  --region us-east-1 \
  --catalog-data '{
    "description": "Chroma indexer that loads CVEs from S3 and indexes into ChromaDB"
  }'
# Push image to ECR Public
docker push public.ecr.aws/x6i8o2b8/chroma-indexer:latest

# Create Log Group
aws logs create-log-group --log-group-name /ecs/chroma-indexer --region us-east-2 || true

# Create Role
aws iam create-role \
  --role-name ecsTaskRoleWithS3Access \
  --assume-role-policy-document file://<(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
)

# Attach a Permission Policy to the Role
aws iam attach-role-policy \
  --role-name ecsTaskRoleWithS3Access \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

# Register the Task
cat > chroma-indexer-task-def.json <<EOF
{
  "family": "chroma-indexer-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "taskRoleArn": "arn:aws:iam::959632173666:role/ecsTaskRoleWithS3Access",
  "executionRoleArn": "arn:aws:iam::959632173666:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "chroma-indexer",
      "image": "public.ecr.aws/x6i8o2b8/chroma-indexer",
      "essential": true,
      "environment": [
        { "name": "CHROMA_URL", "value": "http://18.222.121.173:8000" },
        { "name": "CHROMA_DB_MINILM_MODEL_NAME", "value": "all-MiniLM-L6-v2" },
        { "name": "CHROMA_DB_MINILM_COLLECTION_NAME", "value": "cves_minilm" },
        { "name": "S3_BUCKET", "value": "cve-rag-pipline-bucket" },
        { "name": "S3_PREFIX", "value": "cves/" }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/chroma-indexer",
          "awslogs-region": "us-east-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}

EOF

aws ecs register-task-definition --cli-input-json file://chroma-indexer-task-def.json

# Run chroma-indexer ECS Task

aws ecs run-task \
  --cluster cve_rag_pipline \
  --launch-type FARGATE \
  --network-configuration '{
    "awsvpcConfiguration": {
      "subnets": ["subnet-06e4e5009a4f330ef"],
      "securityGroups": ["sg-0d0bbf64e299c2955"],
      "assignPublicIp": "ENABLED"
    }
  }' \
  --task-definition chroma-indexer-task




### --- DOCKER + ECR SETUP Ollama--- ###

# Build Docker image
docker build -t ollama-gemma ./ollama-server

# Tag image for ECR Public
docker tag ollama-gemma:latest public.ecr.aws/x6i8o2b8/ollama-gemma:latest

# Authenticate with ECR Public
aws ecr-public get-login-password --region us-east-1 | \
docker login --username AWS --password-stdin public.ecr.aws

# Create public ECR repo (no error if it exists)
aws ecr-public create-repository --repository-name ollama-gemma --region us-east-1 || true

# Push image to ECR Public
docker push public.ecr.aws/x6i8o2b8/ollama-gemma:latest


# Register ECS Task Definition Ollama #

cat > ollama-gemma-task.json <<EOF
{
  "family": "ollama-gemma-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "4096",
  "executionRoleArn": "arn:aws:iam::959632173666:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "ollama",
      "image": "public.ecr.aws/x6i8o2b8/ollama-gemma:latest",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 11434,
          "protocol": "tcp"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/ollama-gemma",
          "awslogs-region": "us-east-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
EOF

# Create Log Group
aws logs create-log-group --log-group-name /ecs/ollama-gemma --region us-east-2 || true

# Register the Task
aws ecs register-task-definition --cli-input-json file://ollama-gemma-task.json

# Create security group for Ollama
aws ec2 create-security-group \
  --group-name ollama-sg \
  --description "Allow access to Ollama port 11434" \
  --vpc-id $VPC_ID

# Authorize inbound traffic on port 11434
aws ec2 authorize-security-group-ingress \
  --group-name ollama-sg \
  --protocol tcp \
  --port 11434 \
  --cidr 0.0.0.0/0

SUBNET_ID="subnet-06e4e5009a4f330ef"
SG_ID="sg-0064e5241bb898028"

# Run the ECS service
aws ecs create-service \
  --cluster cve_rag_pipline \
  --service-name ollama-service \
  --task-definition ollama-gemma-task \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration '{
    "awsvpcConfiguration": {
      "subnets": ["subnet-06e4e5009a4f330ef"],
      "securityGroups": ["sg-0064e5241bb898028"],
      "assignPublicIp": "ENABLED"
    }
  }'

#1. Get the Network Interface ID
aws ecs describe-tasks \
--cluster cve_rag_pipline \
--tasks <task-id> \
--query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' \
--output text
#2. Look Up the Public IP from ENI
aws ec2 describe-network-interfaces \
  --network-interface-ids <eni-id> \
  --query 'NetworkInterfaces[0].Association.PublicIp' \
  --output text

#  Final Test
curl http://<your-public-ip>:11434/api/tags




### --- DOCKER + ECR SETUP Cyberlab-api --- ###

# Build Docker image
docker build -t cyberlab-api .

# Tag image for ECR Public
docker tag cyberlab-api:latest public.ecr.aws/x6i8o2b8/cyberlab-api:latest

# Authenticate with ECR Public
aws ecr-public get-login-password --region us-east-1 | \
docker login --username AWS --password-stdin public.ecr.aws

# Create public ECR repo (no error if it exists)
aws ecr-public create-repository --repository-name cyberlab-api --region us-east-1 || true

# Push image to ECR Public
docker push public.ecr.aws/x6i8o2b8/cyberlab-api:latest

# Create Log Group
aws logs create-log-group --log-group-name /ecs/cyberlab-api --region us-east-2 || true

# Create Role
aws iam create-role \
  --role-name ecsTaskRoleWithS3AndDynamo \
  --assume-role-policy-document file://<(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
)

# Attach a Permission Policy to the Role
aws iam attach-role-policy \
  --role-name ecsTaskRoleWithS3AndDynamo \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

aws iam attach-role-policy \
  --role-name ecsTaskRoleWithS3AndDynamo \
  --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess

# Register ECS Task Definition Cyberlab-api #

cat > cyberlab-api-task-def.json <<EOF
{
  "family": "cyberlab-api-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "4096",
  "executionRoleArn": "arn:aws:iam::959632173666:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::959632173666:role/ecsTaskRoleWithS3AndDynamo",
  "containerDefinitions": [
    {
      "name": "cyberlab-api",
      "image": "public.ecr.aws/x6i8o2b8/cyberlab-api:latest",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 5000,
          "protocol": "tcp"
        }
      ],
	  "essential": true,
	  "environment": [
        { "name": "CHROMA_URL", "value": "http://18.191.240.68:8000" },
        { "name": "CHROMA_DB_MINILM_MODEL_NAME", "value": "all-MiniLM-L6-v2" },
        { "name": "CHROMA_DB_MINILM_COLLECTION_NAME", "value": "cves_minilm" },
        { "name": "OLLAMA_HOST", "value": "http://3.137.186.44:11434" },
        { "name": "OLLAMA_MODEL", "value": "gemma:2b" },
        { "name": "S3_BUCKET", "value": "cve-rag-pipline-bucket" },
        { "name": "S3_PREFIX", "value": "lectures/" },
        { "name": "DYNAMODB_TABLE", "value": "CyberlabHighlights" },
        { "name": "AWS_REGION", "value": "us-east-2" }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/cyberlab-api",
          "awslogs-region": "us-east-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
EOF

# Register the Task
aws ecs register-task-definition --cli-input-json file://cyberlab-api-task-def.json

# Create security group for Cyberlab-api
aws ec2 create-security-group \
  --group-name cyberlab-api-sg \
  --description "Security group for cyberlab-api ECS service" \
  --vpc-id vpc-0e23a80099b2d4ec2

aws ec2 authorize-security-group-ingress \
  --group-id sg-0c937126d8036686c \
  --protocol tcp \
  --port 5000 \
  --cidr 0.0.0.0/0

# Run the ECS service

aws ecs create-service \
  --cluster cve_rag_pipline \
  --service-name cyberlab-api-service \
  --task-definition cyberlab-api-task \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration '{
    "awsvpcConfiguration": {
      "subnets": ["subnet-06e4e5009a4f330ef"],
      "securityGroups": ["sg-0c937126d8036686c"],
      "assignPublicIp": "ENABLED"
    }
  }'

