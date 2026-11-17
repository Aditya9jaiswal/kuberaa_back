from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from core.responses import success_response, error_response
from .models import Complaint
from .serializers import ComplaintSerializer


class ComplaintListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Complaint.objects.filter(user=request.user)
        return success_response(data=ComplaintSerializer(qs, many=True).data)

    def post(self, request):
        serializer = ComplaintSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response('Validation failed', 400, serializer.errors)
        serializer.save(user=request.user)
        return success_response(data=serializer.data, message='Complaint submitted', status=201)


class ComplaintDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            c = Complaint.objects.get(id=pk, user=request.user)
        except Complaint.DoesNotExist:
            return error_response('Not found', 404)
        return success_response(data=ComplaintSerializer(c).data)