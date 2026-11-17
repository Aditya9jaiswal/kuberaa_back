import os
import json
import logging
from functools import lru_cache

import firebase_admin
from firebase_admin import credentials, firestore, storage, messaging
from django.conf import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _initialize_firebase():
    if firebase_admin._apps:
        return firebase_admin.get_app()

    cred = None

    if getattr(settings, 'FIREBASE_CREDENTIALS_JSON', None):
        cred_dict = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
        cred = credentials.Certificate(cred_dict)
    elif settings.FIREBASE_CREDENTIALS_PATH and os.path.exists(settings.FIREBASE_CREDENTIALS_PATH):
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
    else:
        raise RuntimeError(
            "Firebase credentials not found. "
            "Place firebase-service-account.json in backend/ folder."
        )

    options = {}
    if settings.FIREBASE_STORAGE_BUCKET:
        options['storageBucket'] = settings.FIREBASE_STORAGE_BUCKET

    app = firebase_admin.initialize_app(cred, options)
    logger.info("Firebase initialized")
    return app


def get_firestore_client():
    _initialize_firebase()
    return firestore.client()


def get_storage_bucket():
    _initialize_firebase()
    return storage.bucket()


def get_messaging():
    _initialize_firebase()
    return messaging