class ApprovalRequired(Exception):
    """Raised when an account-changing action needs explicit approval."""

def require_approval(action: str) -> bool:
    from .config import settings
    if settings.dry_run:
        return False
    if not settings.approval_required:
        return True
    answer = input(f"Approve LinkedIn action '{action}'? [y/N]: ").strip().lower()
    if answer != "y":
        raise ApprovalRequired(f"Action not approved: {action}")
    return True
