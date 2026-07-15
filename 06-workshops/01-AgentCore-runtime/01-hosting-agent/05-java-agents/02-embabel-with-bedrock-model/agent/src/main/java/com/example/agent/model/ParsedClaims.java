package com.example.agent.model;

import java.util.List;

/** 사용자 요청에서 추출하여 LLM이 파싱한 개별 주장입니다. */
public record ParsedClaims(List<String> claims) {}
