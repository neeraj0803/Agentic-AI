# AIDLC-102 Test Documentation

## Executive Summary
This document outlines the testing strategy and detailed test cases for the AIDLC-102 story, which focuses on ensuring the integrity and performance of the AIDLC Inference Gateway Service. The primary objectives include verifying PII masking, maintaining latency under specified thresholds, and ensuring resilience against downstream service failures. The testing will cover boundary conditions, non-functional requirements (NFRs), and various user scenarios to ensure comprehensive coverage.

## Acceptance Criteria Traceability
The acceptance criteria for AIDLC-102 are as follows:

1. **AC1**: Verify PII masking on boundary edge cases: concatenated phone numbers without dashes, international passport numbers, and synthetic SSNs.
2. **AC2**: Verify p95 latency stays under 45ms under a load of 500 concurrent requests/sec.
3. **AC3**: Test resilience when the downstream toxicity classifier service returns HTTP 500 or times out (>100ms fail-open vs fail-closed policy).

| Acceptance Criteria | Test Cases Covered |
|---------------------|--------------------|
| AC1                 | TC-AIDLC-102-01, TC-AIDLC-102-02, TC-AIDLC-102-03, TC-AIDLC-106-01, TC-AIDLC-106-02 |
| AC2                 | TC-AIDLC-102-04 |
| AC3                 | TC-AIDLC-102-05 |

## Complete Test Cases

### Manual Test Cases

| Test ID              | Title                                                  | Type     | Priority | Pre-Conditions                                         | Steps                                                                                     | Expected Result                                                   | AC Covered |
|---------------------|--------------------------------------------------------|----------|----------|-------------------------------------------------------|-------------------------------------------------------------------------------------------|------------------------------------------------------------------|------------|
| TC-AIDLC-102-01     | Verify PII masking on concatenated phone numbers       | Boundary | High     | User has access to the AIDLC Inference Gateway Service. | 1. Input concatenated phone numbers without dashes into the system. <br> 2. Submit the request for processing. | The system masks the PII correctly and does not expose the phone number. | AC1        |
| TC-AIDLC-102-02     | Verify PII masking on international passport numbers    | Boundary | High     | User has access to the AIDLC Inference Gateway Service. | 1. Input international passport numbers into the system. <br> 2. Submit the request for processing. | The system masks the PII correctly and does not expose the passport number. | AC1        |
| TC-AIDLC-102-03     | Verify PII masking on synthetic SSNs                    | Boundary | High     | User has access to the AIDLC Inference Gateway Service. | 1. Input synthetic SSNs into the system. <br> 2. Submit the request for processing. | The system masks the PII correctly and does not expose the SSN. | AC1        |
| TC-AIDLC-102-04     | Verify p95 latency under load                           | NFR      | Critical | Load testing tools are set up to simulate 500 concurrent requests. | 1. Simulate 500 concurrent requests to the system. <br> 2. Measure the response time for each request. | p95 latency should be under 45ms.                                | NFR-LATENCY |
| TC-AIDLC-102-05     | Test resilience on HTTP 500 response from downstream service | NFR      | High     | Downstream toxicity classifier service is configured to return HTTP 500. | 1. Send a request to the system that triggers the downstream service. <br> 2. Observe the system's response. | The system should fail-open and handle the error gracefully.      | NFR-RESILIENCE |
| TC-AIDLC-101-01     | Validate handling of malformed JSONL rows              | Negative | High     | User has access to the AIDLC Eval Engine.             | 1. Input a dataset with malformed JSONL rows. <br> 2. Submit the dataset for processing. | The system fails gracefully with line-numbered error reports.    | Negative    |
| TC-AIDLC-101-02     | Test rate limit handling from judge model API          | Negative | High     | Judge model API is configured to return HTTP 429.     | 1. Send requests to the judge model API until rate limit is hit. <br> 2. Observe the system's behavior. | The system triggers exponential backoff up to 3 retries before pausing the job. | Negative    |
| TC-AIDLC-101-03     | Verify aggregate scoring calculation                    | Functional | High    | User has access to the AIDLC Eval Engine.             | 1. Input valid scoring data for Hallucination, Tone, and Instruction Following. <br> 2. Submit the scoring request. | The system correctly calculates the weighted averages.            | Functional  |
| TC-AIDLC-106-01     | Sanity check for empty strings in reference_output     | Sanity   | High     | User has access to the AIDLC Eval Service.            | 1. Prepare a dataset containing empty strings in 'reference_output'. <br> 2. Attempt to upload the dataset. | The upload is blocked with an appropriate error message.          | AC1        |
| TC-AIDLC-106-02     | Smoke check for BLEU/ROUGE metrics calculation         | Smoke    | Medium   | User has access to the AIDLC Eval Service.            | 1. Prepare a valid dataset with 10 rows. <br> 2. Submit the dataset for BLEU/ROUGE metric calculation. | The metrics are calculated normally without false-positive 100% scores. | AC1        |

## Regression Scope
The regression testing will focus on the following modules and critical paths:

### Modules Affected
- AIDLC Inference Gateway Service
- AIDLC Eval Engine
- AIDLC Eval Service

### Critical Regression Paths
- Checkout transaction processing
- Downstream service error handling
- Input validation and scoring calculations

## Risk Mitigations
1. **Downstream Service Failures**: Ensure robust error handling and circuit breaker patterns are implemented to prevent cascading failures.
2. **Performance Under Load**: Conduct thorough load testing to validate that the system meets latency requirements under peak conditions.
3. **Input Validation**: Implement strict schema validation to prevent malformed inputs from causing system failures or incorrect processing.

## Assumptions and Gaps
- Assuming the downstream toxicity classifier service can be configured to simulate HTTP 500 responses.
- Assuming the load testing tools can accurately simulate 500 concurrent requests.
- Gaps in documentation regarding the exact structure of malformed JSONL rows.

This document serves as a comprehensive guide for the testing of AIDLC-102, ensuring that all acceptance criteria are met and that the system is robust against potential risks.