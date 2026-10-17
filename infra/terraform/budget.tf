# AWS Cost Control & Budget Alarm
# Alerts when real or forecasted infrastructure spend approaches monthly spending ceiling.

resource "aws_budgets_budget" "monthly" {
  name              = "platina-ai-monthly-budget-${var.environment}"
  budget_type       = "COST"
  limit_amount      = var.monthly_budget_usd
  limit_unit        = "USD"
  time_period_start = "2026-10-01_00:00"
  time_unit         = "MONTHLY"

  # Alert 1: Triggered when actual spend exceeds 80% of budget ($0.80)
  notification {
    comparison_operator        = "GREATER_THAN"
    notification_type          = "ACTUAL"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    subscriber_email_addresses = [var.alert_email]
  }

  # Alert 2: Triggered when forecasted spend is projected to exceed 100% ($1.00)
  notification {
    comparison_operator        = "GREATER_THAN"
    notification_type          = "FORECASTED"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    subscriber_email_addresses = [var.alert_email]
  }

  cost_filter {
    name = "TagKeyValue"
    values = [
      "user:Project$platina-ai"
    ]
  }
}
