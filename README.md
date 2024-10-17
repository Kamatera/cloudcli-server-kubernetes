# cloudcli-server-kubernetes

Python CLI, API and Web App for managing Kamatera Kubernetes Clusters

## Local Development

```
poetry install
```

Create a `.env` file with the following content:

```
KAMATERA_API_CLIENT_ID=
KAMATERA_API_SECRET=
CLOUDCLI_DEBUG=yes
```

Create the cluster configuration file, you can use the example `tests/cluster_full.yaml`, just change the cluster name

Create the cluster (this creates the main controlplane node):

```
cloudclik8s create cluster.yaml
```

Add a worker node:

```
cloudclik8s add-worker cluster.yaml <NODEPOOL_NAME> <NODE_NUMBER>
```

Get cluster status with full details for all nodes:

```
cloudclik8s status cluster.yaml
```

SSH to the controlplane node to run kubectl commands (you can use the IP from the status command):

```
ssh root@<IP>
kubectl get nodes
```

Kubernetes is not accessible from the external internet, only from the internal ip of the controlplane node

kuberenetes ingress (ports 80, 443) and ssh are the only services exposed to the internet
