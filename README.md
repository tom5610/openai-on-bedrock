# OpenAI on Amazon Bedrock

Run **OpenAI GPT-5.5 / GPT-5.4** inference on **Amazon Bedrock** using the standard
[OpenAI Python SDK](https://github.com/openai/openai-python).

Bedrock exposes an OpenAI-compatible endpoint ("Mantle"), so you keep the familiar
`OpenAI` client and Responses API — you just point it at Bedrock and authenticate with
your AWS credentials. This project shows two ways to authenticate:

- **`main.py`** — mint a short-lived **bearer token** from your AWS credentials and pass
  it as the API key (simplest).
- **`main_sigv4.py`** — **SigV4-sign** each request directly from your AWS credentials
  via a custom `httpx` client (nothing to mint or refresh).

All processing stays within the Bedrock Region you select.

## How it works

In every case the OpenAI SDK is pointed at the Bedrock Mantle base URL; only the
authentication differs between the two scripts:

| Setting | Value |
| --- | --- |
| `OPENAI_BASE_URL` | `https://bedrock-mantle.{region}.api.aws/openai/v1` |
| Auth (`main.py`) | A short-lived Bedrock **bearer token** minted from your AWS credentials, passed as `OPENAI_API_KEY` |
| Auth (`main_sigv4.py`) | A **SigV4 signature** added to each request by a custom `httpx` client; the API key is an unused placeholder |

`main.py` mints the token at runtime from your AWS credentials with
[`aws-bedrock-token-generator`](https://pypi.org/project/aws-bedrock-token-generator/),
so there is no long-lived API key to manage:

```python
from aws_bedrock_token_generator import provide_token

token = provide_token(region="us-east-1")  # uses your AWS credential chain
```

`main_sigv4.py` instead signs each request directly — see
[SigV4 variant](#sigv4-variant-main_sigv4py) below.

## Models & Regions

| Model | Model ID | Available regions |
| --- | --- | --- |
| GPT-5.5 (complex reasoning + coding) | `openai.gpt-5.5` | `us-east-1` (US East, N. Virginia), `us-east-2` (US East, Ohio) |
| GPT-5.4 (best price-performance)     | `openai.gpt-5.4` | `us-east-1`, `us-east-2`, `us-west-2` (US West, Oregon) |

The auth region (bearer-token region or SigV4 signing region), the base URL, and the
model region must all match. Both `main.py` and `main_sigv4.py` default to `us-east-1`,
but every supported Region works — so pick whichever your credentials and
model access cover.

## Prerequisites

- Python >= 3.13 and [uv](https://docs.astral.sh/uv/)
- AWS credentials available in your environment for the target region (see
  [AWS credentials](#aws-credentials) below), with Bedrock access to the OpenAI models
- Access to the OpenAI models enabled in the Bedrock console for that region

## Setup & Run

### AWS credentials

`main.py` calls `provide_token(region=REGION)` to mint the Bedrock bearer token from
your **standard AWS credential chain** — so you must have valid credentials resolvable
*before* you run it. The token is Region-scoped, so those credentials must be for the
same Region as `REGION` in `main.py` (`us-east-1` by default) and have Bedrock access
to the OpenAI models there.

The simplest setup is to select a configured profile with `AWS_PROFILE`:

```bash
export AWS_PROFILE=my-profile
export AWS_REGION=us-east-1   # optional; should match REGION in main.py
```

Alternatively, export `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` directly, or run
`aws configure`. Verify credentials resolve before running:

```bash
aws sts get-caller-identity   # confirms your identity / that credentials are valid
```

### Install & run

```bash
uv sync          # install dependencies from the lockfile
uv run main.py   # mint a token and call the model
```

The same credentials work for either entry point:

```bash
uv run main_sigv4.py   # SigV4-sign each request and call the model
```

`main.py` sends a single prompt and prints the response:

```python
import os
from aws_bedrock_token_generator import provide_token
from openai import OpenAI

REGION = "us-east-1"
token = provide_token(region=REGION)

os.environ["OPENAI_API_KEY"] = token
os.environ["OPENAI_BASE_URL"] = f"https://bedrock-mantle.{REGION}.api.aws/openai/v1"

client = OpenAI()
response = client.responses.create(
    model="openai.gpt-5.5",
    input=[{"role": "user", "content": "Hello!"}],
)
print(response.output_text)
```

### SigV4 variant (`main_sigv4.py`)

Instead of minting a bearer token, `main_sigv4.py` signs every request with **SigV4** —
the same scheme the AWS SDKs use — directly from your AWS credential chain. There is no
token to mint or refresh, which suits long-running processes; the trade-off is a small
custom `httpx` auth hook. It defaults to `us-east-1` and requires `boto3` (already in the
dependencies).

The OpenAI client is unchanged except for the custom `http_client`, whose auth hook
re-signs each outgoing request:

```python
import boto3, httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from openai import OpenAI

REGION, SERVICE = "us-east-1", "bedrock"

class SigV4HttpxAuth(httpx.Auth):
    requires_request_body = True  # the body is hashed into the signature

    def __init__(self, credentials, service, region):
        self.credentials, self.service, self.region = credentials, service, region

    def auth_flow(self, request):
        aws_request = AWSRequest(
            method=request.method,
            url=str(request.url),
            data=request.content,
            headers={"Content-Type": "application/json"},
        )
        SigV4Auth(self.credentials, self.service, self.region).add_auth(aws_request)
        for name, value in aws_request.headers.items():
            request.headers[name] = value
        yield request

client = OpenAI(
    base_url=f"https://bedrock-mantle.{REGION}.api.aws/openai/v1",
    api_key="not-used",  # placeholder; real auth is the SigV4 signature
    http_client=httpx.Client(auth=SigV4HttpxAuth(boto3.Session().get_credentials(), SERVICE, REGION)),
)
```

Notes specific to SigV4:

- `requires_request_body = True` forces `httpx` to materialize the body before signing,
  since SigV4 hashes it into the signature; without it you can hit intermittent signature
  mismatches.
- Requests are signed against the `bedrock` service. The signing region must match the
  base URL Region and the model's Region.
- Only `Content-Type` is signed; headers `httpx` adds afterward (e.g. `user-agent`) are
  outside `SignedHeaders`, so they don't invalidate the signature.

## IAM permissions

The caller needs permission to invoke Bedrock Mantle. Both entry points perform inference,
so both need `bedrock-mantle:CreateInference`; the bearer-token path additionally passes
through an auth gate — which is what lets you scope down to least privilege:

| Script | Auth | IAM actions |
| --- | --- | --- |
| `main.py` | Bedrock bearer token | `bedrock-mantle:CreateInference` **+** `bedrock-mantle:CallWithBearerToken` |
| `main_sigv4.py` | SigV4-signed request | `bedrock-mantle:CreateInference` |

The quickest setup is to attach the AWS-managed policy
[`AmazonBedrockMantleInferenceAccess`](https://docs.aws.amazon.com/bedrock/latest/userguide/security-iam-awsmanpol.html#security-iam-awsmanpol-AmazonBedrockMantleInferenceAccess),
which grants both actions (plus `bedrock-mantle:Get*`/`List*` and Marketplace subscribe).
For least privilege, grant only the action(s) your script actually uses (see below).

#### Why each script needs a different action

The two actions sit at different layers, which is why the choice of *auth* — not the choice
of model — decides what you grant:

- **`CreateInference` is the inference *operation*.** Every inference call needs it,
  regardless of auth. A SigV4-signed request authenticates as your IAM principal directly and
  authorizes as this native operation — so `main_sigv4.py` needs `CreateInference` alone.
- **`CallWithBearerToken` is an auth-method *gate*.** A bearer token (Bedrock API key) is
  presented as an `Authorization: Bearer …` header; Bedrock resolves it to the IAM principal
  that minted it and first checks whether that principal may *use the bearer-token path at
  all*. That gate is the action — hence it's granted on `Resource: "*"` (it guards a method,
  not a project), and a `Deny` on it is the documented kill switch for a leaked key.

So `main.py` (bearer token) needs **both**: it passes the `CallWithBearerToken` gate and then
performs `CreateInference` (verified — a bearer-token call missing either is denied).
`main_sigv4.py` (SigV4) skips the gate and needs only `CreateInference`. The managed policy
grants both because it supports either auth style; a least-privilege role grants only what its
auth mode uses. (A short-term token also inherits the full permissions of the principal that
minted it, so keep that principal scoped too.)

### Least-privilege policy (`main_sigv4.py`)

SigV4 inference needs just `CreateInference`, scoped to the Region(s) you call:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "MantleInferenceSigV4",
      "Effect": "Allow",
      "Action": "bedrock-mantle:CreateInference",
      "Resource": [
        "arn:aws:bedrock-mantle:us-east-1:ACCOUNT_ID:project/*",
        "arn:aws:bedrock-mantle:us-east-2:ACCOUNT_ID:project/*"
      ]
    }
  ]
}
```

- Replace `ACCOUNT_ID` and keep only the Region(s) you use (GPT-5.5 runs in `us-east-1` /
  `us-east-2`). If you know your Mantle project ID, narrow `project/*` to `project/<id>`.
- If a call returns `AccessDenied`, the IAM error names the exact missing `bedrock-mantle:`
  action — add precisely that. (A plain `responses.create` shouldn't need `Get*`/`List*`.)

### Least-privilege policy (`main.py`)

The bearer-token path adds the auth gate on top of inference. Keep `CreateInference`
Region-scoped and grant the gate on `"*"` (it isn't resource-scopable):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "MantleInference",
      "Effect": "Allow",
      "Action": "bedrock-mantle:CreateInference",
      "Resource": [
        "arn:aws:bedrock-mantle:us-east-1:ACCOUNT_ID:project/*",
        "arn:aws:bedrock-mantle:us-east-2:ACCOUNT_ID:project/*"
      ]
    },
    {
      "Sid": "MantleBearerTokenGate",
      "Effect": "Allow",
      "Action": "bedrock-mantle:CallWithBearerToken",
      "Resource": "*"
    }
  ]
}
```

### EKS service role

Attach the permissions policy above to the role, then let a pod assume it via a trust
policy. Use **EKS Pod Identity** (recommended) or **IRSA**:

**EKS Pod Identity:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "pods.eks.amazonaws.com" },
      "Action": ["sts:AssumeRole", "sts:TagSession"]
    }
  ]
}
```

**IRSA (IAM Roles for Service Accounts, via OIDC):**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/oidc.eks.<region>.amazonaws.com/id/<OIDC_ID>" },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "oidc.eks.<region>.amazonaws.com/id/<OIDC_ID>:sub": "system:serviceaccount:<namespace>:<service-account>",
          "oidc.eks.<region>.amazonaws.com/id/<OIDC_ID>:aud": "sts.amazonaws.com"
        }
      }
    }
  ]
}
```

In the pod, `boto3.Session().get_credentials()` resolves the role automatically (web
identity token or the Pod Identity agent) — no change to `main_sigv4.py`.

## Notes

- **Use the Responses API** (`client.responses.create`), not Chat Completions — it is the
  supported interface and enables model-managed multi-turn state, hosted tools, and
  long-running background work.
- **Reasoning effort:** GPT-5.5 defaults to `medium`; GPT-5.4 requires you to set it
  explicitly. Pass it via `reasoning={"effort": "medium"}`.
- **Pricing** is pay-per-token with no seat licenses; under high demand requests are
  queued rather than rejected. See the [Bedrock pricing page](https://aws.amazon.com/bedrock/pricing/).
- **Codex** (the GPT-5.5-powered coding agent) can target Bedrock too — set
  `AWS_BEARER_TOKEN_BEDROCK` and configure `~/.codex/config.toml` with
  `model_provider = "amazon-bedrock"`.

## References

- [Get started with OpenAI GPT-5.5, GPT-5.4 models and Codex on Amazon Bedrock](https://aws.amazon.com/blogs/aws/get-started-with-openai-gpt-5-5-gpt-5-4-models-and-codex-on-amazon-bedrock/)
- [OpenAI models with Amazon Bedrock (cookbook)](https://developers.openai.com/cookbook/examples/partners/aws/openai_models_with_amazon_bedrock)
- [OpenAI Responses API examples](https://github.com/openai/openai-cookbook/tree/main/examples/responses_api)
