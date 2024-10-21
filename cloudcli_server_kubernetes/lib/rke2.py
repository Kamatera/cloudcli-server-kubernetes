import json
import base64

from .. import config


def get_rke2_config(node_name, is_server, cluster_server, cluster_token):
    rke2_config = {
        'node-name': node_name,
        'node-ip': "${PRIVATE_IP}",
        'node-external-ip': "${PUBLIC_IP}",
    }
    if cluster_server or cluster_token:
        assert cluster_server and cluster_token, 'Both cluster server and token are required to join an existing cluster'
        rke2_config['server'] = cluster_server
        rke2_config['token'] = cluster_token
    if is_server:
        rke2_config.update({
            'bind-address': "0.0.0.0",
            'advertise-address': "${PRIVATE_IP}",
            'tls-san': [
                "0.0.0.0",
                "${PRIVATE_IP}",
                "${PUBLIC_IP}"
            ]
        })
    else:
        assert cluster_server and cluster_token, 'Both cluster server and token are required for agent nodes'
    return rke2_config


def get_rke2_systemd_unit(is_server):
    rke2_type = 'server' if is_server else 'agent'
    return f'rke2-{rke2_type}'


def get_rke2_init_script(node_name, is_server, cluster_server, cluster_token):
    rke2_config = get_rke2_config(node_name, is_server, cluster_server, cluster_token)
    rke2_config_b64 = base64.b64encode(json.dumps(rke2_config).encode()).decode()
    rke2_type = 'server' if is_server else 'agent'
    return ' && '.join([
        "export PUBLIC_IP=$(echo $(ip -4 addr show dev eth0 | grep inet) | cut -d' ' -f2 | cut -d'/' -f1)",
        "export PRIVATE_IP=$(echo $(ip -4 addr show dev eth1 | grep inet) | cut -d' ' -f2 | cut -d'/' -f1)",
        'mkdir -p /etc/rancher/rke2',
        f'echo {rke2_config_b64} | base64 -d | envsubst > /etc/rancher/rke2/config.yaml',
        f'curl -sfL https://get.rke2.io | INSTALL_RKE2_VERSION={config.RKE2_VERSION} INSTALL_RKE2_TYPE={rke2_type} sh -',
        f'systemctl enable rke2-{rke2_type}',
        f'systemctl start rke2-{rke2_type}',
        "echo PATH='$PATH:/var/lib/rancher/rke2/bin' >> ~/.bashrc",
        'echo export KUBECONFIG=/etc/rancher/rke2/rke2.yaml >> ~/.bashrc',
    ])


def get_rke2_update_script(node_name, is_server, cluster_server, cluster_token):
    rke2_config = get_rke2_config(node_name, is_server, cluster_server, cluster_token)
    rke2_config_b64 = base64.b64encode(json.dumps(rke2_config).encode()).decode()
    rke2_type = 'server' if is_server else 'agent'
    return ' && '.join([
        "export PUBLIC_IP=$(echo $(ip -4 addr show dev eth0 | grep inet) | cut -d' ' -f2 | cut -d'/' -f1)",
        "export PRIVATE_IP=$(echo $(ip -4 addr show dev eth1 | grep inet) | cut -d' ' -f2 | cut -d'/' -f1)",
        f'echo {rke2_config_b64} | base64 -d | envsubst > /etc/rancher/rke2/config.yaml',
        f'curl -sfL https://get.rke2.io | INSTALL_RKE2_VERSION={config.RKE2_VERSION} INSTALL_RKE2_TYPE={rke2_type} sh -',
        f'systemctl restart rke2-{rke2_type}',
    ])
