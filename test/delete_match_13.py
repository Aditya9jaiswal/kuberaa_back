"""
Match #13 delete karne ke liye standalone script.
Database + Firebase Storage dono clean karega.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kuberaa.settings')
django.setup()

import firebase_admin
from firebase_admin import storage as fb_storage
from apps.tournaments.models import Tournament


def delete_firebase_folder(prefix):
    """Firebase Storage se folder delete karo."""
    try:
        bucket = fb_storage.bucket()
        blobs = list(bucket.list_blobs(prefix=prefix))

        if not blobs:
            return 0

        count = 0
        for blob in blobs:
            try:
                blob.delete()
                print(f"   🗑️  {blob.name}")
                count += 1
            except Exception as e:
                print(f"   ❌ {blob.name}: {e}")

        return count
    except Exception as e:
        print(f"   ❌ Firebase error: {e}")
        return 0


def main():
    print("=" * 60)
    print("DELETE MATCH #13 — DB + FIREBASE")
    print("=" * 60)

    # ✅ Find tournament
    old = Tournament.objects.filter(serial_number=13).first()

    if not old:
        print("⏭️  #13 not found")
        return

    print(f"\n🔍 Found: #{old.display_id} — {old.title}")
    print(f"   ID: {old.id}")
    print(f"   Created: {old.created_at}")

    # ✅ Confirm
    confirm = input(f"\n⚠️  Delete karna hai? (yes/no): ")

    if confirm.lower() != 'yes':
        print("❌ Cancel")
        return

    # ✅ Firebase cleanup
    print(f"\n🔥 Firebase Storage cleanup...")
    paths = [
        f"tournaments/{old.id}/",
        f"tournaments/{old.display_id}/",
        f"registrations/tournament_{old.id}/",
        f"payments/tournament_{old.id}/",
        f"screenshots/tournament_{old.id}/",
        f"results/tournament_{old.id}/",
        f"matches/tournament_{old.id}/",
    ]

    total = 0
    for path in paths:
        count = delete_firebase_folder(path)
        total += count

    print(f"\n   Total Firebase files deleted: {total}")

    # ✅ Database delete
    print(f"\n🗄️  Database delete...")
    old.delete()
    print(f"   ✅ Done")

    print("\n" + "=" * 60)
    print("✅ COMPLETE")
    print("=" * 60)


if __name__ == '__main__':
    main()