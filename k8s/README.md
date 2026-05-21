# OVH Cloud k3s Deployment Guide

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     OVH Cloud Server (k3s)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Airflow   │  │   MLflow    │  │   PostgreSQL Databases  │  │
│  │  Webserver  │  │   Server    │  │  ┌──────┐ ┌──────┐      │  │
│  │  Scheduler  │  │             │  │  │Airflow│ │MLflow│      │  │
│  │  Workers(x2)│  │             │  │  │   DB  │ │  DB  │      │  │
│  └──────┬──────┘  └──────┬──────┘  │  └──────┘ └──────┘      │  │
│         │                │         │  ┌──────┐                │  │
│         └────────┬───────┘         │  │  EDF │                │  │
│                  │                 │  │DataDB │                │  │
│         ┌────────▼────────┐        │  └──────┘                │  │
│         │      Redis      │        └─────────────────────────┘  │
│         │   (Celery BM)   │                                     │
│         └─────────────────┘                                     │
│                              ┌───────────────────────────────┐ │
│                              │   OVH Object Storage (S3)      │ │
│                              │   ┌─────────────────────────┐  │ │
│                              │   │ • MLflow Artifacts      │  │ │
│                              │   │ • Airflow DAGs          │  │ │
│                              │   │ • Airflow Logs          │  │ │
│                              │   │ • Raw Data Storage      │  │ │
│                              │   └─────────────────────────┘  │ │
│                              └───────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

- OVH Cloud Server with Ubuntu 22.04+
- S3 compatible storage bucket (OVH Object Storage)
- SSH access to the server
- `kubectl` installed locally
- `kustomize` installed locally (optional)

## S3 Storage Setup

1. Create an S3 bucket in OVH Object Storage:
   ```bash
   # Using OVH API or OVH Control Panel
   # Region: GRA (Paris) or your preferred region
   # Bucket name: ml-platform-storage
   ```

2. Generate S3 credentials:
   - Go to OVH Control Panel → Object Storage → S3
   - Create user and generate S3 keys

## Deployment

### 1. Update Secrets

Edit `k8s/base/secrets.yaml` with your actual credentials:

```yaml
stringData:
  AWS_ACCESS_KEY_ID: "your-actual-access-key"
  AWS_SECRET_ACCESS_KEY: "your-actual-secret-key"
  S3_ENDPOINT_URL: "https://s3.gra.cloud.ovh.net"
```

### 2. Install k3s on OVH Server

```bash
# SSH to your OVH server
ssh root@your-ovh-server-ip

# Install k3s
curl -sfL https://get.k3s.io | sh -

# Get kubeconfig
cat /etc/rancher/k3s/k3s.yaml
```

### 3. Configure Local kubectl

```bash
# Copy kubeconfig locally
export KUBECONFIG=~/k3s-config
# Edit and replace server IP with your OVH server IP
```

### 4. Install Storage Provisioner

```bash
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.24/deploy/local-path-storage.yaml

# Set as default
kubectl patch storageclass local-path \
  -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

### 5. Install S3FS CSI Driver

For S3-backed persistent volumes:

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/s3fs-csi-driver/master/deploy/kubernetes/base/csidriver.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/s3fs-csi-driver/master/deploy/kubernetes/base/rbac.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/s3fs-csi-driver/master/deploy/kubernetes/base/nodeplugin.yaml
```

### 6. Deploy ML Platform

```bash
# Clone and navigate to k8s directory
cd k8s

# Deploy
kubectl apply -k overlays/production

# Or with kustomize
kustomize build overlays/production | kubectl apply -f -
```

## Services Access

| Service | Port | URL |
|---------|------|-----|
| Airflow Webserver | 8080 | `http://<server-ip>:8080` |
| MLflow Tracking | 5000 | `http://<server-ip>:5000` |

## Default Credentials

| Service | Username | Password |
|---------|----------|----------|
| Airflow | admin | admin123 |
| PostgreSQL (Airflow) | airflow | airflow |
| PostgreSQL (MLflow) | mlflow | mlflow-pwd |
| PostgreSQL (EDF) | postgres | postgres |

## Volume Strategy

| Volume | Storage Type | Purpose |
|--------|-------------|---------|
| `s3-raw-storage` | S3 (OVH Object Storage) | DAGs, MLflow artifacts, logs |
| `postgres-*-pvc` | local-path (HostPath) | Database persistence |
| `redis-pvc` | local-path (HostPath) | Celery broker state |

## Useful Commands

```bash
# Check pods
kubectl get pods -n ml-platform

# View logs
kubectl logs -n ml-platform deployment/airflow-scheduler -f
kubectl logs -n ml-platform deployment/airflow-worker-0 -f

# Scale workers
kubectl scale deployment airflow-worker --replicas=4 -n ml-platform

# Restart deployment
kubectl rollout restart deployment/airflow-scheduler -n ml-platform

# Check PVCs
kubectl get pvc -n ml-platform

# Check resource usage
kubectl top pods -n ml-platform
```

## Scaling

### Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: airflow-worker-hpa
  namespace: ml-platform
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: airflow-worker
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

## Troubleshooting

### Pods not starting

```bash
kubectl describe pod <pod-name> -n ml-platform
kubectl logs <pod-name> -n ml-platform
```

### S3 mount issues

```bash
# Check CSI driver
kubectl get pods -n kube-system | grep csi-s3

# Check S3 credentials
kubectl get secret s3-credentials -n ml-platform
```

### Database connection issues

```bash
# Wait for PostgreSQL
kubectl wait --for=condition=ready pod -l app=postgresql -n ml-platform --timeout=300s
```

## Cleanup

```bash
kubectl delete -k overlays/production
kubectl delete pvc --all -n ml-platform
```
