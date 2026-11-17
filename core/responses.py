from rest_framework.response import Response


def success_response(data=None, message=None, status=200):
    return Response({
        'success': True,
        'message': message,
        'data': data,
    }, status=status)


def error_response(message, code=400, details=None):
    return Response({
        'success': False,
        'error': {'code': code, 'message': message, 'details': details}
    }, status=code)