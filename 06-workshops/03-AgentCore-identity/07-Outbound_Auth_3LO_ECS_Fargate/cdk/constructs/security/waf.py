# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Application Load Balancer 보호용 WAF construct."""

from aws_cdk import aws_wafv2 as wafv2
from constructs import Construct


class Waf(Construct):
    """AWS 관리형 규칙 그룹이 포함된 WAF WebACL."""

    def __init__(
        self,
        scope: Construct,
        id: str,
        alb_arn: str,
    ):
        """일반 관리형 규칙이 포함된 WAF를 초기화한다."""
        super().__init__(scope, id)

        self.web_acl = wafv2.CfnWebACL(
            self,
            "WebACL",
            scope="REGIONAL",
            default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="WebACL",
                sampled_requests_enabled=True,
            ),
            rules=[
        # AWS Managed Rules - Core Rule Set(CRS)
                wafv2.CfnWebACL.RuleProperty(
                    name="AWSManagedRulesCommonRuleSet",
                    priority=1,
                    statement=wafv2.CfnWebACL.StatementProperty(
                        managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                            vendor_name="AWS",
                            name="AWSManagedRulesCommonRuleSet",
                        )
                    ),
                    override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="AWSManagedRulesCommonRuleSet",
                        sampled_requests_enabled=True,
                    ),
                ),
        # AWS Managed Rules - Known Bad Inputs
                wafv2.CfnWebACL.RuleProperty(
                    name="AWSManagedRulesKnownBadInputsRuleSet",
                    priority=2,
                    statement=wafv2.CfnWebACL.StatementProperty(
                        managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                            vendor_name="AWS",
                            name="AWSManagedRulesKnownBadInputsRuleSet",
                        )
                    ),
                    override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="AWSManagedRulesKnownBadInputsRuleSet",
                        sampled_requests_enabled=True,
                    ),
                ),
            ],
        )

        # WebACL을 ALB와 연결
        wafv2.CfnWebACLAssociation(
            self,
            "WebACLAssociation",
            resource_arn=alb_arn,
            web_acl_arn=self.web_acl.attr_arn,
        )
