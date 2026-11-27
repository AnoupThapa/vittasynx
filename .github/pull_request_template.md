## What and why
<!-- Summary of the change -->

## Principle checklist (docs/00-project/engineering-principles.md)
- [ ] **1. Documentation first:** spec section implemented or updated: <!-- path#section -->
- [ ] **2. Financial rules first:** no calculation changed, OR the rule, rule version and worked-example tests are updated and approved
- [ ] **3. Tenant security:** new tenant data has `organisation_id`, RLS policy and isolation tests; no secrets or real customer data committed
- [ ] **4. Tests:** exact results pasted below; nothing skipped or weakened
- [ ] **5. No deployment:** this PR does not deploy or change production data

## Test results (exact)
```
backend pytest:
frontend typecheck / unit:
e2e (if workflows changed):
```

## Database / migration changes

## Security and tenant-isolation considerations

## Known limitations and follow-up

## Review
- Author (tool/person):
- Independent reviewer (must differ from author):
