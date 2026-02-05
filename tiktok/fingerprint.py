"""
Browser Fingerprint Spoofing for TikTok Scraper
Randomize and mask browser fingerprint to avoid detection
"""

import random
import string
import hashlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class FingerprintProfile:
    """Generated fingerprint profile"""
    canvas_noise: float = 0.0
    webgl_vendor: str = ""
    webgl_renderer: str = ""
    screen_width: int = 1920
    screen_height: int = 1080
    color_depth: int = 24
    timezone: str = "Asia/Jakarta"
    language: str = "id-ID"
    platform: str = "Win32"
    hardware_concurrency: int = 8
    device_memory: int = 8
    fonts: List[str] = field(default_factory=list)


# Common WebGL configurations to mimic real devices
WEBGL_CONFIGS = [
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1060 6GB Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (AMD)", "renderer": "ANGLE (AMD, AMD Radeon RX 580 Series Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Intel Inc.", "renderer": "Intel Iris OpenGL Engine"},
    {"vendor": "Apple Inc.", "renderer": "Apple M1"},
]

# Common screen resolutions
SCREEN_RESOLUTIONS = [
    (1920, 1080), (1366, 768), (1536, 864), (1440, 900),
    (1280, 720), (2560, 1440), (1600, 900), (1280, 800)
]

# Common fonts to report
COMMON_FONTS = [
    "Arial", "Arial Black", "Calibri", "Cambria", "Comic Sans MS",
    "Courier New", "Georgia", "Impact", "Lucida Console", "Microsoft Sans Serif",
    "Palatino Linotype", "Segoe UI", "Tahoma", "Times New Roman", "Trebuchet MS",
    "Verdana", "Consolas", "Roboto", "Open Sans"
]


class FingerprintGenerator:
    """Generate randomized browser fingerprints"""
    
    def __init__(self, seed: Optional[int] = None):
        if seed:
            random.seed(seed)
        self.current_profile: Optional[FingerprintProfile] = None
    
    def generate_profile(self) -> FingerprintProfile:
        """Generate a new fingerprint profile"""
        webgl = random.choice(WEBGL_CONFIGS)
        resolution = random.choice(SCREEN_RESOLUTIONS)
        
        profile = FingerprintProfile(
            canvas_noise=random.uniform(0.0001, 0.001),
            webgl_vendor=webgl["vendor"],
            webgl_renderer=webgl["renderer"],
            screen_width=resolution[0],
            screen_height=resolution[1],
            color_depth=random.choice([24, 32]),
            timezone=random.choice(["Asia/Jakarta", "Asia/Singapore", "America/New_York", "Europe/London"]),
            language=random.choice(["id-ID", "en-US", "en-GB"]),
            platform=random.choice(["Win32", "MacIntel", "Linux x86_64"]),
            hardware_concurrency=random.choice([4, 8, 12, 16]),
            device_memory=random.choice([4, 8, 16, 32]),
            fonts=random.sample(COMMON_FONTS, k=random.randint(10, 15))
        )
        
        self.current_profile = profile
        return profile
    
    def get_fingerprint_hash(self, profile: FingerprintProfile) -> str:
        """Generate consistent hash for profile identification"""
        data = f"{profile.webgl_renderer}{profile.screen_width}{profile.fonts}"
        return hashlib.md5(data.encode()).hexdigest()[:12]


class FingerprintSpoofing:
    """Apply fingerprint spoofing to browser page"""
    
    def __init__(self, profile: Optional[FingerprintProfile] = None):
        self.profile = profile or FingerprintGenerator().generate_profile()
    
    async def apply_to_page(self, page) -> bool:
        """Apply all fingerprint spoofing to a Playwright page"""
        try:
            await self._spoof_canvas(page)
            await self._spoof_webgl(page)
            await self._spoof_screen(page)
            await self._spoof_navigator(page)
            await self._spoof_fonts(page)
            await self._spoof_audio(page)
            print(f"[STEALTH] Fingerprint applied: {FingerprintGenerator().get_fingerprint_hash(self.profile)}")
            return True
        except Exception as e:
            print(f"[STEALTH] Error applying fingerprint: {e}")
            return False
    
    async def _spoof_canvas(self, page):
        """Add noise to canvas fingerprinting"""
        noise = self.profile.canvas_noise
        
        script = f"""
        (() => {{
            const noise = {noise};
            
            // Override toDataURL
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type, quality) {{
                if (type === 'image/png' || !type) {{
                    const ctx = this.getContext('2d');
                    if (ctx) {{
                        const imageData = ctx.getImageData(0, 0, this.width, this.height);
                        const data = imageData.data;
                        
                        // Add subtle noise
                        for (let i = 0; i < data.length; i += 4) {{
                            data[i] = Math.min(255, Math.max(0, data[i] + Math.floor(Math.random() * noise * 255)));
                        }}
                        
                        ctx.putImageData(imageData, 0, 0);
                    }}
                }}
                return originalToDataURL.call(this, type, quality);
            }};
            
            // Override toBlob
            const originalToBlob = HTMLCanvasElement.prototype.toBlob;
            HTMLCanvasElement.prototype.toBlob = function(callback, type, quality) {{
                const ctx = this.getContext('2d');
                if (ctx && (type === 'image/png' || !type)) {{
                    const imageData = ctx.getImageData(0, 0, this.width, this.height);
                    const data = imageData.data;
                    
                    for (let i = 0; i < data.length; i += 4) {{
                        data[i] = Math.min(255, Math.max(0, data[i] + Math.floor(Math.random() * noise * 255)));
                    }}
                    
                    ctx.putImageData(imageData, 0, 0);
                }}
                return originalToBlob.call(this, callback, type, quality);
            }};
            
            return 'Canvas spoofing applied';
        }})()
        """
        
        await page.evaluate(script)
    
    async def _spoof_webgl(self, page):
        """Spoof WebGL renderer and vendor"""
        vendor = self.profile.webgl_vendor
        renderer = self.profile.webgl_renderer
        
        script = f"""
        (() => {{
            const getParameterOriginal = WebGLRenderingContext.prototype.getParameter;
            
            WebGLRenderingContext.prototype.getParameter = function(parameter) {{
                // UNMASKED_VENDOR_WEBGL
                if (parameter === 37445) {{
                    return '{vendor}';
                }}
                // UNMASKED_RENDERER_WEBGL
                if (parameter === 37446) {{
                    return '{renderer}';
                }}
                return getParameterOriginal.call(this, parameter);
            }};
            
            // Also for WebGL2
            if (typeof WebGL2RenderingContext !== 'undefined') {{
                const getParameter2Original = WebGL2RenderingContext.prototype.getParameter;
                
                WebGL2RenderingContext.prototype.getParameter = function(parameter) {{
                    if (parameter === 37445) return '{vendor}';
                    if (parameter === 37446) return '{renderer}';
                    return getParameter2Original.call(this, parameter);
                }};
            }}
            
            return 'WebGL spoofing applied';
        }})()
        """
        
        await page.evaluate(script)
    
    async def _spoof_screen(self, page):
        """Spoof screen dimensions"""
        width = self.profile.screen_width
        height = self.profile.screen_height
        color_depth = self.profile.color_depth
        
        script = f"""
        (() => {{
            Object.defineProperty(screen, 'width', {{ get: () => {width} }});
            Object.defineProperty(screen, 'height', {{ get: () => {height} }});
            Object.defineProperty(screen, 'availWidth', {{ get: () => {width} }});
            Object.defineProperty(screen, 'availHeight', {{ get: () => {height - 40} }});
            Object.defineProperty(screen, 'colorDepth', {{ get: () => {color_depth} }});
            Object.defineProperty(screen, 'pixelDepth', {{ get: () => {color_depth} }});
            
            return 'Screen spoofing applied';
        }})()
        """
        
        await page.evaluate(script)
    
    async def _spoof_navigator(self, page):
        """Spoof navigator properties"""
        platform = self.profile.platform
        language = self.profile.language
        hardware = self.profile.hardware_concurrency
        memory = self.profile.device_memory
        
        script = f"""
        (() => {{
            Object.defineProperty(navigator, 'platform', {{ get: () => '{platform}' }});
            Object.defineProperty(navigator, 'language', {{ get: () => '{language}' }});
            Object.defineProperty(navigator, 'languages', {{ get: () => ['{language}', 'en'] }});
            Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => {hardware} }});
            Object.defineProperty(navigator, 'deviceMemory', {{ get: () => {memory} }});
            
            // Hide automation
            Object.defineProperty(navigator, 'webdriver', {{ get: () => false }});
            delete navigator.__proto__.webdriver;
            
            // Hide Playwright
            Object.defineProperty(navigator, 'plugins', {{
                get: () => [
                    {{ name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' }},
                    {{ name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' }},
                    {{ name: 'Native Client', filename: 'internal-nacl-plugin' }}
                ]
            }});
            
            return 'Navigator spoofing applied';
        }})()
        """
        
        await page.evaluate(script)
    
    async def _spoof_fonts(self, page):
        """Spoof font detection"""
        fonts = self.profile.fonts
        fonts_js = str(fonts).replace("'", '"')
        
        script = f"""
        (() => {{
            const fakeFonts = {fonts_js};
            
            // Override font check
            const originalMeasure = CanvasRenderingContext2D.prototype.measureText;
            CanvasRenderingContext2D.prototype.measureText = function(text) {{
                const result = originalMeasure.call(this, text);
                // Add slight variation
                result.width = result.width + (Math.random() * 0.01);
                return result;
            }};
            
            return 'Font spoofing applied';
        }})()
        """
        
        await page.evaluate(script)
    
    async def _spoof_audio(self, page):
        """Spoof audio fingerprinting"""
        script = """
        (() => {
            const originalGetChannelData = AudioBuffer.prototype.getChannelData;
            
            AudioBuffer.prototype.getChannelData = function(channel) {
                const result = originalGetChannelData.call(this, channel);
                
                // Add noise to audio data
                for (let i = 0; i < result.length; i++) {
                    result[i] = result[i] + (Math.random() * 0.0001);
                }
                
                return result;
            };
            
            return 'Audio spoofing applied';
        })()
        """
        
        await page.evaluate(script)


class IdentityManager:
    """Manage multiple identities for stealth operation"""
    
    def __init__(self):
        self.generator = FingerprintGenerator()
        self.identities: List[FingerprintProfile] = []
        self.current_index = 0
    
    def generate_identities(self, count: int = 5) -> List[FingerprintProfile]:
        """Pre-generate multiple identities"""
        self.identities = [self.generator.generate_profile() for _ in range(count)]
        return self.identities
    
    def get_current_identity(self) -> FingerprintProfile:
        """Get current active identity"""
        if not self.identities:
            self.generate_identities()
        return self.identities[self.current_index]
    
    def rotate_identity(self) -> FingerprintProfile:
        """Rotate to next identity"""
        if not self.identities:
            self.generate_identities()
        self.current_index = (self.current_index + 1) % len(self.identities)
        print(f"[STEALTH] Rotated to identity {self.current_index + 1}/{len(self.identities)}")
        return self.identities[self.current_index]
    
    async def apply_identity(self, page, identity: Optional[FingerprintProfile] = None):
        """Apply identity to page"""
        profile = identity or self.get_current_identity()
        spoofing = FingerprintSpoofing(profile)
        return await spoofing.apply_to_page(page)
