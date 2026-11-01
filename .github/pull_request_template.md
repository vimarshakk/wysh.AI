---
name: 🔧 Pull Request
about: Submit a pull request for wysh.AI
title: '[PR] '
labels: ['pull request']
assignees: ''
---

## 🔧 Pull Request

### Summary
A clear and concise description of what this PR does.

**Related issue**
Closes # (issue number)

**Changes made**
- [ ] Change 1
- [ ] Change 2
- [ ] Change 3

**Tests**
- [ ] I added/updated tests
- [ ] `pytest` passes from `apps/api`
- [ ] No new test failures

**Safety boundary checklist**
- [ ] No PHI or real patient data included
- [ ] Synthetic-only boundary preserved (`synthetic-` prefixed identifiers)
- [ ] No autonomous diagnosis, prescribing, or EHR writes
- [ ] Deny-by-default production mode respected

**Preclinical boundary reminder**
wysh.AI is preclinical engineering — not approved for patient care. All changes must respect deny-by-default and synthetic-only boundaries.

**Additional context**
Add any other context about the PR here.