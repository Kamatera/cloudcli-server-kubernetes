#!/usr/bin/env python3
import os
import sys
import json

from ruamel.yaml import YAML


def main(input_file=None):
    if not input_file:
        input_file = 'tests/cluster_full.yaml'
    with open(input_file) as f:
        data = YAML(typ='safe').load(f)
    with open(os.path.expanduser(data['cluster']['ssh-key']['private'])) as f:
        data['cluster']['ssh-key']['private'] = f.read()
    with open(os.path.expanduser(data['cluster']['ssh-key']['public'])) as f:
        data['cluster']['ssh-key']['public'] = f.read()
    print(json.dumps(data))


if __name__ == "__main__":
    main(*sys.argv[1:])
