from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    message = 'Admin access required'

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and getattr(request.user, 'is_admin_role', False)
        )


class IsSuperAdmin(BasePermission):
    message = 'Super admin access required'

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and getattr(request.user, 'is_super_admin', False)
        )


class IsResultManager(BasePermission):
    message = 'Result manager access required'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.role in ['SUPER_ADMIN', 'ADMIN', 'RESULT_MANAGER']


class IsModerator(BasePermission):
    message = 'Moderator access required'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.role in ['SUPER_ADMIN', 'ADMIN', 'MODERATOR']