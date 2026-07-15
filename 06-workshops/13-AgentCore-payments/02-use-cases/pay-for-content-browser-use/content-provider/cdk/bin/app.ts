#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib";
import { ContentProviderStack } from "../lib/content-provider-stack";

const app = new cdk.App();

// 필수 CDK context 값(--context 또는 cdk.json으로 전달)
//   PAY_TO            merchant wallet address(0x...)
//   PRICE_USDC_UNITS  USDC atomic unit 단위의 가격, 소수점 6자리(기본값: 100000 = $0.10)
//   NETWORK           CAIP-2 network 식별자(기본값: eip155:84532 = Base Sepolia)
//   USDC_ADDRESS      USDC contract address(기본값: Base Sepolia USDC)

new ContentProviderStack(app, "AgentCoreContentProvider", {
  env: {
    // Lambda@Edge는 us-east-1에 배포해야 합니다.
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: "us-east-1",
  },
  description:
    "AgentCore Payments — x402 demo content provider (CloudFront + Lambda@Edge)",
});
