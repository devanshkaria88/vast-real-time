# Activity: API key template (.env.example) and .env loading

## 2026-10-17T12:59:11Z · cursor · planned

Task registered with an agent-neutral plan. Another agent may take it over
after reading this plan and activity history.

**Next action:** Complete the linked plan before changing task-scoped files.

## 2026-10-17T13:00:25Z · cursor · completed

Added .env.example listing all 19 variables the server reads, grouped by service with where to get each key; .env copy created locally (gitignored). Server now loads .env without overriding shell/VM vars. Cosmos Reason Q&A implemented (was only a status dot); Ask tries Cosmos, then W&B, then replay. VastDB shows live only when the SDK is installed. Validated: template matches code exactly, .env ignored and .env.example committed, loader unit check, server reload + health + ask in replay, lints clean.

**Next action:** No further action; task completed.
