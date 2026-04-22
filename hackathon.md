Merged Workshop Plan
====================

Core principle:
Each stage solves the problem revealed by the previous stage.
"Great, that worked. Now we can clearly see the next limitation."

Audience: engineers, some off code for a while.
Calibration: scaffolded but not babied.
- Read and trace the pipeline: fine, no hand-holding
- Edit .env and config/app.yaml: trivial
- Edit YAML prompt files: comfortable, can go deep
- Add eval test cases in Python: fine with the shape provided
- Extend a tool parameter: fine with scaffold
- Build new chains from scratch during workshop: too slow, avoid
- Debug LangChain internals: wrong rabbit hole, avoid


BEFORE STAGE 0: PARTICIPANT SETUP
---------------------------------

Exercise:
Set up the repo from `cmd`, then open it in VS Code.

Objective:
Participants should start from a consistent editor/interpreter environment before touching the app.

Ask:
Create the local `.venv` and install dependencies from `cmd`, then open the repo in VS Code and confirm it is using the venv interpreter.

How To Do It:

Option A: `cmd`

1. Create the venv:
   `py -3.11 -m venv .venv`
   This creates a repo-local Python environment in `.venv`.
2. Activate the environment:
   `.venv\Scripts\activate.bat`
   After activation, your prompt should show `(.venv)` at the start.
3. Install dependencies:
   `py -3.11 -m pip install -r requirements.txt`
   This installs Streamlit, LangChain, and the other Python packages used by the app.

Option B: PowerShell

1. Create the venv:
   `py -3.11 -m venv .venv`
   This creates a repo-local Python environment in `.venv`.
2. Activate the environment:
   `.venv\Scripts\Activate.ps1`
   After activation, your prompt should show `(.venv)` at the start.
   If PowerShell blocks script execution, run:
   `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
   then retry the activation command.
3. Install dependencies:
   `py -3.11 -m pip install -r requirements.txt`
   This installs Streamlit, LangChain, and the other Python packages used by the app.

Then:

1. Launch VS Code
   Open VS Code only after the venv and dependencies exist, so interpreter discovery is easier.
2. Open the `mcp` folder in VS Code
   Open the repo root, not an inner folder like `app/`.
3. Install the Microsoft Python extension
   Accept the recommended extension prompt if VS Code shows it.
4. If needed, run `Python: Select Interpreter`
   Use `Ctrl+Shift+P` to open the command palette, then search for `Python: Select Interpreter`.
5. Choose `.venv\Scripts\python.exe`
   This ensures the editor, terminal, and language server all use the repo-local environment.
6. Open a new integrated terminal if VS Code needs to re-detect the environment
   The new terminal should activate the venv automatically if VS Code picked up the workspace settings.

Relevant files:

- `.vscode/settings.json`
- `.vscode/extensions.json`
- `README.md`

Success Criteria:

- VS Code is using the repo-local interpreter
- the terminal activates `.venv`
- imports resolve cleanly in the editor
- the participant can run the app from VS Code


PREBUILT INFRASTRUCTURE (facilitator builds before workshop)
------------------------------------------------------------

1. Richer Java seed data
   Not just more rows. Scenarios must include:
   - suspicious-but-benign customers (high spend, no fraud flags)
   - mixed-signal customers (one fraud flag, low risk rating)
   - similar alerts with different outcomes
   - customers where spending, alerts, and fraud signals conflict
   - edge cases designed to make routing decisions non-trivial
   Target: 15-20 customers, varied risk ratings, segments, statuses

2. Three prebuilt chains in tool_execution.py + tools.yaml
   - get_customer_profile_and_alerts (already exists)
   - get_full_picture: profile + alerts + spending for one customer
   - compare_customers: profile + alerts for two customers side by side

3. Ground truth eval corpus in app/eval/runner.py
   Written before prompt tuning begins. Treat as the specification.
   Must cover:
   - correct tool/chain selection across natural language variants
   - out-of-scope prompts that must return no tool
   - chain boundary cases (two customer IDs -> compare chain, not profile chain)
   - answer property checks (should_contain, should_not_contain)
   - prompts that should compare but must not trigger single-customer chains
   Target: 15-20 cases

4. Richer starter prompts in prompts/
   - system.yaml: give the model a real role, constraints, and tone
   - tools.yaml: one tool should have a deliberately weak description (Stage 2 setup)
   - ontology.yaml: stub with real terms but incomplete definitions (Stage 6 setup)
   - format.yaml: basic output shape, no audience framing yet (Stage 4 setup)


LIVE DEMO PROMPTS (facilitator use — weak vs strong prompt before/after)
-------------------------------------------------------------------------

Run these three prompts against prompts/ (weak) and prompts_facilitator/ (strong)
to show participants what prompt quality actually changes. Use them in this order.

Script: scripts/demo_compare.py — output goes to output/cl_1.txt.

1. CUS009's profile says LOW risk but I've heard there was recent fraud activity —
   what do the transactions show and should I be concerned?

   Why: contradiction between profile signal and transaction evidence.
   Weak path calls get_full_picture and underplays the issue — acknowledges fraud
   amounts exist but concludes "monitoring advisable" without urgency.
   Strong path calls get_transactions and makes the contradiction explicit: LOW profile
   rating but multiple fraud-flagged transactions totalling over £2,400 in one week,
   indicating current risk is materially higher than the rating reflects.
   Use this to show: prompt quality changes what the model prioritises, not just
   what it retrieves.

2. Give me the full picture on CUS015 — I need to make a credit line decision.

   Why: multi-signal synthesis on a complex account.
   Both paths call get_full_picture. Use this as the secondary example showing that
   prompt quality affects answer richness and business framing even when tool
   selection is identical. CUS015 has stacked signals: HIGH fraud alert, MEDIUM AML
   alert citing unexplained dormancy, a prior address change, and a spending history
   that dropped from £500/month to near zero in six weeks.

3. Look at the full transaction and alert history for CUS017 and CUS018 — which
   presents more risk right now?

   Why: counter-intuitive comparative reasoning.
   Weak path concludes CUS018 is riskier — anchors on the MEDIUM risk rating and
   prior fraud history.
   Strong path concludes CUS017 is riskier — correctly identifies that CUS018's
   fraud alert is resolved and recent activity is clean, while CUS017 has two
   unresolved fraud-flagged transactions in April and an open MEDIUM alert despite
   a LOW risk rating.
   Use this to show: stronger prompts override stale signals with fresher evidence.

Demo sequence rationale:
  1 → profile vs transaction contradiction (prompt changes prioritisation)
  2 → same tool, richer synthesis (prompt changes answer quality)
  3 → counter-intuitive comparison (prompt changes the conclusion entirely)

Optional alternative demo prompts:
  Use these if you want the contradiction stated explicitly in the user question,
  so the audience can more easily see what the weak and strong prompt sets do with it.
  These are especially useful for a cleaner live demo narrative, even though they may
  reduce the weak-vs-strong gap in some cases by helping both sides frame the task.

  1. CUS018 still has a higher risk rating, but CUS017 has had more recent fraud
     activity - which account is the more immediate concern and why?

  2. CUS015 used to spend normally but has gone quiet - do the alerts and
     transaction history suggest a credit line should be declined or just reviewed?

  3. The alert on CUS009 says low severity and no immediate action, but the recent
     transaction pattern looks different - what changed, and how worried should I be?


WORKSHOP STAGES
---------------

Stage 0: Run It, Then Break It
  Activity:
    Run the app with a supported prompt: "Show fraud for CUS007"
    Then run a natural-language variant the deterministic router mishandles
  Details:
    - Start the Java API first, then run the Streamlit app in this repo
    - Use one prompt that clearly fits the existing scaffold and one that is phrased more naturally
    - Observe both the answer and the `Details` panel in the UI
    - Notice which tool was selected and what tool input was extracted
  Aha: it works, but only because the path is narrow and pre-shaped
  Revealed: deterministic routing is brittle; we need semantic routing

Stage 1: Turn On LLM Mode
  Activity:
    Configure .env and config/app.yaml
    Move the app from deterministic to llm-ready
    Re-run the failing prompt from Stage 0
  Details:
    - Copy `.env.example` to `.env`
    - Add a real API key for the provider you want to use
    - Set `llm.enabled: true` and choose provider/model in `config/app.yaml`
    - Restart Streamlit after making the config change
    - Confirm in the sidebar that the mode changed to `llm-ready`
  Aha: the app now understands natural language phrasing
  Revealed: understanding the question is not enough; answers are still weak and raw

Stage 2: Diagnose A Deliberate Misfire
  Activity:
    Use the prebuilt get_full_picture or compare_customers workflow
    Run a prompt that should be handled but misroutes due to the weak tool description
    Diagnose why it misfired, then fix the tool description in tools.yaml
  Details:
    - Start from the intentionally weak prompt/tool description provided in the scaffold
    - Run the target prompt and inspect which tool or chain was actually selected
    - Read `prompts/tools.yaml` and identify why the model may have chosen the wrong path
    - Make the smallest prompt change that should correct the routing
    - Re-run the same prompt and compare before/after behavior
  Aha: the capability exists, but prompt guidance decides whether it fires correctly
  Revealed: even with correct routing, answers lack business framing and feel generic

Stage 3: Brief The Model
  Activity:
    Improve system.yaml: add role, constraints, tone, and behavioral rules
    Improve tools.yaml: add examples and anti-examples to each tool
    Re-run the misfiring prompt and compare behavior
  Details:
    - Treat `system.yaml` like the model's job description
    - Make the role specific to the banking use case instead of generic assistant language
    - Add concrete examples in `tools.yaml` that distinguish nearby workflows
    - Add anti-examples so the model can see what should not trigger a tool
    - Re-run both the original misfire and one nearby prompt to check for regressions
  Aha: prompt wording changes routing behavior without touching Python
  Revealed: routing can improve, but the answer shape and tone may still be wrong for the audience

Stage 4: Shape The Answer For The Audience
  Activity:
    Improve format.yaml for two different roles (e.g. risk officer vs customer service)
    Run the same query with each format configuration and compare answers
  Details:
    - Keep the tool result the same and only change the formatting instructions
    - Make one version direct and risk-focused
    - Make the other version clearer and less internal-jargon heavy
    - Compare not just wording but structure, emphasis, and recommendations
    - Check whether the answer still stays grounded in the tool output
  Aha: same data and same tools produce very different useful outputs depending on briefing
  Revealed: without tests, prompt changes are still just guesswork

Stage 5: Write Ground Truth And Measure
  Activity:
    Inspect or extend the prebuilt eval corpus
    Treat cases as the expected behavior specification, not as after-the-fact checks
    Tune prompts to pass failing cases
    Re-run and compare scores
  Details:
    - Read the existing eval cases before editing prompts
    - Treat each failing case as a statement of desired behavior
    - Add at least one case that checks answer content, not just selected tool
    - Use `should_contain` and `should_not_contain` style checks where exact text is too brittle
    - Re-run the eval after each prompt change rather than batching lots of changes together
  Aha: prompt engineering is a proper loop: write -> test -> measure -> improve
  Revealed: ambiguous domain language still causes inconsistent routing and interpretation

Stage 6: Define Ontology
  Activity:
    Use ontology.yaml to define key business terms:
    - behaviour
    - risk profile
    - alert posture
    - spending behaviour
    - comparison request
    - suspicious vs confirmed fraud
  Details:
    - Keep the ontology tied to concepts the app can actually fetch or infer from tool output
    - Define both meaning and usage, not just dictionary-style labels
    - Be explicit where terms are often confused, such as suspicious vs confirmed fraud
    - Use the eval failures from Stage 5 to decide which terms most need definition
    - Avoid turning ontology into a generic glossary detached from app behavior
  Aha: ambiguity is a domain-definition problem, not just a prompt-wording problem
  Revealed: prompts still need to use the ontology consistently through examples

Stage 7: Tune Prompts With Ontology
  Activity:
    Refine system.yaml and tools.yaml using the ontology definitions
    Add ontology-backed examples and anti-examples
    Re-run evals and compare outcomes against Stage 5 baseline
  Details:
    - Revisit the prompts with the ontology terms in front of you
    - Replace vague words with the ontology-backed wording where useful
    - Add examples that exercise the newly defined concepts
    - Add anti-examples that protect workflow boundaries
    - Compare eval results against the earlier baseline, not just against intuition
  Aha: ontology plus prompt tuning improves precision, consistency, and boundary handling
  Revealed: next frontier is broader workflow coverage and harder scenario types

Stage 8: Expand And Harden
  Activity:
    Add more eval cases for edge scenarios
    Extend or add a chain for a more complex workflow
    Or harden for production: error handling, out-of-scope refusals, ambiguous inputs
  Details:
    - Pick one direction rather than trying to do all of them in one session
    - For edge scenarios, prefer cases that stress boundaries rather than just adding volume
    - For workflow expansion, reuse the existing chain pattern instead of redesigning the architecture
    - For hardening, focus on refusal quality, missing inputs, and ambiguous requests
    - Use the same loop from Stage 5: define expected behavior, then implement and verify it
  Aha: the loop (data -> chain -> eval -> prompt) is repeatable and extensible
  No single revealed problem - this is the open frontier


BUILD BACKLOG (this repo)
--------------------------

Priority 1: get_full_picture chain
  - tool_execution.py: add elif for get_full_picture
  - tools.yaml: add entry with use_for, examples, do_not_use_for

Priority 2: compare_customers chain
  - tool_execution.py: add elif for compare_customers (two customer IDs)
  - tools.yaml: add entry with strict boundary conditions

Priority 3: Ground truth eval corpus
  - app/eval/runner.py: expand to 15-20 cases
  - Add should_contain / should_not_contain answer checks

Priority 4: Richer starter prompts
  - system.yaml: real role and constraints
  - tools.yaml: one deliberately weak description for Stage 2
  - ontology.yaml: real terms, incomplete definitions (gap for Stage 6)
  - format.yaml: output shape only, no audience framing (gap for Stage 4)

Priority 5: Java seed data
  - Facilitator prereq, not in this repo
  - Must be co-designed with eval cases and chain boundaries
