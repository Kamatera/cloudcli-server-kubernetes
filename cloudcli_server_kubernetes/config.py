import os
import json

from dotenv import load_dotenv


load_dotenv()


KAMATERA_API_SERVER = os.getenv("KAMATERA_API_SERVER", 'https://cloudcli.cloudwm.com')
KAMATERA_API_CLIENT_ID = os.getenv("KAMATERA_API_CLIENT_ID")
KAMATERA_API_SECRET = os.getenv("KAMATERA_API_SECRET")

CLOUDCLI_DEBUG = os.getenv("CLOUDCLI_DEBUG", "yes").lower() in ['1', 'true', "yes"]
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG" if CLOUDCLI_DEBUG else "INFO")

CELERY_BROKER = os.getenv('CELERY_BROKER', 'amqp://guest:guest@localhost:5672')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'db+postgresql://postgres:123456@localhost:5432/postgres')

RKE2_VERSION = os.getenv('RKE2_VERSION', 'v1.31.1+rke2r1')

DEFAULT_SERVER_CONFIG = json.loads(os.getenv('DEFAULT_SERVER_CONFIG', '''{
    "image": "ubuntu_server_24.04_64-bit",
    "cpu": "2B",
    "ram": "4096",
    "disk": "size=100",
    "dailybackup": "no",
    "managed": "no",
    "billingcycle": "hourly",
    "monthlypackage": ""
}'''))
