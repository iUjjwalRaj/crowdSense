# Provider Integration Guide

## Provider interfaces

The provider module defines protocols for:

1. `StaticGTFSProvider`
2. `ETMProvider`
3. `GPSProvider`
4. `PassengerCountProvider`

Implementations must validate their source, record provenance, synchronize explicitly,
and report health without exposing credentials or transport-authority assumptions.

## Required provider behavior

Every provider implementation should:

- accept a source configuration supplied outside source code
- validate required IDs, timestamps and geographic coordinates
- de-duplicate records deterministically
- reject duplicate/inconsistent observations
- report source provenance and record-level source status
- return `last_successful_sync`
- return valid record counts
- report blocking errors
- return freshness as `current`, `stale`, or `unknown`
- log sync start, completion, count and failure class without passenger-level secrets

## Health and readiness

`GET /api/v1/health/readiness` reports:

- GTFS configured status and valid stop count
- crowd configured status
- prediction provider status
- last successful sync timestamps
- freshness status
- blocking errors

An endpoint returns readiness state but does not claim provider success when no provider
has been configured.

## OCC endpoint

`GET /api/v1/occ/occupancy/corridor` reports `source: unknown`, no corridor rows and a
blocking error until an actual OCC provider is integrated.
