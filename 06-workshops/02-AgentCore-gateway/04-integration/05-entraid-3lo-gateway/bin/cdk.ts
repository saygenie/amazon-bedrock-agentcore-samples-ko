#!/usr/bin/env node
// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0
import * as cdk from "aws-cdk-lib/core";
import { CdkEntraIdStack } from "../infra/cdk-stack";

const app = new cdk.App();

// context에서 가져오는 스택 이름 - 여러 독립 배포를 지원
const stackName = app.node.tryGetContext("stackName") || "CdkStackIdeMcpEntraId";

new CdkEntraIdStack(app, stackName, {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
});
