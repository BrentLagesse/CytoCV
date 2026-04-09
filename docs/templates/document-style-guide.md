# Document Style Guide

## Purpose

This document defines the baseline writing and maintenance rules for the CytoCV documentation set.

## Writing Principles

- write for the intended audience first
- use a formal, direct, procedural tone
- prefer specific codebase behavior over generic advice
- avoid vague statements unless the behavior is genuinely conditional

## Required Tutorial Structure

Tutorial and user-operation documents should use this order:

1. Purpose
2. Prerequisites
3. Procedure or workflow
4. Expected outputs
5. Common errors
6. Related documents

## Required Reference Structure

Reference documents should use this order:

1. Purpose
2. definitions
3. constraints and edge cases
4. related documents

## Naming Conventions

- use lowercase kebab-case file names
- reserve root-level docs for repo entrypoints only
- keep detailed material under `docs/`

## Linking Conventions

- use relative Markdown links
- link to the canonical location, not to old stubs
- update `README.md` and `docs/README.md` when adding or removing top-level documentation entries

## Source Of Truth Policy

- Markdown is the maintained source of truth
- PDFs are derived formal deliverables
- diagram source files must remain editable alongside rendered assets

## Update Requirements

Update documentation whenever any of these change:

- code paths exposed through routes
- environment variables or defaults
- output artifacts or file locations
- plugin identities or channel requirements
- retention or storage behavior
- authentication or account behavior

