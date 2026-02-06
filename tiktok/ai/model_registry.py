"""
Model Registry and Versioning Module for TikTok AI
Model version control, A/B testing, rollback mechanism
"""

import json
import hashlib
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ==================== DATA CLASSES ====================

class ModelStatus(Enum):
    DRAFT = "draft"
    TESTING = "testing"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


@dataclass
class ModelVersion:
    """Single model version"""
    model_name: str
    version: str
    path: str
    status: ModelStatus = ModelStatus.DRAFT
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str = "system"
    description: str = ""
    
    # Performance metrics
    metrics: Dict[str, float] = field(default_factory=dict)
    
    # Checksums
    file_hash: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "model_name": self.model_name,
            "version": self.version,
            "path": self.path,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "description": self.description,
            "metrics": self.metrics,
            "file_hash": self.file_hash
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ModelVersion':
        return cls(
            model_name=data["model_name"],
            version=data["version"],
            path=data["path"],
            status=ModelStatus(data.get("status", "draft")),
            created_at=datetime.fromisoformat(data["created_at"]),
            created_by=data.get("created_by", "system"),
            description=data.get("description", ""),
            metrics=data.get("metrics", {}),
            file_hash=data.get("file_hash", "")
        )


@dataclass
class ABTestConfig:
    """A/B test configuration"""
    name: str
    model_a: str  # version
    model_b: str  # version
    traffic_split: float = 0.5  # Fraction going to model_b
    
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    # Results
    samples_a: int = 0
    samples_b: int = 0
    metrics_a: Dict[str, float] = field(default_factory=dict)
    metrics_b: Dict[str, float] = field(default_factory=dict)
    
    is_active: bool = True


@dataclass
class RollbackEvent:
    """Model rollback event"""
    model_name: str
    from_version: str
    to_version: str
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)
    performed_by: str = "system"


# ==================== MODEL REGISTRY ====================

class ModelRegistry:
    """
    Central registry for model versions
    """
    
    def __init__(self, registry_path: str = "./model_registry"):
        self.registry_path = Path(registry_path)
        self.registry_path.mkdir(parents=True, exist_ok=True)
        
        self.models: Dict[str, Dict[str, ModelVersion]] = {}
        self.production_versions: Dict[str, str] = {}
        
        self._load_registry()
    
    def _load_registry(self):
        """Load registry from disk"""
        registry_file = self.registry_path / "registry.json"
        
        if registry_file.exists():
            with open(registry_file, 'r') as f:
                data = json.load(f)
            
            for model_name, versions in data.get("models", {}).items():
                self.models[model_name] = {
                    v["version"]: ModelVersion.from_dict(v)
                    for v in versions
                }
            
            self.production_versions = data.get("production_versions", {})
    
    def _save_registry(self):
        """Save registry to disk"""
        registry_file = self.registry_path / "registry.json"
        
        data = {
            "models": {
                name: [v.to_dict() for v in versions.values()]
                for name, versions in self.models.items()
            },
            "production_versions": self.production_versions
        }
        
        with open(registry_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def register(
        self,
        model_name: str,
        version: str,
        model_path: str,
        description: str = "",
        metrics: Dict[str, float] = None
    ) -> ModelVersion:
        """Register a new model version"""
        # Calculate file hash
        file_hash = self._compute_hash(model_path)
        
        # Create version
        model_version = ModelVersion(
            model_name=model_name,
            version=version,
            path=model_path,
            description=description,
            metrics=metrics or {},
            file_hash=file_hash
        )
        
        # Store
        if model_name not in self.models:
            self.models[model_name] = {}
        
        self.models[model_name][version] = model_version
        
        # Copy to registry storage
        target_path = self.registry_path / model_name / version
        target_path.mkdir(parents=True, exist_ok=True)
        
        if Path(model_path).exists():
            shutil.copy2(model_path, target_path / Path(model_path).name)
        
        self._save_registry()
        print(f"[REGISTRY] Registered {model_name} v{version}")
        
        return model_version
    
    def get_version(self, model_name: str, version: str) -> Optional[ModelVersion]:
        """Get specific model version"""
        return self.models.get(model_name, {}).get(version)
    
    def get_production(self, model_name: str) -> Optional[ModelVersion]:
        """Get production version"""
        prod_version = self.production_versions.get(model_name)
        if prod_version:
            return self.get_version(model_name, prod_version)
        return None
    
    def get_latest(self, model_name: str) -> Optional[ModelVersion]:
        """Get latest version"""
        versions = self.models.get(model_name, {})
        if not versions:
            return None
        
        # Sort by version (semantic versioning)
        sorted_versions = sorted(
            versions.values(),
            key=lambda v: tuple(map(int, v.version.split('.'))),
            reverse=True
        )
        
        return sorted_versions[0] if sorted_versions else None
    
    def list_versions(self, model_name: str) -> List[ModelVersion]:
        """List all versions of a model"""
        return list(self.models.get(model_name, {}).values())
    
    def promote_to_production(self, model_name: str, version: str) -> bool:
        """Promote version to production"""
        model = self.get_version(model_name, version)
        if not model:
            print(f"[REGISTRY] Version {version} not found")
            return False
        
        # Demote current production
        old_prod = self.production_versions.get(model_name)
        if old_prod and old_prod != version:
            old_model = self.get_version(model_name, old_prod)
            if old_model:
                old_model.status = ModelStatus.DEPRECATED
        
        # Promote new version
        model.status = ModelStatus.PRODUCTION
        self.production_versions[model_name] = version
        
        self._save_registry()
        print(f"[REGISTRY] Promoted {model_name} v{version} to production")
        
        return True
    
    def _compute_hash(self, file_path: str) -> str:
        """Compute file hash"""
        if not Path(file_path).exists():
            return ""
        
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()


# ==================== A/B TESTING ====================

class ABTestManager:
    """
    Manage A/B tests between model versions
    """
    
    def __init__(self, registry: ModelRegistry):
        self.registry = registry
        self.tests: Dict[str, ABTestConfig] = {}
    
    def create_test(
        self,
        name: str,
        model_name: str,
        version_a: str,
        version_b: str,
        traffic_split: float = 0.5
    ) -> ABTestConfig:
        """Create new A/B test"""
        test = ABTestConfig(
            name=name,
            model_a=version_a,
            model_b=version_b,
            traffic_split=traffic_split
        )
        
        self.tests[name] = test
        print(f"[A/B TEST] Created test '{name}': {version_a} vs {version_b}")
        
        return test
    
    def get_model_for_request(self, test_name: str) -> str:
        """Get which model to use for a request"""
        test = self.tests.get(test_name)
        if not test or not test.is_active:
            return None
        
        import random
        if random.random() < test.traffic_split:
            test.samples_b += 1
            return test.model_b
        else:
            test.samples_a += 1
            return test.model_a
    
    def record_outcome(
        self,
        test_name: str,
        version: str,
        metric_name: str,
        value: float
    ):
        """Record outcome for a test"""
        test = self.tests.get(test_name)
        if not test:
            return
        
        if version == test.model_a:
            if metric_name not in test.metrics_a:
                test.metrics_a[metric_name] = []
            test.metrics_a[metric_name] = (
                test.metrics_a.get(metric_name, 0) * (test.samples_a - 1) + value
            ) / test.samples_a
        else:
            if metric_name not in test.metrics_b:
                test.metrics_b[metric_name] = []
            test.metrics_b[metric_name] = (
                test.metrics_b.get(metric_name, 0) * (test.samples_b - 1) + value
            ) / test.samples_b
    
    def get_results(self, test_name: str) -> Dict[str, Any]:
        """Get A/B test results"""
        test = self.tests.get(test_name)
        if not test:
            return {}
        
        return {
            "name": test.name,
            "model_a": test.model_a,
            "model_b": test.model_b,
            "samples_a": test.samples_a,
            "samples_b": test.samples_b,
            "metrics_a": test.metrics_a,
            "metrics_b": test.metrics_b,
            "is_active": test.is_active,
            "winner": self._determine_winner(test)
        }
    
    def _determine_winner(self, test: ABTestConfig) -> Optional[str]:
        """Determine test winner"""
        if test.samples_a < 100 or test.samples_b < 100:
            return None  # Not enough samples
        
        # Compare primary metric (accuracy)
        acc_a = test.metrics_a.get("accuracy", 0)
        acc_b = test.metrics_b.get("accuracy", 0)
        
        if abs(acc_a - acc_b) < 0.01:
            return "tie"
        return test.model_a if acc_a > acc_b else test.model_b
    
    def end_test(self, test_name: str, auto_promote: bool = False) -> Dict[str, Any]:
        """End A/B test"""
        test = self.tests.get(test_name)
        if not test:
            return {}
        
        test.is_active = False
        test.end_time = datetime.now()
        
        results = self.get_results(test_name)
        
        if auto_promote and results.get("winner"):
            winner = results["winner"]
            if winner not in ["tie", None]:
                # Promote winner to production
                model_name = test_name.split("_")[0]  # Assuming test name format
                self.registry.promote_to_production(model_name, winner)
        
        return results


# ==================== ROLLBACK MANAGER ====================

class RollbackManager:
    """
    Manage model rollbacks
    """
    
    def __init__(self, registry: ModelRegistry):
        self.registry = registry
        self.history: List[RollbackEvent] = []
    
    def rollback(
        self,
        model_name: str,
        to_version: Optional[str] = None,
        reason: str = "Manual rollback"
    ) -> bool:
        """Rollback model to previous version"""
        current = self.registry.get_production(model_name)
        if not current:
            print(f"[ROLLBACK] No production version for {model_name}")
            return False
        
        # Get target version
        if to_version:
            target = self.registry.get_version(model_name, to_version)
        else:
            # Get previous production version
            versions = self.registry.list_versions(model_name)
            sorted_versions = sorted(
                versions,
                key=lambda v: tuple(map(int, v.version.split('.'))),
                reverse=True
            )
            
            if len(sorted_versions) < 2:
                print(f"[ROLLBACK] No previous version available")
                return False
            
            target = sorted_versions[1]
        
        if not target:
            print(f"[ROLLBACK] Target version not found")
            return False
        
        # Perform rollback
        event = RollbackEvent(
            model_name=model_name,
            from_version=current.version,
            to_version=target.version,
            reason=reason
        )
        
        self.registry.promote_to_production(model_name, target.version)
        self.history.append(event)
        
        print(f"[ROLLBACK] Rolled back {model_name} from {current.version} to {target.version}")
        
        return True
    
    def auto_rollback_on_error(
        self,
        model_name: str,
        error_rate: float,
        threshold: float = 0.1
    ) -> bool:
        """Automatically rollback if error rate exceeds threshold"""
        if error_rate > threshold:
            return self.rollback(
                model_name,
                reason=f"Auto-rollback due to error rate {error_rate:.2%} > {threshold:.2%}"
            )
        return False
    
    def get_history(self, model_name: Optional[str] = None) -> List[RollbackEvent]:
        """Get rollback history"""
        if model_name:
            return [e for e in self.history if e.model_name == model_name]
        return self.history


# ==================== AUTO UPDATE SYSTEM ====================

class AutoUpdateSystem:
    """
    System for automatic model updates
    """
    
    def __init__(self, registry: ModelRegistry, ab_manager: ABTestManager):
        self.registry = registry
        self.ab_manager = ab_manager
        self.update_policies: Dict[str, Dict] = {}
    
    def set_update_policy(
        self,
        model_name: str,
        min_improvement: float = 0.05,
        min_samples: int = 1000,
        auto_promote: bool = False
    ):
        """Set update policy for a model"""
        self.update_policies[model_name] = {
            "min_improvement": min_improvement,
            "min_samples": min_samples,
            "auto_promote": auto_promote
        }
    
    def check_for_updates(self, model_name: str) -> Optional[str]:
        """Check if new version should be promoted"""
        policy = self.update_policies.get(model_name)
        if not policy:
            return None
        
        current = self.registry.get_production(model_name)
        latest = self.registry.get_latest(model_name)
        
        if not current or not latest:
            return None
        
        if current.version == latest.version:
            return None  # Already on latest
        
        # Compare metrics
        current_acc = current.metrics.get("accuracy", 0)
        latest_acc = latest.metrics.get("accuracy", 0)
        
        improvement = latest_acc - current_acc
        
        if improvement >= policy["min_improvement"]:
            if policy["auto_promote"]:
                self.registry.promote_to_production(model_name, latest.version)
                return latest.version
            else:
                # Create A/B test
                test_name = f"{model_name}_update_{latest.version}"
                self.ab_manager.create_test(
                    test_name,
                    model_name,
                    current.version,
                    latest.version
                )
                return None
        
        return None
