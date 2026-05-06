# Customer Data Framework

This document describes how customer data currently works across the workshop system and how content authors should think about it when designing exercises.

It is intended as a handoff for Claude, GPT, or any other content-design agent that needs to propose realistic workshop exercises based on the current banking dataset.

## High-Level Architecture

There are two layers:

1. Java banking API
   This is the actual source of customer, transaction, alert, and spending-summary data.
2. Python `mcp` app
   This does not own the data. It calls the Java API over HTTP through thin tool wrappers.

Current flow:

```text
Participant / agent prompt
  -> Python tool selection
  -> Python tool wrapper
  -> Java /api/banking endpoint
  -> in-memory banking repository
  -> JSON response back to Python
```

## Current Source Of Truth

The current source of truth is:

- [BankingRepository.java](/C:/Users/upadh/git/hackathon/java/src/main/java/com/hackathon/banking/repository/BankingRepository.java)

This repository builds three in-memory datasets at startup:

- `customers`
- `transactions`
- `alerts`

These are currently hardcoded Java fixtures, not rows loaded from SQLite.

That means:

- content changes currently require code edits in the Java repo
- the Python repo does not define the customer corpus
- the data is deterministic and stable for workshop use
- scenario design is embedded directly in Java comments and fixture construction

## Data Models

### Customer

Defined in [Customer.java](/C:/Users/upadh/git/hackathon/java/src/main/java/com/hackathon/banking/model/Customer.java).

Fields:

- `customerId`
- `fullName`
- `segment`
- `email`
- `phone`
- `status`
- `accountBalance`
- `riskRating`

Example shape:

```json
{
  "customerId": "CUS015",
  "fullName": "Kenji Watanabe",
  "segment": "Retail",
  "email": "kenji.watanabe@example.com",
  "phone": "+44-7700-100015",
  "status": "REVIEW",
  "accountBalance": 320.00,
  "riskRating": "HIGH"
}
```

### Transaction

Defined in [Transaction.java](/C:/Users/upadh/git/hackathon/java/src/main/java/com/hackathon/banking/model/Transaction.java).

Fields:

- `transactionId`
- `customerId`
- `transactionDate`
- `merchant`
- `category`
- `amount`
- `currency`
- `fraud`
- `channel`

Example shape:

```json
{
  "transactionId": "TXN3020",
  "customerId": "CUS017",
  "transactionDate": "2026-04-10",
  "merchant": "CRYPTOEXCHANGE",
  "category": "finance",
  "amount": 1250.00,
  "currency": "GBP",
  "fraud": true,
  "channel": "bank_transfer"
}
```

### Alert

Defined in [Alert.java](/C:/Users/upadh/git/hackathon/java/src/main/java/com/hackathon/banking/model/Alert.java).

Fields:

- `alertId`
- `customerId`
- `severity`
- `type`
- `message`
- `createdAt`
- `status`

Example shape:

```json
{
  "alertId": "ALT4004",
  "customerId": "CUS017",
  "severity": "MEDIUM",
  "type": "FRAUD",
  "message": "Two transactions flagged in April...",
  "createdAt": "2026-04-10T14:00:00",
  "status": "OPEN"
}
```

### Spending Summary

Defined in [SpendingSummary.java](/C:/Users/upadh/git/hackathon/java/src/main/java/com/hackathon/banking/model/SpendingSummary.java).

Fields:

- `customerId`
- `groupBy`
- `totalSpend`
- `breakdown[]`

Each breakdown item contains:

- `key`
- `totalAmount`
- `transactionCount`

This is derived data, not an independently authored dataset.

## Java API Surface

The Python app calls these Java endpoints exposed by [BankingResource.java](/C:/Users/upadh/git/hackathon/java/src/main/java/com/hackathon/banking/resource/BankingResource.java):

- `GET /api/banking/customers/{customerId}`
- `GET /api/banking/transactions?customerId=...&fraudOnly=...`
- `GET /api/banking/alerts?customerId=...&severity=...`
- `GET /api/banking/spending-summary?customerId=...&groupBy=...`

Service behavior is implemented in [BankingService.java](/C:/Users/upadh/git/hackathon/java/src/main/java/com/hackathon/banking/service/BankingService.java).

Important behavior:

- customer ids are normalized to uppercase
- missing customer ids for required endpoints fail cleanly
- spending summary is computed from transactions
- filtering is currently in memory over the fixture lists

## Python Tool Layer

The Python tools are thin wrappers over the Java API:

- [customer.py](/C:/Users/upadh/git/hackathon/mcp/app/tools/customer.py)
- [transactions.py](/C:/Users/upadh/git/hackathon/mcp/app/tools/transactions.py)
- [alerts.py](/C:/Users/upadh/git/hackathon/mcp/app/tools/alerts.py)
- `spending_summary.py`

The HTTP client is [client.py](/C:/Users/upadh/git/hackathon/mcp/app/api/client.py).

Important implication:

- the Python app does not currently store or shape the banking data itself
- if you want richer scenarios, the main corpus change belongs in the Java data source

## Current Scenario Design Philosophy

The dataset is not random reference data. It is deliberately shaped to create workshop teaching cases.

The repository comments already describe scenario intent, for example:

- suspicious-but-benign heavy spend
- low risk profile with emerging fraud evidence
- alert without confirmed fraud
- high risk profile with no current alerts
- similar alerts with different implications
- low spend but high risk
- full-picture one-customer scenario
- compare-two-customers scenario

This means the dataset should be treated as a **scenario corpus**, not just customer records.

## Current Customer Set

The current corpus contains customers `CUS001` through `CUS018`.

Several are generic baseline records. Several are explicitly scenario-driven records used to test reasoning boundaries:

- `CUS008`
  Very high spend, low risk, no fraud, no alerts.
- `CUS009`
  Low risk profile, but recent fraud-flagged transactions create a contradiction.
- `CUS010`
  Alert present, but no confirmed fraud transactions.
- `CUS011`
  High risk profile, sparse activity, no current alerts.
- `CUS012` and `CUS013`
  Similar alert families with different severity and business implications.
- `CUS014`
  Huge but stable spend, clean pattern.
- `CUS015`
  High risk, abrupt dormancy, layered alerts.
- `CUS016`
  Full-picture scenario where profile, alerts, and transactions all matter.
- `CUS017` and `CUS018`
  Comparison pair where profile rating and current evidence point in different directions.

## Data Relationships

The data model is relational in concept even though it is currently stored in Java collections.

Core relationships:

- one customer -> many transactions
- one customer -> many alerts
- one customer -> one profile record
- one spending summary -> derived from that customer's transactions

Logical join key:

- `customerId`

This is one of the reasons moving the corpus to SQLite makes sense.

## Why This Dataset Matters For Content

The workshop is teaching participants not just to fetch data, but to reason about:

- stale profile ratings vs fresh transactional evidence
- alerts vs transactions
- severity vs actual business meaning
- high spend vs genuine risk
- low activity vs dangerous risk posture
- one-customer “full picture” synthesis
- two-customer comparison without collapsing both into one narrative

So exercises should usually exploit **signal conflict** or **signal composition**, not just raw lookup.

## Good Exercise Themes For This Dataset

This customer corpus is well suited to exercises around:

- selecting the right tool based on prompt wording
- combining profile + alerts
- adding transaction evidence when profile-only logic is wrong
- deciding when spending summaries are relevant
- explaining contradictions clearly
- comparing two customers without dropping one
- avoiding overreaction to superficial signals

## Less Suitable Exercise Themes

The current corpus is less suited to:

- deep time-series analytics beyond the authored dates
- arbitrary SQL-heavy reporting tasks
- open-ended many-customer screening workflows
- dynamic state mutation on the business data itself

The corpus is curated for teaching scenarios, not broad operational analytics.

## Current Weakness Of The Data Architecture

Right now, the banking corpus is hardcoded inside Java:

- hard to edit in bulk
- harder for non-Java authors to maintain
- awkward to diff and validate as a dataset
- not ideal for generating larger scenario libraries
- difficult to run external checks for consistency

This is the main reason your instinct to move the data to SQLite is sound.

## Recommendation: Move The Banking Corpus To SQLite

Yes, the customer dataset should probably move to SQLite.

That would be a clean improvement if done carefully.

### Why SQLite is a good fit

- the data is relational
- the workshop already uses SQLite elsewhere for participant progress
- content authors can evolve the corpus without editing Java fixture code
- the scenario corpus becomes easier to inspect, query, diff, and validate
- compare/full-picture scenarios become easier to author systematically
- future scripts can generate or verify scenario coverage automatically

### What should move into SQLite

At minimum:

- `customers`
- `transactions`
- `alerts`

Possibly also:

- scenario metadata
- commentary or author notes
- expected reasoning tags for evaluation

I would keep workshop participant progress in its existing profile-specific SQLite store, separate from the business corpus. They serve different purposes.

## Recommended SQLite Schema

If you move the corpus, a practical first-pass schema would be:

### `customers`

- `customer_id` TEXT PRIMARY KEY
- `full_name` TEXT NOT NULL
- `segment` TEXT NOT NULL
- `email` TEXT NOT NULL
- `phone` TEXT NOT NULL
- `status` TEXT NOT NULL
- `account_balance` REAL NOT NULL
- `risk_rating` TEXT NOT NULL

### `transactions`

- `transaction_id` TEXT PRIMARY KEY
- `customer_id` TEXT NOT NULL
- `transaction_date` TEXT NOT NULL
- `merchant` TEXT NOT NULL
- `category` TEXT NOT NULL
- `amount` REAL NOT NULL
- `currency` TEXT NOT NULL
- `fraud` INTEGER NOT NULL
- `channel` TEXT NOT NULL

Foreign key:

- `customer_id -> customers.customer_id`

### `alerts`

- `alert_id` TEXT PRIMARY KEY
- `customer_id` TEXT NOT NULL
- `severity` TEXT NOT NULL
- `type` TEXT NOT NULL
- `message` TEXT NOT NULL
- `created_at` TEXT NOT NULL
- `status` TEXT NOT NULL

Foreign key:

- `customer_id -> customers.customer_id`

### Optional `scenario_tags`

This is not required for runtime, but it would help content design:

- `customer_id`
- `scenario_code`
- `scenario_label`
- `notes`

Example tags:

- `mixed_signal_low_risk`
- `high_spend_benign`
- `alert_without_confirmed_fraud`
- `compare_pair_a`

## Migration Guidance

If you do move to SQLite, the cleanest implementation path is:

1. Keep the Java API contract unchanged.
2. Replace `BankingRepository` fixture builders with SQLite-backed reads.
3. Preserve the same response shapes for:
   - customer
   - transactions
   - alerts
   - spending summary
4. Add a seed script or seed SQL file for the corpus.
5. Keep the Python side unchanged initially.

That approach minimizes blast radius:

- content improves
- API consumers stay stable
- workshop exercises do not need to be rewritten

## What Not To Do

Avoid mixing two concerns into one database design:

- workshop participant progress and workflow state
- banking business corpus

Those should remain logically separate even if both use SQLite.

Also avoid making the business corpus too generic too early. The real value of this dataset is that it is intentionally shaped for teaching.

## Suggested Prompt For Content Agents

If you want Claude or GPT to use this data model well, ask them to propose exercises using the current signals:

```text
Use the current customer corpus as a scenario dataset, not a generic banking database.
Propose exercises that exploit meaningful tension between:
- profile risk rating
- alert state and severity
- transaction evidence
- spending pattern

For each exercise, identify:
- which customer or customer pair it should use
- what signal conflict or teaching point it relies on
- why the scenario is interesting in this dataset
- what the participant should notice before and after the fix
```

## Reality Check

As of now:

- the customer corpus is Java-owned
- the Python tools are API wrappers only
- customer data is not yet in SQLite
- moving the corpus to SQLite is a sensible next architectural step

That move would improve content authoring substantially, but it should be done without changing the external banking API contract.
