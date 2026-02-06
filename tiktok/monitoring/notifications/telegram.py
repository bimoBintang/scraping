"""
Telegram Notifier for TikTok Monitoring
Send alerts and reports via Telegram Bot
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

try:
    from telegram import Bot
    from telegram.constants import ParseMode
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    Bot = None
    ParseMode = None

from .base import BaseNotifier
from ..events import ScrapingEvent, Severity, EventType


class TelegramNotifier(BaseNotifier):
    """
    Telegram Bot Notifier
    
    Sends alerts and reports to a Telegram chat.
    Requires: pip install python-telegram-bot
    
    To set up:
    1. Create a bot via @BotFather
    2. Get the bot token
    3. Get your chat_id (send /start to the bot, then check updates)
    """
    
    # Emoji mappings for severity
    SEVERITY_EMOJI = {
        Severity.DEBUG: "🔍",
        Severity.INFO: "ℹ️",
        Severity.WARNING: "⚠️",
        Severity.ERROR: "❌",
        Severity.CRITICAL: "🚨",
    }
    
    # Emoji mappings for event types
    EVENT_EMOJI = {
        EventType.PROFILE_SCRAPED: "👤",
        EventType.FOLLOWERS_SCRAPED: "👥",
        EventType.FOLLOWING_SCRAPED: "➡️",
        EventType.ERROR: "❌",
        EventType.RATE_LIMIT: "🚫",
        EventType.CAPTCHA: "🤖",
        EventType.TIMEOUT: "⏱️",
        EventType.ANOMALY_DETECTED: "📊",
        EventType.BROWSER_CRASH: "💥",
    }
    
    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        name: str = "telegram",
        parse_mode: str = "HTML"
    ):
        """
        Args:
            bot_token: Telegram bot token from @BotFather
            chat_id: Chat ID to send messages to
            name: Notifier name
            parse_mode: Message parse mode (HTML/Markdown)
        """
        super().__init__(name=name)
        
        if not TELEGRAM_AVAILABLE:
            raise ImportError(
                "python-telegram-bot required. Install with: pip install python-telegram-bot"
            )
        
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.parse_mode = parse_mode
        self._bot: Optional[Bot] = None
    
    async def _get_bot(self) -> Bot:
        """Get or create bot instance"""
        if self._bot is None:
            self._bot = Bot(token=self.bot_token)
        return self._bot
    
    async def send_alert(self, event: ScrapingEvent) -> bool:
        """
        Send alert for scraping event
        
        Args:
            event: Event to send alert for
            
        Returns:
            True if sent successfully
        """
        try:
            bot = await self._get_bot()
            message = self._format_alert(event)
            
            await bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=self.parse_mode
            )
            return True
            
        except Exception as e:
            print(f"[Telegram] Error sending alert: {e}")
            raise
    
    async def send_report(self, stats: Dict[str, Any]) -> bool:
        """
        Send periodic statistics report
        
        Args:
            stats: Statistics dictionary
            
        Returns:
            True if sent successfully
        """
        try:
            bot = await self._get_bot()
            message = self._format_report(stats)
            
            await bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=self.parse_mode
            )
            return True
            
        except Exception as e:
            print(f"[Telegram] Error sending report: {e}")
            raise
    
    async def send_custom(self, message: str) -> bool:
        """
        Send custom message
        
        Args:
            message: Message text
            
        Returns:
            True if sent successfully
        """
        try:
            bot = await self._get_bot()
            
            await bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=self.parse_mode
            )
            return True
            
        except Exception as e:
            print(f"[Telegram] Error sending message: {e}")
            return False
    
    def _format_alert(self, event: ScrapingEvent) -> str:
        """Format event as alert message"""
        severity_emoji = self.SEVERITY_EMOJI.get(event.severity, "📢")
        event_emoji = self.EVENT_EMOJI.get(event.event_type, "📌")
        
        event_type_str = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
        severity_str = event.severity.value if hasattr(event.severity, 'value') else str(event.severity)
        
        lines = [
            f"{severity_emoji} <b>TikTok Scraper Alert</b>",
            "",
            f"{event_emoji} <b>Event:</b> {event_type_str}",
            f"📊 <b>Severity:</b> {severity_str.upper()}",
        ]
        
        if event.username:
            lines.append(f"👤 <b>User:</b> @{event.username}")
        
        lines.append(f"🕐 <b>Time:</b> {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Add event data
        if event.data:
            lines.append("")
            lines.append("<b>Details:</b>")
            for key, value in list(event.data.items())[:5]:  # Limit to 5 fields
                lines.append(f"  • {key}: {value}")
        
        return "\n".join(lines)
    
    def _format_report(self, stats: Dict[str, Any]) -> str:
        """Format statistics as report message"""
        lines = [
            "📊 <b>TikTok Scraper Report</b>",
            f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        
        # Scraping stats
        if "total_scrapes" in stats:
            lines.extend([
                "<b>📈 Scraping Statistics:</b>",
                f"  • Total: {stats.get('total_scrapes', 0)}",
                f"  • Success: {stats.get('successful_scrapes', 0)}",
                f"  • Failed: {stats.get('failed_scrapes', 0)}",
                f"  • Rate: {stats.get('scrapes_per_minute', 0):.1f}/min",
            ])
        
        # Success rate
        success_rate = stats.get('success_rate', 1.0) * 100
        success_emoji = "✅" if success_rate >= 90 else "⚠️" if success_rate >= 70 else "❌"
        lines.append(f"  • {success_emoji} Success Rate: {success_rate:.1f}%")
        
        # Response time
        if "response_time_ema" in stats:
            lines.extend([
                "",
                "<b>⏱️ Response Time:</b>",
                f"  • EMA: {stats.get('response_time_ema', 0):.0f}ms",
            ])
            
            rt_stats = stats.get('response_time_stats', {})
            if rt_stats:
                lines.extend([
                    f"  • Mean: {rt_stats.get('mean', 0):.0f}ms",
                    f"  • Min: {rt_stats.get('min', 0):.0f}ms",
                    f"  • Max: {rt_stats.get('max', 0):.0f}ms",
                ])
        
        # Errors
        error_counts = stats.get('error_counts', {})
        if error_counts:
            lines.extend([
                "",
                "<b>❌ Errors:</b>",
            ])
            for error_type, count in list(error_counts.items())[:5]:
                lines.append(f"  • {error_type}: {count}")
        
        # Uptime
        uptime = stats.get('uptime_seconds', 0)
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        lines.append(f"\n⏰ <b>Uptime:</b> {hours}h {minutes}m")
        
        return "\n".join(lines)


class TelegramNotifierMock(BaseNotifier):
    """
    Mock Telegram notifier for testing (no actual API calls)
    """
    
    def __init__(self, name: str = "telegram_mock"):
        super().__init__(name=name)
        self.messages: list = []
    
    async def send_alert(self, event: ScrapingEvent) -> bool:
        self.messages.append({"type": "alert", "event": event.to_dict()})
        print(f"[TelegramMock] Alert: {event.event_type.value}")
        return True
    
    async def send_report(self, stats: Dict[str, Any]) -> bool:
        self.messages.append({"type": "report", "stats": stats})
        print(f"[TelegramMock] Report sent")
        return True
    
    def get_messages(self) -> list:
        return self.messages
    
    def clear(self) -> None:
        self.messages.clear()
