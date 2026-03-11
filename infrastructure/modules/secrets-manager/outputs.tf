output "striga_api_secret_arn" {
  description = "ARN of Striga API secret"
  value       = aws_secretsmanager_secret.striga_api.arn
}

output "database_secret_arn" {
  description = "ARN of database secret"
  value       = aws_secretsmanager_secret.database.arn
}

output "webhook_secret_arn" {
  description = "ARN of webhook secret"
  value       = aws_secretsmanager_secret.webhook.arn
}
