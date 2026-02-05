"""
TikTok DOM Maintenance Phase
Monitor and re-apply modifications when TikTok resets them
"""
import asyncio
import json
from typing import Dict, List, Optional, Callable
from playwright.async_api import Page
import time

from .selectors import PRIVACY_GATE_SELECTORS, FOLLOW_ITEM_SELECTORS, PRIVACY_FLAGS
from .async_utils import safe_evaluate, TaskManager, IntervalRunner


class TikTokMaintenance:
    """
    Maintain DOM modifications and monitor for resets
    
    Features:
    - State change monitoring
    - Mutation observation
    - Anti-detection monitoring
    - Auto re-injection
    """
    
    def __init__(
        self, 
        page: Page, 
        injection_results: List[Dict],
        check_interval: float = 5.0,
        max_history: int = 100
    ):
        self.page = page
        self.injection_results = injection_results
        self.check_interval = check_interval
        self.max_history = max_history
        
        self.monitoring = False
        self.modifications_applied = 0
        self.state_resets_detected = 0
        self.reinjections = 0
        self.start_time = time.time()
        
        # Task management
        self._task_manager = TaskManager()
        self._interval_runner = IntervalRunner(check_interval)
        
        # Callbacks for different events
        self.on_state_reset: Optional[Callable] = None
        self.on_new_content: Optional[Callable] = None
        self.on_detection: Optional[Callable] = None
        
    async def start_maintenance(self):
        """Start maintenance monitoring"""
        print("[MAINTENANCE] Starting maintenance phase...")
        self.monitoring = True
        self.start_time = time.time()
        
        # Setup all monitoring systems
        await self._setup_state_monitoring()
        await self._setup_mutation_monitoring()
        await self._setup_detection_monitoring()
        await self._setup_performance_monitoring()
        
        print("[MAINTENANCE] Maintenance systems active")
        
        # Start monitoring loop with task manager
        self._task_manager.add_task(self._monitoring_loop())
    
    async def _setup_state_monitoring(self):
        """Setup state change monitoring"""
        print("[MAINTENANCE] Setting up state monitoring...")
        
        state_monitor_script = """
        (() => {
            window._tiktokStateChanges = [];
            let lastStateSnapshot = null;
            
            // Function to take state snapshot
            function takeStateSnapshot() {
                const snapshot = {};
                
                // Check various state locations
                const targets = [
                    '__REDUX_STORE__',
                    '__VUE__',
                    '__META_DATA__',
                    '_tiktok'
                ];
                
                targets.forEach(target => {
                    if (window[target]) {
                        try {
                            snapshot[target] = JSON.stringify(window[target]).length;
                        } catch (e) {
                            snapshot[target] = 'error';
                        }
                    }
                });
                
                // Check privacy flags
                const privacyFlags = [
                    'privateAccount',
                    'isPrivate',
                    'followingVisibility',
                    'followerStatus'
                ];
                
                privacyFlags.forEach(flag => {
                    snapshot[flag] = window[flag];
                });
                
                return snapshot;
            }
            
            // Initial snapshot
            lastStateSnapshot = takeStateSnapshot();
            
            // Monitor for state changes
            setInterval(() => {
                const currentSnapshot = takeStateSnapshot();
                let changed = false;
                
                // Compare with last snapshot
                Object.keys(currentSnapshot).forEach(key => {
                    if (currentSnapshot[key] !== lastStateSnapshot[key]) {
                        changed = true;
                        window._tiktokStateChanges.push({
                            timestamp: Date.now(),
                            key: key,
                            old: lastStateSnapshot[key],
                            new: currentSnapshot[key],
                            type: 'state_change'
                        });
                    }
                });
                
                if (changed) {
                    lastStateSnapshot = currentSnapshot;
                    
                    // Dispatch event
                    document.dispatchEvent(new CustomEvent('tiktokStateChanged', {
                        detail: { changes: window._tiktokStateChanges.slice(-5) }
                    }));
                }
            }, 1000);
            
            return 'State monitoring active';
        })()
        """
        
        await self.page.evaluate(state_monitor_script)
        
        # Listen for state change events
        await self.page.expose_function("onStateReset", self._handle_state_reset)
    
    async def _setup_mutation_monitoring(self):
        """Setup DOM mutation monitoring"""
        print("[MAINTENANCE] Setting up DOM mutation monitoring...")
        
        mutation_script = """
        (() => {
            window._tiktokMutations = [];
            
            // Track follow-related elements
            const followSelectors = [
                '[class*="follow"]',
                '[data-e2e*="follow"]',
                '[class*="Follow"]',
                '[class*="Follower"]',
                '[class*="Following"]'
            ].join(', ');
            
            const observer = new MutationObserver((mutations) => {
                mutations.forEach(mutation => {
                    // Check for added nodes
                    if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                        mutation.addedNodes.forEach(node => {
                            if (node.nodeType === 1) { // Element node
                                // Check if it's follow-related
                                if (node.matches?.(followSelectors) || 
                                    node.querySelector?.(followSelectors)) {
                                    
                                    window._tiktokMutations.push({
                                        timestamp: Date.now(),
                                        type: 'element_added',
                                        tag: node.tagName,
                                        classes: node.className,
                                        hasFollowData: node.textContent?.includes('@') || false
                                    });
                                    
                                    // Dispatch event for new content
                                    document.dispatchEvent(new CustomEvent('tiktokNewContent', {
                                        detail: { element: node.outerHTML.substring(0, 200) }
                                    }));
                                }
                            }
                        });
                    }
                    
                    // Check for attribute changes (especially display/hidden)
                    if (mutation.type === 'attributes') {
                        const attrName = mutation.attributeName;
                        if (attrName === 'style' || attrName === 'class') {
                            const target = mutation.target;
                            if (target.matches?.(followSelectors)) {
                                const computedStyle = window.getComputedStyle(target);
                                const isHidden = computedStyle.display === 'none' || 
                                                computedStyle.visibility === 'hidden';
                                
                                if (isHidden) {
                                    window._tiktokMutations.push({
                                        timestamp: Date.now(),
                                        type: 'element_hidden',
                                        tag: target.tagName,
                                        reason: 'style_change'
                                    });
                                }
                            }
                        }
                    }
                });
            });
            
            // Start observing
            observer.observe(document.body, {
                childList: true,
                subtree: true,
                attributes: true,
                attributeFilter: ['style', 'class', 'data-e2e']
            });
            
            return 'Mutation monitoring active';
        })()
        """
        
        await self.page.evaluate(mutation_script)
    
    async def _setup_detection_monitoring(self):
        """Setup anti-detection monitoring"""
        print("[MAINTENANCE] Setting up detection monitoring...")
        
        detection_script = """
        (() => {
            window._tiktokDetections = [];
            
            // Monitor for TikTok's anti-bot measures
            const detectionSignals = [
                // Network request patterns
                'fetch',
                'XMLHttpRequest',
                'WebSocket',
                
                // DOM manipulation detection
                'MutationObserver',
                'ResizeObserver',
                'IntersectionObserver',
                
                // Performance monitoring
                'performance.mark',
                'performance.measure',
                
                // Error tracking
                'window.onerror',
                'console.error'
            ];
            
            // Store original methods
            detectionSignals.forEach(signal => {
                if (window[signal]) {
                    const original = window[signal];
                    window[`_original${signal}`] = original;
                    
                    // Wrap to monitor usage
                    window[signal] = function(...args) {
                        window._tiktokDetections.push({
                            timestamp: Date.now(),
                            signal: signal,
                            args: args.slice(0, 2) // Limit argument logging
                        });
                        
                        return original.apply(this, args);
                    };
                    
                    // Copy static properties
                    Object.keys(original).forEach(key => {
                        window[signal][key] = original[key];
                    });
                }
            });
            
            // Monitor for error events
            window.addEventListener('error', (event) => {
                if (event.message?.includes('tiktok') || 
                    event.filename?.includes('tiktok')) {
                    window._tiktokDetections.push({
                        timestamp: Date.now(),
                        type: 'error',
                        message: event.message,
                        filename: event.filename
                    });
                }
            });
            
            // Monitor console for warnings
            const originalWarn = console.warn;
            console.warn = function(...args) {
                const message = args.join(' ');
                if (message.includes('tiktok') || 
                    message.includes('private') ||
                    message.includes('follow')) {
                    window._tiktokDetections.push({
                        timestamp: Date.now(),
                        type: 'console_warn',
                        message: message
                    });
                }
                return originalWarn.apply(this, args);
            };
            
            return 'Detection monitoring active';
        })()
        """
        
        await self.page.evaluate(detection_script)
    
    async def _setup_performance_monitoring(self):
        """Setup performance and timing monitoring"""
        print("[MAINTENANCE] Setting up performance monitoring...")
        
        performance_script = """
        (() => {
            window._tiktokPerformance = {
                render_times: [],
                data_load_times: [],
                interaction_delays: []
            };
            
            // Measure render times
            const originalRequestAnimationFrame = window.requestAnimationFrame;
            window.requestAnimationFrame = function(callback) {
                const start = performance.now();
                
                return originalRequestAnimationFrame(function(...args) {
                    const end = performance.now();
                    window._tiktokPerformance.render_times.push(end - start);
                    
                    // Keep only last 100 measurements
                    if (window._tiktokPerformance.render_times.length > 100) {
                        window._tiktokPerformance.render_times.shift();
                    }
                    
                    return callback.apply(this, args);
                });
            };
            
            // Measure data load times
            const originalFetch = window.fetch;
            window.fetch = async function(...args) {
                const start = performance.now();
                const url = args[0]?.url || args[0];
                
                const response = await originalFetch.apply(this, args);
                const end = performance.now();
                
                if (url && (url.includes('follow') || url.includes('user'))) {
                    window._tiktokPerformance.data_load_times.push({
                        url: url,
                        time: end - start,
                        timestamp: Date.now()
                    });
                }
                
                return response;
            };
            
            return 'Performance monitoring active';
        })()
        """
        
        await self.page.evaluate(performance_script)
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        check_interval = 5  # seconds
        
        while self.monitoring:
            try:
                # Check for state resets
                await self._check_state_resets()
                
                # Check for hidden elements
                await self._check_hidden_elements()
                
                # Check for detection signals
                await self._check_detection_signals()
                
                # Re-apply modifications if needed
                await self._reapply_modifications()
                
                # Clean up traces
                await self._cleanup_traces()
                
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                print(f"[MAINTENANCE] Error in monitoring loop: {e}")
                await asyncio.sleep(check_interval)
    
    async def _check_state_resets(self):
        """Check if TikTok has reset our modifications"""
        check_script = """
        (() => {
            const issues = [];
            
            // Check if privacy flags are back to private
            const privacyFlags = [
                'privateAccount',
                'isPrivate',
                'followingVisibility',
                'followerStatus'
            ];
            
            privacyFlags.forEach(flag => {
                if (window[flag] === true || window[flag] === 1) {
                    issues.push({
                        type: 'privacy_flag_reset',
                        flag: flag,
                        value: window[flag]
                    });
                }
            });
            
            // Check if our CSS is still applied
            const overrideStyle = document.getElementById('tiktok-private-override');
            if (!overrideStyle || overrideStyle.disabled) {
                issues.push({
                    type: 'css_override_removed',
                    style_exists: !!overrideStyle,
                    style_disabled: overrideStyle?.disabled || false
                });
            }
            
            // Check if follow data is visible
            const followElements = document.querySelectorAll([
                '[class*="follow-item"]',
                '[data-e2e*="follow"]'
            ].join(','));
            
            const hiddenCount = Array.from(followElements).filter(el => {
                const style = window.getComputedStyle(el);
                return style.display === 'none' || style.visibility === 'hidden';
            }).length;
            
            if (hiddenCount > 0 && followElements.length > 0) {
                issues.push({
                    type: 'elements_hidden',
                    total: followElements.length,
                    hidden: hiddenCount,
                    percentage: (hiddenCount / followElements.length * 100).toFixed(1) + '%'
                });
            }
            
            return issues;
        })()
        """
        
        issues = await self.page.evaluate(check_script)
        
        if issues:
            self.state_resets_detected += len(issues)
            print(f"[MAINTENANCE] Detected {len(issues)} state reset(s)")
            
            if self.on_state_reset:
                await self.on_state_reset(issues)
    
    async def _check_hidden_elements(self):
        """Check for elements that should be visible but are hidden"""
        check_script = """
        (() => {
            const hiddenElements = [];
            
            // Elements that should show follow data
            const followSelectors = [
                '[class*="follow-list"]',
                '[data-e2e*="follow-list"]',
                '[class*="FollowingList"]',
                '[class*="FollowerList"]'
            ].join(', ');
            
            const elements = document.querySelectorAll(followSelectors);
            
            elements.forEach(el => {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                
                const isProblematic = 
                    style.display === 'none' ||
                    style.visibility === 'hidden' ||
                    style.opacity === '0' ||
                    rect.height === 0 ||
                    rect.width === 0;
                
                if (isProblematic) {
                    hiddenElements.push({
                        selector: followSelectors,
                        display: style.display,
                        visibility: style.visibility,
                        opacity: style.opacity,
                        dimensions: { width: rect.width, height: rect.height }
                    });
                }
            });
            
            return hiddenElements;
        })()
        """
        
        hidden_elements = await self.page.evaluate(check_script)
        
        if hidden_elements and self.on_new_content:
            await self.on_new_content(hidden_elements)
    
    async def _check_detection_signals(self):
        """Check for TikTok detection signals"""
        check_script = """
        (() => {
            const signals = window._tiktokDetections || [];
            const recentSignals = signals.filter(s => 
                Date.now() - s.timestamp < 30000 // Last 30 seconds
            );
            
            // Check for patterns indicating detection
            const detectionPatterns = recentSignals.filter(s => 
                s.signal?.includes('error') ||
                s.message?.includes('security') ||
                s.message?.includes('blocked') ||
                s.message?.includes('suspicious')
            );
            
            return {
                total_signals: signals.length,
                recent_signals: recentSignals.length,
                detection_patterns: detectionPatterns.length,
                sample: detectionPatterns.slice(0, 3)
            };
        })()
        """
        
        detection_info = await self.page.evaluate(check_script)
        
        if detection_info['detection_patterns'] > 0:
            print(f"[MAINTENANCE] Detection patterns detected: {detection_info['detection_patterns']}")
            
            if self.on_detection:
                await self.on_detection(detection_info)
    
    async def _reapply_modifications(self):
        """Re-apply modifications if they've been reset"""
        reapply_script = """
        (() => {
            const actions = [];
            
            // Re-apply CSS if missing
            if (!document.getElementById('tiktok-private-override')) {
                const style = document.createElement('style');
                style.id = 'tiktok-private-override';
                style.textContent = `
                    [class*="PrivateAccount"],
                    [class*="private-account"],
                    [data-e2e*="private"] {
                        display: block !important;
                        visibility: visible !important;
                    }
                `;
                document.head.appendChild(style);
                actions.push('css_reapplied');
            }
            
            // Reset privacy flags
            const privacyFlags = [
                'privateAccount',
                'isPrivate',
                'followingVisibility',
                'followerStatus'
            ];
            
            privacyFlags.forEach(flag => {
                if (window[flag] !== undefined && window[flag] !== false && window[flag] !== 0) {
                    window[flag] = false;
                    actions.push(`${flag}_reset`);
                }
            });
            
            // Trigger re-render if possible
            if (window.__REDUX_STORE__) {
                try {
                    window.__REDUX_STORE__.dispatch({ type: 'USER/REFRESH' });
                    actions.push('redux_refresh_dispatched');
                } catch (e) {}
            }
            
            return actions;
        })()
        """
        
        actions = await self.page.evaluate(reapply_script)
        
        if actions:
            self.reinjections += 1
            self.modifications_applied += len(actions)
            print(f"[MAINTENANCE] Re-applied modifications: {actions}")
    
    async def _cleanup_traces(self):
        """Clean up monitoring traces to avoid detection"""
        cleanup_script = """
        (() => {
            const actions = [];
            
            // Clean up old monitoring data
            const monitors = [
                '_tiktokStateChanges',
                '_tiktokMutations',
                '_tiktokDetections',
                '_tiktokPerformance'
            ];
            
            monitors.forEach(monitor => {
                if (window[monitor] && Array.isArray(window[monitor])) {
                    // Keep only last 100 entries
                    if (window[monitor].length > 100) {
                        window[monitor] = window[monitor].slice(-100);
                        actions.push(`${monitor}_trimmed`);
                    }
                }
            });
            
            // Remove old error events
            if (window._tiktokDetections) {
                const thirtySecondsAgo = Date.now() - 30000;
                window._tiktokDetections = window._tiktokDetections.filter(
                    d => d.timestamp > thirtySecondsAgo
                );
            }
            
            return actions;
        })()
        """
        
        await self.page.evaluate(cleanup_script)
    
    async def _handle_state_reset(self, issues):
        """Handle state reset events"""
        print(f"[MAINTENANCE] Handling state reset: {len(issues)} issues")
        
        # Log issues
        for issue in issues:
            print(f"  - {issue['type']}: {issue.get('value', issue.get('percentage', 'N/A'))}")
        
        # Re-inject based on issue type
        if any('privacy_flag_reset' in issue['type'] for issue in issues):
            await self._reinject_state()
        
        if any('css_override_removed' in issue['type'] for issue in issues):
            await self._reinject_css()
    
    async def _reinject_state(self):
        """Re-inject state modifications"""
        print("[MAINTENANCE] Re-injecting state modifications...")
        
        script = """
        (() => {
            // Reset all privacy flags
            const flags = ['privateAccount', 'isPrivate', 'followingVisibility', 'followerStatus'];
            flags.forEach(flag => {
                if (window[flag] !== undefined) {
                    window[flag] = false;
                }
            });
            
            // Trigger state update
            if (window.__REDUX_STORE__) {
                window.__REDUX_STORE__.dispatch({
                    type: 'USER/UPDATE_PRIVACY',
                    payload: { privateAccount: false }
                });
            }
            
            return 'State re-injected';
        })()
        """
        
        await self.page.evaluate(script)
    
    async def _reinject_css(self):
        """Re-inject CSS modifications"""
        print("[MAINTENANCE] Re-injecting CSS modifications...")
        
        script = """
        (() => {
            // Remove old style if exists
            const oldStyle = document.getElementById('tiktok-private-override');
            if (oldStyle) oldStyle.remove();
            
            // Add new style
            const style = document.createElement('style');
            style.id = 'tiktok-private-override-2';
            
            style.textContent = `
                /* More aggressive override */
                [class*="Private"],
                [class*="private"],
                [data-e2e*="private"],
                [aria-label*="private"] {
                    display: block !important;
                    visibility: visible !important;
                    opacity: 1 !important;
                    position: relative !important;
                    z-index: 1000 !important;
                }
                
                /* Ensure follow lists are visible */
                div:has([class*="follow"]),
                section:has([data-e2e*="follow"]) {
                    display: block !important;
                }
            `;
            
            document.head.appendChild(style);
            return 'CSS re-injected';
        })()
        """
        
        await self.page.evaluate(script)
    
    async def stop_maintenance(self):
        """Stop all maintenance activities"""
        print("[MAINTENANCE] Stopping maintenance...")
        self.monitoring = False
        
        # Clean up everything
        cleanup_script = """
        (() => {
            // Remove our styles
            const styles = [
                'tiktok-private-override',
                'tiktok-private-override-2'
            ];
            
            styles.forEach(id => {
                const style = document.getElementById(id);
                if (style) style.remove();
            });
            
            // Restore original methods
            const methods = [
                'fetch',
                'requestAnimationFrame',
                'addEventListener',
                'dispatchEvent'
            ];
            
            methods.forEach(method => {
                if (window[`_original${method}`]) {
                    window[method] = window[`_original${method}`];
                    delete window[`_original${method}`];
                }
            });
            
            // Clear monitoring data
            const monitors = [
                '_tiktokStateChanges',
                '_tiktokMutations',
                '_tiktokDetections',
                '_tiktokPerformance'
            ];
            
            monitors.forEach(monitor => {
                delete window[monitor];
            });
            
            return 'Maintenance cleaned up';
        })()
        """
        
        await self.page.evaluate(cleanup_script)
        print("[MAINTENANCE] Maintenance stopped and cleaned up")
    
    def get_maintenance_report(self) -> Dict:
        """Generate maintenance phase report"""
        return {
            "timestamp": time.time(),
            "monitoring_active": self.monitoring,
            "statistics": {
                "modifications_applied": self.modifications_applied,
                "state_resets_detected": self.state_resets_detected,
                "reinjections_performed": self.reinjections,
                "total_monitoring_time": time.time() - getattr(self, 'start_time', time.time())
            }
        }