import logging
from typing import Optional, List, Dict
from datetime import datetime, timezone
from google.cloud.firestore_v1 import FieldFilter

from .client import get_firestore_client

logger = logging.getLogger(__name__)


class FirestoreService:
    COLLECTIONS = {
        'users': 'users',
        'tournaments': 'tournaments',
        'registrations': 'registrations',
        'matches': 'matches',
        'results': 'results',
        'leaderboards': 'leaderboards',
        'notifications': 'notifications',
        'complaints': 'complaints',
        'audit_logs': 'audit_logs',
        'result_uploads': 'result_uploads',
    }

    def __init__(self):
        self.db = get_firestore_client()

    def collection(self, name: str):
        if name not in self.COLLECTIONS:
            raise ValueError(f"Unknown collection: {name}")
        return self.db.collection(self.COLLECTIONS[name])

    def create(self, collection: str, data: Dict, doc_id: Optional[str] = None) -> str:
        data = self._add_timestamps(data, creating=True)
        if doc_id:
            self.collection(collection).document(doc_id).set(data)
            return doc_id
        ref = self.collection(collection).document()
        ref.set(data)
        return ref.id

    def get(self, collection: str, doc_id: str) -> Optional[Dict]:
        doc = self.collection(collection).document(doc_id).get()
        if not doc.exists:
            return None
        d = doc.to_dict()
        d['id'] = doc.id
        return d

    def update(self, collection: str, doc_id: str, data: Dict) -> None:
        data = self._add_timestamps(data, updating=True)
        self.collection(collection).document(doc_id).update(data)

    def delete(self, collection: str, doc_id: str) -> None:
        self.collection(collection).document(doc_id).delete()

    def query(self, collection: str, filters: List = None, order_by: str = None,
              direction: str = 'DESCENDING', limit: int = None, offset: int = None):
        q = self.collection(collection)
        if filters:
            for f in filters:
                q = q.where(filter=f)
        if order_by:
            from google.cloud.firestore_v1 import Query
            d = Query.DESCENDING if direction == 'DESCENDING' else Query.ASCENDING
            q = q.order_by(order_by, direction=d)
        if offset:
            q = q.offset(offset)
        if limit:
            q = q.limit(limit)
        return q

    def find_one(self, collection: str, **kwargs) -> Optional[Dict]:
        filters = [FieldFilter(k, '==', v) for k, v in kwargs.items()]
        docs = self.query(collection, filters=filters, limit=1).stream()
        for doc in docs:
            d = doc.to_dict()
            d['id'] = doc.id
            return d
        return None

    def find_many(self, collection: str, filters: List = None,
                  order_by: str = None, direction: str = 'DESCENDING',
                  limit: int = None, offset: int = None) -> List[Dict]:
        docs = self.query(collection, filters, order_by, direction, limit, offset).stream()
        result = []
        for doc in docs:
            d = doc.to_dict()
            d['id'] = doc.id
            result.append(d)
        return result

    def count(self, collection: str, filters: List = None) -> int:
        q = self.collection(collection)
        if filters:
            for f in filters:
                q = q.where(filter=f)
        return len(list(q.stream()))

    @staticmethod
    def _add_timestamps(data: Dict, creating=False, updating=False) -> Dict:
        now = datetime.now(timezone.utc)
        data = dict(data)
        if creating:
            data.setdefault('createdAt', now)
            data['updatedAt'] = now
        elif updating:
            data['updatedAt'] = now
        return data