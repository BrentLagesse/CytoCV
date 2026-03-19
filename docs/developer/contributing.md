# Contributing

## Purpose

This document defines the expected local workflow for code and documentation changes.

## Local Setup Expectations

- use Python `3.11.5`
- use a project-specific virtual environment
- install dependencies from `requirements.txt`
- configure `.env` explicitly
- use SQLite only for local development and testing
- use PostgreSQL for production-like validation

## Standard Development Workflow

1. pull or check out the target branch
2. activate the virtual environment
3. verify `.env`
4. run migrations as needed
5. make code changes
6. run tests
7. update documentation when behavior, env vars, routes, outputs, or diagrams changed

## Migration Rules

When changing database models:

- create migrations under the correct app
- run migrations locally
- verify affected views and exports
- update `docs/reference/data-model.md`

## Documentation Update Rules

Documentation must be updated when any of these change:

- public routes or APIs
- environment variables or defaults
- storage and retention behavior
- plugin IDs or required channels
- output artifact names or locations
- account or auth behavior

## Safety Expectations

- do not rely on implicit environment defaults in production
- do not treat transient runs as permanent retained data
- do not add plugin metadata in more than one source of truth
- keep generated caches out of the documentation tree

## Related Documents

- [`testing-guide.md`](testing-guide.md)
- [`../templates/document-style-guide.md`](../templates/document-style-guide.md)
