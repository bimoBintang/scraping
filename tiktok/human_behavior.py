"""
Human Behavior Simulation for TikTok Scraper
Simulate realistic mouse movements, scrolling, and typing
"""

import asyncio
import random
import math
from typing import Tuple, List, Optional
from dataclasses import dataclass


@dataclass
class Point:
    x: float
    y: float


class BezierCurve:
    """Generate Bezier curve for realistic mouse paths"""
    
    @staticmethod
    def generate_points(
        start: Point, 
        end: Point, 
        num_points: int = 50,
        randomness: float = 0.3
    ) -> List[Point]:
        """Generate points along a Bezier curve with randomness"""
        
        # Generate control points with randomness
        dx = end.x - start.x
        dy = end.y - start.y
        
        # Add random control points
        ctrl1 = Point(
            start.x + dx * 0.25 + random.uniform(-dx * randomness, dx * randomness),
            start.y + dy * 0.25 + random.uniform(-dy * randomness, dy * randomness)
        )
        ctrl2 = Point(
            start.x + dx * 0.75 + random.uniform(-dx * randomness, dx * randomness),
            start.y + dy * 0.75 + random.uniform(-dy * randomness, dy * randomness)
        )
        
        points = []
        for i in range(num_points):
            t = i / (num_points - 1)
            
            # Cubic Bezier formula
            x = (1-t)**3 * start.x + \
                3*(1-t)**2 * t * ctrl1.x + \
                3*(1-t) * t**2 * ctrl2.x + \
                t**3 * end.x
            
            y = (1-t)**3 * start.y + \
                3*(1-t)**2 * t * ctrl1.y + \
                3*(1-t) * t**2 * ctrl2.y + \
                t**3 * end.y
            
            points.append(Point(x, y))
        
        return points


class HumanMouse:
    """Simulate human-like mouse movements"""
    
    def __init__(self, page):
        self.page = page
        self.current_pos = Point(0, 0)
    
    async def move_to(
        self, 
        x: float, 
        y: float, 
        speed: float = 1.0
    ):
        """Move mouse to target with human-like curve"""
        target = Point(x, y)
        
        # Calculate distance for timing
        distance = math.sqrt((target.x - self.current_pos.x)**2 + 
                           (target.y - self.current_pos.y)**2)
        
        # Number of points based on distance
        num_points = max(10, int(distance / 10))
        
        # Generate curve
        points = BezierCurve.generate_points(
            self.current_pos, target, num_points,
            randomness=random.uniform(0.1, 0.4)
        )
        
        # Move through points with variable speed
        for i, point in enumerate(points):
            # Variable delay (faster in middle, slower at start/end)
            progress = i / len(points)
            easing = math.sin(progress * math.pi)  # Smooth ease in/out
            delay = (0.005 + 0.02 * (1 - easing)) / speed
            
            await self.page.mouse.move(point.x, point.y)
            await asyncio.sleep(delay)
        
        self.current_pos = target
    
    async def click_at(self, x: float, y: float, button: str = "left"):
        """Move to position and click with realistic timing"""
        await self.move_to(x, y)
        
        # Random pre-click pause
        await asyncio.sleep(random.uniform(0.05, 0.15))
        
        # Click with random hold duration
        await self.page.mouse.down(button=button)
        await asyncio.sleep(random.uniform(0.05, 0.12))
        await self.page.mouse.up(button=button)
        
        # Random post-click pause
        await asyncio.sleep(random.uniform(0.1, 0.3))
    
    async def double_click_at(self, x: float, y: float):
        """Double click with realistic timing"""
        await self.move_to(x, y)
        
        for _ in range(2):
            await self.page.mouse.down()
            await asyncio.sleep(random.uniform(0.03, 0.08))
            await self.page.mouse.up()
            await asyncio.sleep(random.uniform(0.08, 0.15))


class HumanScroll:
    """Simulate human-like scrolling behavior"""
    
    def __init__(self, page):
        self.page = page
    
    async def scroll_down(
        self, 
        amount: int = 500, 
        smooth: bool = True
    ):
        """Scroll down with human-like behavior"""
        if smooth:
            await self._smooth_scroll(amount)
        else:
            await self._chunked_scroll(amount)
    
    async def scroll_up(self, amount: int = 500, smooth: bool = True):
        """Scroll up with human-like behavior"""
        if smooth:
            await self._smooth_scroll(-amount)
        else:
            await self._chunked_scroll(-amount)
    
    async def _smooth_scroll(self, total: int):
        """Smooth scrolling with momentum"""
        steps = random.randint(8, 15)
        remaining = total
        
        for i in range(steps):
            # Easing: fast start, slow end
            progress = i / steps
            easing = 1 - (1 - progress) ** 2  # Ease out quad
            
            # Calculate scroll for this step
            if i == steps - 1:
                scroll = remaining
            else:
                scroll = int(total * (1 - easing) / (steps - i))
                remaining -= scroll
            
            await self.page.evaluate(f"window.scrollBy(0, {scroll})")
            await asyncio.sleep(random.uniform(0.02, 0.08))
        
        # Small momentum at end
        for _ in range(random.randint(1, 3)):
            small_scroll = random.randint(5, 20) * (1 if total > 0 else -1)
            await self.page.evaluate(f"window.scrollBy(0, {small_scroll})")
            await asyncio.sleep(random.uniform(0.05, 0.1))
    
    async def _chunked_scroll(self, total: int):
        """Chunk-based scrolling (like mouse wheel)"""
        chunk_size = random.randint(80, 150)
        direction = 1 if total > 0 else -1
        remaining = abs(total)
        
        while remaining > 0:
            scroll = min(chunk_size, remaining) * direction
            await self.page.evaluate(f"window.scrollBy(0, {scroll})")
            remaining -= abs(scroll)
            
            # Variable delay between chunks
            await asyncio.sleep(random.uniform(0.05, 0.2))
    
    async def scroll_to_element(self, selector: str):
        """Scroll to element with human behavior"""
        # Get element position
        element = await self.page.query_selector(selector)
        if not element:
            return False
        
        box = await element.bounding_box()
        if not box:
            return False
        
        # Calculate scroll needed
        viewport = await self.page.evaluate("""
            () => ({
                height: window.innerHeight,
                scrollY: window.scrollY
            })
        """)
        
        target_y = box['y'] - viewport['height'] / 2
        await self._smooth_scroll(int(target_y))
        
        return True


class HumanTyping:
    """Simulate human-like typing"""
    
    def __init__(self, page):
        self.page = page
    
    async def type_text(
        self, 
        text: str, 
        wpm: int = 60,
        mistakes: bool = True
    ):
        """Type text with human-like timing and optional mistakes"""
        
        # Calculate base delay from WPM
        chars_per_sec = (wpm * 5) / 60  # 5 chars per word average
        base_delay = 1 / chars_per_sec
        
        i = 0
        while i < len(text):
            char = text[i]
            
            # Simulate occasional typo
            if mistakes and random.random() < 0.02 and char.isalpha():
                # Type wrong key
                wrong_char = self._nearby_key(char)
                await self.page.keyboard.press(wrong_char)
                await asyncio.sleep(random.uniform(0.1, 0.3))
                
                # Backspace
                await self.page.keyboard.press("Backspace")
                await asyncio.sleep(random.uniform(0.05, 0.15))
            
            # Type correct character
            await self.page.keyboard.press(char)
            
            # Variable delay
            delay = base_delay * random.uniform(0.5, 1.5)
            
            # Longer pause after punctuation
            if char in '.!?,':
                delay *= random.uniform(2, 4)
            
            # Longer pause after space sometimes
            if char == ' ' and random.random() < 0.3:
                delay *= random.uniform(1.5, 3)
            
            await asyncio.sleep(delay)
            i += 1
    
    def _nearby_key(self, char: str) -> str:
        """Get a random nearby key for typo simulation"""
        keyboard_layout = {
            'q': 'wa', 'w': 'qeas', 'e': 'wrsd', 'r': 'etfd',
            't': 'ryfg', 'y': 'tugh', 'u': 'yijh', 'i': 'uokj',
            'o': 'iplk', 'p': 'ol', 'a': 'qwsz', 's': 'awedxz',
            'd': 'serfcx', 'f': 'drtgvc', 'g': 'ftyhbv', 'h': 'gyujnb',
            'j': 'huikmn', 'k': 'jiolm', 'l': 'kop', 'z': 'asx',
            'x': 'zsdc', 'c': 'xdfv', 'v': 'cfgb', 'b': 'vghn',
            'n': 'bhjm', 'm': 'njk'
        }
        
        nearby = keyboard_layout.get(char.lower(), char)
        return random.choice(nearby) if nearby else char


class HumanBehavior:
    """Combined human behavior simulation"""
    
    def __init__(self, page):
        self.page = page
        self.mouse = HumanMouse(page)
        self.scroll = HumanScroll(page)
        self.typing = HumanTyping(page)
    
    async def think_pause(self, min_sec: float = 0.5, max_sec: float = 2.0):
        """Random pause to simulate thinking"""
        await asyncio.sleep(random.uniform(min_sec, max_sec))
    
    async def reading_pause(self, text_length: int = 100):
        """Pause based on text length (simulate reading)"""
        words = text_length / 5  # Average 5 chars per word
        reading_time = words / 4  # ~240 WPM reading speed
        await asyncio.sleep(min(reading_time, 5))  # Max 5 seconds
    
    async def random_movement(self):
        """Perform random mouse movement (idle behavior)"""
        viewport = await self.page.evaluate("""
            () => ({width: window.innerWidth, height: window.innerHeight})
        """)
        
        x = random.randint(100, viewport['width'] - 100)
        y = random.randint(100, viewport['height'] - 100)
        
        await self.mouse.move_to(x, y, speed=0.5)
    
    async def simulate_browsing(self, duration: float = 10.0):
        """Simulate natural browsing behavior for a duration"""
        end_time = asyncio.get_event_loop().time() + duration
        
        while asyncio.get_event_loop().time() < end_time:
            action = random.choice(['scroll', 'move', 'pause'])
            
            if action == 'scroll':
                amount = random.randint(200, 600)
                direction = random.choice([1, -1])
                await self.scroll.scroll_down(amount * direction)
            
            elif action == 'move':
                await self.random_movement()
            
            else:
                await self.think_pause(0.5, 1.5)
            
            await asyncio.sleep(random.uniform(0.5, 2))
