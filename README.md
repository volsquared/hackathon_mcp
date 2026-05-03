# Hackathon Agent

Python-side GenAI application for the hackathon. This project is designed to run locally against the Java API at `http://localhost:8080`.

## Python Version

Use Python `3.11` explicitly.

## VS Code After Setup

Create the local virtual environment and install dependencies from `cmd` first. Then open the `mcp` folder in VS Code.

This repo includes workspace settings in `.vscode/` that:

- point VS Code at `.venv\Scripts\python.exe`
- activate the virtual environment in the integrated terminal
- help Pylance resolve imports from the repo root

## Setup

```cmd
py -3.11 -m venv .venv
.venv\Scripts\activate.bat
py -3.11 -m pip install --upgrade pip
py -3.11 -m pip install -r requirements.txt
```

## Open In VS Code

After the commands above complete:

1. Launch VS Code
2. Open the `mcp` folder
3. Install the Microsoft Python extension
4. Run `Python: Select Interpreter`
5. Choose `.venv\Scripts\python.exe`

## Run

Start the Java API first in the sibling `java` project:

```powershell
cd ..\java
mvn quarkus:dev
```

Then run the Streamlit UI here:

```powershell
cd ..\mcp
.venv\Scripts\Activate.ps1
streamlit run app/ui.py
```

If VS Code does not pick the interpreter automatically, use:

- `Ctrl+Shift+P`
- `Python: Select Interpreter`
- choose `.venv\Scripts\python.exe`

Recommended order:

1. In `cmd`, create `.venv` and install dependencies
2. Launch VS Code and open the repo
3. Install the Microsoft Python extension
4. Confirm VS Code is using `.venv\Scripts\python.exe`

## Logging

The app writes logs to:

- `logs/app.log`

This includes real LLM routing, probe, and answer-generation exceptions with tracebacks, plus normal console output when running Streamlit.

## Environment

Optional environment variables:

- `DATA_API_URL` defaults to `http://localhost:8080`
- `OPENAI_API_KEY` for local LLM setup
- `GEMINI_API_KEY` if you are using Gemini directly or via an OpenAI-compatible proxy
- `LLM_ENABLED`, `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_BASE`, `LLM_API_KEY_ENV` as overrides

## Optional LLM Mode

The app still defaults to deterministic mode.

To enable live LLM routing and grounded answer generation:

1. Copy `.env.example` to `.env`
2. Add your API key to `.env`
3. Edit `config/app.yaml` to choose provider/model and set `llm.enabled: true`
4. Restart Streamlit

The LLM layer uses LangChain chat-model integrations for `openai`, `gemini`, and `claude`.

This repo also supports `cortex` as a first-class provider label for OpenAI-compatible internal gateways.

If you are routing through an internal OpenAI-compatible gateway such as CorteX, use:

- `provider: cortex`
- `model: gemini-2.5-flash` or `gemini-2.5-pro`
- `LLM_API_BASE` or `llm.api_base` set to the gateway URL
- `api_key_env` set to the env var that holds the shared key, for example `GEMINI_API_KEY`

What "choose provider and model" means:

- `provider` is the LLM vendor family, currently one of `openai`, `gemini`, `claude`, or `cortex`
- `model` is the model name string for that provider, for example:
  - `gpt-4.1-mini`
  - `gemini-2.5-flash`
  - `claude-3-5-sonnet-latest`
- `api_key_env` tells the app which environment variable contains the key for that provider

Example config choices live in `config/app.yaml`.

The UI now shows the current runtime mode:

- `deterministic`: current keyword-routing starter mode
- `llm-ready`: provider config and API key detected, with live LLM calls enabled
- `llm-misconfigured`: LLM was enabled but config is incomplete or unsupported

Example chained request now supported:

- `Review the risk profile and alerts for CUS007`

What this chained path is for:

- questions that need both the customer profile and the customer's alerts
- questions about combining risk/status context with alert context
- narrow two-step requests for a single customer

Examples that should work well:

- `Review the risk profile and alerts for CUS007`
- `Give me the customer profile and active alerts for CUS007`
- `Summarize the risk rating and alerts for CUS007`
- `Does CUS007 have a high risk rating and any alerts?`

Examples that should not be expected to work from this chained path alone:

- `Compare CUS007 and CUS008 on risk and alerts`
- `Show spending, fraud, and alerts for CUS007`
- `Which high-risk customers have alerts?`
- `Explain why this customer is risky`

Those require a broader planner or additional chained workflows, not just the current two-step example.

## Notes

- The UI is intentionally thin.
- Agent/tool logic lives under `app/agent`, `app/tools`, and `app/api`.
- Prompts are externalized under `prompts/`.
- An interactive architecture walkthrough lives at `docs/flow.html`.

