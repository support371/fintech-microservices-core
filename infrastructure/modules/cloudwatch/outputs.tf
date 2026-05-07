output "sns_topic_arn" {
  description = "SNS topic ARN for alerts"
  value       = aws_sns_topic.alerts.arn
}

output "audit_log_group_name" {
  description = "CloudWatch audit log group name"
  value       = aws_cloudwatch_log_group.audit.name
}
