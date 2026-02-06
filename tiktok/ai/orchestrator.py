"""
Workflow Orchestration Module for TikTok AI
Manage dependencies, execute parallel analyses, aggregate results
"""

import asyncio
from typing import List, Dict, Optional, Any, Callable, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import traceback


# ==================== DATA CLASSES ====================

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowStep:
    """Single step in workflow"""
    name: str
    handler: Callable
    dependencies: List[str] = field(default_factory=list)
    timeout: float = 60.0
    required: bool = True
    
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class WorkflowResult:
    """Complete workflow execution result"""
    workflow_name: str
    status: TaskStatus
    results: Dict[str, Any] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)
    total_duration_ms: float = 0.0
    step_durations: Dict[str, float] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        total = len(self.results) + len(self.errors)
        return len(self.results) / total if total > 0 else 0


@dataclass 
class ProgressReport:
    """Progress report for long-running workflows"""
    workflow_name: str
    total_steps: int
    completed_steps: int
    current_step: Optional[str] = None
    percent_complete: float = 0.0
    estimated_remaining_seconds: float = 0.0


# ==================== WORKFLOW ORCHESTRATOR ====================

class WorkflowOrchestrator:
    """
    Orchestrate complex AI analysis workflows
    Handles parallel execution and dependencies
    """
    
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self.workflows: Dict[str, List[WorkflowStep]] = {}
        self._running_workflows: Dict[str, asyncio.Task] = {}
        self._progress: Dict[str, ProgressReport] = {}
    
    def define_workflow(
        self,
        name: str,
        steps: List[WorkflowStep]
    ) -> 'WorkflowOrchestrator':
        """Define a new workflow"""
        self.workflows[name] = steps
        return self
    
    async def execute(
        self,
        workflow_name: str,
        input_data: Any,
        on_progress: Optional[Callable[[ProgressReport], None]] = None
    ) -> WorkflowResult:
        """Execute a workflow"""
        if workflow_name not in self.workflows:
            return WorkflowResult(
                workflow_name=workflow_name,
                status=TaskStatus.FAILED,
                errors={"workflow": f"Unknown workflow: {workflow_name}"}
            )
        
        steps = self.workflows[workflow_name]
        start_time = datetime.now()
        
        # Reset step states
        for step in steps:
            step.status = TaskStatus.PENDING
            step.result = None
            step.error = None
        
        # Initialize progress
        progress = ProgressReport(
            workflow_name=workflow_name,
            total_steps=len(steps),
            completed_steps=0
        )
        self._progress[workflow_name] = progress
        
        # Build dependency graph
        completed: Set[str] = set()
        results = {}
        errors = {}
        step_durations = {}
        
        while True:
            # Find steps that can run
            ready = [
                step for step in steps
                if step.status == TaskStatus.PENDING
                and all(dep in completed for dep in step.dependencies)
            ]
            
            if not ready:
                # Check if stuck
                pending = [s for s in steps if s.status == TaskStatus.PENDING]
                if pending:
                    # Check for missing dependencies
                    for step in pending:
                        missing = [d for d in step.dependencies if d not in completed]
                        if missing and any(steps_dict[m].status == TaskStatus.FAILED 
                                          for m in missing if m in (steps_dict := {s.name: s for s in steps})):
                            step.status = TaskStatus.CANCELLED
                            step.error = f"Dependency failed: {missing}"
                            errors[step.name] = step.error
                break
            
            # Execute ready steps in parallel
            semaphore = asyncio.Semaphore(self.max_concurrent)
            
            async def run_step(step: WorkflowStep):
                async with semaphore:
                    step.status = TaskStatus.RUNNING
                    progress.current_step = step.name
                    
                    if on_progress:
                        on_progress(progress)
                    
                    step_start = datetime.now()
                    
                    try:
                        # Gather dependency results
                        dep_results = {
                            dep: results.get(dep) 
                            for dep in step.dependencies
                        }
                        
                        # Run with timeout
                        result = await asyncio.wait_for(
                            step.handler(input_data, dep_results),
                            timeout=step.timeout
                        )
                        
                        step.result = result
                        step.status = TaskStatus.COMPLETED
                        results[step.name] = result
                        
                    except asyncio.TimeoutError:
                        step.status = TaskStatus.FAILED
                        step.error = f"Timeout after {step.timeout}s"
                        if step.required:
                            errors[step.name] = step.error
                            
                    except Exception as e:
                        step.status = TaskStatus.FAILED
                        step.error = str(e)
                        if step.required:
                            errors[step.name] = step.error
                    
                    finally:
                        step.duration_ms = (datetime.now() - step_start).total_seconds() * 1000
                        step_durations[step.name] = step.duration_ms
                        completed.add(step.name)
                        progress.completed_steps = len(completed)
                        progress.percent_complete = len(completed) / len(steps) * 100
            
            # Run all ready steps
            await asyncio.gather(*[run_step(step) for step in ready])
        
        # Determine overall status
        if errors:
            status = TaskStatus.FAILED
        elif all(s.status == TaskStatus.COMPLETED for s in steps):
            status = TaskStatus.COMPLETED
        else:
            status = TaskStatus.COMPLETED  # Partial success
        
        total_duration = (datetime.now() - start_time).total_seconds() * 1000
        
        return WorkflowResult(
            workflow_name=workflow_name,
            status=status,
            results=results,
            errors=errors,
            total_duration_ms=total_duration,
            step_durations=step_durations
        )
    
    async def cancel(self, workflow_name: str) -> bool:
        """Cancel running workflow"""
        if workflow_name in self._running_workflows:
            self._running_workflows[workflow_name].cancel()
            return True
        return False
    
    def get_progress(self, workflow_name: str) -> Optional[ProgressReport]:
        """Get workflow progress"""
        return self._progress.get(workflow_name)


# ==================== STANDARD WORKFLOWS ====================

class StandardWorkflows:
    """
    Pre-defined standard AI workflows
    """
    
    @staticmethod
    def create_full_analysis_workflow() -> List[WorkflowStep]:
        """Full content analysis workflow"""
        return [
            # Phase 1: Parallel extraction
            WorkflowStep(
                name="preprocess",
                handler=StandardWorkflows._preprocess,
                timeout=30.0
            ),
            
            # Phase 2: Parallel AI analysis (depends on preprocess)
            WorkflowStep(
                name="vision",
                handler=StandardWorkflows._vision_analysis,
                dependencies=["preprocess"],
                timeout=60.0,
                required=False
            ),
            WorkflowStep(
                name="nlp",
                handler=StandardWorkflows._nlp_analysis,
                dependencies=["preprocess"],
                timeout=30.0
            ),
            WorkflowStep(
                name="audio",
                handler=StandardWorkflows._audio_analysis,
                dependencies=["preprocess"],
                timeout=30.0,
                required=False
            ),
            
            # Phase 3: Fusion (depends on Phase 2)
            WorkflowStep(
                name="fusion",
                handler=StandardWorkflows._multimodal_fusion,
                dependencies=["vision", "nlp", "audio"],
                timeout=15.0
            ),
            
            # Phase 4: Final analysis (depends on fusion)
            WorkflowStep(
                name="virality",
                handler=StandardWorkflows._virality_prediction,
                dependencies=["fusion"],
                timeout=15.0
            ),
            WorkflowStep(
                name="anomaly",
                handler=StandardWorkflows._anomaly_detection,
                dependencies=["fusion"],
                timeout=15.0
            ),
        ]
    
    @staticmethod
    def create_quick_analysis_workflow() -> List[WorkflowStep]:
        """Quick analysis (NLP + anomaly only)"""
        return [
            WorkflowStep(
                name="nlp",
                handler=StandardWorkflows._nlp_analysis,
                timeout=30.0
            ),
            WorkflowStep(
                name="anomaly",
                handler=StandardWorkflows._anomaly_detection,
                dependencies=["nlp"],
                timeout=15.0
            ),
        ]
    
    # Step handlers
    @staticmethod
    async def _preprocess(input_data: Any, deps: Dict) -> Dict:
        """Preprocessing step"""
        return {"preprocessed": True, "data": input_data}
    
    @staticmethod
    async def _vision_analysis(input_data: Any, deps: Dict) -> Dict:
        """Vision analysis step"""
        await asyncio.sleep(0.1)  # Simulated processing
        return {"vision": "completed", "objects": [], "faces": 0}
    
    @staticmethod
    async def _nlp_analysis(input_data: Any, deps: Dict) -> Dict:
        """NLP analysis step"""
        await asyncio.sleep(0.1)
        return {"nlp": "completed", "sentiment": 0.5, "topics": []}
    
    @staticmethod
    async def _audio_analysis(input_data: Any, deps: Dict) -> Dict:
        """Audio analysis step"""
        await asyncio.sleep(0.1)
        return {"audio": "completed", "transcript": ""}
    
    @staticmethod
    async def _multimodal_fusion(input_data: Any, deps: Dict) -> Dict:
        """Multimodal fusion step"""
        return {
            "fusion": "completed",
            "vision": deps.get("vision", {}),
            "nlp": deps.get("nlp", {}),
            "audio": deps.get("audio", {})
        }
    
    @staticmethod
    async def _virality_prediction(input_data: Any, deps: Dict) -> Dict:
        """Virality prediction step"""
        return {"probability": 0.5, "tier": "medium"}
    
    @staticmethod
    async def _anomaly_detection(input_data: Any, deps: Dict) -> Dict:
        """Anomaly detection step"""
        return {"bot_probability": 0.1, "spam_score": 0.05}


# ==================== PRIORITY QUEUE ====================

@dataclass
class PriorityTask:
    """Task with priority"""
    priority: int  # Lower = higher priority
    task_id: str
    handler: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    
    def __lt__(self, other):
        return self.priority < other.priority


class PriorityQueue:
    """
    Priority queue for task scheduling
    """
    
    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self._queue: List[PriorityTask] = []
        self._running = 0
        self._results: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
    
    async def add(
        self,
        task_id: str,
        handler: Callable,
        priority: int = 5,
        *args,
        **kwargs
    ):
        """Add task to queue"""
        async with self._lock:
            task = PriorityTask(
                priority=priority,
                task_id=task_id,
                handler=handler,
                args=args,
                kwargs=kwargs
            )
            self._queue.append(task)
            self._queue.sort()  # Maintain priority order
    
    async def process_next(self) -> Optional[Tuple[str, Any]]:
        """Process next task in queue"""
        async with self._lock:
            if not self._queue or self._running >= self.max_concurrent:
                return None
            
            task = self._queue.pop(0)
            self._running += 1
        
        try:
            if asyncio.iscoroutinefunction(task.handler):
                result = await task.handler(*task.args, **task.kwargs)
            else:
                result = task.handler(*task.args, **task.kwargs)
            
            self._results[task.task_id] = result
            return (task.task_id, result)
            
        finally:
            async with self._lock:
                self._running -= 1
    
    async def process_all(self) -> Dict[str, Any]:
        """Process all tasks in queue"""
        while self._queue:
            tasks = []
            for _ in range(min(self.max_concurrent, len(self._queue))):
                task_coro = self.process_next()
                if task_coro:
                    tasks.append(task_coro)
            
            if tasks:
                await asyncio.gather(*tasks)
        
        return self._results.copy()
    
    def get_result(self, task_id: str) -> Optional[Any]:
        """Get result for task"""
        return self._results.get(task_id)
    
    @property
    def pending_count(self) -> int:
        return len(self._queue)


# ==================== RESULT AGGREGATOR ====================

class ResultAggregator:
    """
    Aggregate results from multiple analyses
    """
    
    @staticmethod
    def combine(results: Dict[str, Any]) -> Dict[str, Any]:
        """Combine results into unified format"""
        combined = {
            "timestamp": datetime.now().isoformat(),
            "components": list(results.keys()),
            "data": {}
        }
        
        # Vision results
        if "vision" in results:
            combined["data"]["vision"] = {
                "objects": results["vision"].get("objects", []),
                "faces": results["vision"].get("faces", 0),
                "scenes": results["vision"].get("scenes", [])
            }
        
        # NLP results
        if "nlp" in results:
            combined["data"]["nlp"] = {
                "sentiment": results["nlp"].get("sentiment", 0),
                "topics": results["nlp"].get("topics", []),
                "hashtags": results["nlp"].get("hashtags", [])
            }
        
        # Virality
        if "virality" in results:
            combined["data"]["virality"] = results["virality"]
        
        # Anomaly
        if "anomaly" in results:
            combined["data"]["anomaly"] = results["anomaly"]
        
        return combined
    
    @staticmethod
    def summarize(combined: Dict[str, Any]) -> str:
        """Generate human-readable summary"""
        data = combined.get("data", {})
        
        lines = ["=== AI Analysis Summary ==="]
        
        if "vision" in data:
            v = data["vision"]
            lines.append(f"Vision: {v.get('faces', 0)} faces, {len(v.get('objects', []))} objects")
        
        if "nlp" in data:
            n = data["nlp"]
            sentiment = n.get("sentiment", 0)
            sentiment_label = "positive" if sentiment > 0.2 else "negative" if sentiment < -0.2 else "neutral"
            lines.append(f"NLP: {sentiment_label} sentiment ({sentiment:.2f})")
        
        if "virality" in data:
            v = data["virality"]
            lines.append(f"Virality: {v.get('tier', 'unknown')} ({v.get('probability', 0):.1%} probability)")
        
        if "anomaly" in data:
            a = data["anomaly"]
            lines.append(f"Anomaly: {a.get('bot_probability', 0):.1%} bot probability")
        
        return "\n".join(lines)
