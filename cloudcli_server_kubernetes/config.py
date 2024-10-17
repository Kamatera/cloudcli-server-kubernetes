import os

from dotenv import load_dotenv


load_dotenv()


KAMATERA_API_SERVER = os.getenv("KAMATERA_API_SERVER", 'https://cloudcli.cloudwm.com')
KAMATERA_API_CLIENT_ID = os.getenv("KAMATERA_API_CLIENT_ID")
KAMATERA_API_SECRET = os.getenv("KAMATERA_API_SECRET")

CLOUDCLI_DEBUG = os.getenv("CLOUDCLI_DEBUG", "no").lower() in ['1', 'true', "yes"]
