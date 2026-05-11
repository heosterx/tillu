"""
Import Safety Wrapper
Safely imports optional packages with fallback handling
"""
from typing import Optional, Any, Callable
from app.utils.logging import get_logger

logger = get_logger("import_safety")


def safe_import(
    module_name: str,
    package_name: Optional[str] = None,
    fallback: Optional[Any] = None,
    raise_error: bool = False
) -> Any:
    """
    Safely import a module with fallback handling
    
    Args:
        module_name: Full module path (e.g., 'langchain_groq.ChatGroq')
        package_name: Package name for error messages (e.g., 'langchain-groq')
        fallback: Value to return if import fails
        raise_error: Whether to raise error or return fallback
        
    Returns:
        Imported module/class or fallback value
    """
    try:
        parts = module_name.rsplit('.', 1)
        if len(parts) == 2:
            module_path, class_name = parts
            module = __import__(module_path, fromlist=[class_name])
            return getattr(module, class_name)
        else:
            return __import__(module_name)
    except (ImportError, AttributeError) as e:
        pkg = package_name or module_name
        msg = f"Failed to import {module_name} from {pkg}: {str(e)}"
        
        if raise_error:
            logger.error(msg)
            raise RuntimeError(msg)
        else:
            logger.warning(msg)
            return fallback


def safe_import_class(
    module_path: str,
    class_name: str,
    package_name: Optional[str] = None,
    fallback: Optional[Any] = None,
    raise_error: bool = False
) -> Any:
    """
    Safely import a class from a module
    
    Args:
        module_path: Module path (e.g., 'langchain_groq')
        class_name: Class name (e.g., 'ChatGroq')
        package_name: Package name for error messages
        fallback: Value to return if import fails
        raise_error: Whether to raise error or return fallback
        
    Returns:
        Imported class or fallback value
    """
    return safe_import(
        f"{module_path}.{class_name}",
        package_name=package_name,
        fallback=fallback,
        raise_error=raise_error
    )


def check_package_available(package_name: str) -> bool:
    """Check if a package is available"""
    import importlib.util
    spec = importlib.util.find_spec(package_name)
    return spec is not None


def get_available_llm_providers() -> dict[str, bool]:
    """Get availability of all LLM providers (free tier only)"""
    return {
        "groq": check_package_available("langchain_groq"),
        "cerebras": check_package_available("langchain_cerebras"),
        "together": check_package_available("together"),
        "google": check_package_available("langchain_google_genai"),
    }


def validate_at_least_one_provider() -> bool:
    """Validate that at least one LLM provider is available"""
    available = get_available_llm_providers()
    has_provider = any(available.values())
    
    if not has_provider:
        logger.error("No LLM providers available. Please install at least one: langchain-groq, langchain-cerebras, together, etc.")
        return False
    
    available_list = [k for k, v in available.items() if v]
    logger.info(f"Available LLM providers: {', '.join(available_list)}")
    return True
