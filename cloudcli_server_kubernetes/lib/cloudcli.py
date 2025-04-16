import time
import logging
import secrets
import datetime

import requests

from .. import config, common


class CloudcliApiException(common.CloudcliException):
    pass


CREATE_SERVER_COMMAND_INFO = 'Create Server'


def get_auth_client_id_secret(creds):
    if creds is not None:
        auth_client_id, auth_secret = creds
    else:
        auth_client_id = config.KAMATERA_API_CLIENT_ID
        auth_secret = config.KAMATERA_API_SECRET
    if not auth_client_id or not auth_secret:
        raise CloudcliApiException("Auth credentials are missing")
    return auth_client_id, auth_secret


def cloudcli_server_request(path, creds, **kwargs):
    auth_client_id, auth_secret = get_auth_client_id_secret(creds)
    url = "%s%s" % (config.KAMATERA_API_SERVER, path)
    method = kwargs.pop("method", "GET")
    res = requests.request(method=method, url=url, headers={
        "AuthClientId": auth_client_id,
        "AuthSecret": auth_secret,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }, **kwargs)
    try:
        data = res.json()
    except:
        data = None
    return res.status_code, data


def find_server_command_in_queue(command_info, server_name_startswith, creds):
    status, res = cloudcli_server_request("/svc/queue", creds=creds)
    assert status == 200
    for row in res:
        if (
            str(row.get('commandInfo')) == command_info
            and str(row.get('serviceName')).startswith(server_name_startswith)
        ):
            return row['id']
    return None


def get_server_info(creds, name_startswith):
    common.logging.debug(f'cloudcli get_server_info name_startswith={name_startswith}')
    status, res = cloudcli_server_request("/service/server/info", creds, method="POST", json={"name": f'{name_startswith}-.*'})
    if status != 200:
        assert 'No servers found' in res['message'], f'Unexpected error {status}: {res}'
        res = []
    if len(res) == 0:
        return None
    elif len(res) > 1:
        raise Exception(f"Multiple matching servers found: {','.join([s['name'] for s in res])}")
    else:
        return res[0]


def get_server_name(name_startswith):
    return f'{name_startswith}-{secrets.token_urlsafe(5)}'


def get_command_status(creds, command_id) -> dict:
    status, response = cloudcli_server_request("/service/queue?id=" + str(command_id), creds)
    if status != 200 or len(response) != 1 or not isinstance(response[0], dict):
        return {}
    else:
        return response[0]


def wait_command(creds, command_id):
    logging.debug("Waiting for command_id to complete %s" % command_id)
    wait_poll_interval_seconds = 2
    wait_timeout_seconds = 3600
    start_time = datetime.datetime.now()
    max_time = start_time + datetime.timedelta(seconds=wait_timeout_seconds)
    time.sleep(wait_poll_interval_seconds)
    command = {}
    while True:
        if max_time < datetime.datetime.now():
            logging.warning("WARNING! Timeout waiting for command (timeout_seconds={0}, command_id={1})".format(
                str(wait_timeout_seconds), str(command_id)
            ))
            return command
        time.sleep(wait_poll_interval_seconds)
        command = get_command_status(creds, command_id)
        if command.get("status") in ["complete", "error"]:
            return command


def get_server_public_private_ips(server_info):
    public_ip, private_ip = None, None
    for network in server_info['networks']:
        if not public_ip and network['network'].startswith('wan-'):
            public_ip = network['ips'][0]
        elif not private_ip:
            private_ip = network['ips'][0]
    assert public_ip and private_ip, 'Both public and private IPs are required'
    return public_ip, private_ip
