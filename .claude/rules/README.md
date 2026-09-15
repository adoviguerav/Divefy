# Project Rules

Add project-specific rules here as plain `.md` files. They load only when imported via `@imports` in the project `CLAUDE.md`.

## When to add a project rule

- Stack-specific patterns (e.g. `tailwind-v4.md`, `supabase.md`)
- Domain-specific behavior (e.g. `saas-patterns.md` for Stripe + Resend flows)
- Project conventions that override global defaults

## When NOT to add a project rule

- Universal rules already live in `~/.claude/rules/` (coding-style, security, testing, git-workflow, agents, performance, hooks). Do not duplicate them.

## Format

```markdown
# Rule Name

## Section
Content...
```

No frontmatter needed. Reference from `CLAUDE.md`:

```markdown
@.claude/rules/your-rule.md
```

## Token cost

Each `@imported` rule loads on every session in this project. Keep rules short. If content is long reference material, prefer a skill (see `.claude/skills/README.md`).
