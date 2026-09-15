# Project Skills

Add project-specific skills here. Each skill is a **folder** with `SKILL.md` and YAML frontmatter.

## Structure

```
my-skill/
├── SKILL.md         # Required: instructions + frontmatter
├── scripts/         # Optional: executable helpers
├── resources/       # Optional: reference docs
└── templates/       # Optional: code templates
```

## SKILL.md frontmatter

```yaml
---
name: my-skill
description: What this skill does and when to invoke it. Claude uses this to auto-trigger.
---

# Skill instructions
...
```

## When to add a project skill

- Reusable workflows specific to this project (e.g. `landing-builder`, `dashboard-builder`)
- Long reference material (auto-loads only when relevant — saves context)
- Stack/domain specific helpers

## When NOT to add a project skill

- Universal skills (TDD, security review, postgres design) belong in `~/.claude/skills/` globally
- If it duplicates a built-in or existing global skill, do not re-add

## Invocation

- Manual: `/skill-name` in chat
- Auto: Claude triggers based on `description` matching the current task

## Token cost

Description always loads (~150 chars). Body only loads when invoked. Cheap.

## See also

- Official skills docs: https://code.claude.com/docs/en/skills
- Examples: clone official skills from GitHub (e.g. `supabase/supabase-postgres-best-practices`)
