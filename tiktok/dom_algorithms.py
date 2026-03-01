"""
Advanced DOM Algorithms (D1-D5)
Deep content extraction through Shadow DOM, IFrame, Virtual DOM,
Serialization, and Event Loop techniques
"""

import asyncio
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from playwright.async_api import Page


# ==================== DATA CLASSES ====================

@dataclass
class DOMAlgorithmResult:
    """Result from a DOM algorithm"""
    algorithm: str
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    nodes_found: int = 0
    error: Optional[str] = None


# ==================== D1: SHADOW DOM PENETRATION ====================

class ShadowDOMPenetrator:
    """
    D1: Menembus Shadow DOM components
    - Hijack attachShadow → force open mode
    - Recursive traverse shadow roots
    - Merge shadow + light DOM
    """

    def __init__(self, page: Page):
        self.page = page

    async def execute(self) -> DOMAlgorithmResult:
        """Execute Shadow DOM penetration"""
        print("[D1] Shadow DOM Penetration...")

        try:
            result = await self.page.evaluate("""
            (() => {
                const result = {
                    shadow_roots_found: 0,
                    forced_open: 0,
                    nodes_extracted: [],
                    follow_data: []
                };

                // ===== PHASE 1: Hijack attachShadow =====
                const originalAttachShadow = Element.prototype.attachShadow;
                Element.prototype.attachShadow = function(init) {
                    // Force open mode
                    if (init && init.mode === 'closed') {
                        init.mode = 'open';
                        result.forced_open++;
                    }
                    return originalAttachShadow.call(this, init);
                };

                // ===== PHASE 2: Scan existing shadow roots =====
                function traverseShadowDOM(root, depth = 0) {
                    if (depth > 10) return; // Max depth guard

                    const elements = root.querySelectorAll('*');
                    for (const el of elements) {
                        // Check for shadow root
                        if (el.shadowRoot) {
                            result.shadow_roots_found++;

                            // Extract content from shadow
                            const shadowContent = el.shadowRoot.innerHTML;
                            result.nodes_extracted.push({
                                tag: el.tagName.toLowerCase(),
                                id: el.id || null,
                                classes: Array.from(el.classList),
                                shadow_content_length: shadowContent.length,
                                depth: depth
                            });

                            // Look for follow-related content in shadow
                            const links = el.shadowRoot.querySelectorAll('a[href*="/@"]');
                            for (const link of links) {
                                const href = link.getAttribute('href');
                                if (href && href.includes('/@')) {
                                    const username = href.split('/@')[1]?.split('?')[0]?.split('/')[0];
                                    if (username) {
                                        result.follow_data.push({
                                            username: username,
                                            text: link.textContent?.trim(),
                                            source: 'shadow_dom'
                                        });
                                    }
                                }
                            }

                            // Recursive traverse
                            traverseShadowDOM(el.shadowRoot, depth + 1);
                        }
                    }
                }

                traverseShadowDOM(document);

                // ===== PHASE 3: Check closed shadow roots via prototype =====
                try {
                    const allElements = document.querySelectorAll('*');
                    for (const el of allElements) {
                        // Try accessing internal shadow
                        const internals = el.constructor?.prototype;
                        if (internals && typeof internals.attachInternals === 'function') {
                            try {
                                const shadow = el.attachShadow({ mode: 'open' });
                                if (shadow && shadow.innerHTML) {
                                    result.nodes_extracted.push({
                                        tag: el.tagName.toLowerCase(),
                                        forced: true,
                                        content_length: shadow.innerHTML.length
                                    });
                                }
                            } catch (e) {
                                // Already has shadow root - that's fine
                            }
                        }
                    }
                } catch (e) {}

                return result;
            })()
            """)

            follow_count = len(result.get('follow_data', []))
            shadow_count = result.get('shadow_roots_found', 0)
            print(f"[D1] Found {shadow_count} shadow roots, {follow_count} users")

            return DOMAlgorithmResult(
                algorithm="D1_ShadowDOM",
                success=True,
                data=result,
                nodes_found=shadow_count
            )

        except Exception as e:
            print(f"[D1] Error: {e}")
            return DOMAlgorithmResult(
                algorithm="D1_ShadowDOM",
                success=False,
                error=str(e)
            )


# ==================== D2: IFRAME BRIDGING ====================

class IFrameBridge:
    """
    D2: Cross-origin iframe content extraction
    - Same-origin: direct contentDocument access
    - Cross-origin: postMessage interception
    - MutationObserver inside iframes
    """

    def __init__(self, page: Page):
        self.page = page

    async def execute(self) -> DOMAlgorithmResult:
        """Execute IFrame bridging"""
        print("[D2] IFrame Bridging...")

        try:
            result = await self.page.evaluate("""
            (() => {
                const result = {
                    iframes_found: 0,
                    same_origin: 0,
                    cross_origin: 0,
                    content_extracted: [],
                    messages_captured: [],
                    follow_data: []
                };

                // ===== PHASE 1: Find all iframes =====
                const iframes = document.querySelectorAll('iframe');
                result.iframes_found = iframes.length;

                for (const iframe of iframes) {
                    const src = iframe.src || iframe.getAttribute('src') || '';

                    try {
                        // ===== PHASE 2: Same-origin access =====
                        const doc = iframe.contentDocument || iframe.contentWindow?.document;
                        if (doc) {
                            result.same_origin++;

                            // Clone content
                            const html = doc.body?.innerHTML || '';
                            result.content_extracted.push({
                                src: src.substring(0, 100),
                                type: 'same_origin',
                                content_length: html.length,
                                title: doc.title || ''
                            });

                            // Look for follow data
                            const links = doc.querySelectorAll('a[href*="/@"]');
                            for (const link of links) {
                                const href = link.getAttribute('href');
                                const username = href?.split('/@')[1]?.split('?')[0]?.split('/')[0];
                                if (username) {
                                    result.follow_data.push({
                                        username: username,
                                        text: link.textContent?.trim(),
                                        source: 'iframe_same_origin'
                                    });
                                }
                            }

                            // Setup mutation observer
                            const observer = new MutationObserver((mutations) => {
                                for (const m of mutations) {
                                    if (m.addedNodes.length > 0) {
                                        for (const node of m.addedNodes) {
                                            if (node.querySelectorAll) {
                                                const newLinks = node.querySelectorAll('a[href*="/@"]');
                                                for (const link of newLinks) {
                                                    const href = link.getAttribute('href');
                                                    const u = href?.split('/@')[1]?.split('?')[0]?.split('/')[0];
                                                    if (u) result.follow_data.push({
                                                        username: u, source: 'iframe_mutation'
                                                    });
                                                }
                                            }
                                        }
                                    }
                                }
                            });
                            observer.observe(doc.body, { childList: true, subtree: true });
                        }
                    } catch (e) {
                        // Cross-origin blocked
                        result.cross_origin++;
                        result.content_extracted.push({
                            src: src.substring(0, 100),
                            type: 'cross_origin',
                            blocked: true
                        });
                    }
                }

                // ===== PHASE 3: Intercept postMessage =====
                const originalPostMessage = window.postMessage;
                window.addEventListener('message', (event) => {
                    result.messages_captured.push({
                        origin: event.origin,
                        data_type: typeof event.data,
                        data_preview: JSON.stringify(event.data).substring(0, 200),
                        timestamp: Date.now()
                    });
                });

                // ===== PHASE 4: Check srcdoc iframes =====
                const srcdocIframes = document.querySelectorAll('iframe[srcdoc]');
                for (const iframe of srcdocIframes) {
                    const srcdoc = iframe.getAttribute('srcdoc');
                    if (srcdoc) {
                        result.content_extracted.push({
                            type: 'srcdoc',
                            content_length: srcdoc.length
                        });
                    }
                }

                return result;
            })()
            """)

            iframe_count = result.get('iframes_found', 0)
            follow_count = len(result.get('follow_data', []))
            print(f"[D2] Found {iframe_count} iframes, {follow_count} users")

            return DOMAlgorithmResult(
                algorithm="D2_IFrameBridge",
                success=True,
                data=result,
                nodes_found=iframe_count
            )

        except Exception as e:
            print(f"[D2] Error: {e}")
            return DOMAlgorithmResult(
                algorithm="D2_IFrameBridge",
                success=False,
                error=str(e)
            )


# ==================== D3: VIRTUAL DOM RECONSTRUCTION ====================

class VirtualDOMReconstructor:
    """
    D3: Extract data from React/Vue internal state
    - React: traverse fiber tree via __reactFiber$
    - Vue: access __vue__ / __vue_app__
    - Extract component props, state, hooks
    """

    def __init__(self, page: Page):
        self.page = page

    async def execute(self) -> DOMAlgorithmResult:
        """Execute Virtual DOM reconstruction"""
        print("[D3] Virtual DOM Reconstruction...")

        try:
            result = await self.page.evaluate("""
            (() => {
                const result = {
                    framework: 'unknown',
                    components_found: 0,
                    state_data: {},
                    follow_data: [],
                    privacy_flags: [],
                    props_extracted: []
                };

                // ===== Detect Framework =====
                const root = document.getElementById('app') ||
                             document.getElementById('root') ||
                             document.getElementById('__next') ||
                             document.querySelector('[data-reactroot]') ||
                             document.querySelector('#main');

                // ===== REACT FIBER TRAVERSAL =====
                function findReactFiber(element) {
                    const keys = Object.keys(element);
                    const fiberKey = keys.find(k =>
                        k.startsWith('__reactFiber$') ||
                        k.startsWith('__reactInternalInstance$')
                    );
                    return fiberKey ? element[fiberKey] : null;
                }

                function traverseFiber(fiber, depth = 0) {
                    if (!fiber || depth > 20) return;
                    result.components_found++;

                    // Extract props
                    if (fiber.memoizedProps) {
                        const props = fiber.memoizedProps;
                        const propsInfo = {
                            type: fiber.type?.displayName || fiber.type?.name || typeof fiber.type,
                            depth: depth
                        };

                        // Privacy-related props
                        const privacyKeys = ['isPrivate', 'privateAccount', 'hideFollowing',
                                           'hideFollowers', 'isBlocked', 'isRestricted',
                                           'showFollowingList', 'followingListVisible'];

                        for (const key of privacyKeys) {
                            if (props[key] !== undefined) {
                                propsInfo[key] = props[key];
                                result.privacy_flags.push({
                                    component: propsInfo.type,
                                    flag: key,
                                    value: props[key]
                                });
                            }
                        }

                        // Follow data props
                        if (props.userList || props.followList || props.users) {
                            const list = props.userList || props.followList || props.users;
                            if (Array.isArray(list)) {
                                for (const user of list) {
                                    if (user.uniqueId || user.username || user.nickName) {
                                        result.follow_data.push({
                                            username: user.uniqueId || user.username || '',
                                            nickname: user.nickName || user.nickname || '',
                                            uid: user.id || user.uid || '',
                                            source: 'react_props'
                                        });
                                    }
                                }
                            }
                        }

                        // User info props
                        if (props.userData || props.userInfo || props.user) {
                            const u = props.userData || props.userInfo || props.user;
                            if (u && (u.uniqueId || u.username)) {
                                result.follow_data.push({
                                    username: u.uniqueId || u.username || '',
                                    nickname: u.nickName || u.nickname || '',
                                    followers: u.followerCount,
                                    following: u.followingCount,
                                    source: 'react_user_props'
                                });
                            }
                        }

                        result.props_extracted.push(propsInfo);
                    }

                    // Extract state (hooks)
                    if (fiber.memoizedState) {
                        let stateNode = fiber.memoizedState;
                        let hookIndex = 0;

                        while (stateNode && hookIndex < 10) {
                            if (stateNode.queue?.lastRenderedState) {
                                const state = stateNode.queue.lastRenderedState;

                                // Check for follow list in state
                                if (state && typeof state === 'object') {
                                    const stateKeys = Object.keys(state);
                                    for (const key of stateKeys) {
                                        if (key.toLowerCase().includes('follow') ||
                                            key.toLowerCase().includes('user')) {
                                            result.state_data[key] = Array.isArray(state[key])
                                                ? `[Array: ${state[key].length} items]`
                                                : typeof state[key];
                                        }
                                    }

                                    // Extract user arrays from state
                                    for (const key of stateKeys) {
                                        if (Array.isArray(state[key])) {
                                            for (const item of state[key]) {
                                                if (item && (item.uniqueId || item.username)) {
                                                    result.follow_data.push({
                                                        username: item.uniqueId || item.username,
                                                        nickname: item.nickName || item.nickname || '',
                                                        source: 'react_state'
                                                    });
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            stateNode = stateNode.next;
                            hookIndex++;
                        }
                    }

                    // Traverse children
                    if (fiber.child) traverseFiber(fiber.child, depth + 1);
                    if (fiber.sibling) traverseFiber(fiber.sibling, depth);
                }

                // ===== VUE TRAVERSAL =====
                function traverseVue(element) {
                    const vue = element.__vue__ || element.__vue_app__;
                    if (!vue) return;

                    result.framework = 'vue';
                    result.components_found++;

                    // Extract data
                    const data = vue.$data || vue._data || {};
                    const keys = Object.keys(data);
                    for (const key of keys) {
                        if (key.toLowerCase().includes('follow') ||
                            key.toLowerCase().includes('user') ||
                            key.toLowerCase().includes('private')) {
                            result.state_data[key] = typeof data[key];

                            if (Array.isArray(data[key])) {
                                for (const item of data[key]) {
                                    if (item && (item.uniqueId || item.username)) {
                                        result.follow_data.push({
                                            username: item.uniqueId || item.username,
                                            source: 'vue_data'
                                        });
                                    }
                                }
                            }
                        }
                    }

                    // Traverse children
                    if (vue.$children) {
                        for (const child of vue.$children) {
                            traverseVue(child.$el || child);
                        }
                    }
                }

                // ===== Execute =====
                // Try React first
                if (root) {
                    const fiber = findReactFiber(root);
                    if (fiber) {
                        result.framework = 'react';
                        traverseFiber(fiber);
                    }
                }

                // Try Vue
                if (result.framework === 'unknown') {
                    const allElements = document.querySelectorAll('*');
                    for (const el of allElements) {
                        if (el.__vue__ || el.__vue_app__) {
                            traverseVue(el);
                            break;
                        }
                    }
                }

                // ===== Fallback: scan all elements for fibers =====
                if (result.components_found === 0) {
                    const candidates = document.querySelectorAll(
                        '[class*="follow"], [class*="Follow"], [data-e2e*="follow"], [data-e2e*="user"]'
                    );
                    for (const el of candidates) {
                        const fiber = findReactFiber(el);
                        if (fiber) {
                            result.framework = 'react';
                            traverseFiber(fiber, 0);
                        }
                    }
                }

                // Deduplicate follow_data
                const seen = new Set();
                result.follow_data = result.follow_data.filter(u => {
                    if (!u.username || seen.has(u.username)) return false;
                    seen.add(u.username);
                    return true;
                });

                return result;
            })()
            """)

            framework = result.get('framework', 'unknown')
            components = result.get('components_found', 0)
            follow_count = len(result.get('follow_data', []))
            privacy = result.get('privacy_flags', [])
            print(f"[D3] Framework: {framework}, {components} components, {follow_count} users, {len(privacy)} privacy flags")

            return DOMAlgorithmResult(
                algorithm="D3_VirtualDOM",
                success=True,
                data=result,
                nodes_found=components
            )

        except Exception as e:
            print(f"[D3] Error: {e}")
            return DOMAlgorithmResult(
                algorithm="D3_VirtualDOM",
                success=False,
                error=str(e)
            )


# ==================== D4: DOM CLONING & DEEP SERIALIZATION ====================

class DOMCloner:
    """
    D4: Deep clone DOM with hidden state
    - Trigger lazy-loaded content
    - Clone with computed styles
    - Serialize datasets, custom properties
    - Offline analysis ready
    """

    def __init__(self, page: Page):
        self.page = page

    async def execute(self) -> DOMAlgorithmResult:
        """Execute DOM deep cloning"""
        print("[D4] DOM Cloning & Deep Serialization...")

        try:
            # Phase 1: Trigger lazy loading
            await self._trigger_lazy_content()

            # Phase 2: Deep serialize
            result = await self.page.evaluate("""
            (() => {
                const result = {
                    total_elements: 0,
                    serialized_nodes: [],
                    datasets_found: [],
                    hidden_elements: [],
                    follow_data: [],
                    lazy_triggered: 0
                };

                // ===== PHASE 1: Force IntersectionObserver triggers =====
                try {
                    const originalIO = window.IntersectionObserver;
                    // Make all observed elements "visible"
                    window.IntersectionObserver = class extends originalIO {
                        constructor(callback, options) {
                            super((entries, observer) => {
                                // Force all entries to be intersecting
                                const modifiedEntries = entries.map(entry => ({
                                    ...entry,
                                    isIntersecting: true,
                                    intersectionRatio: 1.0
                                }));
                                result.lazy_triggered += modifiedEntries.length;
                                callback(modifiedEntries, observer);
                            }, options);
                        }
                    };
                } catch (e) {}

                // ===== PHASE 2: Scan all elements =====
                const allElements = document.querySelectorAll('*');
                result.total_elements = allElements.length;

                for (const el of allElements) {
                    // Check for hidden elements with data
                    const style = window.getComputedStyle(el);
                    const isHidden = style.display === 'none' ||
                                     style.visibility === 'hidden' ||
                                     style.opacity === '0' ||
                                     el.hasAttribute('hidden');

                    // Extract datasets
                    if (Object.keys(el.dataset).length > 0) {
                        const dataInfo = {
                            tag: el.tagName.toLowerCase(),
                            dataset: { ...el.dataset },
                            hidden: isHidden
                        };

                        result.datasets_found.push(dataInfo);

                        // Check for follow/user data in dataset
                        for (const [key, value] of Object.entries(el.dataset)) {
                            if (key.toLowerCase().includes('user') ||
                                key.toLowerCase().includes('follow')) {
                                try {
                                    const parsed = JSON.parse(value);
                                    if (Array.isArray(parsed)) {
                                        for (const item of parsed) {
                                            if (item.uniqueId || item.username) {
                                                result.follow_data.push({
                                                    username: item.uniqueId || item.username,
                                                    source: 'dataset'
                                                });
                                            }
                                        }
                                    }
                                } catch (e) {}
                            }
                        }
                    }

                    // Collect hidden elements that might have content
                    if (isHidden && el.innerHTML.length > 50) {
                        result.hidden_elements.push({
                            tag: el.tagName.toLowerCase(),
                            classes: Array.from(el.classList).slice(0, 5),
                            content_length: el.innerHTML.length,
                            has_links: el.querySelectorAll('a').length > 0,
                            text_preview: el.textContent?.trim().substring(0, 100)
                        });

                        // Extract links from hidden elements
                        const links = el.querySelectorAll('a[href*="/@"]');
                        for (const link of links) {
                            const href = link.getAttribute('href');
                            const username = href?.split('/@')[1]?.split('?')[0]?.split('/')[0];
                            if (username) {
                                result.follow_data.push({
                                    username: username,
                                    text: link.textContent?.trim(),
                                    source: 'hidden_element'
                                });
                            }
                        }
                    }
                }

                // ===== PHASE 3: Check script tags for embedded data =====
                const scripts = document.querySelectorAll('script[type="application/json"], script[id*="SIGI"], script[id*="__NEXT_DATA__"]');
                for (const script of scripts) {
                    try {
                        const data = JSON.parse(script.textContent);
                        result.serialized_nodes.push({
                            type: 'embedded_json',
                            id: script.id || 'anonymous',
                            keys: Object.keys(data).slice(0, 20)
                        });

                        // Deep search for user data
                        function searchForUsers(obj, path = '') {
                            if (!obj || typeof obj !== 'object') return;
                            if (Array.isArray(obj)) {
                                for (const item of obj) {
                                    if (item && (item.uniqueId || item.username)) {
                                        result.follow_data.push({
                                            username: item.uniqueId || item.username,
                                            nickname: item.nickName || item.nickname || '',
                                            source: 'embedded_json_' + path
                                        });
                                    }
                                }
                                return;
                            }
                            for (const [key, value] of Object.entries(obj)) {
                                if (key.toLowerCase().includes('follow') ||
                                    key.toLowerCase().includes('userlist') ||
                                    key.toLowerCase().includes('users')) {
                                    searchForUsers(value, path + '.' + key);
                                }
                            }
                        }
                        searchForUsers(data);

                    } catch (e) {}
                }

                // Deduplicate
                const seen = new Set();
                result.follow_data = result.follow_data.filter(u => {
                    if (!u.username || seen.has(u.username)) return false;
                    seen.add(u.username);
                    return true;
                });

                return result;
            })()
            """)

            total = result.get('total_elements', 0)
            hidden = len(result.get('hidden_elements', []))
            follow_count = len(result.get('follow_data', []))
            print(f"[D4] {total} elements, {hidden} hidden, {follow_count} users")

            return DOMAlgorithmResult(
                algorithm="D4_DOMClone",
                success=True,
                data=result,
                nodes_found=total
            )

        except Exception as e:
            print(f"[D4] Error: {e}")
            return DOMAlgorithmResult(
                algorithm="D4_DOMClone",
                success=False,
                error=str(e)
            )

    async def _trigger_lazy_content(self):
        """Trigger lazy-loaded content by scrolling"""
        try:
            # Scroll page to trigger lazy loading
            await self.page.evaluate("""
                async () => {
                    const delay = ms => new Promise(r => setTimeout(r, ms));
                    for (let i = 0; i < 5; i++) {
                        window.scrollBy(0, 500);
                        await delay(300);
                    }
                    window.scrollTo(0, 0);
                }
            """)
            await asyncio.sleep(1)
        except:
            pass


# ==================== D5: EVENT LOOP INTERCEPTION ====================

class EventLoopInterceptor:
    """
    D5: Capture & replay browser events
    - Monkey-patch addEventListener/dispatchEvent
    - Record event bindings
    - Auto-replay hover/click/focus on target elements
    - Capture DOM mutations
    """

    def __init__(self, page: Page):
        self.page = page

    async def execute(self) -> DOMAlgorithmResult:
        """Execute event loop interception"""
        print("[D5] Event Loop Interception...")

        try:
            # Phase 1: Install interceptors
            await self.page.evaluate("""
            (() => {
                window.__eventLog = [];
                window.__mutationLog = [];

                // ===== Monkey-patch addEventListener =====
                const origAdd = EventTarget.prototype.addEventListener;
                EventTarget.prototype.addEventListener = function(type, listener, options) {
                    window.__eventLog.push({
                        action: 'add',
                        type: type,
                        target: this.tagName || this.constructor.name,
                        timestamp: Date.now()
                    });
                    return origAdd.call(this, type, listener, options);
                };

                // ===== Monkey-patch dispatchEvent =====
                const origDispatch = EventTarget.prototype.dispatchEvent;
                EventTarget.prototype.dispatchEvent = function(event) {
                    window.__eventLog.push({
                        action: 'dispatch',
                        type: event.type,
                        target: this.tagName || this.constructor.name,
                        timestamp: Date.now()
                    });
                    return origDispatch.call(this, event);
                };

                // ===== MutationObserver =====
                const observer = new MutationObserver((mutations) => {
                    for (const m of mutations) {
                        if (m.addedNodes.length > 0) {
                            window.__mutationLog.push({
                                type: 'childList',
                                added: m.addedNodes.length,
                                target: m.target.tagName || 'unknown',
                                timestamp: Date.now()
                            });
                        }
                        if (m.type === 'attributes') {
                            window.__mutationLog.push({
                                type: 'attributes',
                                attr: m.attributeName,
                                target: m.target.tagName || 'unknown'
                            });
                        }
                    }
                });
                observer.observe(document.body, {
                    childList: true,
                    subtree: true,
                    attributes: true,
                    attributeFilter: ['class', 'style', 'hidden', 'data-visible']
                });
            })()
            """)

            # Phase 2: Auto-replay events on follow-related elements
            await self.page.evaluate("""
            (() => {
                const targets = document.querySelectorAll([
                    '[data-e2e*="follow"]',
                    '[data-e2e*="user"]',
                    '[class*="follow"]',
                    '[class*="Follow"]',
                    '[class*="private"]',
                    '[class*="Private"]',
                    '[class*="UserList"]',
                    'div[role="dialog"]',
                    'div[role="list"]'
                ].join(','));

                for (const el of targets) {
                    // Simulate hover
                    el.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
                    el.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));

                    // Simulate focus
                    el.dispatchEvent(new FocusEvent('focus', { bubbles: true }));

                    // Force visibility
                    el.style.display = '';
                    el.style.visibility = 'visible';
                    el.style.opacity = '1';
                    el.removeAttribute('hidden');
                }
            })()
            """)

            # Phase 3: Wait for mutations to settle
            await asyncio.sleep(2)

            # Phase 4: Collect results
            result = await self.page.evaluate("""
            (() => {
                const result = {
                    events_logged: window.__eventLog?.length || 0,
                    mutations_logged: window.__mutationLog?.length || 0,
                    event_types: {},
                    follow_data: [],
                    new_content_found: false
                };

                // Summarize event types
                for (const event of (window.__eventLog || [])) {
                    const key = event.type;
                    result.event_types[key] = (result.event_types[key] || 0) + 1;
                }

                // Check for new content after event replay
                const newLinks = document.querySelectorAll('a[href*="/@"]');
                for (const link of newLinks) {
                    const href = link.getAttribute('href');
                    const username = href?.split('/@')[1]?.split('?')[0]?.split('/')[0];
                    if (username) {
                        result.follow_data.push({
                            username: username,
                            text: link.textContent?.trim(),
                            visible: link.offsetParent !== null,
                            source: 'event_replay'
                        });
                    }
                }

                // Deduplicate
                const seen = new Set();
                result.follow_data = result.follow_data.filter(u => {
                    if (!u.username || seen.has(u.username)) return false;
                    seen.add(u.username);
                    return true;
                });

                if (result.follow_data.length > 0) {
                    result.new_content_found = true;
                }

                // Cleanup
                delete window.__eventLog;
                delete window.__mutationLog;

                return result;
            })()
            """)

            events = result.get('events_logged', 0)
            mutations = result.get('mutations_logged', 0)
            follow_count = len(result.get('follow_data', []))
            print(f"[D5] {events} events, {mutations} mutations, {follow_count} users")

            return DOMAlgorithmResult(
                algorithm="D5_EventLoop",
                success=True,
                data=result,
                nodes_found=events
            )

        except Exception as e:
            print(f"[D5] Error: {e}")
            return DOMAlgorithmResult(
                algorithm="D5_EventLoop",
                success=False,
                error=str(e)
            )


# ==================== D6: MUTATION OBSERVER WITH HISTORICAL TRACKING ====================

class MutationHistoryTracker:
    """
    D6: Track DOM changes since page load
    - Install early MutationObserver
    - Periodic DOM snapshots
    - Detect ephemeral elements (appeared then removed)
    - Reconstruct content history
    """

    def __init__(self, page: Page):
        self.page = page

    async def execute(self) -> DOMAlgorithmResult:
        """Execute mutation history tracking"""
        print("[D6] Mutation History Tracking...")

        try:
            # Phase 1: Install observer and take initial snapshot
            await self.page.evaluate("""
            (() => {
                window.__mutHistory = {
                    snapshots: [],
                    added_nodes: [],
                    removed_nodes: [],
                    attribute_changes: [],
                    ephemeral: []
                };

                // Take initial snapshot
                window.__mutHistory.snapshots.push({
                    timestamp: Date.now(),
                    element_count: document.querySelectorAll('*').length,
                    links: document.querySelectorAll('a[href*="/@"]').length
                });

                // Track added/removed nodes with content
                const nodeTimestamps = new Map();

                const observer = new MutationObserver((mutations) => {
                    for (const m of mutations) {
                        // Track added nodes
                        for (const node of m.addedNodes) {
                            if (node.nodeType === 1) {
                                const id = node.tagName + '.' + (node.className || '').toString().substring(0, 50);
                                nodeTimestamps.set(node, Date.now());

                                window.__mutHistory.added_nodes.push({
                                    tag: node.tagName?.toLowerCase(),
                                    classes: node.className?.toString().substring(0, 100) || '',
                                    text_preview: node.textContent?.trim().substring(0, 150) || '',
                                    has_user_links: (node.querySelectorAll?.('a[href*="/@"]') || []).length > 0,
                                    timestamp: Date.now()
                                });
                            }
                        }

                        // Track removed nodes - detect ephemeral content
                        for (const node of m.removedNodes) {
                            if (node.nodeType === 1) {
                                const addedAt = nodeTimestamps.get(node);
                                const lifetime = addedAt ? Date.now() - addedAt : null;

                                const info = {
                                    tag: node.tagName?.toLowerCase(),
                                    classes: node.className?.toString().substring(0, 100) || '',
                                    text_preview: node.textContent?.trim().substring(0, 200) || '',
                                    html_length: node.innerHTML?.length || 0,
                                    lifetime_ms: lifetime,
                                    timestamp: Date.now()
                                };

                                window.__mutHistory.removed_nodes.push(info);

                                // Ephemeral: existed less than 2 seconds
                                if (lifetime && lifetime < 2000) {
                                    window.__mutHistory.ephemeral.push(info);
                                }

                                // Extract user links before removal
                                try {
                                    const links = node.querySelectorAll?.('a[href*="/@"]') || [];
                                    for (const link of links) {
                                        const href = link.getAttribute('href');
                                        const username = href?.split('/@')[1]?.split('?')[0]?.split('/')[0];
                                        if (username) {
                                            window.__mutHistory.removed_nodes[
                                                window.__mutHistory.removed_nodes.length - 1
                                            ].extracted_user = username;
                                        }
                                    }
                                } catch (e) {}
                            }
                        }

                        // Track attribute changes
                        if (m.type === 'attributes') {
                            window.__mutHistory.attribute_changes.push({
                                tag: m.target.tagName?.toLowerCase(),
                                attr: m.attributeName,
                                old_value: m.oldValue?.substring(0, 100),
                                new_value: m.target.getAttribute(m.attributeName)?.substring(0, 100),
                                timestamp: Date.now()
                            });
                        }
                    }
                });

                observer.observe(document.documentElement, {
                    childList: true,
                    subtree: true,
                    attributes: true,
                    attributeOldValue: true,
                    characterData: true,
                    characterDataOldValue: true
                });
            })()
            """)

            # Phase 2: Wait and take periodic snapshots
            for i in range(3):
                await asyncio.sleep(2)
                await self.page.evaluate("""
                (() => {
                    if (window.__mutHistory) {
                        window.__mutHistory.snapshots.push({
                            timestamp: Date.now(),
                            element_count: document.querySelectorAll('*').length,
                            links: document.querySelectorAll('a[href*="/@"]').length
                        });
                    }
                })()
                """)

            # Phase 3: Collect results
            result = await self.page.evaluate("""
            (() => {
                const h = window.__mutHistory || {};
                const result = {
                    snapshots: h.snapshots || [],
                    total_additions: (h.added_nodes || []).length,
                    total_removals: (h.removed_nodes || []).length,
                    ephemeral_count: (h.ephemeral || []).length,
                    attribute_changes: (h.attribute_changes || []).length,
                    ephemeral_content: (h.ephemeral || []).slice(0, 20),
                    follow_data: []
                };

                // Extract users from all tracked nodes
                for (const node of [...(h.added_nodes || []), ...(h.removed_nodes || [])]) {
                    if (node.extracted_user) {
                        result.follow_data.push({
                            username: node.extracted_user,
                            source: 'mutation_history',
                            ephemeral: node.lifetime_ms ? node.lifetime_ms < 2000 : false
                        });
                    }
                }

                // Also scan current page for users
                const links = document.querySelectorAll('a[href*="/@"]');
                for (const link of links) {
                    const href = link.getAttribute('href');
                    const username = href?.split('/@')[1]?.split('?')[0]?.split('/')[0];
                    if (username) {
                        result.follow_data.push({
                            username, source: 'mutation_current'
                        });
                    }
                }

                // Deduplicate
                const seen = new Set();
                result.follow_data = result.follow_data.filter(u => {
                    if (!u.username || seen.has(u.username)) return false;
                    seen.add(u.username);
                    return true;
                });

                delete window.__mutHistory;
                return result;
            })()
            """)

            adds = result.get('total_additions', 0)
            removes = result.get('total_removals', 0)
            ephemeral = result.get('ephemeral_count', 0)
            follow_count = len(result.get('follow_data', []))
            print(f"[D6] +{adds} -{removes} nodes, {ephemeral} ephemeral, {follow_count} users")

            return DOMAlgorithmResult(
                algorithm="D6_MutationHistory",
                success=True,
                data=result,
                nodes_found=adds + removes
            )

        except Exception as e:
            print(f"[D6] Error: {e}")
            return DOMAlgorithmResult(
                algorithm="D6_MutationHistory",
                success=False,
                error=str(e)
            )


# ==================== D7: PSEUDO-ELEMENT EXTRACTION ====================

class PseudoElementExtractor:
    """
    D7: Extract content from CSS pseudo-elements
    - ::before, ::after, ::placeholder content
    - Parse attr() references and url() values
    - Filter for user/follow related content
    """

    def __init__(self, page: Page):
        self.page = page

    async def execute(self) -> DOMAlgorithmResult:
        """Execute pseudo-element extraction"""
        print("[D7] Pseudo-Element Extraction...")

        try:
            result = await self.page.evaluate("""
            (() => {
                const result = {
                    pseudo_elements_found: 0,
                    content_extracted: [],
                    urls_found: [],
                    follow_data: []
                };

                const allElements = document.querySelectorAll('*');

                for (const el of allElements) {
                    // Check ::before
                    try {
                        const before = window.getComputedStyle(el, '::before');
                        const beforeContent = before.getPropertyValue('content');
                        if (beforeContent && beforeContent !== 'none' && beforeContent !== 'normal' && beforeContent !== '""') {
                            result.pseudo_elements_found++;
                            const cleaned = beforeContent.replace(/^["']|["']$/g, '');

                            if (cleaned.length > 1) {
                                result.content_extracted.push({
                                    type: '::before',
                                    tag: el.tagName.toLowerCase(),
                                    classes: Array.from(el.classList).slice(0, 3),
                                    content: cleaned.substring(0, 200),
                                    has_url: cleaned.includes('url(')
                                });

                                // Check for URL references
                                const urlMatch = cleaned.match(/url\(["']?([^)"']+)["']?\)/);
                                if (urlMatch) {
                                    result.urls_found.push({
                                        url: urlMatch[1],
                                        source: '::before',
                                        element: el.tagName.toLowerCase()
                                    });
                                }

                                // Check for user-related content
                                if (cleaned.includes('@') || cleaned.includes('follow') ||
                                    cleaned.includes('user')) {
                                    result.follow_data.push({
                                        username: cleaned.replace('@', '').trim(),
                                        source: 'pseudo_before',
                                        raw_content: cleaned
                                    });
                                }
                            }
                        }
                    } catch (e) {}

                    // Check ::after
                    try {
                        const after = window.getComputedStyle(el, '::after');
                        const afterContent = after.getPropertyValue('content');
                        if (afterContent && afterContent !== 'none' && afterContent !== 'normal' && afterContent !== '""') {
                            result.pseudo_elements_found++;
                            const cleaned = afterContent.replace(/^["']|["']$/g, '');

                            if (cleaned.length > 1) {
                                result.content_extracted.push({
                                    type: '::after',
                                    tag: el.tagName.toLowerCase(),
                                    classes: Array.from(el.classList).slice(0, 3),
                                    content: cleaned.substring(0, 200),
                                    has_url: cleaned.includes('url(')
                                });

                                const urlMatch = cleaned.match(/url\(["']?([^)"']+)["']?\)/);
                                if (urlMatch) {
                                    result.urls_found.push({
                                        url: urlMatch[1],
                                        source: '::after',
                                        element: el.tagName.toLowerCase()
                                    });
                                }

                                if (cleaned.includes('@') || cleaned.includes('follow') ||
                                    cleaned.includes('user')) {
                                    result.follow_data.push({
                                        username: cleaned.replace('@', '').trim(),
                                        source: 'pseudo_after',
                                        raw_content: cleaned
                                    });
                                }
                            }
                        }
                    } catch (e) {}

                    // Check ::placeholder for input elements
                    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                        try {
                            const placeholder = window.getComputedStyle(el, '::placeholder');
                            const phContent = el.getAttribute('placeholder');
                            if (phContent && phContent.length > 1) {
                                result.content_extracted.push({
                                    type: '::placeholder',
                                    tag: el.tagName.toLowerCase(),
                                    content: phContent
                                });
                            }
                        } catch (e) {}
                    }
                }

                // Deduplicate
                const seen = new Set();
                result.follow_data = result.follow_data.filter(u => {
                    if (!u.username || seen.has(u.username)) return false;
                    seen.add(u.username);
                    return true;
                });

                return result;
            })()
            """)

            pseudo_count = result.get('pseudo_elements_found', 0)
            content_count = len(result.get('content_extracted', []))
            follow_count = len(result.get('follow_data', []))
            print(f"[D7] {pseudo_count} pseudo-elements, {content_count} content items, {follow_count} users")

            return DOMAlgorithmResult(
                algorithm="D7_PseudoElement",
                success=True,
                data=result,
                nodes_found=pseudo_count
            )

        except Exception as e:
            print(f"[D7] Error: {e}")
            return DOMAlgorithmResult(
                algorithm="D7_PseudoElement",
                success=False,
                error=str(e)
            )


# ==================== D8: CANVAS & WEBGL CAPTURE ====================

class CanvasWebGLCapture:
    """
    D8: Capture content rendered via Canvas/WebGL
    - Hook getImageData and toDataURL
    - Capture fillText/strokeText calls
    - Extract WebGL shader source and uniforms
    """

    def __init__(self, page: Page):
        self.page = page

    async def execute(self) -> DOMAlgorithmResult:
        """Execute Canvas/WebGL capture"""
        print("[D8] Canvas & WebGL Capture...")

        try:
            result = await self.page.evaluate("""
            (() => {
                const result = {
                    canvases_found: 0,
                    webgl_canvases: 0,
                    text_rendered: [],
                    canvas_data: [],
                    shaders: [],
                    follow_data: []
                };

                // ===== PHASE 1: Hook Canvas text rendering =====
                const origFillText = CanvasRenderingContext2D.prototype.fillText;
                const origStrokeText = CanvasRenderingContext2D.prototype.strokeText;

                CanvasRenderingContext2D.prototype.fillText = function(text, x, y, maxWidth) {
                    result.text_rendered.push({
                        text: text,
                        method: 'fillText',
                        x: x, y: y,
                        font: this.font,
                        timestamp: Date.now()
                    });

                    // Check for usernames
                    if (text.includes('@') || text.match(/[a-zA-Z0-9_.]+/)) {
                        const userMatch = text.match(/@([a-zA-Z0-9_.]+)/);
                        if (userMatch) {
                            result.follow_data.push({
                                username: userMatch[1],
                                source: 'canvas_fillText'
                            });
                        }
                    }

                    return origFillText.call(this, text, x, y, maxWidth);
                };

                CanvasRenderingContext2D.prototype.strokeText = function(text, x, y, maxWidth) {
                    result.text_rendered.push({
                        text: text,
                        method: 'strokeText',
                        x: x, y: y,
                        timestamp: Date.now()
                    });
                    return origStrokeText.call(this, text, x, y, maxWidth);
                };

                // ===== PHASE 2: Scan existing canvases =====
                const canvases = document.querySelectorAll('canvas');
                result.canvases_found = canvases.length;

                for (const canvas of canvases) {
                    const info = {
                        width: canvas.width,
                        height: canvas.height,
                        id: canvas.id || null,
                        classes: Array.from(canvas.classList),
                        has_content: false,
                        context_type: null
                    };

                    // Try 2D context
                    try {
                        const ctx = canvas.getContext('2d');
                        if (ctx) {
                            info.context_type = '2d';
                            const imageData = ctx.getImageData(0, 0, 1, 1);
                            info.has_content = imageData.data.some(v => v > 0);
                        }
                    } catch (e) {}

                    // Try WebGL context
                    try {
                        const gl = canvas.getContext('webgl') || canvas.getContext('webgl2');
                        if (gl) {
                            info.context_type = 'webgl';
                            result.webgl_canvases++;

                            // Extract shader info
                            const ext = gl.getExtension('WEBGL_debug_shaders');
                            const programs = [];

                            // Get active program info
                            const program = gl.getParameter(gl.CURRENT_PROGRAM);
                            if (program) {
                                const vertShader = gl.getAttachedShaders(program)?.[0];
                                const fragShader = gl.getAttachedShaders(program)?.[1];

                                if (vertShader) {
                                    result.shaders.push({
                                        type: 'vertex',
                                        source: gl.getShaderSource(vertShader)?.substring(0, 500) || '[compiled]'
                                    });
                                }
                                if (fragShader) {
                                    result.shaders.push({
                                        type: 'fragment',
                                        source: gl.getShaderSource(fragShader)?.substring(0, 500) || '[compiled]'
                                    });
                                }
                            }
                        }
                    } catch (e) {}

                    // Try to get canvas as data URL
                    try {
                        const dataUrl = canvas.toDataURL('image/png');
                        info.data_url_length = dataUrl.length;
                        info.has_content = dataUrl.length > 100;
                    } catch (e) {
                        info.tainted = true;
                    }

                    result.canvas_data.push(info);
                }

                // Deduplicate
                const seen = new Set();
                result.follow_data = result.follow_data.filter(u => {
                    if (!u.username || seen.has(u.username)) return false;
                    seen.add(u.username);
                    return true;
                });

                return result;
            })()
            """)

            canvas_count = result.get('canvases_found', 0)
            webgl_count = result.get('webgl_canvases', 0)
            text_count = len(result.get('text_rendered', []))
            follow_count = len(result.get('follow_data', []))
            print(f"[D8] {canvas_count} canvases ({webgl_count} WebGL), {text_count} text items, {follow_count} users")

            return DOMAlgorithmResult(
                algorithm="D8_CanvasWebGL",
                success=True,
                data=result,
                nodes_found=canvas_count
            )

        except Exception as e:
            print(f"[D8] Error: {e}")
            return DOMAlgorithmResult(
                algorithm="D8_CanvasWebGL",
                success=False,
                error=str(e)
            )


# ==================== D9: SVG & FOREIGN OBJECT PARSING ====================

class SVGForeignObjectParser:
    """
    D9: Parse SVG elements and embedded HTML via <foreignObject>
    - Extract <text>, <tspan> content
    - Parse <foreignObject> embedded HTML
    - Extract <a> links from SVG
    - Serialize path data and transforms
    """

    def __init__(self, page: Page):
        self.page = page

    async def execute(self) -> DOMAlgorithmResult:
        """Execute SVG/ForeignObject parsing"""
        print("[D9] SVG & ForeignObject Parsing...")

        try:
            result = await self.page.evaluate("""
            (() => {
                const result = {
                    svgs_found: 0,
                    text_elements: [],
                    foreign_objects: [],
                    links_in_svg: [],
                    paths_found: 0,
                    follow_data: []
                };

                // ===== PHASE 1: Find all SVG elements =====
                const svgs = document.querySelectorAll('svg');
                // Also check <object> and <embed> with SVG
                const svgObjects = document.querySelectorAll('object[type*="svg"], embed[type*="svg"]');

                result.svgs_found = svgs.length + svgObjects.length;

                for (const svg of svgs) {
                    // ===== PHASE 2: Extract text content =====
                    const textEls = svg.querySelectorAll('text, tspan');
                    for (const textEl of textEls) {
                        const text = textEl.textContent?.trim();
                        if (text && text.length > 0) {
                            result.text_elements.push({
                                tag: textEl.tagName.toLowerCase(),
                                text: text,
                                x: textEl.getAttribute('x'),
                                y: textEl.getAttribute('y'),
                                font_size: textEl.getAttribute('font-size') ||
                                           window.getComputedStyle(textEl).fontSize
                            });

                            // Check for usernames
                            const userMatch = text.match(/@([a-zA-Z0-9_.]+)/);
                            if (userMatch) {
                                result.follow_data.push({
                                    username: userMatch[1],
                                    source: 'svg_text'
                                });
                            }
                        }
                    }

                    // ===== PHASE 3: Parse <foreignObject> =====
                    const foreignObjects = svg.querySelectorAll('foreignObject');
                    for (const fo of foreignObjects) {
                        const html = fo.innerHTML;
                        result.foreign_objects.push({
                            width: fo.getAttribute('width'),
                            height: fo.getAttribute('height'),
                            content_length: html.length,
                            text_preview: fo.textContent?.trim().substring(0, 200)
                        });

                        // Extract links from foreignObject HTML
                        const links = fo.querySelectorAll('a[href*="/@"]');
                        for (const link of links) {
                            const href = link.getAttribute('href');
                            const username = href?.split('/@')[1]?.split('?')[0]?.split('/')[0];
                            if (username) {
                                result.follow_data.push({
                                    username: username,
                                    text: link.textContent?.trim(),
                                    source: 'svg_foreignObject'
                                });
                            }
                        }
                    }

                    // ===== PHASE 4: Extract links inside SVG =====
                    const svgLinks = svg.querySelectorAll('a');
                    for (const link of svgLinks) {
                        const href = link.getAttribute('href') ||
                                     link.getAttributeNS('http://www.w3.org/1999/xlink', 'href');
                        if (href) {
                            result.links_in_svg.push({
                                href: href,
                                text: link.textContent?.trim()
                            });

                            if (href.includes('/@')) {
                                const username = href.split('/@')[1]?.split('?')[0]?.split('/')[0];
                                if (username) {
                                    result.follow_data.push({
                                        username: username,
                                        source: 'svg_link'
                                    });
                                }
                            }
                        }
                    }

                    // Count paths
                    result.paths_found += svg.querySelectorAll('path').length;
                }

                // ===== PHASE 5: Check SVG in <object>/<embed> =====
                for (const obj of svgObjects) {
                    try {
                        const doc = obj.contentDocument || obj.getSVGDocument?.();
                        if (doc) {
                            const texts = doc.querySelectorAll('text, tspan');
                            for (const t of texts) {
                                result.text_elements.push({
                                    tag: t.tagName.toLowerCase(),
                                    text: t.textContent?.trim(),
                                    source: 'embedded_svg'
                                });
                            }
                        }
                    } catch (e) {}
                }

                // Deduplicate
                const seen = new Set();
                result.follow_data = result.follow_data.filter(u => {
                    if (!u.username || seen.has(u.username)) return false;
                    seen.add(u.username);
                    return true;
                });

                return result;
            })()
            """)

            svg_count = result.get('svgs_found', 0)
            text_count = len(result.get('text_elements', []))
            fo_count = len(result.get('foreign_objects', []))
            follow_count = len(result.get('follow_data', []))
            print(f"[D9] {svg_count} SVGs, {text_count} text elements, {fo_count} foreignObjects, {follow_count} users")

            return DOMAlgorithmResult(
                algorithm="D9_SVGForeignObject",
                success=True,
                data=result,
                nodes_found=svg_count
            )

        except Exception as e:
            print(f"[D9] Error: {e}")
            return DOMAlgorithmResult(
                algorithm="D9_SVGForeignObject",
                success=False,
                error=str(e)
            )


# ==================== D10: WEB COMPONENT CUSTOM STATE ACCESS ====================

class WebComponentStateAccess:
    """
    D10: Access internal state of custom Web Components
    - Find custom elements and their definitions
    - Inspect observedAttributes and trigger changes
    - Prototype chain analysis for getters/setters
    - Force re-render via attribute mutation
    """

    def __init__(self, page: Page):
        self.page = page

    async def execute(self) -> DOMAlgorithmResult:
        """Execute Web Component state access"""
        print("[D10] Web Component State Access...")

        try:
            result = await self.page.evaluate("""
            (() => {
                const result = {
                    custom_elements_found: 0,
                    registered_components: [],
                    observed_attributes: {},
                    internal_state: [],
                    re_render_results: [],
                    follow_data: []
                };

                // ===== PHASE 1: Find custom elements =====
                const allElements = document.querySelectorAll('*');
                const customElements = [];

                for (const el of allElements) {
                    const tagName = el.tagName.toLowerCase();
                    // Custom elements contain hyphens
                    if (tagName.includes('-')) {
                        customElements.push(el);
                        result.custom_elements_found++;
                    }
                }

                // ===== PHASE 2: Inspect registered custom elements =====
                for (const el of customElements) {
                    const tagName = el.tagName.toLowerCase();
                    const constructor = el.constructor;

                    const componentInfo = {
                        tag: tagName,
                        defined: constructor !== HTMLElement,
                        has_shadow: !!el.shadowRoot,
                        attributes: {},
                        properties: [],
                        content_preview: ''
                    };

                    // Get observed attributes
                    try {
                        const observed = constructor.observedAttributes || [];
                        componentInfo.observed_attrs = Array.from(observed);
                        result.observed_attributes[tagName] = componentInfo.observed_attrs;
                    } catch (e) {}

                    // Get current attributes
                    for (const attr of el.attributes) {
                        componentInfo.attributes[attr.name] = attr.value.substring(0, 100);
                    }

                    // ===== PHASE 3: Prototype chain analysis =====
                    try {
                        let proto = Object.getPrototypeOf(el);
                        let depth = 0;

                        while (proto && proto !== HTMLElement.prototype && depth < 5) {
                            const descriptors = Object.getOwnPropertyDescriptors(proto);

                            for (const [name, desc] of Object.entries(descriptors)) {
                                // Find getters that might expose internal state
                                if (desc.get && !['constructor', 'toString'].includes(name)) {
                                    componentInfo.properties.push({
                                        name: name,
                                        has_getter: true,
                                        has_setter: !!desc.set
                                    });

                                    // Try to read the property
                                    try {
                                        const value = el[name];
                                        if (value !== undefined && value !== null) {
                                            const valueStr = JSON.stringify(value);
                                            if (valueStr && valueStr.length < 500) {
                                                // Check for user data
                                                if (typeof value === 'object') {
                                                    if (value.uniqueId || value.username) {
                                                        result.follow_data.push({
                                                            username: value.uniqueId || value.username,
                                                            source: 'webcomponent_property_' + name
                                                        });
                                                    }
                                                    if (Array.isArray(value)) {
                                                        for (const item of value) {
                                                            if (item?.uniqueId || item?.username) {
                                                                result.follow_data.push({
                                                                    username: item.uniqueId || item.username,
                                                                    source: 'webcomponent_array_' + name
                                                                });
                                                            }
                                                        }
                                                    }
                                                }
                                                result.internal_state.push({
                                                    component: tagName,
                                                    property: name,
                                                    value_preview: valueStr.substring(0, 200)
                                                });
                                            }
                                        }
                                    } catch (e) {}
                                }
                            }

                            proto = Object.getPrototypeOf(proto);
                            depth++;
                        }
                    } catch (e) {}

                    // ===== PHASE 4: Trigger attribute changes for re-render =====
                    if (componentInfo.observed_attrs?.length > 0) {
                        const beforeHTML = el.innerHTML.length;

                        for (const attr of componentInfo.observed_attrs) {
                            try {
                                // Toggle boolean-like attributes
                                const currentVal = el.getAttribute(attr);
                                if (currentVal === 'true' || currentVal === 'false') {
                                    el.setAttribute(attr, currentVal === 'true' ? 'false' : 'true');
                                    // Revert after capture
                                    setTimeout(() => el.setAttribute(attr, currentVal), 100);
                                }
                            } catch (e) {}
                        }

                        const afterHTML = el.innerHTML.length;
                        if (afterHTML !== beforeHTML) {
                            result.re_render_results.push({
                                component: tagName,
                                before_length: beforeHTML,
                                after_length: afterHTML,
                                delta: afterHTML - beforeHTML
                            });

                            // Check for new user links
                            const links = el.querySelectorAll('a[href*="/@"]');
                            for (const link of links) {
                                const href = link.getAttribute('href');
                                const username = href?.split('/@')[1]?.split('?')[0]?.split('/')[0];
                                if (username) {
                                    result.follow_data.push({
                                        username: username,
                                        source: 'webcomponent_rerender'
                                    });
                                }
                            }
                        }
                    }

                    // Capture shadow DOM content
                    if (el.shadowRoot) {
                        componentInfo.content_preview = el.shadowRoot.innerHTML.substring(0, 200);

                        const shadowLinks = el.shadowRoot.querySelectorAll('a[href*="/@"]');
                        for (const link of shadowLinks) {
                            const href = link.getAttribute('href');
                            const username = href?.split('/@')[1]?.split('?')[0]?.split('/')[0];
                            if (username) {
                                result.follow_data.push({
                                    username: username,
                                    source: 'webcomponent_shadow'
                                });
                            }
                        }
                    }

                    result.registered_components.push(componentInfo);
                }

                // Deduplicate
                const seen = new Set();
                result.follow_data = result.follow_data.filter(u => {
                    if (!u.username || seen.has(u.username)) return false;
                    seen.add(u.username);
                    return true;
                });

                return result;
            })()
            """)

            custom_count = result.get('custom_elements_found', 0)
            state_count = len(result.get('internal_state', []))
            rerender_count = len(result.get('re_render_results', []))
            follow_count = len(result.get('follow_data', []))
            print(f"[D10] {custom_count} custom elements, {state_count} state items, {rerender_count} re-renders, {follow_count} users")

            return DOMAlgorithmResult(
                algorithm="D10_WebComponent",
                success=True,
                data=result,
                nodes_found=custom_count
            )

        except Exception as e:
            print(f"[D10] Error: {e}")
            return DOMAlgorithmResult(
                algorithm="D10_WebComponent",
                success=False,
                error=str(e)
            )


# ==================== D11: LAZY-LOADING FORCE TRIGGER ====================

class LazyLoadingForceTrigger:
    """
    D11: Force all lazy-loaded content to load immediately
    - Override IntersectionObserver → all entries visible
    - Remove loading="lazy" from img/iframe
    - Fake scroll events for infinite scroll
    """

    def __init__(self, page: Page):
        self.page = page

    async def execute(self) -> DOMAlgorithmResult:
        """Execute lazy-loading force trigger"""
        print("[D11] Lazy-Loading Force Trigger...")

        try:
            # Phase 1: Override IO + remove lazy attrs
            await self.page.evaluate("""
            (() => {
                window.__lazyStats = { triggered: 0, attrs_removed: 0 };

                const OrigIO = window.IntersectionObserver;
                window.IntersectionObserver = class extends OrigIO {
                    constructor(callback, options) {
                        super((entries, observer) => {
                            const forced = entries.map(e => {
                                try { return Object.assign({}, e, { isIntersecting: true, intersectionRatio: 1.0 }); }
                                catch (err) { return e; }
                            });
                            window.__lazyStats.triggered += forced.length;
                            callback(forced, observer);
                        }, options);
                    }
                };

                // Remove loading="lazy"
                for (const el of document.querySelectorAll('[loading="lazy"]')) {
                    el.removeAttribute('loading');
                    if (el.tagName === 'IMG' && el.dataset.src) el.src = el.dataset.src;
                    window.__lazyStats.attrs_removed++;
                }
                // Handle data-src patterns
                for (const el of document.querySelectorAll('[data-src]:not([src])')) {
                    el.src = el.dataset.src;
                    window.__lazyStats.attrs_removed++;
                }
            })()
            """)

            # Phase 2: Infinite scroll simulation
            scroll_results = await self.page.evaluate("""
            async () => {
                const result = { scroll_iterations: 0, content_before: document.querySelectorAll('a[href*="/@"]').length, content_after: 0, max_reached: false };
                const delay = ms => new Promise(r => setTimeout(r, ms));
                let lastHeight = document.body.scrollHeight, noChange = 0;

                for (let i = 0; i < 20; i++) {
                    window.scrollTo(0, document.body.scrollHeight);
                    window.dispatchEvent(new Event('scroll', { bubbles: true }));
                    await delay(800);
                    result.scroll_iterations++;

                    if (document.body.scrollHeight === lastHeight) {
                        if (++noChange >= 3) { result.max_reached = true; break; }
                    } else { noChange = 0; }
                    lastHeight = document.body.scrollHeight;
                }
                window.scrollTo(0, 0);
                result.content_after = document.querySelectorAll('a[href*="/@"]').length;
                return result;
            }
            """)

            # Phase 3: Collect users
            result = await self.page.evaluate("""
            (() => {
                const stats = window.__lazyStats || {};
                const result = { io_triggered: stats.triggered || 0, lazy_attrs_removed: stats.attrs_removed || 0, follow_data: [] };
                const seen = new Set();
                for (const link of document.querySelectorAll('a[href*="/@"]')) {
                    const username = link.getAttribute('href')?.split('/@')[1]?.split('?')[0]?.split('/')[0];
                    if (username && !seen.has(username)) { seen.add(username); result.follow_data.push({ username, source: 'lazy_force' }); }
                }
                delete window.__lazyStats;
                return result;
            })()
            """)

            result['scroll'] = scroll_results
            follow_count = len(result.get('follow_data', []))
            print(f"[D11] IO:{result.get('io_triggered',0)} lazy:{result.get('lazy_attrs_removed',0)} scrolls:{scroll_results.get('scroll_iterations',0)} users:{follow_count}")

            return DOMAlgorithmResult(algorithm="D11_LazyLoading", success=True, data=result, nodes_found=result.get('io_triggered', 0))

        except Exception as e:
            print(f"[D11] Error: {e}")
            return DOMAlgorithmResult(algorithm="D11_LazyLoading", success=False, error=str(e))


# ==================== D12: DOM FINGERPRINTING & ANTI-TAMPERING ====================

class DOMFingerprintDetector:
    """
    D12: Detect and bypass anti-tampering mechanisms
    - Detect periodic DOM monitoring (setInterval)
    - Patch monitoring callbacks
    - Detect integrity checks (nonce, CSP)
    """

    def __init__(self, page: Page):
        self.page = page

    async def execute(self) -> DOMAlgorithmResult:
        """Execute DOM fingerprint detection"""
        print("[D12] DOM Fingerprinting & Anti-Tampering...")

        try:
            result = await self.page.evaluate("""
            (() => {
                const result = { monitoring_detected: [], intervals_patched: 0, timeouts_patched: 0, integrity_checks: [], bypass_strategies: [], follow_data: [] };

                // Intercept setInterval to detect monitoring
                const origSI = window.setInterval;
                window.setInterval = function(cb, delay, ...args) {
                    const s = cb.toString().substring(0, 300);
                    const isMonitor = ['checksum','integrity','tamper','innerHTML','outerHTML','hash','fingerprint'].some(k => s.includes(k));
                    if (isMonitor) {
                        result.monitoring_detected.push({ type: 'setInterval', delay, preview: s.substring(0, 150) });
                        result.intervals_patched++;
                        return origSI.call(this, () => {}, delay);
                    }
                    return origSI.call(this, cb, delay, ...args);
                };

                // Intercept setTimeout
                const origST = window.setTimeout;
                window.setTimeout = function(cb, delay, ...args) {
                    const s = cb.toString().substring(0, 300);
                    const isCheck = ['integrity','tamper','checkDOM','validateDOM'].some(k => s.includes(k));
                    if (isCheck) {
                        result.timeouts_patched++;
                        result.monitoring_detected.push({ type: 'setTimeout', delay, preview: s.substring(0, 150) });
                        return origST.call(this, () => {}, delay);
                    }
                    return origST.call(this, cb, delay, ...args);
                };

                // Check script integrity
                for (const script of document.querySelectorAll('script[integrity], script[nonce]')) {
                    result.integrity_checks.push({ src: (script.src||'').substring(0,100), integrity: script.getAttribute('integrity')?.substring(0,80), nonce: script.getAttribute('nonce') ? '[present]' : null });
                }

                // CSP meta
                const cspMeta = document.querySelector('meta[http-equiv="Content-Security-Policy"]');
                if (cspMeta) result.integrity_checks.push({ type: 'CSP', content: cspMeta.getAttribute('content')?.substring(0,200) });

                // Strategies
                if (result.intervals_patched > 0) result.bypass_strategies.push('interval_neutralization');
                if (result.integrity_checks.length > 0) result.bypass_strategies.push('shadow_dom_manipulation');
                result.bypass_strategies.push('timing_window');

                // Extract users
                const seen = new Set();
                for (const link of document.querySelectorAll('a[href*="/@"]')) {
                    const u = link.getAttribute('href')?.split('/@')[1]?.split('?')[0]?.split('/')[0];
                    if (u && !seen.has(u)) { seen.add(u); result.follow_data.push({ username: u, source: 'anti_tamper_bypass' }); }
                }
                return result;
            })()
            """)

            monitors = len(result.get('monitoring_detected', []))
            patched = result.get('intervals_patched', 0) + result.get('timeouts_patched', 0)
            follow_count = len(result.get('follow_data', []))
            print(f"[D12] {monitors} monitors, {patched} patched, {len(result.get('integrity_checks',[]))} integrity, {follow_count} users")

            return DOMAlgorithmResult(algorithm="D12_DOMFingerprint", success=True, data=result, nodes_found=monitors)

        except Exception as e:
            print(f"[D12] Error: {e}")
            return DOMAlgorithmResult(algorithm="D12_DOMFingerprint", success=False, error=str(e))


# ==================== D13: JS CONTEXT ISOLATION BYPASS ====================

class JSContextIsolationBypass:
    """
    D13: Bypass JavaScript context isolation
    - Probe window.parent/top/opener
    - Cross-context postMessage / BroadcastChannel
    - SharedArrayBuffer / Atomics probing
    - Global variable scanning
    """

    def __init__(self, page: Page):
        self.page = page

    async def execute(self) -> DOMAlgorithmResult:
        """Execute JS context isolation bypass"""
        print("[D13] JS Context Isolation Bypass...")

        try:
            result = await self.page.evaluate("""
            (() => {
                const result = { contexts_found: [], cross_context_data: [], capabilities: {}, follow_data: [] };

                // Probe window references
                for (const [name, ref] of [['parent', window.parent], ['top', window.top], ['opener', window.opener]]) {
                    try {
                        if (ref && ref !== window) {
                            const info = { name, accessible: true, same_origin: false };
                            try {
                                info.url = ref.location.href?.substring(0, 100);
                                info.same_origin = true;
                                const links = ref.document?.querySelectorAll('a[href*="/@"]') || [];
                                for (const link of links) {
                                    const u = link.getAttribute('href')?.split('/@')[1]?.split('?')[0]?.split('/')[0];
                                    if (u) result.follow_data.push({ username: u, source: 'context_' + name });
                                }
                            } catch (e) {}
                            result.contexts_found.push(info);
                        }
                    } catch (e) {}
                }

                // Capabilities
                result.capabilities = {
                    shared_array_buffer: typeof SharedArrayBuffer !== 'undefined',
                    atomics: typeof Atomics !== 'undefined',
                    web_workers: typeof Worker !== 'undefined',
                    service_workers: 'serviceWorker' in navigator,
                    broadcast_channel: typeof BroadcastChannel !== 'undefined'
                };

                // BroadcastChannel sniffing
                if (result.capabilities.broadcast_channel) {
                    try {
                        for (const name of ['app', 'data', 'state', 'user', 'tiktok']) {
                            const bc = new BroadcastChannel(name);
                            bc.onmessage = (e) => { result.cross_context_data.push({ channel: name, preview: JSON.stringify(e.data).substring(0,200) }); };
                        }
                    } catch (e) {}
                }

                // Scan global variables for user data
                for (const key of Object.keys(window)) {
                    try {
                        if (['user','follow','state','store'].some(k => key.toLowerCase().includes(k))) {
                            const val = window[key];
                            if (val && typeof val === 'object' && !Array.isArray(val)) {
                                const str = JSON.stringify(val).substring(0, 100);
                                if (str.includes('uniqueId') || str.includes('username')) {
                                    result.cross_context_data.push({ type: 'global_var', key, preview: str });
                                }
                            }
                        }
                    } catch (e) {}
                }

                const seen = new Set();
                result.follow_data = result.follow_data.filter(u => { if (!u.username || seen.has(u.username)) return false; seen.add(u.username); return true; });
                return result;
            })()
            """)

            contexts = len(result.get('contexts_found', []))
            caps = sum(1 for v in result.get('capabilities', {}).values() if v)
            follow_count = len(result.get('follow_data', []))
            print(f"[D13] {contexts} contexts, {caps} capabilities, {len(result.get('cross_context_data',[]))} cross-data, {follow_count} users")

            return DOMAlgorithmResult(algorithm="D13_ContextIsolation", success=True, data=result, nodes_found=contexts)

        except Exception as e:
            print(f"[D13] Error: {e}")
            return DOMAlgorithmResult(algorithm="D13_ContextIsolation", success=False, error=str(e))


# ==================== D14: CSP BYPASS VIA INLINE HIJACKING ====================

class CSPBypassInlineHijack:
    """
    D14: Bypass Content Security Policy restrictions
    - Read and analyze CSP policy
    - Test injection via event handlers
    - TrustedTypes API usage
    - Nonce reuse detection
    """

    def __init__(self, page: Page):
        self.page = page

    async def execute(self) -> DOMAlgorithmResult:
        """Execute CSP bypass"""
        print("[D14] CSP Bypass via Inline Hijacking...")

        try:
            result = await self.page.evaluate("""
            (() => {
                const result = { csp_detected: false, csp_directives: {}, trusted_types: false, injection_methods: [], data_extracted: [], follow_data: [] };

                // Read CSP from meta
                const cspMeta = document.querySelector('meta[http-equiv="Content-Security-Policy"]');
                if (cspMeta) {
                    result.csp_detected = true;
                    const content = cspMeta.getAttribute('content') || '';
                    for (const dir of content.split(';').map(d => d.trim())) {
                        const parts = dir.split(/\\s+/);
                        if (parts.length > 0) result.csp_directives[parts[0]] = parts.slice(1);
                    }
                }

                // Check TrustedTypes
                try {
                    if (window.trustedTypes) {
                        result.trusted_types = true;
                        try {
                            window.trustedTypes.createPolicy('scraper', { createHTML: s => s, createScript: s => s, createScriptURL: s => s });
                            result.injection_methods.push({ method: 'trustedTypes_policy', success: true });
                        } catch (e) {
                            result.injection_methods.push({ method: 'trustedTypes_policy', success: false, error: e.message?.substring(0,100) });
                        }
                    }
                } catch (e) {}

                // Test event handler injection
                const testEl = document.createElement('div');
                testEl.style.display = 'none';
                document.body.appendChild(testEl);
                for (const h of ['onload', 'onerror', 'onmouseover', 'onfocus']) {
                    try { testEl.setAttribute(h, 'void(0)'); result.injection_methods.push({ method: 'handler_' + h, success: true }); }
                    catch (e) { result.injection_methods.push({ method: 'handler_' + h, success: false }); }
                }
                testEl.remove();

                // Analyze script-src
                const scriptSrc = result.csp_directives['script-src'] || [];
                result.data_extracted.push({
                    unsafe_inline: scriptSrc.includes("'unsafe-inline'"),
                    unsafe_eval: scriptSrc.includes("'unsafe-eval'"),
                    has_nonce: scriptSrc.some(s => s.startsWith("'nonce-")),
                    sources: scriptSrc.slice(0, 10)
                });

                // Find reusable nonces
                if (scriptSrc.some(s => s.startsWith("'nonce-"))) {
                    const s = document.querySelector('script[nonce]');
                    if (s) result.data_extracted.push({ found_nonce: s.getAttribute('nonce'), method: 'nonce_reuse' });
                }

                // Extract users
                const seen = new Set();
                for (const link of document.querySelectorAll('a[href*="/@"]')) {
                    const u = link.getAttribute('href')?.split('/@')[1]?.split('?')[0]?.split('/')[0];
                    if (u && !seen.has(u)) { seen.add(u); result.follow_data.push({ username: u, source: 'csp_bypass' }); }
                }
                return result;
            })()
            """)

            csp = "yes" if result.get('csp_detected') else "no"
            methods = len([m for m in result.get('injection_methods', []) if m.get('success')])
            follow_count = len(result.get('follow_data', []))
            print(f"[D14] CSP:{csp}, {methods} injection methods, {follow_count} users")

            return DOMAlgorithmResult(algorithm="D14_CSPBypass", success=True, data=result, nodes_found=methods)

        except Exception as e:
            print(f"[D14] Error: {e}")
            return DOMAlgorithmResult(algorithm="D14_CSPBypass", success=False, error=str(e))


# ==================== D15: SERVICE WORKER INTERCEPTION ====================

class ServiceWorkerInterceptor:
    """
    D15: Intercept and manipulate Service Workers
    - List registered SWs
    - Inspect Cache Storage for API responses
    - Extract cached user data
    - Intercept SW messages
    """

    def __init__(self, page: Page):
        self.page = page

    async def execute(self) -> DOMAlgorithmResult:
        """Execute Service Worker interception"""
        print("[D15] Service Worker Interception...")

        try:
            result = await self.page.evaluate("""
            async () => {
                const result = { sw_supported: 'serviceWorker' in navigator, registrations: [], caches_found: [], cached_responses: [], follow_data: [] };
                if (!result.sw_supported) return result;

                // List SW registrations
                try {
                    const regs = await navigator.serviceWorker.getRegistrations();
                    for (const reg of regs) {
                        result.registrations.push({ scope: reg.scope, active: !!reg.active, script_url: reg.active?.scriptURL?.substring(0,150) || null });
                    }
                } catch (e) {}

                // Inspect Cache Storage
                try {
                    const cacheNames = await caches.keys();
                    result.caches_found = cacheNames;

                    for (const name of cacheNames) {
                        try {
                            const cache = await caches.open(name);
                            const requests = await cache.keys();

                            for (const req of requests) {
                                const url = req.url;
                                if (url.includes('/api/') && ['follow','user','friend'].some(k => url.includes(k))) {
                                    try {
                                        const response = await cache.match(req);
                                        if (response) {
                                            const text = await response.text();
                                            result.cached_responses.push({ url: url.substring(0,200), cache_name: name, content_length: text.length });

                                            try {
                                                const data = JSON.parse(text);
                                                function findUsers(obj, path) {
                                                    if (!obj || typeof obj !== 'object') return;
                                                    if (Array.isArray(obj)) {
                                                        for (const item of obj) {
                                                            if (item?.uniqueId || item?.username) result.follow_data.push({ username: item.uniqueId || item.username, source: 'sw_cache_' + path });
                                                        }
                                                        return;
                                                    }
                                                    for (const [k, v] of Object.entries(obj)) {
                                                        if (['user','follow','list'].some(s => k.includes(s))) findUsers(v, k);
                                                    }
                                                }
                                                findUsers(data, '');
                                            } catch (e) {}
                                        }
                                    } catch (e) {}
                                }

                                // Check cached profile pages
                                if (url.includes('/@')) {
                                    try {
                                        const resp = await cache.match(req);
                                        const html = await resp?.text();
                                        if (html) {
                                            const matches = html.match(/\\/@([a-zA-Z0-9_.]+)/g) || [];
                                            for (const m of matches) {
                                                const u = m.replace('/@', '');
                                                if (u) result.follow_data.push({ username: u, source: 'sw_cached_page' });
                                            }
                                        }
                                    } catch (e) {}
                                }
                            }
                        } catch (e) {}
                    }
                } catch (e) {}

                // Intercept SW messages
                try {
                    if (navigator.serviceWorker.controller) {
                        navigator.serviceWorker.controller.postMessage({ type: 'INTERCEPT_MODE', action: 'log_api_calls' });
                    }
                } catch (e) {}

                // Deduplicate
                const seen = new Set();
                result.follow_data = result.follow_data.filter(u => { if (!u.username || seen.has(u.username)) return false; seen.add(u.username); return true; });
                return result;
            }
            """)

            regs = len(result.get('registrations', []))
            caches_count = len(result.get('caches_found', []))
            cached = len(result.get('cached_responses', []))
            follow_count = len(result.get('follow_data', []))
            print(f"[D15] {regs} SWs, {caches_count} caches, {cached} cached responses, {follow_count} users")

            return DOMAlgorithmResult(algorithm="D15_ServiceWorker", success=True, data=result, nodes_found=regs)

        except Exception as e:
            print(f"[D15] Error: {e}")
            return DOMAlgorithmResult(algorithm="D15_ServiceWorker", success=False, error=str(e))


# ==================== ORCHESTRATOR ====================

class DOMAlgorithmOrchestrator:
    """
    Run all D1-D15 algorithms and aggregate results
    """

    def __init__(self, page: Page):
        self.page = page
        self.algorithms = [
            ShadowDOMPenetrator(page),
            IFrameBridge(page),
            VirtualDOMReconstructor(page),
            DOMCloner(page),
            EventLoopInterceptor(page),
            MutationHistoryTracker(page),
            PseudoElementExtractor(page),
            CanvasWebGLCapture(page),
            SVGForeignObjectParser(page),
            WebComponentStateAccess(page),
            LazyLoadingForceTrigger(page),
            DOMFingerprintDetector(page),
            JSContextIsolationBypass(page),
            CSPBypassInlineHijack(page),
            ServiceWorkerInterceptor(page),
        ]

    async def run_all(self) -> Dict[str, Any]:
        """Run all algorithms sequentially"""
        print("\n[DOM] === Starting Advanced DOM Algorithms (D1-D15) ===")

        results = {}
        all_users = []

        for algo in self.algorithms:
            try:
                result = await algo.execute()
                results[result.algorithm] = result

                # Collect follow data
                follow_data = result.data.get('follow_data', [])
                all_users.extend(follow_data)

            except Exception as e:
                print(f"[DOM] Algorithm failed: {e}")

        # Deduplicate all collected users
        seen = set()
        unique_users = []
        for user in all_users:
            username = user.get('username', '')
            if username and username not in seen:
                seen.add(username)
                unique_users.append(user)

        # Summary
        print(f"\n[DOM] === Results Summary ===")
        for name, result in results.items():
            status = "✅" if result.success else "❌"
            users = len(result.data.get('follow_data', []))
            print(f"  {status} {name}: {result.nodes_found} nodes, {users} users")

        print(f"  📊 Total unique users: {len(unique_users)}")
        print(f"[DOM] === Complete ===\n")

        return {
            'algorithms': {k: v.data for k, v in results.items()},
            'users_extracted': unique_users,
            'total_unique_users': len(unique_users),
            'algorithms_succeeded': sum(1 for r in results.values() if r.success),
            'algorithms_total': len(results)
        }

    async def run_single(self, algorithm_name: str) -> DOMAlgorithmResult:
        """Run a single algorithm by name"""
        name_map = {
            'd1': 0, 'shadow': 0,
            'd2': 1, 'iframe': 1,
            'd3': 2, 'vdom': 2, 'virtual': 2,
            'd4': 3, 'clone': 3,
            'd5': 4, 'event': 4,
            'd6': 5, 'mutation': 5, 'history': 5,
            'd7': 6, 'pseudo': 6,
            'd8': 7, 'canvas': 7, 'webgl': 7,
            'd9': 8, 'svg': 8,
            'd10': 9, 'webcomponent': 9, 'wc': 9,
            'd11': 10, 'lazy': 10,
            'd12': 11, 'fingerprint': 11, 'tamper': 11,
            'd13': 12, 'context': 12, 'isolation': 12,
            'd14': 13, 'csp': 13,
            'd15': 14, 'sw': 14, 'serviceworker': 14,
        }

        idx = name_map.get(algorithm_name.lower())
        if idx is not None and idx < len(self.algorithms):
            return await self.algorithms[idx].execute()

        print(f"[DOM] Unknown algorithm: {algorithm_name}")
        return DOMAlgorithmResult(
            algorithm=algorithm_name,
            success=False,
            error=f"Unknown algorithm: {algorithm_name}"
        )

