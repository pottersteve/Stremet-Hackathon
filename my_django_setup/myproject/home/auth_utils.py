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
    Create a UserProfile on first use. Superusers default to admin; everyone else to customer.
    Does not change role if the profile already exists.
    """
    UserProfile.objects.get_or_create(
        user=user,
        defaults={'role': 'admin' if user.is_superuser else 'customer'},
    )
