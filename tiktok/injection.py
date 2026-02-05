"""
TikTok DOM Injection Phase
"""
import asyncio
import json
from typing import Dict, List, Optional, Any
from playwright.async_api import Page, Locator
from dataclasses import dataclass
import time

@dataclass
class InjectionResult:
    success: bool
    method: str
    target: str
    data_obtained: Optional[Any] = None
    error: Optional[str] = None

class TikTokInjector:
    def __init__(self, page: Page, recon_report: Dict):
        self.page = page
        self.recon = recon_report
        self.injected = False
        self.results: List[InjectionResult] = []
        
        # State modification targets from recon
        self.state_targets = self._extract_state_targets()
        self.css_selectors = self._extract_css_targets()
        
    def _extract_state_targets(self) -> List[Dict]:
        """Extract state modification targets from recon"""
        targets = []
        
        if 'state_structures' in self.recon:
            state_data = self.recon['state_structures']
            
            # Look for privacy markers
            if 'privacy_markers' in state_data:
                for marker in state_data['privacy_markers']:
                    targets.append({
                        'type': 'state_property',
                        'path': marker.get('path'),
                        'current_value': marker.get('value'),
                        'target_value': False if 'private' in str(marker.get('key')).lower() else 0
                    })
        
        return targets
    
    def _extract_css_targets(self) -> List[Dict]:
        """Extract CSS injection targets from recon"""
        targets = []
        
        if 'css_selectors' in self.recon:
            for selector in self.recon['css_selectors']:
                if any(keyword in selector['purpose'] for keyword in ['privacy', 'private', 'hidden']):
                    targets.append({
                        'selector': selector['pattern'],
                        'action': 'unhide',
                        'styles': {
                            'display': 'block !important',
                            'visibility': 'visible !important',
                            'opacity': '1 !important'
                        }
                    })
        
        return targets
    
    async def execute_injection_phase(self) -> List[InjectionResult]:
        """Execute complete injection phase"""
        print("[INJECTION] Starting injection phase...")
        
        # Wait for TikTok to fully load
        await self._wait_for_tiktok_load()
        
        # Execute injection strategies in order
        strategies = [
            self._inject_state_manipulation,
            self._inject_css_override,
            self._inject_component_props,
            self._inject_event_listeners,
            self._force_data_refetch
        ]
        
        for strategy in strategies:
            try:
                result = await strategy()
                self.results.append(result)
                
                if result.success and result.data_obtained:
                    print(f"[INJECTION] Strategy {result.method} succeeded")
                    # If we got data, we can stop early
                    break
                    
            except Exception as e:
                self.results.append(InjectionResult(
                    success=False,
                    method=strategy.__name__,
                    target="unknown",
                    error=str(e)
                ))
        
        self.injected = True
        return self.results
    
    async def _wait_for_tiktok_load(self):
        """Wait for TikTok to fully load"""
        print("[INJECTION] Waiting for TikTok to load...")
        
        # Wait for main content
        await self.page.wait_for_selector('main', timeout=10000)
        
        # Wait for user profile to load
        await self.page.wait_for_selector('[data-e2e="user-page"]', timeout=10000)
        
        # Additional wait for JavaScript
        await self.page.wait_for_load_state('networkidle')
        await asyncio.sleep(2)
    
    async def _inject_state_manipulation(self) -> InjectionResult:
        """Inject state management modifications"""
        print("[INJECTION] Attempting state manipulation...")
        
        injection_script = """
        (() => {
            const results = {
                modified: [],
                errors: [],
                data_obtained: null
            };
            
            // Function to safely set nested property
            function setNestedProperty(obj, path, value) {
                const parts = path.split('.');
                let current = obj;
                
                for (let i = 1; i < parts.length - 1; i++) { // Skip 'root'
                    if (!current[parts[i]]) {
                        current[parts[i]] = {};
                    }
                    current = current[parts[i]];
                }
                
                const lastPart = parts[parts.length - 1];
                const oldValue = current[lastPart];
                current[lastPart] = value;
                
                return { path, oldValue, newValue: value };
            }
            
            // Try to modify Redux store
            if (window.__REDUX_STORE__ && window.__REDUX_STORE__.dispatch) {
                try {
                    // Dispatch action to update privacy state
                    window.__REDUX_STORE__.dispatch({
                        type: 'USER/UPDATE_PRIVACY_SETTINGS',
                        payload: {
                            privateAccount: false,
                            followingVisibility: 0,
                            followerStatus: 1
                        }
                    });
                    results.modified.push('redux_store');
                } catch (e) {
                    results.errors.push('redux_error: ' + e.message);
                }
            }
            
            // Try to modify Vue store
            if (window.__VUE__ && window.__VUE__.$store) {
                try {
                    window.__VUE__.$store.commit('user/setPrivacy', {
                        isPrivate: false,
                        hideFollowing: false,
                        hideFollowers: false
                    });
                    results.modified.push('vue_store');
                } catch (e) {
                    results.errors.push('vue_error: ' + e.message);
                }
            }
            
            // Try direct window property modification
            const privacyTargets = [
                'privateAccount',
                'isPrivate',
                'followingVisibility',
                'followerVisibility',
                'hideFollowing',
                'hideFollowers'
            ];
            
            privacyTargets.forEach(target => {
                if (window[target] !== undefined) {
                    const oldValue = window[target];
                    window[target] = false;
                    results.modified.push(`window.${target}: ${oldValue} -> false`);
                }
            });
            
            // Check if modifications worked by trying to access following data
            try {
                // Look for follow data in DOM
                const followElements = document.querySelectorAll('[class*="follow"], [data-e2e*="follow"]');
                if (followElements.length > 0) {
                    const sampleData = Array.from(followElements)
                        .slice(0, 5)
                        .map(el => ({
                            text: el.textContent?.trim(),
                            classes: el.className,
                            href: el.href
                        }));
                    results.data_obtained = sampleData;
                }
            } catch (e) {
                results.errors.push('data_check_error: ' + e.message);
            }
            
            return results;
        })()
        """
        
        try:
            result = await self.page.evaluate(injection_script)
            
            return InjectionResult(
                success=len(result['modified']) > 0,
                method="state_manipulation",
                target="window_state",
                data_obtained=result.get('data_obtained'),
                error='; '.join(result['errors']) if result['errors'] else None
            )
            
        except Exception as e:
            return InjectionResult(
                success=False,
                method="state_manipulation",
                target="window_state",
                error=str(e)
            )
    
    async def _inject_css_override(self) -> InjectionResult:
        """Inject CSS to override privacy styles"""
        print("[INJECTION] Injecting CSS overrides...")
        
        css_injection = """
        (() => {
            // Create style element
            const style = document.createElement('style');
            style.id = 'tiktok-private-override';
            
            style.textContent = `
                /* Unhide private sections */
                [class*="PrivateAccount"],
                [class*="private-account"],
                [data-e2e*="private"],
                [aria-label*="private"],
                div[class*="DivPrivateAccount"],
                section[class*="PrivateProfile"] {
                    display: block !important;
                    visibility: visible !important;
                    opacity: 1 !important;
                    height: auto !important;
                    max-height: none !important;
                }
                
                /* Remove blur overlays */
                .blur-overlay,
                .private-overlay,
                [class*="overlay"],
                [style*="blur"] {
                    display: none !important;
                    backdrop-filter: none !important;
                    filter: none !important;
                }
                
                /* Show follow lists */
                [class*="follow-list"],
                [data-e2e*="follow-list"],
                [class*="FollowingList"],
                [class*="FollowerList"] {
                    display: grid !important;
                    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)) !important;
                    gap: 16px !important;
                }
                
                /* Show individual follow items */
                [class*="follow-item"],
                [class*="FollowerItem"],
                [class*="FollowingItem"] {
                    display: flex !important;
                    flex-direction: column !important;
                    align-items: center !important;
                    padding: 12px !important;
                    border-radius: 8px !important;
                    background: #f8f8f8 !important;
                }
                
                /* Remove lock icons */
                svg[class*="lock"],
                i[class*="icon-lock"],
                [class*="icon-private"],
                [class*="PrivateIcon"] {
                    display: none !important;
                }
                
                /* Make buttons accessible */
                button[class*="follow"],
                button:has-text("Follow"),
                button:has-text("Following") {
                    pointer-events: auto !important;
                    cursor: pointer !important;
                    opacity: 1 !important;
                }
            `;
            
            document.head.appendChild(style);
            
            // Check if CSS had effect
            const privateElements = document.querySelectorAll([
                '[class*="PrivateAccount"]',
                '[class*="private-account"]',
                '[data-e2e*="private"]'
            ].join(','));
            
            const visibleCount = Array.from(privateElements)
                .filter(el => {
                    const style = window.getComputedStyle(el);
                    return style.display !== 'none' && 
                           style.visibility !== 'hidden' &&
                           style.opacity !== '0';
                }).length;
            
            return {
                injected: true,
                style_id: style.id,
                private_elements_found: privateElements.length,
                private_elements_visible: visibleCount
            };
        })()
        """
        
        try:
            result = await self.page.evaluate(css_injection)
            
            # Give CSS time to apply
            await asyncio.sleep(1)
            
            # Check for follow data after CSS injection
            follow_data = await self._extract_follow_data()
            
            return InjectionResult(
                success=result['injected'] and result['private_elements_visible'] > 0,
                method="css_override",
                target="privacy_styles",
                data_obtained=follow_data,
                error=None
            )
            
        except Exception as e:
            return InjectionResult(
                success=False,
                method="css_override", 
                target="privacy_styles",
                error=str(e)
            )
    
    async def _inject_component_props(self) -> InjectionResult:
        """Inject component prop overrides for React/Vue"""
        print("[INJECTION] Injecting component prop overrides...")
        
        component_injection = """
        (() => {
            const results = {
                react_patched: false,
                vue_patched: false,
                components_modified: 0,
                data_obtained: null
            };
            
            // Patch React.createElement if exists
            if (typeof React !== 'undefined' && React.createElement) {
                const originalCreateElement = React.createElement;
                
                React.createElement = function(type, props, ...children) {
                    // Modify props for follow-related components
                    if (props && (
                        (props.className && (
                            props.className.includes('follow') ||
                            props.className.includes('Follow') ||
                            props.className.includes('private') ||
                            props.className.includes('Private')
                        )) ||
                        (props['data-e2e'] && props['data-e2e'].includes('follow')) ||
                        (props.isPrivate !== undefined)
                    )) {
                        const modifiedProps = { ...props };
                        
                        // Force public props
                        if (modifiedProps.isPrivate !== undefined) {
                            modifiedProps.isPrivate = false;
                            results.components_modified++;
                        }
                        
                        if (modifiedProps.privateAccount !== undefined) {
                            modifiedProps.privateAccount = false;
                            results.components_modified++;
                        }
                        
                        if (modifiedProps.hideFollowing !== undefined) {
                            modifiedProps.hideFollowing = false;
                            results.components_modified++;
                        }
                        
                        if (modifiedProps.hideFollowers !== undefined) {
                            modifiedProps.hideFollowers = false;
                            results.components_modified++;
                        }
                        
                        return originalCreateElement.call(this, type, modifiedProps, ...children);
                    }
                    
                    return originalCreateElement.call(this, type, props, ...children);
                };
                
                results.react_patched = true;
            }
            
            // Patch Vue.component if exists
            if (typeof Vue !== 'undefined' && Vue.component) {
                const originalComponent = Vue.component;
                
                Vue.component = function(name, options) {
                    // Check if this is a follow-related component
                    if (name && (
                        name.includes('Follow') ||
                        name.includes('follow') ||
                        name.includes('Private') ||
                        name.includes('private')
                    )) {
                        if (options.props) {
                            // Force default props to public
                            Object.keys(options.props).forEach(propName => {
                                if (propName.toLowerCase().includes('private') ||
                                    propName.toLowerCase().includes('hide')) {
                                    if (options.props[propName].default !== undefined) {
                                        options.props[propName].default = false;
                                        results.components_modified++;
                                    }
                                }
                            });
                        }
                    }
                    
                    return originalComponent.call(this, name, options);
                };
                
                results.vue_patched = true;
            }
            
            // Try to extract data after patching
            try {
                const followContainers = document.querySelectorAll([
                    '[class*="follow-list"]',
                    '[data-e2e*="follow"]'
                ].join(','));
                
                if (followContainers.length > 0) {
                    const container = followContainers[0];
                    const items = container.querySelectorAll([
                        '[class*="item"]',
                        '[class*="Item"]',
                        'a[href*="@"]'
                    ].join(','));
                    
                    results.data_obtained = Array.from(items)
                        .slice(0, 10)
                        .map(item => ({
                            text: item.textContent?.trim(),
                            href: item.href,
                            tagName: item.tagName
                        }));
                }
            } catch (e) {
                console.warn('Could not extract data:', e);
            }
            
            return results;
        })()
        """
        
        try:
            result = await self.page.evaluate(component_injection)
            
            # Trigger re-render
            await self.page.evaluate("""
                if (window.__REDUX_STORE__) {
                    window.__REDUX_STORE__.dispatch({ type: 'FORCE_RE_RENDER' });
                }
                if (window.__VUE__) {
                    window.__VUE__.$forceUpdate();
                }
            """)
            
            await asyncio.sleep(2)
            
            return InjectionResult(
                success=result['components_modified'] > 0,
                method="component_props",
                target="react_vue_components",
                data_obtained=result.get('data_obtained'),
                error=None
            )
            
        except Exception as e:
            return InjectionResult(
                success=False,
                method="component_props",
                target="react_vue_components",
                error=str(e)
            )
    
    async def _inject_event_listeners(self) -> InjectionResult:
        """Inject event listener overrides"""
        print("[INJECTION] Injecting event listener overrides...")
        
        event_injection = """
        (() => {
            const results = {
                listeners_removed: 0,
                listeners_added: 0,
                events_intercepted: []
            };
            
            // Store original methods
            const originalAddEventListener = EventTarget.prototype.addEventListener;
            const originalRemoveEventListener = EventTarget.prototype.removeEventListener;
            const originalDispatchEvent = EventTarget.prototype.dispatchEvent;
            
            // Track privacy-related events
            const privacyEvents = [
                'privacyCheck',
                'privateAccountLoaded',
                'followingVisibilityChanged',
                'followerStatusUpdated',
                'userPrivacyUpdated'
            ];
            
            // Override addEventListener to block privacy checks
            EventTarget.prototype.addEventListener = function(type, listener, options) {
                if (privacyEvents.some(event => type.includes(event))) {
                    results.listeners_removed++;
                    results.events_intercepted.push({
                        type: 'blocked',
                        event: type,
                        target: this.tagName || this.constructor.name
                    });
                    return; // Don't add the listener
                }
                
                // Add our own interceptors for follow events
                if (type.includes('load') && (
                    type.includes('follow') ||
                    type.includes('user') ||
                    type.includes('data')
                )) {
                    const wrappedListener = function(...args) {
                        // Before original listener
                        results.events_intercepted.push({
                            type: 'intercepted',
                            event: type,
                            timestamp: Date.now()
                        });
                        
                        // Call original with modified arguments if needed
                        return listener.apply(this, args);
                    };
                    
                    results.listeners_added++;
                    return originalAddEventListener.call(this, type, wrappedListener, options);
                }
                
                return originalAddEventListener.call(this, type, listener, options);
            };
            
            // Override dispatchEvent to modify privacy events
            EventTarget.prototype.dispatchEvent = function(event) {
                if (event.type && privacyEvents.some(pe => event.type.includes(pe))) {
                    // Modify event detail if it's a CustomEvent
                    if (event instanceof CustomEvent && event.detail) {
                        if (event.detail.isPrivate !== undefined) {
                            event.detail.isPrivate = false;
                        }
                        if (event.detail.privateAccount !== undefined) {
                            event.detail.privateAccount = false;
                        }
                    }
                    
                    results.events_intercepted.push({
                        type: 'modified',
                        event: event.type,
                        detail: event.detail
                    });
                }
                
                return originalDispatchEvent.call(this, event);
            };
            
            // Dispatch fake events to trigger data loading
            setTimeout(() => {
                // Fake privacy check complete event
                const privacyEvent = new CustomEvent('privacyCheckComplete', {
                    detail: {
                        isPrivate: false,
                        followingVisibility: 0,
                        followerStatus: 1,
                        checkPassed: true
                    }
                });
                document.dispatchEvent(privacyEvent);
                
                // Fake data loaded event
                const dataEvent = new CustomEvent('followingDataLoaded', {
                    detail: { hasData: true, count: 100 }
                });
                document.dispatchEvent(dataEvent);
            }, 100);
            
            return results;
        })()
        """
        
        try:
            result = await self.page.evaluate(event_injection)
            await asyncio.sleep(1)
            
            # Check if events triggered data load
            follow_data = await self._extract_follow_data()
            
            return InjectionResult(
                success=len(result.get('events_intercepted', [])) > 0,
                method="event_listeners",
                target="dom_events",
                data_obtained=follow_data,
                error=None
            )
            
        except Exception as e:
            return InjectionResult(
                success=False,
                method="event_listeners",
                target="dom_events",
                error=str(e)
            )
    
    async def _force_data_refetch(self) -> InjectionResult:
        """Force data refetch with modified parameters"""
        print("[INJECTION] Forcing data refetch...")
        
        refetch_script = """
        (() => {
            const results = {
                requests_intercepted: 0,
                requests_modified: 0,
                data_received: null
            };
            
            // Store original fetch
            const originalFetch = window.fetch;
            
            window.fetch = async function(input, init = {}) {
                const url = typeof input === 'string' ? input : input.url;
                
                // Intercept follow-related requests
                if (url && (
                    url.includes('/follow') ||
                    url.includes('/user/') ||
                    url.includes('/relation') ||
                    url.includes('/profile')
                )) {
                    results.requests_intercepted++;
                    
                    // Modify request parameters
                    if (init.body) {
                        try {
                            const body = JSON.parse(init.body);
                            
                            // Remove privacy parameters
                            delete body.privateAccount;
                            delete body.isPrivate;
                            delete body.followingVisibility;
                            delete body.followerStatus;
                            
                            // Add force-public flag
                            body.forcePublic = true;
                            body.ignorePrivacy = true;
                            
                            init.body = JSON.stringify(body);
                            results.requests_modified++;
                        } catch (e) {
                            // Body might not be JSON
                        }
                    }
                    
                    // Modify headers
                    init.headers = {
                        ...init.headers,
                        'X-Force-Public': 'true',
                        'X-Ignore-Privacy': '1'
                    };
                }
                
                const response = await originalFetch.call(this, input, init);
                
                // Intercept responses
                if (url && url.includes('/follow')) {
                    const clone = response.clone();
                    try {
                        const data = await clone.json();
                        results.data_received = {
                            url: url,
                            data_count: data?.data?.length || data?.items?.length || 0,
                            sample: data?.data?.slice(0, 3) || data?.items?.slice(0, 3)
                        };
                    } catch (e) {
                        // Response might not be JSON
                    }
                }
                
                return response;
            };
            
            // Trigger follow data fetch
            setTimeout(async () => {
                try {
                    // Try to find and click follow tab
                    const followTab = document.querySelector([
                        '[data-e2e="following-tab"]',
                        '[data-e2e="follower-tab"]',
                        'button:has-text("Following")',
                        'button:has-text("Followers")'
                    ].find(selector => document.querySelector(selector)));
                    
                    if (followTab) {
                        followTab.click();
                    }
                } catch (e) {
                    console.warn('Could not click follow tab:', e);
                }
            }, 500);
            
            return results;
        })()
        """
        
        try:
            result = await self.page.evaluate(refetch_script)
            
            # Wait for data to load
            await asyncio.sleep(3)
            
            # Extract any new data
            follow_data = await self._extract_follow_data()
            
            return InjectionResult(
                success=result['requests_modified'] > 0,
                method="data_refetch",
                target="network_requests",
                data_obtained=follow_data or result.get('data_received'),
                error=None
            )
            
        except Exception as e:
            return InjectionResult(
                success=False,
                method="data_refetch",
                target="network_requests",
                error=str(e)
            )
    
    async def _extract_follow_data(self) -> Optional[List[Dict]]:
        """Extract follow data from page after injection"""
        extraction_script = """
        (() => {
            const followData = [];
            
            // Look for follow items in various formats
            const selectors = [
                '[class*="follow-item"]',
                '[class*="FollowItem"]',
                '[class*="FollowerItem"]',
                '[class*="FollowingItem"]',
                '[data-e2e*="user-"]',
                'a[href*="/@"]:not([href*="/video/"])'
            ];
            
            selectors.forEach(selector => {
                document.querySelectorAll(selector).forEach(el => {
                    // Avoid duplicates
                    const href = el.href;
                    if (href && !followData.some(item => item.href === href)) {
                        const username = href.split('/@')[1]?.split('?')[0]?.split('/')[0];
                        if (username && username.length > 2) {
                            followData.push({
                                username: username,
                                href: href,
                                text: el.textContent?.trim() || '',
                                tagName: el.tagName,
                                className: el.className
                            });
                        }
                    }
                });
            });
            
            // Remove obvious non-follow items
            const filtered = followData.filter(item => 
                item.href.includes('/@') &&
                !item.href.includes('/video/') &&
                !item.href.includes('/music/') &&
                !item.href.includes('/tag/') &&
                item.username !== window.location.pathname.split('/@')[1]
            );
            
            return filtered.slice(0, 50); // Limit to 50
        })()
        """
        
        try:
            return await self.page.evaluate(extraction_script)
        except:
            return None
    
    def get_injection_report(self) -> Dict:
        """Generate injection phase report"""
        return {
            "timestamp": time.time(),
            "injected": self.injected,
            "results": [
                {
                    "method": r.method,
                    "success": r.success,
                    "target": r.target,
                    "data_count": len(r.data_obtained) if r.data_obtained else 0,
                    "error": r.error
                }
                for r in self.results
            ],
            "summary": {
                "successful_injections": sum(1 for r in self.results if r.success),
                "total_data_extracted": sum(len(r.data_obtained) for r in self.results if r.data_obtained),
                "best_method": max(self.results, key=lambda x: len(x.data_obtained) if x.data_obtained else 0).method if self.results else None
            }
        }