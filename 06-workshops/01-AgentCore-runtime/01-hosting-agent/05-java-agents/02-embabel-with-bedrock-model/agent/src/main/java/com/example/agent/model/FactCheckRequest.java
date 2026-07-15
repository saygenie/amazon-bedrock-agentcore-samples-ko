package com.example.agent.model;

import java.util.List;

/** 사용자가 제출한 팩트 체크 대상 주장입니다. GOAP 파이프라인의 진입점입니다. */
public record FactCheckRequest(List<String> claims) {}
