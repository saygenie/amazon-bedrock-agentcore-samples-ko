package com.example.agent.model;

import java.util.List;

/** 브라우저로 검증한 주장과 상태 및 출처 URL입니다. */
public record VerifiedClaims(List<VerifiedClaim> results) {

    public record VerifiedClaim(
        String claim,
        String status,   // VERIFIED, UNVERIFIED, CONTRADICTED
        String sourceUrl,
        String details
    ) {}
}
