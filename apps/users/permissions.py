from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """
    Allow access if:
    - Django superuser
    - Django staff
    - User with admin roles (SUPER_ADMIN, ADMIN, MODERATOR, etc.)
    """

    message = 'Admin access required'

    ADMIN_ROLES = {
        'SUPER_ADMIN',
        'ADMIN',
        'MODERATOR',
        'RESULT_MANAGER',
        'SUPPORT',
    }

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Django superuser
        if request.user.is_superuser:
            return True

        # Django staff
        if request.user.is_staff:
            return True

        # Custom role check
        user_role = getattr(request.user, 'role', '')
        return user_role in self.ADMIN_ROLES