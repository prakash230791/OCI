# OCI Homelab - Variable Definitions
# All values are supplied at runtime via terraform.tfvars (generated from GitHub Secrets)
# No defaults are set — a missing value will cause Terraform to error early and clearly.

variable "tenancy_ocid" {
  description = "OCID of the OCI tenancy (root compartment). Found in OCI Console → Profile → Tenancy."
  type        = string
  sensitive   = true
}

variable "user_ocid" {
  description = "OCID of the OCI IAM user whose API key is used. Found in OCI Console → Profile → My Profile."
  type        = string
  sensitive   = true
}

variable "fingerprint" {
  description = "MD5 fingerprint of the API key uploaded to the OCI user. Found in OCI Console → My Profile → API Keys."
  type        = string
  sensitive   = true
}

variable "private_key" {
  description = "PEM-formatted RSA private key that corresponds to the uploaded API key fingerprint."
  type        = string
  sensitive   = true
}

variable "region" {
  description = "OCI region identifier, e.g. ap-mumbai-1, us-ashburn-1. Found in OCI Console top-right region selector."
  type        = string
}

variable "ssh_public_key" {
  description = "SSH public key (ed25519 or RSA) to inject into the instance for ubuntu user login."
  type        = string
}

variable "ad_index" {
  description = "Zero-based index into the availability_domains list. Cycled by the deploy workflow to find an AD with free ARM capacity."
  type        = number
  default     = 0
}
