# Technology Best Practices

This suite studies the technologies ApplyPilot actually uses. It is not a generic Python guide. Every pattern here is grounded in files from this repository.

The main technologies are:

- Python 3.11+ packaging
- Typer CLI
- Rich terminal UI
- SQLite
- pytest
- Playwright/browser automation
- BeautifulSoup scraping
- httpx LLM client
- YAML/dotenv configuration
- subprocess-based Claude/Codex agent runners

The repo does not use React, TypeScript, Node backend frameworks, Next.js, Express, NestJS, Prisma, TypeORM, Redux, Zustand, React Query, GraphQL, or REST controllers internally. When those concepts matter, this suite explains the closest equivalent.

## How To Use This Suite

Read one technology at a time. For each one:

1. Open the cited files.
2. Identify the boundary it owns.
3. Find the risk if it fails.
4. Do the mini practice task.
5. Explain the pattern out loud as if in a code review.

## How This Differs From The Architecture Suite

The architecture suite asks how the whole system fits together. This suite asks how each tool is used well or riskily inside the system.
