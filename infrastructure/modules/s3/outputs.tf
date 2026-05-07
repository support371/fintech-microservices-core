output "logging_bucket_name" {
  description = "S3 audit logging bucket name"
  value       = aws_s3_bucket.logging.id
}

output "logging_bucket_arn" {
  description = "S3 audit logging bucket ARN"
  value       = aws_s3_bucket.logging.arn
}
