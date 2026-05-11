"""
Provider Availability Checker
Validates that all configured LLM providers and their packages are available
"""
import importlib.util
from typing import Dict, List, Tuple
from app.config import settings
from app.utils.logging import get_logger

logger = get_logger("provider_check")


class ProviderChecker:
    """Check availability of LLM providers and their packages"""
    
    PROVIDER_PACKAGES = {
        "groq": "langchain_groq",
        "cerebras": "langchain_cerebras",
        "together": "together",
        "openrouter": "httpx",
        "google": "langchain_google_genai",
    }
    
    @staticmethod
    def is_package_available(package_name: str) -> bool:
        """Check if a package is installed"""
        spec = importlib.util.find_spec(package_name)
        return spec is not None
    
    @staticmethod
    def get_available_providers() -> Dict[str, bool]:
        """Get availability status of all configured providers"""
        providers = {}
        
        # Check Groq
        if settings.groq_api_key:
            providers["groq"] = ProviderChecker.is_package_available("langchain_groq")
        
        # Check Cerebras
        if settings.cerebras_api_key:
            providers["cerebras"] = ProviderChecker.is_package_available("langchain_cerebras")
        
        # Check Together AI
        if settings.together_api_key:
            providers["together"] = ProviderChecker.is_package_available("together")
        
        # Check OpenRouter
        if settings.openrouter_api_key:
            providers["openrouter"] = ProviderChecker.is_package_available("httpx")
        
        # Check Google
        if settings.google_api_key:
            providers["google"] = ProviderChecker.is_package_available("langchain_google_genai")
        
        return providers
    
    @staticmethod
    def validate_providers() -> Tuple[bool, List[str]]:
        """
        Validate that at least one provider is available
        Returns: (is_valid, list_of_issues)
        """
        available = ProviderChecker.get_available_providers()
        issues = []
        
        if not available:
            issues.append("No LLM providers configured")
            return False, issues
        
        unavailable = {k: v for k, v in available.items() if not v}
        
        if unavailable:
            for provider, _ in unavailable.items():
                package = ProviderChecker.PROVIDER_PACKAGES.get(provider)
                issues.append(f"Provider '{provider}' configured but package '{package}' not installed")
        
        # Check if at least one provider is available
        available_providers = [k for k, v in available.items() if v]
        
        if not available_providers:
            issues.append("No LLM providers are available. Please install at least one: langchain-groq, langchain-cerebras, together, etc.")
            return False, issues
        
        logger.info(f"Available LLM providers: {', '.join(available_providers)}")
        return True, issues
    
    @staticmethod
    def log_provider_status():
        """Log the status of all providers"""
        available = ProviderChecker.get_available_providers()
        
        if not available:
            logger.warning("No LLM providers configured")
            return
        
        for provider, is_available in available.items():
            status = "✅ Available" if is_available else "❌ Not Available"
            logger.info(f"Provider '{provider}': {status}")


def check_providers_on_startup():
    """Check providers at application startup"""
    is_valid, issues = ProviderChecker.validate_providers()
    
    if issues:
        for issue in issues:
            logger.warning(issue)
    
    if not is_valid:
        logger.error("Provider validation failed - application may not work correctly")
        raise RuntimeError("No LLM providers available. Please configure at least one provider.")
    
    ProviderChecker.log_provider_status()
