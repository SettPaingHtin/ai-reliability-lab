AI Reliability Lab

A small tool for testing AI apps. You write a set of test cases, run them against a model, and see which ones pass, which fail, and why. It keeps every run in a database so results can be looked at later. Right now it only talks to a built-in mock model, so you don't need any API keys to try it.

Current status: 

You can create a project, create a dataset inside it, import test cases from a JSONL file, run the dataset against the mock model, and look at the results in the browser. Failed cases show the expected answer, the actual answer, and which scoring rule failed. Runs record pass rate, latency, token counts and an estimated cost. If a model doesn't report something, like token usage, it shows as a dash instead of a zero.

Not yet implmented:

Comparing two runs, pass/fail thresholds, the command line tool, real model providers (OpenAI and the like), AI-assisted grading, user accounts, and the GitHub Actions setup. These are planned, in about that order.

Running it

You need Docker. Then:

    cp .env.example .env

Open .env and set POSTGRES_PASSWORD to anything you like. Then:

    docker compose up --build

When it finishes starting, open http://localhost:3000. The API docs are at http://localhost:8000/docs.

Trying it out

Create a project, open it, create a dataset, and import datasets/mock-qa-suite.jsonl. Pick mock-1 from the model dropdown and click Run evaluation. You should end up with 36 passed, 5 failed and 3 errors out of 44. Running it again with mock-2 gives 34 passed, 8 failed and 2 errors. The two models are scripted to differ on purpose, so you have something to compare later.

If you see everything failing, you are probably running an older copy of the code. Run "docker compose down -v", unpack a fresh copy, and rebuild with "docker compose build --no-cache".

Dataset format

One JSON object per line. Each needs an input, plus either an expected answer or a list of rules.

    {"input": "What is 2 + 2?", "expected": "4"}
    {"input": "Name a color", "rules": [{"type": "regex", "value": "red|blue", "case_sensitive": false}]}

The rule types are exact, contains, not_contains and regex. A case passes only if every rule passes. You can also add context and metadata. If any line is invalid, nothing is imported and you get a list of the bad lines.

The mock model reads its behavior from metadata: mock_output, mock_latency_ms, mock_error (error, timeout, rate_limited or flaky:N) and mock_report_usage. The first three can be given per model, like {"mock-1": "Paris", "mock-2": "Lyon"}. There is more detail in datasets/README.md.

Running the tests

    cd backend
    python -m venv .venv
    source .venv/bin/activate
    pip install -e ".[dev]"
    pytest

For the frontend:

    cd frontend
    npm install
    npm run typecheck
    npm test

How it is laid out:

backend/app/domain holds the core logic (scoring, JSONL parsing, the mock model, the engine that runs cases). It doesn't depend on FastAPI or the database, which keeps it easy to test. backend/app/api and backend/app/services hold the web routes and the code that saves runs to Postgres. frontend is a Next.js app. docs/architecture.md explains the design choices in more detail.

Things to note:

There is no real login. If you set API_KEY in .env, the API requires it, but that is a single shared key and not user accounts, so don't put this on the public internet yet.

Runs execute in a background task inside the API process. If the server restarts mid-run, that run is stuck. A proper job queue is planned.

The domain tests have been run and pass. The API tests, the frontend lint and the production build were written but not run by me, so expect to fix a few small things if they fail on your machine.
