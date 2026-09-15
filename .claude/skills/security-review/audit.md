# Security Audit Reference

Detailed audit phases, severity tiers, confidence calibration, false-positive rules, and output format. Read this when in Audit Mode (see SKILL.md "Two Modes").

---

## Audit Mode — Systematic Phases

Run only when in Audit Mode. Use the Grep tool for all code searches; scope file extensions to the detected stack.

### Phase 1: Stack & Attack Surface

Detect stack first to prioritize scanning:
```bash
ls package.json tsconfig.json 2>/dev/null && echo "STACK: Node/TypeScript"
grep -q "next" package.json 2>/dev/null && echo "FRAMEWORK: Next.js"
grep -q "supabase" package.json 2>/dev/null && echo "USES: Supabase"
grep -q "stripe" package.json 2>/dev/null && echo "USES: Stripe"
```

Map the attack surface:
- Public endpoints (no auth)
- Authenticated endpoints
- Admin-only routes
- File upload paths
- External integrations (webhooks, OAuth)
- Background jobs

Output a brief summary before continuing. This is reasoning, not findings.

### Phase 2: Secrets Archaeology

Scan git history for leaked credentials:
```bash
git log -p --all -S "sk-" --diff-filter=A -- "*.env" "*.ts" "*.js" 2>/dev/null
git log -p --all -G "ghp_|gho_|github_pat_" 2>/dev/null
git log -p --all -G "AKIA[0-9A-Z]{16}" 2>/dev/null
git log -p --all -G "stripe.*sk_live_" 2>/dev/null
```

Check `.env` files tracked by git:
```bash
git ls-files '*.env' '.env.*' 2>/dev/null | grep -v '.example\|.sample\|.template'
grep -q "^\.env" .gitignore 2>/dev/null || echo "WARNING: .env NOT in .gitignore"
```

**Severity:** CRITICAL for active secret patterns. HIGH for `.env` tracked. MEDIUM for suspicious `.env.example` values.

### Phase 3: Dependency Supply Chain

Beyond `npm audit`:
```bash
npm audit --json 2>/dev/null | jq '.metadata.vulnerabilities'
# Production deps with install scripts (supply chain vector)
node -e "const p=require('./package.json');Object.keys(p.dependencies||{}).forEach(d=>{try{const pp=require(d+'/package.json');if(pp.scripts&&(pp.scripts.preinstall||pp.scripts.postinstall||pp.scripts.install))console.log('INSTALL SCRIPT:',d)}catch{}})" 2>/dev/null
# Lockfile committed
git ls-files package-lock.json yarn.lock pnpm-lock.yaml 2>/dev/null | head -1 || echo "WARNING: no lockfile tracked"
```

**Severity:** CRITICAL for high/critical CVEs in direct prod deps. HIGH for install scripts in prod deps / missing lockfile.

### Phase 4: CI/CD Pipeline

For each `.github/workflows/*.yml`:
- Unpinned third-party actions (no SHA)
- `pull_request_target` + PR code checkout (RCE risk)
- Script injection via `${{ github.event.* }}` in `run:` steps
- Secrets as env vars without masking

```bash
grep -rn "pull_request_target" .github/workflows/ 2>/dev/null
grep -rn "github.event.pull_request.body\|github.event.issue.body" .github/workflows/ 2>/dev/null
grep -rn "uses:.*@[^a-f0-9]" .github/workflows/ 2>/dev/null | grep -v "actions/"
```

**Severity:** CRITICAL for `pull_request_target` + PR checkout / script injection. HIGH for unpinned third-party actions.

### Phase 5: Webhook & Integration Audit

Find webhook routes without signature verification:
```bash
grep -rln "webhook\|/hook/\|callback" --include="*.ts" --include="*.js" app/api 2>/dev/null
# For each match, verify it ALSO contains signature/hmac/stripe-signature/svix-id checks
```

Find TLS verification disabled:
```bash
grep -rn "rejectUnauthorized.*false\|NODE_TLS_REJECT_UNAUTHORIZED.*0\|verify.*false" --include="*.ts" --include="*.js" 2>/dev/null
```

**Severity:** CRITICAL for webhooks without signature verification. HIGH for TLS disabled in prod paths.

### Phase 6: LLM & AI Security

For projects using Claude/OpenAI/LLMs:
- User input flowing into system prompts (prompt injection)
- Unsanitized LLM output rendered as HTML (`dangerouslySetInnerHTML`, `v-html`)
- `eval()` / `Function()` on LLM responses
- Tool/function calls without validation
- Unbounded LLM calls (cost attack)

```bash
grep -rn "dangerouslySetInnerHTML\|innerHTML.*=" --include="*.tsx" --include="*.ts" 2>/dev/null
grep -rn "system.*prompt.*\\$\|systemPrompt.*\\$\|system:.*user" --include="*.ts" 2>/dev/null
```

**Severity:** CRITICAL for user input in system prompts / unsanitized LLM output as HTML / eval of LLM output. HIGH for missing tool validation. MEDIUM for unbounded LLM calls.

### Phase 7: OWASP Top 10

Targeted checks per category. Use Grep for all searches.

**A01 Broken Access Control:**
- Missing auth on controllers (`skip_before_action`, no `getUser()` in handler)
- Direct object reference (`params.id` used in queries without ownership check)

**A02 Cryptographic Failures:**
- Weak crypto: `md5`, `sha1`, `DES`, `ECB`
- Hardcoded secrets (covered in Phase 2)

**A03 Injection:**
- SQL injection: string interpolation in `db.query(`)
- Command injection: `exec()`, `spawn(`, `popen(`
- Template injection: `eval()`, `Function()`, `dangerouslySetInnerHTML`

**A04 Insecure Design:**
- Rate limits on `/api/auth/*`
- Account lockout after failed attempts
- Server-side validation of business logic

**A05 Security Misconfiguration:**
- CORS wildcard in production (`origin: '*'`)
- Missing CSP headers
- Debug mode in production

**A06 Vulnerable Components:** See Phase 3.

**A07 Auth Failures:**
- Weak session management
- Missing MFA on admin
- JWT in localStorage (use httpOnly cookies — see Section 4)

**A08 Software/Data Integrity:**
- Webhook signature verification (Phase 5)
- Unsigned CI artifacts
- Auto-update without verification

**A09 Logging/Monitoring Failures:**
- No audit logs on sensitive operations
- Logs leak sensitive data (covered in Section 8)

**A10 SSRF:**
- User-controlled URLs in server-side `fetch()`, `axios.get(url)`
- No allowlist on outbound URLs

---

## Severity & Confidence

### Severity Tiers
- **CRITICAL**: Active vulnerability, exploitable now, public-facing. Fix immediately.
- **HIGH**: Exploitable under realistic conditions. Fix this sprint.
- **MEDIUM**: Defense-in-depth gap. Fix in normal flow.
- **LOW**: Hardening opportunity. Document, fix if convenient.

### Confidence Scale
Rate each finding 1-10:
- **9-10**: Saw the actual vulnerable code path. Traced data flow end-to-end.
- **7-8**: Strong pattern match, partial trace. Likely real.
- **5-6**: Suspicious pattern but couldn't fully verify (e.g., uses external lib that may already sanitize).
- **1-4**: Theoretical concern, no concrete evidence.

In **Daily audit mode**, only report findings with confidence ≥ 8. Below that, mention "additional speculative findings available, switch to comprehensive mode to see them."

---

## False Positive Rules

These are NOT findings (do not report):
- Placeholder secrets: `your_api_key_here`, `changeme`, `TODO`, `<replace_me>`
- Test fixtures with secrets, unless same value also in production code
- `dangerouslySetInnerHTML` on content the developer wrote (not user input)
- `eval()` in build tooling (vite, webpack configs)
- `pull_request_target` without PR ref checkout (safe pattern)
- TLS verification disabled in test/dev files (path contains `test/`, `__tests__/`, `dev/`)
- devDependency CVEs → MEDIUM max, not CRITICAL/HIGH
- First-party `actions/*` unpinned → MEDIUM, not HIGH
- Internal service-to-service webhooks on private networks → MEDIUM max
- Skills/scripts using `curl` for legitimate purposes (downloads, health checks) — only flag if target URL is suspicious or includes credential vars
- User content in the user-message position of an LLM conversation is NOT prompt injection — only flag when it enters system prompts or tool schemas

---

## Audit Output Format

For each finding produce:

```
FINDING #N: [Title]
File: path/to/file.ts:LINE
Severity: CRITICAL | HIGH | MEDIUM | LOW
Confidence: N/10
OWASP: [A01-A10] (if applicable)

What:
[1-2 lines explaining the vulnerability]

Evidence:
[code snippet or grep match]

Exploit:
[how it could be exploited]

Fix:
[concrete remediation, ideally code example]
```

Group findings by severity at the end. Summary:
- N CRITICAL, N HIGH, N MEDIUM, N LOW
- Confidence breakdown
- Top 3 most urgent fixes

