# AI-Powered SEM Workflow Automation

> A semi-automated workflow system for Yandex SEM campaign preparation, built with Python and LLMs.

## Overview

This project aims to automate repetitive tasks in Yandex Search Engine Marketing (SEM), while keeping human review at key decision points.

Instead of pursuing full automation, the system follows a **Human-in-the-Loop** workflow, allowing AI to handle repetitive analysis and content generation while important business decisions remain under manual review.

Current development focuses on the **pre-campaign** stage.

---

## Project Goals

The complete workflow is planned to cover four stages:

- Pre-campaign
  - Market research
  - Competitor analysis
  - Keyword generation
  - Ad copy generation
  - Landing page diagnosis

- Campaign launch
  - Upload advertising materials

- Campaign optimization
  - Performance analysis
  - Negative keyword discovery
  - Keyword expansion
  - Weekly / Monthly reports

- Campaign summary
  - Final campaign presentation

At present, the project is implementing the first stage.

---

## Design Principles

### Human-in-the-Loop

Some business decisions should remain manual.

For example:

AI → keyword_v1.md

↓

Human review

↓

keyword_v1_reviewed.md

↓

Next module continues

This design keeps AI efficient while maintaining business quality.

---

### File-based Workflow

Instead of passing objects directly between modules, each module communicates through files.

Example:

raw_text.txt

↓

project_brief.md

↓

keyword_v1.md

↓

keyword_v1_reviewed.md

↓

ad_copy.md

This makes every step independently testable and replaceable.

---

### Modular Architecture

```
User

↓

Workflow

↓

Service Layer

↓

AI Core

↓

Infrastructure

↓

Project Data
```

---

## Current Progress

Completed:

- PDF / DOCX / Excel reader
- AI project brief generation
- Keyword generation (Version 1)
- Local project management
- Prompt management
- Git version control

In Progress:

- Ad copy generation
- Wordstat integration (Human-assisted)

Planned:

- Website crawler
- Competitor discovery
- Report generation
- Yandex Direct API
- Metrika reporting

---

## Tech Stack

- Python
- VS Code
- Git
- GitHub
- OpenRouter API
- GPT / DeepSeek
- Markdown

---

## Project Structure

```
modules/
prompts/
projects/
outputs/
workflows/
main.py
```

---

## Roadmap

- [x] Project structure
- [x] AI analysis
- [x] Keyword generation
- [ ] Ad copy generation
- [ ] Wordstat integration
- [ ] Report generation
- [ ] Yandex Direct API
- [ ] Campaign analytics
- [ ] Web interface

---

## Disclaimer

This repository is a development version.

Customer data, API keys, and commercial materials are intentionally excluded.