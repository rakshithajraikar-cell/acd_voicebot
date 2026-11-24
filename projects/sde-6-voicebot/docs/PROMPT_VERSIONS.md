# Academiaai Voicebot — Record of Prompt Versions (W3)

**Workstream**: W3 – Context, Vision & Reasoning  
**Team**: SDE 6  
**Author**: Prathibhashree K  
**Version Governance Registry**: Weeks 1–4  

---

## 1. Version Governance Overview

All reasoning prompts used by the Academiaai Voicebot are strictly version-controlled, immutable at runtime, and maintain architectural isolation between:
1. **Trusted Instructions**: System policy, persona, grounding requirements, and safety fences.
2. **Untrusted Context**: Screen frames, OCR snippets, and document contents.
3. **Untrusted User Query**: User audio transcripts or typed queries.

---

## 2. Prompt Versions Registry

### Version `1.0.0` (Week 1 Foundation)
- **Status**: Stable / Historical Baseline
- **Release Date**: Week 1 (Day 7)
- **Quarantine Delimiters**: `<untrusted_context schema_version="1.0.0">` and `<untrusted_user_query schema_version="1.0.0">`
- **Core Directives**:
  - Grounding requirement: cite exact `SourceReference` IDs for all claims.
  - Uncertainty handling: state insufficient evidence explicitly when data is absent.
  - Basic injection defense: regex check on user queries for `"ignore previous instructions"`.
  - Offline mock mode compliance.
- **Deficiencies Addressed in Later Versions**: Only scanned user query for prompt injection; did not scan screen content or mask PII.

---

### Version `1.1.0` (Week 2 High Assurance)
- **Status**: Active / Production
- **Release Date**: Week 2 (Day 14)
- **Quarantine Delimiters**: `<untrusted_context schema_version="1.1.0">` and `<untrusted_user_query schema_version="1.1.0">`
- **Enhancements**:
  - Strict provenance: every fact returned must be cited to a valid `source_id`.
  - Honest uncertainty: mandatory surfacing of evidence gaps.
  - Zero tool access: tool invocation proposals explicitly disclaimed without downstream approval gates.
  - XML entity encoding: `<` and `>` characters inside untrusted text are escaped to prevent delimiter injection.

---

### Version `1.2.0` (Week 3 & 4 Release Hardening)
- **Status**: Recommended / Default Release Version
- **Release Date**: Week 4 (Day 30 Release Gate)
- **Quarantine Delimiters**: `<untrusted_context schema_version="1.2.0">` and `<untrusted_user_query schema_version="1.2.0">`
- **Enhancements & Security Fences**:
  1. **Dual-Vector Injection Defense**: Scans both user query and all screen context items against 16+ adversarial injection vectors (instruction overrides, developer/DAN mode triggers, system prompts leakage, file deletion directives).
  2. **Data-Only Directives**: Explicit immutable instruction that all text enclosed within untrusted tags is passive data, never executable commands.
  3. **Automated PII Redaction**: Emails, Bearer JWTs, passwords, and API tokens are redacted before prompt assembly.
  4. **Workflow Approval Gate**: Formal integration with `WorkflowProposal` contracts for consequential action approval.

---

## 3. Template Comparison Matrix

| Capability | Version 1.0.0 | Version 1.1.0 | Version 1.2.0 (Release) |
| :--- | :---: | :---: | :---: |
| Strict Structural Separation | ✅ Yes | ✅ Yes | ✅ Yes |
| Evidence Grounding & Citations | ✅ Yes | ✅ Yes | ✅ Yes |
| Honest No-Evidence Handling | ✅ Yes | ✅ Yes | ✅ Yes |
| User Query Injection Scanning | ⚠️ Basic | ⚠️ Basic | ✅ Comprehensive (16+ vectors) |
| Screen Content Injection Scanning | ❌ No | ❌ No | ✅ Yes |
| Automated PII / Credential Redaction | ❌ No | ❌ No | ✅ Yes |
| Delimiter Breakout Sanitization | ⚠️ Partial | ✅ Yes | ✅ Yes |
| Downstream Workflow Proposal Gate | ❌ No | ⚠️ Notice only | ✅ Validated Schema Gate |
