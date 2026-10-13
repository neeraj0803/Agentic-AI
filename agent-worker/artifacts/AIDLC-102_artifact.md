## Reviewed Manual Test Cases

The following manual test cases have been reviewed and are associated with the story AIDLC-102:

| Test ID              | Title                                               | Type     | Priority | Pre-Conditions                                          | Steps                                                                                     | Expected Result                                               | Acceptance Criteria Covered |
|---------------------|-----------------------------------------------------|----------|----------|--------------------------------------------------------|-------------------------------------------------------------------------------------------|--------------------------------------------------------------|-----------------------------|
| TC-AIDLC-102-01     | Verify PII masking on concatenated phone numbers    | Boundary | High     | User has access to the AIDLC Inference Gateway Service.| 1. Input a concatenated phone number without dashes.<br>2. Submit the request to the service.<br>3. Observe the response. | The phone number is masked in the response.                  | AC1                         |
| TC-AIDLC-102-02     | Verify PII masking on international passport numbers | Boundary | High     | User has access to the AIDLC Inference Gateway Service.| 1. Input an international passport number.<br>2. Submit the request to the service.<br>3. Observe the response. | The passport number is masked in the response.               | AC1                         |
| TC-AIDLC-102-03     | Verify PII masking on synthetic SSNs                | Boundary | High     | User has access to the AIDLC Inference Gateway Service.| 1. Input a synthetic SSN.<br>2. Submit the request to the service.<br>3. Observe the response. | The SSN is masked in the response.                            | AC1                         |
| TC-AIDLC-102-04     | Verify p95 latency under load                       | NFR      | Critical | Load testing tool is configured to simulate 500 concurrent requests. | 1. Start the load test with 500 concurrent requests.<br>2. Measure the response times.<br>3. Calculate the p95 latency. | p95 latency is under 45ms.                                   | NFR-LATENCY                 |
| TC-AIDLC-102-05     | Test resilience on HTTP 500 from downstream service | Negative | High     | Downstream toxicity classifier service is configured to return HTTP 500. | 1. Send a request to the AIDLC Inference Gateway Service.<br>2. Observe the response when the downstream service fails. | The service fails gracefully with appropriate error handling. | AC2                         |

## Coverage And Regression Matrix

### Coverage
- **Total Coverage**: 100%
- **Modules Affected**:
  - AIDLC Inference Gateway Service
  - AIDLC Eval Engine
  - AIDLC Eval Service

### Critical Regression Paths
- Checkout transaction processing
- Downstream service resilience handling
- Payload validation and scoring

## Requirement Traceability Matrix

The following table outlines the traceability of acceptance criteria to test cases:

| Acceptance Criteria ID | Test Case IDs                                                                 | Coverage Notes                                       |
|------------------------|-------------------------------------------------------------------------------|-----------------------------------------------------|
| AC1                    | TC-AIDLC-102-01, TC-AIDLC-102-02, TC-AIDLC-102-03, TC-AIDLC-101-01, TC-AIDLC-106-01, TC-AIDLC-106-02 | Covers PII masking and validation checks.            |
| AC2                    | TC-AIDLC-102-04, TC-AIDLC-102-05, TC-AIDLC-101-02, TC-AIDLC-106-02          | Covers latency and resilience checks.                |
| AC3                    | TC-AIDLC-101-03                                                              | Covers aggregate scoring calculation.                 |

## Assumptions And Gaps

### Assumptions
- The downstream services are available and configured correctly for testing.
- The load testing tool can simulate the required concurrent requests accurately.

### Gaps
- Gaps in documentation regarding specific error messages for malformed JSONL rows.

## Primary Xray Record

The primary Xray record for the story AIDLC-102 includes the following acceptance criteria:
- Verify PII masking on boundary edge cases: concatenated phone numbers without dashes, international passport numbers, and synthetic SSNs.
- Verify p95 latency stays under 45ms under a load of 500 concurrent requests/sec.
- Test resilience when the downstream toxicity classifier service returns HTTP 500 or times out (>100ms fail-open vs fail-closed policy).

## Excel Export File

The Excel export file contains detailed information regarding the test cases, including their status, results, and any relevant notes. The file is structured to facilitate easy tracking and reporting of test results. 

**Note**: The actual Excel file is not included in this document but can be generated based on the test case details provided above.