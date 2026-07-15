package com.example.agent.model;

import java.util.List;

/** 사람이 읽을 수 있는 최종 팩트 체크 요약입니다. GOAP 파이프라인의 최종 목표입니다. */
public record FactCheckReport(String summary, List<VerifiedClaims.VerifiedClaim> verifiedClaims) {}
