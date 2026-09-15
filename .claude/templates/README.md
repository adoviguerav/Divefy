# Templates

Reusable `CLAUDE.md` templates for new projects. Each template encodes an opinionated stack + patterns.

## Available templates

| File | Stack | When to use |
|---|---|---|
| `saas.md` | Next.js 15 + Supabase + Stripe + Resend + Vercel | SaaS B2C with paid subscriptions, landing + dashboard, transactional emails |

## How to use

The `/define_project` command scans this folder and offers templates as optional starting point. You can also reference one manually:

```bash
cp .claude/templates/saas.md CLAUDE.md
```

Then fill placeholders `[Fill...]` manually or run `/define_project` to populate via Q&A.

## Add new template

1. Create `<name>.md` in this folder
2. Add frontmatter with `name`, `description`, `stack`, `applies_when`
3. Use placeholders `[Fill...]` for project-specific sections
4. Update the table above
