# cloudcli k8s usage example

Following is a minimal usage example which will create 1 controlplane node and 3 worker nodes.

## Prerequisites

* Latest cloudcli installed and configured with your credentials
* Bash shell
* `jq` installed to parse JSON output

Create the following bash functions to make it easier to run the commands:

```bash
CLOUDCLI_K8S_KCONFIG=mycluster.yaml
function cloudcli_k8s_task_status() {
  cloudcli k8s task_status --task_id $CLOUDCLI_K8S_TASK_ID
}
function cloudcli_k8s_task_start() {
  CLOUDCLI_K8S_TASK_ID=$(cloudcli k8s $@ --kconfig $CLOUDCLI_K8S_KCONFIG | jq -r .task_id)
  while true; do
    if [ "$(cloudcli_k8s_task_status | jq -r .state)" == "PENDING" ]; then
      echo task_id: $CLOUDCLI_K8S_TASK_ID - PENDING...
      sleep 1
    else
      local status=$(cloudcli_k8s_task_status)
      echo task_id: $(echo $status | jq -r .task_id)
      echo task_name: $(echo $status | jq -r .task_name)
      echo state: $(echo $status | jq -r .state)
      break
    fi
  done
}
```

## Create Cluster

Create the cluster config file at `mycluster.yaml`, see comments for details to fill-in:

```yaml
cluster:
  # unique cluster name, should be short, it will be used as prefix for all resources
  name: ""
  # Kamatera datacenter
  datacenter: ""
  ssh-key:
    # Paste private and public ssh keys here, this is required and will be used to access the nodes
    private: |  
      -----BEGIN OPENSSH PRIVATE KEY-----
      ...
      -----END OPENSSH PRIVATE KEY-----
    public: |
      ssh-....
  private-network:
    # Kamatera private network name which will be used for cluster internal communication
    name: ""

node-pools:
  worker1:
    nodes: 3
    node-config:
      cpu: 4B
      memory: 2048
```

Create cluster

```bash
cloudcli_k8s_task_start create_cluster
```

You can check the full status of the last task with:

```bash
cloudcli_k8s_task_status
```

## Connect to the cluster

Get the cluster status:

```bash
cloudcli_k8s_task_start status
cloudcli_k8s_task_status | jq .result
```

Get the cluster kubeconfig file

```bash
cloudcli_k8s_task_start kubeconfig
cloudcli_k8s_task_status | jq -r .result > .kubeconfig
```

Now you can run kubectl commands against the cluster:

```bash
export KUBECONFIG=.kubeconfig
kubectl get nodes
```

## Add nodes to a node pool

Edit the cluster config file `mycluster.yaml` and change the number of nodes in the worker1 node pool to 5.

Start the create nodepool task - it will create any missing nodes in the nodepool

```bash
cloudcli_k8s_task_start create_nodepool --nodepool_name worker1
```
