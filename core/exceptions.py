from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        response.data = {
            'success': False,
            'error': {
                'code': response.status_code,
                'message': _extract_message(response.data),
                'details': response.data if isinstance(response.data, dict) else None,
            }
        }
    else:
        logger.exception(f"Unhandled exception: {exc}")
        response = Response(
            {'success': False, 'error': {'code': 500, 'message': 'Internal server error'}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    return response


def _extract_message(data):
    if isinstance(data, dict):
        if 'detail' in data:
            return str(data['detail'])
        for key, value in data.items():
            if isinstance(value, list) and value:
                return f"{key}: {value[0]}"
            return f"{key}: {value}"
    elif isinstance(data, list):
        return str(data[0]) if data else 'Error'
    return str(data)