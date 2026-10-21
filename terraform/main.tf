terraform {
  required_version = ">= 1.5.0"
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.45"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ============================================================================
# Variables for Environment Separation (staging / prod) & Cost Control
# ============================================================================
variable "environment" {
  description = "Deployment environment name (staging or prod)"
  type        = string
  default     = "prod"
}

variable "aws_region" {
  description = "AWS region for managed storage and secrets"
  type        = string
  default     = "eu-central-1" # Frankfurt (closest to Hetzner fsn1)
}

variable "enable_aws_resources" {
  description = "Set to true to provision live AWS resources, or false for $0 cost validation"
  type        = bool
  default     = false
}

# ============================================================================
# Providers
# ============================================================================
provider "hcloud" {}

provider "aws" {
  region                      = var.aws_region
  skip_credentials_validation = !var.enable_aws_resources
  skip_requesting_account_id  = !var.enable_aws_resources
}

# ============================================================================
# 1. Hetzner Cloud Compute & Zero-Trust Firewall (Active Production)
# ============================================================================
resource "hcloud_server" "app_server" {
  name        = "leadflow-cx23"
  server_type = "cx23"
  image       = "rocky-9"
  location    = "fsn1"

  lifecycle {
    prevent_destroy = true
    ignore_changes  = [user_data, ssh_keys, labels, placement_group_id]
  }
}

# Zero-Trust Firewall: All HTTP/HTTPS traffic enters via Cloudflare Tunnel only
resource "hcloud_firewall" "zero_trust_fw" {
  name = "leadflow-zero-trust-fw-${var.environment}"

  # Allow ICMP (Ping) for basic health monitoring
  rule {
    direction  = "in"
    protocol   = "icmp"
    source_ips = ["0.0.0.0/0", "::/0"]
  }
}

# ============================================================================
# 2. AWS Managed Storage, Secrets & IAM (Hybrid Cloud Architecture)
# ============================================================================

# S3 Bucket for Audio Transcriptions & PDFs with Lifecycle Cost Optimization
resource "aws_s3_bucket" "media_storage" {
  count  = var.enable_aws_resources ? 1 : 0
  bucket = "leadflow-ai-media-${var.environment}"
}

resource "aws_s3_bucket_lifecycle_configuration" "media_lifecycle" {
  count  = var.enable_aws_resources ? 1 : 0
  bucket = aws_s3_bucket.media_storage[0].id

  rule {
    id     = "archive-and-expire-media"
    status = "Enabled"

    # Move audio recordings to cheap Glacier storage after 30 days
    transition {
      days          = 30
      storage_class = "GLACIER_IR"
    }

    # Permanently delete recordings after 365 days for privacy compliance (GDPR)
    expiration {
      days = 365
    }
  }
}

# Centralized Secrets Manager for Gemini API Keys, WhatsApp & Database
resource "aws_secretsmanager_secret" "app_secrets" {
  count       = var.enable_aws_resources ? 1 : 0
  name        = "leadflow-ai/${var.environment}/app-secrets"
  description = "Centralized secrets for Gemini API, WhatsApp tokens, and PostgreSQL"
}

# CloudWatch Log Group for FastAPI & AI Agent Audit Logs
resource "aws_cloudwatch_log_group" "agent_logs" {
  count             = var.enable_aws_resources ? 1 : 0
  name              = "/leadflow-ai/${var.environment}/fastapi-agents"
  retention_in_days = 30
}

# Least-Privilege IAM Policy for Application Backend
data "aws_iam_policy_document" "least_privilege_backend" {
  count = var.enable_aws_resources ? 1 : 0

  statement {
    sid       = "AllowReadAppSecretsOnly"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.app_secrets[0].arn]
  }

  statement {
    sid       = "AllowS3MediaReadWriteOnly"
    effect    = "Allow"
    actions   = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.media_storage[0].arn}/*"]
  }

  statement {
    sid       = "AllowCloudWatchLogIngestion"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.agent_logs[0].arn}:*"]
  }
}

resource "aws_iam_policy" "backend_policy" {
  count  = var.enable_aws_resources ? 1 : 0
  name   = "leadflow-ai-${var.environment}-least-privilege"
  policy = data.aws_iam_policy_document.least_privilege_backend[0].json
}