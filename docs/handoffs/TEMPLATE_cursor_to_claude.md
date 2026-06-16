# Cursor to Claude Handoff

## Packet ID

## Sender
Cursor

## Recipient
Claude

## Objective

## Allowed input files

## Required source-of-truth files

## Required output file

## Forbidden actions
- approve
- size
- submit
- close
- cancel
- replace
- route
- call MCP
- call broker
- change gates
- change schemas
- change thresholds
- infer missing market data

## Required caveat behavior
If required data is missing, write missing_context.

## Expected response status
ADVISORY_OK / ADVISORY_CAUTION / ADVISORY_DOWNGRADE / ADVISORY_SKIP
