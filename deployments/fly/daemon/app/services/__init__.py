"""
Phase 5: Real World Services
News, Financial, Web Monitoring, Email, Calendar integrations
"""
from .news_service import NewsService
from .financial_service import FinancialService
from .web_monitor_service import WebMonitorService
from .email_service import EmailService
from .calendar_service import CalendarService

__all__ = [
    "NewsService",
    "FinancialService",
    "WebMonitorService",
    "EmailService",
    "CalendarService",
]
