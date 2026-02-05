"""
Time Delay & Jitter Module
Human-like delays untuk menghindari deteksi bot
"""

import random
import asyncio
from typing import Tuple


class DelayManager:
    """
    Manage delays dengan jitter untuk scraping yang natural
    
    Usage:
        delay = DelayManager(base_delay=2.0, jitter=0.3)
        await delay.wait()  # Tunggu 2 ± 0.6 detik
    """
    
    def __init__(
        self, 
        base_delay: float = 2.0,
        jitter: float = 0.3,
        min_delay: float = 0.5,
        max_delay: float = 10.0
    ):
        """
        Args:
            base_delay: Delay dasar dalam detik
            jitter: Persentase variasi (0.3 = ±30%)
            min_delay: Minimum delay
            max_delay: Maximum delay
        """
        self.base_delay = base_delay
        self.jitter = jitter
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._request_count = 0
    
    def calculate_delay(self) -> float:
        """Hitung delay dengan jitter"""
        # Apply jitter
        variance = self.base_delay * self.jitter
        delay = self.base_delay + random.uniform(-variance, variance)
        
        # Progressive delay - semakin banyak request, semakin lambat
        if self._request_count > 10:
            delay *= 1.2
        if self._request_count > 25:
            delay *= 1.5
        if self._request_count > 50:
            delay *= 2.0
        
        # Clamp ke min/max
        return max(self.min_delay, min(delay, self.max_delay))
    
    async def wait(self) -> float:
        """Tunggu dengan delay yang dihitung"""
        delay = self.calculate_delay()
        self._request_count += 1
        await asyncio.sleep(delay)
        return delay
    
    async def wait_short(self) -> float:
        """Delay pendek untuk interaksi cepat (scroll, click)"""
        delay = random.uniform(0.3, 0.8)
        await asyncio.sleep(delay)
        return delay
    
    async def wait_long(self) -> float:
        """Delay panjang setelah aksi penting"""
        delay = random.uniform(3.0, 6.0)
        await asyncio.sleep(delay)
        return delay
    
    def reset(self):
        """Reset request counter"""
        self._request_count = 0
    
    @property
    def request_count(self) -> int:
        return self._request_count


# Preset delays untuk berbagai skenario
DELAY_PRESETS = {
    'aggressive': DelayManager(base_delay=0.5, jitter=0.2),
    'normal': DelayManager(base_delay=2.0, jitter=0.3),
    'cautious': DelayManager(base_delay=4.0, jitter=0.4),
    'stealth': DelayManager(base_delay=8.0, jitter=0.5),
}


def get_delay_manager(preset: str = 'normal') -> DelayManager:
    """Get delay manager dari preset"""
    return DELAY_PRESETS.get(preset, DELAY_PRESETS['normal'])
