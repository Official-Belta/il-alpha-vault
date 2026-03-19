# IL Alpha Vault

## Project
Uniswap V4 hook-based automated LP vault.
Compare fee yield vs IL cost using options pricing in real-time.
Only maintain LP in positive expected value ranges.

## Tech Stack
- Solidity (Foundry)
- Uniswap V4 hooks
- Python (backtesting)

## Key Functions (from BELTA)
- _calculateIL
- _positionValueUSDC
- _feesToUSDC

## Language
- Code and comments: English
- Print statements: English

## Design System
Always read DESIGN.md before making any visual or UI decisions.
All font choices, colors, spacing, and aesthetic direction are defined there.
Do not deviate without explicit user approval.
In QA mode, flag any code that doesn't match DESIGN.md.

## gstack
- Use /browse skill from gstack for all web browsing
- Never use mcp__claude-in-chrome__* tools
- Available skills: /plan-ceo-review, /plan-eng-review, /review, /ship, /browse, /qa, /setup-browser-cookies, /retro, /document-release
- If gstack skills aren't working, run: cd ~/.claude/skills/gstack && ./setup
