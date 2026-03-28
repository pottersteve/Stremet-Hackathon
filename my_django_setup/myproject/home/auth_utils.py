"""Safe access to UserProfile (reverse OneToOne can raise DoesNotExist, not AttributeError)."""

from .models import UserProfile


def get_profile_role(user):
    """Return profile.role or None if no profile row exists."""
    try:
        return user.profile.role
    except UserProfile.DoesNotExist:
        return None


def ensure_user_profile(user):
    """
    Create a UserProfile on first use. Superusers and Django staff default to admin
    (portal administrators); everyone else defaults to customer.
    Does not change role if the profile already exists.
    """
    default_admin = user.is_superuser or user.is_staff
    UserProfile.objects.get_or_create(
        user=user,
        defaults={"role": "admin" if default_admin else "customer"},
    )
