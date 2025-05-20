## Summary

This document outlines the SOC 2 certification process for Ceneca, covering both Type I and Type II audits. It explains the AICPA Trust Services Criteria, describes the detailed steps—from scoping and readiness assessment through control implementation and auditor engagement—to achieve compliance, and highlights which security, availability, processing integrity, confidentiality, and privacy controls an on-prem AI data analysis agent must prioritize. It also provides realistic timelines for each audit type, helping Ceneca plan its compliance roadmap efficiently. ([aicpa-cima.com](https://www.aicpa-cima.com/topic/audit-assurance/audit-and-assurance-greater-than-soc-2?utm_source=chatgpt.com), [secureframe.com](https://secureframe.com/hub/soc-2/type-1-vs-type-2?utm_source=chatgpt.com), [vanta.com](https://www.vanta.com/collection/soc-2/soc-2-audit-timeline?utm_source=chatgpt.com))

## 1. Overview of SOC 2

SOC 2 is an attestation report on a service organization’s controls relevant to one or more of the AICPA Trust Services Criteria: Security, Availability, Processing Integrity, Confidentiality, and Privacy ([aicpa-cima.com](https://www.aicpa-cima.com/topic/audit-assurance/audit-and-assurance-greater-than-soc-2?utm_source=chatgpt.com), [secureframe.com](https://secureframe.com/hub/soc-2/trust-services-criteria?utm_source=chatgpt.com)). Reports come in two forms:

* **Type I** evaluates the design of controls at a specific point in time ([secureframe.com](https://secureframe.com/hub/soc-2/type-1-vs-type-2?utm_source=chatgpt.com)).
* **Type II** assesses both the design and operating effectiveness of those controls over a defined period (typically 3–12 months) ([secureframe.com](https://secureframe.com/hub/soc-2/type-1-vs-type-2?utm_source=chatgpt.com)).

## 2. Trust Services Criteria (TSC)

Ceneca must choose which of the five TSCs to include, though **Security** is mandatory for all SOC 2 engagements ([secureframe.com](https://secureframe.com/hub/soc-2/trust-services-criteria?utm_source=chatgpt.com)). The full list is:

1. **Security (Common Criteria):** Protects against unauthorized access and cyber threats ([secureframe.com](https://secureframe.com/hub/soc-2/trust-services-criteria?utm_source=chatgpt.com)).
2. **Availability:** Ensures system uptime and resilience, critical for on-prem deployments ([secureframe.com](https://secureframe.com/hub/soc-2/trust-services-criteria?utm_source=chatgpt.com)).
3. **Processing Integrity:** Guarantees that system processing is complete, valid, accurate, and authorized ([secureframe.com](https://secureframe.com/hub/soc-2/trust-services-criteria?utm_source=chatgpt.com)).
4. **Confidentiality:** Safeguards sensitive data, such as proprietary or customer information, through encryption and access controls ([secureframe.com](https://secureframe.com/hub/soc-2/trust-services-criteria?utm_source=chatgpt.com)).
5. **Privacy:** Covers personal data handling, consent, and GDPR/COPPA-like requirements ([secureframe.com](https://secureframe.com/hub/soc-2/trust-services-criteria?utm_source=chatgpt.com)).

## 3. SOC 2 Type I

### 3.1 Objective and Scope

* **Type I** attests that controls are suitably designed and implemented as of a specific date, but does not test their operating effectiveness ([secureframe.com](https://secureframe.com/hub/soc-2/type-1-vs-type-2?utm_source=chatgpt.com)).

### 3.2 Key Steps

1. **Scoping:** Determine which TSCs apply and what systems/modules are in scope (e.g., database connectors, inference engine). ([secureframe.com](https://secureframe.com/hub/soc-2/audit-process?utm_source=chatgpt.com))
2. **Readiness Assessment:** Conduct gap analysis of current policies, procedures, and tooling against SOC 2 criteria ([vanta.com](https://www.vanta.com/resources/what-is-a-soc-2-readiness-assessment?utm_source=chatgpt.com)).
3. **Control Documentation:** Document policies (access control, change management, incident response), configure tools (logging, monitoring), and collect evidence for each control design ([secureframe.com](https://secureframe.com/hub/soc-2/audit-process?utm_source=chatgpt.com)).
4. **Select Auditor:** Engage an AICPA-accredited auditor for the formal Type I review ([secureframe.com](https://secureframe.com/hub/soc-2/audit-process?utm_source=chatgpt.com)).
5. **Audit Execution:** Auditor reviews design documentation and interviews staff, culminating in a Type I report ([secureframe.com](https://secureframe.com/hub/soc-2/audit-process?utm_source=chatgpt.com)).

### 3.3 Timeline

* **Preparation & Remediation:** 1–3 months, depending on control maturity ([vanta.com](https://www.vanta.com/collection/soc-2/soc-2-audit-timeline?utm_source=chatgpt.com)).
* **Audit Fieldwork:** 2–4 weeks. ([vanta.com](https://www.vanta.com/collection/soc-2/soc-2-audit-timeline?utm_source=chatgpt.com)).
* **Report Delivery:** 1–2 weeks post fieldwork. ([aicpa-cima.com](https://www.aicpa-cima.com/topic/audit-assurance/audit-and-assurance-greater-than-soc-2?utm_source=chatgpt.com))

2. Secureframe: Type 1 vs Type 2 differences ([secureframe.com](https://secureframe.com/hub/soc-2/type-1-vs-type-2?utm_source=chatgpt.com))
3. Vanta: Readiness assessment definition ([vanta.com](https://www.vanta.com/resources/what-is-a-soc-2-readiness-assessment?utm_source=chatgpt.com))
4. Drata: SOC 2 controls examples ([drata.com](https://drata.com/blog/soc-2-controls?utm_source=chatgpt.com))
5. Vanta: Audit timeline ([vanta.com](https://www.vanta.com/collection/soc-2/soc-2-audit-timeline?utm_source=chatgpt.com))
6. Secureframe: Audit process steps ([secureframe.com](https://secureframe.com/hub/soc-2/audit-process?utm_source=chatgpt.com))
7. RSI Security: Common challenges ([blog.rsisecurity.com](https://blog.rsisecurity.com/how-to-overcome-common-challenges-of-the-soc-2-framework/?utm_source=chatgpt.com))
8. TrustNet: Encryption requirements ([trustnetinc.com](https://trustnetinc.com/does-soc-2-require-data-to-be-encrypted/?utm_source=chatgpt.com))
9. AuditBoard: Trust Services Criteria breakdown ([secureframe.com](https://secureframe.com/hub/soc-2/trust-services-criteria?utm_source=chatgpt.com))
10. Vanta: Readiness checklist ([vanta.com](https://www.vanta.com/collection/soc-2/soc-2-readiness-assessment-checklist?utm_source=chatgpt.com))
11. Sprinto: Gap analysis steps citeturn0search12
12. IS Partners: SOC 2 timeline guideline citeturn0search13
13. AuditBoard: Framework introduction citeturn0search14
14. Security Boulevard: Encryption at rest control citeturn0search16
15. Linford Co: TSC guidance citeturn0search17
16. AuditBoard: Type 1 vs Type 2 use cases citeturn0search18
