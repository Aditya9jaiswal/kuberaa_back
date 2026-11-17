# C:\Kuberaa\backend\test\delete_14.py
"""
SIRF #14 DELETE KARO
=====================
- Purana #14 tournament delete karega
- Uske saare registrations, matches, results bhi delete honge
"""

import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kuberaa.settings')
django.setup()

from apps.tournaments.models import Tournament


def main():
    print("\n" + "=" * 60)
    print("PURANA #14 DELETE")
    print("=" * 60)

    # ✅ Purana #14 dhundo
    old = Tournament.objects.filter(serial_number=14).first()

    if not old:
        print("\n⏭️  #14 nahi mila — kuch delete karne ki zarurat nahi")
        return

    print(f"\n🔍 Found:")
    print(f"   Title: {old.title}")
    print(f"   Display ID: #{old.display_id}")
    print(f"   ID: {old.id}")
    print(f"   Entry Fee: ₹{old.entry_fee}")
    print(f"   Status: {old.status}")
    print(f"   Created: {old.created_at}")

    # ✅ Confirm
    confirm = input("\n⚠️  Delete? (yes/no): ").strip().lower()

    if confirm != 'yes':
        print("❌ Cancel kar diya")
        return

    # ✅ Delete
    try:
        old.delete()
        print(f"\n✅ #14 delete ho gaya!")
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == '__main__':
    main()
    