# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Minimal experiment that calls OpenAI models (e.g. `openai.gpt-5.5`) through **Amazon Bedrock's Mantle OpenAI-compatible endpoint**, using the OpenAI Python SDK rather than the Bedrock SDK. The whole program is `main.py`.

## Commands

This is a [uv](https://docs.astral.sh/uv/)-managed project (Python >=3.13).

- Run: `uv run main.py`
- Add a dependency: `uv add <package>` (updates `pyproject.toml` + `uv.lock`)
- Sync the environment from the lockfile: `uv sync`

There are no tests, linting, or build steps configured.

## Architecture

The key idea is bridging the OpenAI SDK to Bedrock:

1. `aws_bedrock_token_generator.provide_token(region)` mints a short-lived bearer token from the caller's AWS credentials.
2. That token is injected as `OPENAI_API_KEY`, and `OPENAI_BASE_URL` is pointed at `https://bedrock-mantle.{REGION}.api.aws/openai/v1`.
3. A standard `OpenAI()` client then transparently talks to Bedrock; calls use the OpenAI Responses API (`client.responses.create`).

Implications when editing:
- Valid AWS credentials for `REGION` (currently `us-east-2`) must be present in the environment; the token is region-scoped, so changing `REGION` requires the base URL and credentials to match.
- Model IDs are Bedrock-namespaced (`openai.<model>`), not bare OpenAI names.
