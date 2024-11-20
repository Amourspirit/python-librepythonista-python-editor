import os
from dotenv import load_dotenv
import subprocess

# Load environment variables from .env file
load_dotenv()

# Get the username and password from environment variables
token = os.getenv("UV_PUBLISH_TOKEN_TEST")

# Command to publish to Test PyPI
command = [
    "uv",
    "publish",
    "--token",
    f"{token}",
    "--publish-url",
    "https://test.pypi.org/legacy/",
]


# Run the command and provide the username and password
process = subprocess.Popen(
    command,
    # stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
stdout, stderr = process.communicate()

# Print the output and error (if any)
print(stdout)
print(stderr)
