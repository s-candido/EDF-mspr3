#!/bin/bash
set -e

echo "=== ML Platform k3s Deployment Script for OVH Cloud ==="

# Configuration
S3_BUCKET="ml-platform-storage"
OVH_REGION="gra"
S3_ENDPOINT="https://s3.${OVH_REGION}.cloud.ovh.net"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check prerequisites
command -v kubectl >/dev/null 2>&1 || { log_error "kubectl is required but not installed."; exit 1; }
command -v kustomize >/dev/null 2>&1 || { log_warn "kustomize not found. Will use kubectl apply -k"; }
command -v helm >/dev/null 2>&1 || { log_warn "helm not found. Some installations may fail."; }

# Get secrets from user
log_info "Please set your OVH S3 credentials:"
read -p "AWS Access Key ID: " AWS_ACCESS_KEY_ID
read -sp "AWS Secret Access Key: " AWS_SECRET_ACCESS_KEY
echo ""

# Update secrets file with actual credentials
sed -i "s/your-s3-access-key/${AWS_ACCESS_KEY_ID}/g" base/secrets.yaml
sed -i "s/your-s3-secret-key/${AWS_SECRET_ACCESS_KEY}/g" base/secrets.yaml

log_info "Creating S3 bucket if not exists..."
# Create S3 bucket using OVH S3 API or aws cli
if command -v aws >/dev/null 2>&1; then
    aws s3 mb s3://${S3_BUCKET} --endpoint-url ${S3_ENDPOINT} 2>/dev/null || log_warn "Bucket may already exist"
else
    log_warn "aws cli not found. Please create bucket manually at ${S3_ENDPOINT}"
fi

log_info "Installing k3s on OVH server..."
# SSH to OVH server and install k3s
read -p "OVH Server IP: " OVH_IP
read -p "SSH User (default: root): " SSH_USER
SSH_USER=${SSH_USER:-root}

ssh ${SSH_USER}@${OVH_IP} << 'ENDSSH'
curl -sfL https://get.k3s.io | sh -
mkdir -p /var/lib/rancher/k3s/storage
ENDSSH

# Configure kubectl
scp ${SSH_USER}@${OVH_IP}:/etc/rancher/k3s/k3s.yaml ./k3s.yaml
export KUBECONFIG=./k3s.yaml

log_info "Waiting for k3s to be ready..."
kubectl wait --for=condition=ready node --all --timeout=120s

# Install local-path provisioner for PVCs
log_info "Installing local-path provisioner..."
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.24/deploy/local-path-storage.yaml

# Patch local-path as default storage class
kubectl patch storageclass local-path -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'

# Install S3FS CSI driver for S3-backed storage
log_info "Installing S3FS CSI driver..."
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/s3fs-csi-driver/master/deploy/kubernetes/base/csidriver.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/s3fs-csi-driver/master/deploy/kubernetes/base/rbac.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/s3fs-csi-driver/master/deploy/kubernetes/base/nodeplugin.yaml

# Create secret for S3 credentials
log_info "Creating S3 credentials secret..."
kubectl create secret generic s3-credentials \
    --from-literal=aws_access_key_id=${AWS_ACCESS_KEY_ID} \
    --from-literal=aws_secret_access_key=${AWS_SECRET_ACCESS_KEY} \
    -n ml-platform || true

# Deploy the platform
log_info "Deploying ML Platform..."
kubectl apply -k k8s/overlays/production

# Wait for deployments
log_info "Waiting for deployments to be ready..."
kubectl wait --for=condition=available deployment/postgresql -n ml-platform --timeout=300s
kubectl wait --for=condition=available deployment/redis -n ml-platform --timeout=300s
kubectl wait --for=condition=available deployment/mlflow -n ml-platform --timeout=300s
kubectl wait --for=condition=available deployment/airflow-scheduler -n ml-platform --timeout=300s
kubectl wait --for=condition=available deployment/airflow-webserver -n ml-platform --timeout=300s
kubectl wait --for=condition=available deployment/airflow-worker -n ml-platform --timeout=300s

log_info "Deployment complete!"
echo ""
echo "=== Access URLs ==="
echo "Airflow Webserver: http://${OVH_IP}:8080"
echo "MLflow Tracking: http://${OVH_IP}:5000"
echo ""
echo "Login credentials:"
echo "  Airflow: admin / admin123"
echo "  MLflow: No authentication (internal network only)"
echo ""
echo "To check status: kubectl get pods -n ml-platform"
echo "To view logs: kubectl logs -n ml-platform -l app=airflow -f"
