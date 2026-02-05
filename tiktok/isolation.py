"""
Session Isolation for TikTok Scraper
Manage isolated browser contexts and identity switching
"""

import asyncio
import json
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime
import os

from .fingerprint import FingerprintProfile, FingerprintGenerator, FingerprintSpoofing, IdentityManager


@dataclass
class SessionState:
    """State of an isolated session"""
    session_id: str
    created_at: datetime = field(default_factory=datetime.now)
    requests_made: int = 0
    last_activity: datetime = field(default_factory=datetime.now)
    fingerprint_hash: str = ""
    proxy_used: Optional[str] = None
    is_compromised: bool = False


class SessionIsolator:
    """
    Manage isolated browser sessions for stealth operation
    Each session has its own cookies, storage, and fingerprint
    """
    
    def __init__(self, browser):
        self.browser = browser
        self.identity_manager = IdentityManager()
        self.sessions: Dict[str, SessionState] = {}
        self.current_context = None
        self.current_page = None
        
        # Pre-generate identities
        self.identity_manager.generate_identities(5)
    
    async def create_isolated_context(
        self, 
        proxy: Optional[str] = None,
        identity: Optional[FingerprintProfile] = None
    ):
        """Create a fresh isolated browser context"""
        
        # Generate session ID
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{id(self) % 10000}"
        
        # Get identity
        profile = identity or self.identity_manager.get_current_identity()
        
        # Context options
        context_options = {
            "viewport": {
                "width": profile.screen_width,
                "height": profile.screen_height
            },
            "locale": profile.language,
            "timezone_id": profile.timezone,
            "color_scheme": "light",
            "device_scale_factor": 1,
            "has_touch": False,
            "is_mobile": False,
            "java_script_enabled": True,
        }
        
        # Add proxy if provided
        if proxy:
            if proxy.startswith("socks"):
                context_options["proxy"] = {"server": proxy}
            else:
                context_options["proxy"] = {"server": f"http://{proxy}"}
        
        # Create new context
        context = await self.browser.new_context(**context_options)
        
        # Create page
        page = await context.new_page()
        
        # Apply fingerprint spoofing
        spoofing = FingerprintSpoofing(profile)
        await spoofing.apply_to_page(page)
        
        # Track session
        self.sessions[session_id] = SessionState(
            session_id=session_id,
            fingerprint_hash=FingerprintGenerator().get_fingerprint_hash(profile),
            proxy_used=proxy
        )
        
        self.current_context = context
        self.current_page = page
        
        print(f"[ISOLATION] Created session: {session_id}")
        return context, page, session_id
    
    async def wipe_session(self, session_id: Optional[str] = None):
        """Wipe all data from a session"""
        if self.current_page:
            try:
                # Clear cookies
                await self.current_context.clear_cookies()
                
                # Clear localStorage and sessionStorage
                await self.current_page.evaluate("""
                    () => {
                        localStorage.clear();
                        sessionStorage.clear();
                        
                        // Clear IndexedDB
                        indexedDB.databases().then(dbs => {
                            dbs.forEach(db => indexedDB.deleteDatabase(db.name));
                        });
                        
                        return 'Storage cleared';
                    }
                """)
                
                print(f"[ISOLATION] Session wiped: {session_id or 'current'}")
                
            except Exception as e:
                print(f"[ISOLATION] Wipe error: {e}")
    
    async def destroy_session(self):
        """Completely destroy current session"""
        if self.current_context:
            await self.wipe_session()
            await self.current_context.close()
            
            self.current_context = None
            self.current_page = None
            
            print("[ISOLATION] Session destroyed")
    
    async def switch_identity(self, proxy: Optional[str] = None):
        """Switch to a new identity (new context + fingerprint)"""
        # Destroy old session
        await self.destroy_session()
        
        # Rotate identity
        self.identity_manager.rotate_identity()
        
        # Create new session with new identity
        return await self.create_isolated_context(proxy=proxy)
    
    def mark_compromised(self, session_id: str):
        """Mark a session as compromised (detected)"""
        if session_id in self.sessions:
            self.sessions[session_id].is_compromised = True
            print(f"[ISOLATION] Session marked compromised: {session_id}")
    
    def increment_requests(self, session_id: str):
        """Track request count for session"""
        if session_id in self.sessions:
            self.sessions[session_id].requests_made += 1
            self.sessions[session_id].last_activity = datetime.now()


class EmergencyWipe:
    """Emergency identity wipe for detection evasion"""
    
    def __init__(self, isolator: SessionIsolator):
        self.isolator = isolator
        self.wipe_triggered = False
    
    async def emergency_wipe(self):
        """Perform emergency wipe of all identifying data"""
        print("[EMERGENCY] Initiating emergency wipe...")
        self.wipe_triggered = True
        
        try:
            if self.isolator.current_page:
                # Stop all network requests
                await self.isolator.current_page.route("**/*", lambda route: route.abort())
                
                # Clear all possible tracking data
                await self.isolator.current_page.evaluate("""
                    () => {
                        // Clear all storage
                        localStorage.clear();
                        sessionStorage.clear();
                        
                        // Clear cookies via document
                        document.cookie.split(";").forEach(c => {
                            document.cookie = c.replace(/^ +/, "")
                                .replace(/=.*/, "=;expires=" + new Date().toUTCString() + ";path=/");
                        });
                        
                        // Remove tracking pixels
                        document.querySelectorAll('img[src*="track"], img[src*="pixel"]').forEach(e => e.remove());
                        
                        // Stop all intervals and timeouts
                        const highestId = window.setTimeout(() => {}, 0);
                        for (let i = 0; i < highestId; i++) {
                            window.clearTimeout(i);
                            window.clearInterval(i);
                        }
                        
                        // Remove event listeners (prevents tracking)
                        window.onbeforeunload = null;
                        window.onunload = null;
                        
                        return 'Emergency wipe complete';
                    }
                """)
            
            # Destroy the session
            await self.isolator.destroy_session()
            
            print("[EMERGENCY] Emergency wipe complete")
            return True
            
        except Exception as e:
            print(f"[EMERGENCY] Wipe error: {e}")
            return False
    
    async def quick_exit(self):
        """Fastest possible exit (when detection is imminent)"""
        print("[EMERGENCY] Quick exit initiated")
        
        if self.isolator.current_context:
            # Force close without cleanup
            try:
                await self.isolator.current_context.close()
            except:
                pass
        
        self.isolator.current_context = None
        self.isolator.current_page = None


class IdentityRotationPolicy:
    """Policy for automatic identity rotation"""
    
    def __init__(
        self,
        max_requests: int = 50,
        max_duration_minutes: int = 30,
        rotate_on_error: bool = True
    ):
        self.max_requests = max_requests
        self.max_duration_minutes = max_duration_minutes
        self.rotate_on_error = rotate_on_error
    
    def should_rotate(self, session: SessionState) -> bool:
        """Check if identity should be rotated"""
        # Check request limit
        if session.requests_made >= self.max_requests:
            return True
        
        # Check time limit
        duration = (datetime.now() - session.created_at).total_seconds() / 60
        if duration >= self.max_duration_minutes:
            return True
        
        # Check if compromised
        if session.is_compromised:
            return True
        
        return False
