"""Invoke OpenAI GPT-5.5 on Amazon Bedrock's Mantle endpoint using SigV4 auth.

Unlike main.py (which mints a short-lived bearer token via
aws-bedrock-token-generator), this signs every outgoing request directly with the
caller's AWS credentials using SigV4 — the same scheme the AWS SDKs use. The OpenAI
SDK is otherwise unchanged: we just hand it a custom httpx client whose auth hook
signs each request before it goes out.
"""

import boto3
import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from openai import OpenAI

REGION = "us-east-1"
SERVICE = "bedrock"  # Bedrock Mantle requests are signed against the "bedrock" service


class SigV4HttpxAuth(httpx.Auth):
    """httpx auth hook that SigV4-signs each request with AWS credentials."""

    # The body is part of the SigV4 signature, so httpx must materialize it before
    # auth_flow runs.
    requires_request_body = True

    def __init__(self, credentials, service, region):
        self.credentials = credentials
        self.service = service
        self.region = region

    def auth_flow(self, request):
        # Re-create the outgoing request as a botocore AWSRequest, sign it, then copy
        # the signed headers back. We sign only the minimal header set (host /
        # x-amz-date / content-type, computed by SigV4Auth); headers httpx adds later
        # (user-agent, etc.) are outside SignedHeaders, so they don't break the
        # signature.
        aws_request = AWSRequest(
            method=request.method,
            url=str(request.url),
            data=request.content,
            headers={"Content-Type": "application/json"},
        )
        SigV4Auth(self.credentials, self.service, self.region).add_auth(aws_request)
        for name, value in aws_request.headers.items():
            request.headers[name] = value  # overwrites the OpenAI SDK's placeholder Authorization
        yield request


def main():
    credentials = boto3.Session().get_credentials()
    if credentials is None:
        raise SystemExit(
            "No AWS credentials found. Set AWS_PROFILE or AWS_ACCESS_KEY_ID/SECRET first."
        )

    client = OpenAI(
        base_url=f"https://bedrock-mantle.{REGION}.api.aws/openai/v1",
        api_key="not-used",  # placeholder; real auth is the SigV4 signature
        http_client=httpx.Client(auth=SigV4HttpxAuth(credentials, SERVICE, REGION)),
    )

    response = client.responses.create(
        model="openai.gpt-5.5",
        input="Hello!",
    )
    print(response.output_text)


if __name__ == "__main__":
    main()
