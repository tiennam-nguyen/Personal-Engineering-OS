---
id: art_cdc3dc70508d4a629bdf4565b4fbbf7d
type: system.eval_report
schema_version: 1
title: 'Evaluation: model.claim-extraction.core / deterministic-claim-extractor-v1@1'
status: accepted
workspace_id: ws_5e87f5d6d22a4b3d937510bea8ddead3
created_at: '2026-08-10T04:08:50.366430Z'
updated_at: '2026-08-10T04:08:50.366430Z'
authors:
- kind: system
  id: peos
sensitivity: private
tags:
- evaluation
- claim_extraction
links: []
provenance:
  producer: system
  run_id: run_e5717949da8b4057aab29199b1579238
  source_refs: []
payload:
  suite:
    name: model.claim-extraction.core
    version: 1.0.0
    task_kind: claim_extraction
    fingerprint: sha256:dcbd9cddcd5894db19a0022461421eff8999f0bc78b27d0674af69250e5a11ff
    protocol_ref:
      name: research.claim-extraction
      version: 1.0.0
      sha256: sha256:795f61056b4d2d3068c7f13190ea4084832b5c1231719e42c7c3b56eb41d8440
    output_contract:
      name: research.candidate_claim_set.v1
      schema_hash: sha256:a219de3c8d569a2005b9d840246608f0dcede4432b4c30337f5bf4a6f16b19b8
    scorer_versions:
    - deterministic.contract.v1
    - deterministic.budget.v1
    - reference.exact_output.v1
    thresholds:
      deterministic_all_pass: true
      min_reference_pass_rate: 1.0
    budget:
      max_provider_calls_per_case: 1
      max_input_tokens_per_case: 10000
      max_output_tokens_per_case: 10000
      max_input_bytes_per_case: 1000000
      max_output_bytes_per_case: 1000000
  route:
    provider: mock
    model: deterministic-claim-extractor-v1
    model_revision: '1'
    route_fingerprint: sha256:f81ab6284182afbe146ffc96fd1875725f63cfec16757e23723e58dec29df4ba
  cases:
  - case_id: claim_extraction.basic
    frozen_case_hash: sha256:9b4c3f04217830541ffb7a7efeeb98a83cc8b0be70793b7ae6f9a34e9d1c0ee8
    request_fingerprint: sha256:faa287985eaa3afe837236c610c27f1f8d24dfcda4bd9a81eb07121e98cb1ea8
    response_hash: sha256:ee2261d60096458c14b2af03a2300a9a3fed8a7f82a0d5ca8f0ab3d6087bda56
    provider_request_id: mockreq_faa287985eaa3afe837236c610c27f1f
    deterministic_scorers:
    - scorer: deterministic.contract.v1
      passed: true
      reason_codes: []
    - scorer: deterministic.budget.v1
      passed: true
      reason_codes: []
    reference_scorers:
    - scorer: reference.exact_output.v1
      passed: true
      reason_codes: []
    usage:
      provider_calls: 1
      cache_hit_count: 0
      input_bytes: 754
      output_bytes: 595
      input_tokens: 14
      output_tokens: 10
      token_measurement: mock_whitespace_v1
      observed_wall_seconds: 0.0
      monetary_cost: null
      pricing_status: unknown
  aggregate:
    deterministic_gate:
      required_scorer_count: 2
      passed_count: 2
      failed_count: 0
      all_required_passed: true
      failure_reason_codes: []
    reference_quality:
      matching_cases: 1
      total_cases: 1
      pass_rate: 1.0
      configured_minimum: 1.0
    resource_usage:
      provider_calls: 1
      cache_hit_count: 0
      input_bytes: 754
      output_bytes: 595
      input_tokens: 14
      output_tokens: 10
      token_measurement: mock_whitespace_v1
      observed_wall_seconds: 0.0
      monetary_cost: null
      pricing_status: unknown
  qualification:
    status: QUALIFIED
    reasons: []
  method:
    evaluator_version: 1.0.0
    cache_policy: bypass
    token_measurement: mock_whitespace_v1
  source_run_id: run_e5717949da8b4057aab29199b1579238
integrity:
  content_hash: sha256:f49b90c7dd5258749b20bc05bbc4040e2ca71c87ed900ee0632273f9234d08b3
---

# Evaluation Report

Deterministic qualification evidence.
