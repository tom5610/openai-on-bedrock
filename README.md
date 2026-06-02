# openai-test

Run **OpenAI GPT-5.5 / GPT-5.4** inference on **Amazon Bedrock** using the standard
[OpenAI Python SDK](https://github.com/openai/openai-python).

Bedrock exposes an OpenAI-compatible endpoint ("Mantle"), so you keep the familiar
`OpenAI` client and Responses API — you just point it at Bedrock and authenticate with
an AWS-issued bearer token. All processing stays within the Bedrock Region you select.

## How it works

The OpenAI SDK is configured with two settings:

| Setting | Value |
| --- | --- |
| `OPENAI_BASE_URL` | `https://bedrock-mantle.{region}.api.aws/openai/v1` |
| `OPENAI_API_KEY`  | A short-lived Bedrock bearer token minted from your AWS credentials |

This project mints the token at runtime from your AWS credentials with
[`aws-bedrock-token-generator`](https://pypi.org/project/aws-bedrock-token-generator/),
so there is no long-lived API key to manage:

```python
from aws_bedrock_token_generator import provide_token

token = provide_token(region="us-east-2")  # uses your AWS credential chain
```

## Models & Regions

| Model | Model ID | Available regions |
| --- | --- | --- |
| GPT-5.5 (complex reasoning + coding) | `openai.gpt-5.5` | `us-east-2` (US East, Ohio) |
| GPT-5.4 (best price-performance)     | `openai.gpt-5.4` | `us-east-2`, `us-west-2` (US West, Oregon) |

The token, base URL, and model region must all match. This project defaults to
`us-east-2`.

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
same Region as `REGION` in `main.py` (`us-east-2` by default) and have Bedrock access
to the OpenAI models there.

The simplest setup is to select a configured profile with `AWS_PROFILE`:

```bash
export AWS_PROFILE=my-profile
export AWS_REGION=us-east-2   # optional; should match REGION in main.py
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

`main.py` sends a single prompt and prints the response:

```python
import os
from aws_bedrock_token_generator import provide_token
from openai import OpenAI

REGION = "us-east-2"
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
