"""
TikTok DOM Structure Reconnaissance Phase
"""
import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from playwright.async_api import Page, Locator
import time

@dataclass
class TikTokComponent:
    name: str
    selector: str
    attributes: Dict[str, str] = field(default_factory=dict)
    classes: List[str] = field(default_factory=list)
    children: List['TikTokComponent'] = field(default_factory=list)
    type: str = "unknown"  # 'following', 'follower', 'privacy', 'container'

@dataclass
class CSSSelector:
    pattern: str
    purpose: str
    elements_found: int = 0
    specificity: str = ""

@dataclass
class EventFlow:
    event_type: str
    source: str
    target: str
    payload_pattern: Optional[str] = None
    frequency: int = 0

class TikTokReconnaissance:
    def __init__(self, page: Page):
        self.page = page
        self.components: List[TikTokComponent] = []
        self.css_selectors: List[CSSSelector] = []
        self.event_flows: List[EventFlow] = []
        self.state_structures: Dict[str, Any] = {}
        
    async def start_reconnaissance(self, target_username: str):
        """Main reconnaissance entry point"""
        print(f"[RECON] Starting reconnaissance for @{target_username}")
        
        # Navigate to target profile
        await self.page.goto(f"https://www.tiktok.com/@{target_username}")
        await self.page.wait_for_load_state("networkidle")
        
        # Execute all reconnaissance phases
        await self.analyze_state_management()
        await self.map_following_components()
        await self.identify_css_selectors()
        await self.trace_event_flows()
        
        # Generate comprehensive report
        report = self.generate_recon_report()
        
        print(f"[RECON] Reconnaissance complete. Found {len(self.components)} components")
        return report
    
    async def analyze_state_management(self):
        """Analyze TikTok's state management structure"""
        print("[RECON] Analyzing state management...")
        
        # Inject script to extract window state
        state_script = """
        (() => {
            const stateTargets = [
                '__REDUX_STORE__',
                '__VUE__',
                '__NEXT_DATA__',
                '__META_DATA__',
                '_tiktok',
                'TT_CONFIG',
                'ssrData',
                'webpackJsonp',
                '__INITIAL_STATE__'
            ];
            
            const results = {};
            
            stateTargets.forEach(target => {
                if (window[target]) {
                    try {
                        // Try to stringify for analysis
                        const value = window[target];
                        results[target] = {
                            exists: true,
                            type: typeof value,
                            keys: Object.keys(value || {}),
                            sample: JSON.stringify(value, null, 2).substring(0, 500)
                        };
                    } catch (e) {
                        results[target] = {
                            exists: true,
                            type: typeof value,
                            error: e.message
                        };
                    }
                } else {
                    results[target] = { exists: false };
                }
            });
            
            // Check for framework instances
            results.frameworks = {
                hasReact: typeof React !== 'undefined',
                hasVue: typeof Vue !== 'undefined',
                hasRedux: typeof Redux !== 'undefined'
            };
            
            return results;
        })()
        """
        
        state_data = await self.page.evaluate(state_script)
        self.state_structures = state_data
        
        # Look for privacy-related state
        privacy_script = """
        (() => {
            const privacyMarkers = [];
            
            // Search in redux store
            if (window.__REDUX_STORE__) {
                const store = window.__REDUX_STORE__;
                if (store.getState) {
                    const state = store.getState();
                    searchForPrivacy(state, 'root', privacyMarkers);
                }
            }
            
            function searchForPrivacy(obj, path, markers) {
                if (!obj || typeof obj !== 'object') return;
                
                Object.keys(obj).forEach(key => {
                    const newPath = path + '.' + key;
                    const value = obj[key];
                    
                    // Look for privacy-related keys
                    if (typeof key === 'string' && 
                        (key.toLowerCase().includes('private') || 
                         key.toLowerCase().includes('visibility') ||
                         key.toLowerCase().includes('follow') && 
                         (key.toLowerCase().includes('status') || key.toLowerCase().includes('setting')))) {
                        markers.push({
                            path: newPath,
                            key: key,
                            value: value,
                            type: typeof value
                        });
                    }
                    
                    // Recursively search
                    if (value && typeof value === 'object') {
                        searchForPrivacy(value, newPath, markers);
                    }
                });
            }
            
            return privacyMarkers;
        })()
        """
        
        try:
            privacy_markers = await self.page.evaluate(privacy_script)
            print(f"[RECON] Found {len(privacy_markers)} privacy markers")
            self.state_structures['privacy_markers'] = privacy_markers
        except:
            print("[RECON] Could not extract privacy markers")
    
    async def map_following_components(self):
        """Map all following/follower related components"""
        print("[RECON] Mapping following/follower components...")
        
        # Common TikTok component patterns
        component_patterns = [
            # Following list containers
            ('following_container', '[data-e2e="following-list"]'),
            ('following_container', '[class*="FollowingList"]'),
            ('following_container', '[class*="follow-list"]'),
            ('following_container', 'section[aria-label*="Following"]'),
            
            # Follower list containers
            ('follower_container', '[data-e2e="follower-list"]'),
            ('follower_container', '[class*="FollowerList"]'),
            ('follower_container', 'section[aria-label*="Follower"]'),
            
            # Privacy gates
            ('privacy_gate', '[class*="PrivateAccount"]'),
            ('privacy_gate', '[class*="private-account"]'),
            ('privacy_gate', '[data-e2e*="private"]'),
            ('privacy_gate', 'div[class*="DivPrivateAccount"]'),
            
            # Individual follow items
            ('follow_item', '[class*="follow-item"]'),
            ('follow_item', '[class*="FollowerItem"]'),
            ('follow_item', '[class*="FollowingItem"]'),
            ('follow_item', 'div[data-e2e*="user"]'),
            
            # Buttons and controls
            ('follow_button', '[class*="follow-button"]'),
            ('follow_button', 'button:has-text("Follow")'),
            ('more_button', 'button:has-text("Following")'),
        ]
        
        for comp_type, selector in component_patterns:
            try:
                elements = await self.page.locator(selector).count()
                if elements > 0:
                    component = TikTokComponent(
                        name=f"{comp_type}_{len(self.components)}",
                        selector=selector,
                        type=comp_type
                    )
                    
                    # Get attributes of first element
                    first_element = self.page.locator(selector).first
                    attrs = await first_element.evaluate("""
                        el => {
                            const attrs = {};
                            for (let attr of el.attributes) {
                                attrs[attr.name] = attr.value;
                            }
                            return attrs;
                        }
                    """)
                    
                    component.attributes = attrs
                    component.classes = attrs.get('class', '').split()
                    
                    self.components.append(component)
                    print(f"[RECON] Found {elements} elements with selector: {selector}")
                    
            except Exception as e:
                continue
    
    async def identify_css_selectors(self):
        """Identify TikTok-specific CSS classes and selectors"""
        print("[RECON] Identifying CSS selectors...")
        
        # Extract all CSS classes from the page
        css_script = """
        (() => {
            const allElements = document.getElementsByTagName('*');
            const classSet = new Set();
            const attributeSelectors = [];
            
            // Collect all classes
            for (let el of allElements) {
                if (el.className) {
                    el.className.toString().trim().split(/\\s+/).forEach(cls => {
                        if (cls && cls.length > 2) {
                            classSet.add(cls);
                        }
                    });
                }
                
                // Collect data attributes
                for (let attr of el.attributes) {
                    if (attr.name.startsWith('data-') || 
                        attr.name.startsWith('aria-') ||
                        attr.name.includes('e2e')) {
                        attributeSelectors.push({
                            name: attr.name,
                            value: attr.value,
                            tag: el.tagName.toLowerCase()
                        });
                    }
                }
            }
            
            // Filter for TikTok-specific patterns
            const tiktokClasses = Array.from(classSet).filter(cls => 
                cls.includes('tiktok') || 
                cls.includes('tt-') ||
                cls.includes('-Div') ||
                cls.includes('follow') ||
                cls.includes('private') ||
                cls.includes('account') ||
                cls.includes('user') ||
                cls.includes('profile') ||
                cls.match(/^[A-Z][a-z]+[A-Z]/) // PascalCase components
            );
            
            return {
                classes: tiktokClasses.slice(0, 100), // Limit to 100
                attributes: attributeSelectors.slice(0, 50),
                total_elements: allElements.length
            };
        })()
        """
        
        css_data = await self.page.evaluate(css_script)
        
        # Create CSS selector objects
        for cls in css_data['classes']:
            selector = CSSSelector(
                pattern=f".{cls}",
                purpose=self._classify_css_purpose(cls),
                elements_found=await self._count_elements(f".{cls}")
            )
            self.css_selectors.append(selector)
        
        for attr in css_data['attributes']:
            selector_pattern = f"{attr['tag']}[{attr['name']}=\"{attr['value']}\"]"
            selector = CSSSelector(
                pattern=selector_pattern,
                purpose=f"Attribute selector for {attr['name']}",
                elements_found=await self._count_elements(selector_pattern)
            )
            self.css_selectors.append(selector)
    
    async def trace_event_flows(self):
        """Trace event flows for data fetching"""
        print("[RECON] Tracing event flows...")
        
        # Monitor network requests
        await self._setup_request_monitoring()
        
        # Monitor DOM mutations
        await self._setup_mutation_observer()
        
        # Monitor JavaScript events
        await self._setup_event_monitoring()
        
        # Trigger some actions to see events
        await self._trigger_test_actions()
    
    async def _setup_request_monitoring(self):
        """Setup network request monitoring"""
        self.page.on("request", lambda request: self._handle_request(request))
        self.page.on("response", lambda response: self._handle_response(response))
    
    async def _setup_mutation_observer(self):
        """Setup DOM mutation observer"""
        mutation_script = """
        (() => {
            window._tiktokMutations = [];
            
            const observer = new MutationObserver((mutations) => {
                mutations.forEach(mutation => {
                    if (mutation.type === 'childList') {
                        mutation.addedNodes.forEach(node => {
                            if (node.nodeType === 1) { // Element node
                                const tags = ['DIV', 'SECTION', 'UL', 'LI'];
                                if (tags.includes(node.tagName)) {
                                    const classAttr = node.getAttribute('class') || '';
                                    if (classAttr.includes('follow') || 
                                        classAttr.includes('user') ||
                                        classAttr.includes('list')) {
                                        window._tiktokMutations.push({
                                            type: 'added',
                                            tag: node.tagName,
                                            classes: classAttr,
                                            timestamp: Date.now()
                                        });
                                    }
                                }
                            }
                        });
                    }
                });
            });
            
            observer.observe(document.body, {
                childList: true,
                subtree: true,
                attributes: false,
                characterData: false
            });
            
            return 'Mutation observer installed';
        })()
        """
        
        await self.page.evaluate(mutation_script)
    
    async def _setup_event_monitoring(self):
        """Setup event listener monitoring"""
        event_script = """
        (() => {
            const originalAddEventListener = EventTarget.prototype.addEventListener;
            const eventsTracked = [];
            
            EventTarget.prototype.addEventListener = function(type, listener, options) {
                // Track following/follower related events
                if (typeof type === 'string' && (
                    type.includes('follow') ||
                    type.includes('user') ||
                    type.includes('data') ||
                    type.includes('load') ||
                    type.includes('scroll'))) {
                    
                    eventsTracked.push({
                        type: type,
                        target: this.tagName || this.constructor.name,
                        timestamp: Date.now()
                    });
                }
                
                return originalAddEventListener.call(this, type, listener, options);
            };
            
            window._tiktokEvents = eventsTracked;
            return 'Event monitoring installed';
        })()
        """
        
        await self.page.evaluate(event_script)
    
    async def _trigger_test_actions(self):
        """Trigger test actions to capture events"""
        # Try to click follow buttons if visible
        try:
            follow_buttons = self.page.locator('button:has-text("Follow")')
            count = await follow_buttons.count()
            if count > 0 and count < 5:  # Don't click too many
                await follow_buttons.first.click(timeout=2000)
                await asyncio.sleep(1)
        except:
            pass
        
        # Try scrolling to trigger lazy loading
        await self.page.evaluate("window.scrollBy(0, 500)")
        await asyncio.sleep(1)
    
    async def _handle_request(self, request):
        """Handle network requests"""
        url = request.url
        if any(keyword in url for keyword in ['follow', 'user', 'profile', 'relation']):
            event = EventFlow(
                event_type="network_request",
                source="browser",
                target=url,
                payload_pattern=request.post_data or ""
            )
            self.event_flows.append(event)
    
    async def _handle_response(self, response):
        """Handle network responses"""
        url = response.url
        if any(keyword in url for keyword in ['follow', 'user', 'profile', 'relation']):
            try:
                json_data = await response.json()
                event = EventFlow(
                    event_type="network_response",
                    source=url,
                    target="browser",
                    payload_pattern=json.dumps(json_data)[:200] if json_data else ""
                )
                self.event_flows.append(event)
            except:
                pass
    
    async def _count_elements(self, selector: str) -> int:
        """Count elements matching selector"""
        try:
            return await self.page.locator(selector).count()
        except:
            return 0
    
    def _classify_css_purpose(self, class_name: str) -> str:
        """Classify CSS class purpose based on name patterns"""
        patterns = {
            'private': 'privacy_gate',
            'follow': 'follow_component',
            'user': 'user_component',
            'profile': 'profile_component',
            'list': 'list_container',
            'item': 'list_item',
            'button': 'interactive_element',
            'container': 'layout_container',
            'Div': 'tiktok_component',  # TikTok uses Div prefix
            'tt-': 'tiktok_prefix'
        }
        
        for pattern, purpose in patterns.items():
            if pattern.lower() in class_name.lower():
                return purpose
        
        return "unknown"
    
    def generate_recon_report(self) -> Dict:
        """Generate comprehensive reconnaissance report"""
        return {
            "timestamp": time.time(),
            "components": [
                {
                    "name": c.name,
                    "selector": c.selector,
                    "type": c.type,
                    "attributes": c.attributes,
                    "class_count": len(c.classes)
                }
                for c in self.components
            ],
            "css_selectors": [
                {
                    "pattern": s.pattern,
                    "purpose": s.purpose,
                    "elements_found": s.elements_found
                }
                for s in self.css_selectors[:50]  # Limit
            ],
            "state_structures": self.state_structures,
            "event_flows_count": len(self.event_flows),
            "summary": {
                "total_components": len(self.components),
                "privacy_components": len([c for c in self.components if 'privacy' in c.type]),
                "follow_components": len([c for c in self.components if 'follow' in c.type]),
                "unique_css_classes": len(self.css_selectors)
            }
        }