# =============================================================================
# CloudWatch Module - Monitoring and alerting
# =============================================================================

# Application log groups with 5-year retention for compliance
resource "aws_cloudwatch_log_group" "card_platform" {
  name              = "/fintech/${var.environment}/card-platform-service"
  retention_in_days = 1827

  tags = {
    Name    = "${var.project_name}-${var.environment}-card-platform-logs"
    Service = "card-platform-service"
  }
}

resource "aws_cloudwatch_log_group" "converter" {
  name              = "/fintech/${var.environment}/converter-service"
  retention_in_days = 1827

  tags = {
    Name    = "${var.project_name}-${var.environment}-converter-logs"
    Service = "converter-service"
  }
}

resource "aws_cloudwatch_log_group" "gem_dashboard" {
  name              = "/fintech/${var.environment}/gem-dashboard"
  retention_in_days = 1827

  tags = {
    Name    = "${var.project_name}-${var.environment}-gem-dashboard-logs"
    Service = "gem-dashboard"
  }
}

resource "aws_cloudwatch_log_group" "audit" {
  name              = "/fintech/${var.environment}/audit-trail"
  retention_in_days = 1827

  tags = {
    Name       = "${var.project_name}-${var.environment}-audit-trail"
    Compliance = "pci-dss"
  }
}

# EKS cluster log group
resource "aws_cloudwatch_log_group" "eks" {
  name              = "/aws/eks/${var.eks_cluster_name}/cluster"
  retention_in_days = 1827

  tags = {
    Name = "${var.project_name}-${var.environment}-eks-logs"
  }
}

# -----------------------------------------------------------------------------
# CloudWatch Alarms
# -----------------------------------------------------------------------------

# High error rate alarm
resource "aws_cloudwatch_metric_alarm" "high_error_rate" {
  alarm_name          = "${var.project_name}-${var.environment}-high-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "5XXError"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "High 5XX error rate detected"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]

  tags = {
    Name = "${var.project_name}-${var.environment}-high-error-rate"
  }
}

# CPU utilization alarm for EKS nodes
resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  alarm_name          = "${var.project_name}-${var.environment}-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "High CPU utilization on EKS nodes"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  tags = {
    Name = "${var.project_name}-${var.environment}-high-cpu"
  }
}

# Database connections alarm
resource "aws_cloudwatch_metric_alarm" "db_connections" {
  alarm_name          = "${var.project_name}-${var.environment}-high-db-connections"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "High database connection count"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  tags = {
    Name = "${var.project_name}-${var.environment}-high-db-connections"
  }
}

# SNS Topic for alerts
resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-${var.environment}-alerts"

  tags = {
    Name = "${var.project_name}-${var.environment}-alerts"
  }
}

# Dashboard
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project_name}-${var.environment}-overview"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "API Latency"
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", "${var.project_name}-${var.environment}"]
          ]
          period = 300
          stat   = "Average"
          region = "us-east-1"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "Error Rates"
          metrics = [
            ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", "${var.project_name}-${var.environment}"],
            ["AWS/ApplicationELB", "HTTPCode_Target_4XX_Count", "LoadBalancer", "${var.project_name}-${var.environment}"]
          ]
          period = 300
          stat   = "Sum"
          region = "us-east-1"
        }
      }
    ]
  })
}
