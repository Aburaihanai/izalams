import os
import django

# 1. Set the settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'izalams.settings')

# 2. Setup Django (ONLY HERE, NOT IN MODELS)
if not django.apps.apps.ready:
    django.setup()

# 3. Import models AFTER django.setup()
from accounts.models import OrganizationUnit, Profile, State, LGA
from django.contrib.auth import get_user_model

User = get_user_model()

def populate():
    print("--- Starting JIBWIS Structural Population ---")
    
    # Ensure Geography exists
    state, _ = State.objects.get_or_create(name="Kaduna")
    lga, _ = LGA.objects.get_or_create(state=state, name="Jos North")

    categories = [('ADMIN', 'Administration'), ('ULAMA', 'Council of Ulama'), ('FAG', 'First Aid Group')]
    levels = [('NATIONAL', 'National'), ('STATE', 'State'), ('LG', 'Local Government'), ('WARD', 'Ward/Unit')]

    for cat_code, cat_name in categories:
        for level_code, level_name in levels:
            # Create Unit
            unit, _ = OrganizationUnit.objects.get_or_create(
                name=f"{cat_name} {level_name} HQ",
                category=cat_code,
                level=level_code,
                state=state if level_code != 'NATIONAL' else None,
                lga=lga if level_code in ['LG', 'WARD'] else None
            )

            # Create Leader
            username = f"{level_code.lower()}_chair_{cat_code.lower()}"
            leader, created = User.objects.get_or_create(username=username)
            if created:
                leader.set_password('password123')
                leader.save()

            # Assign Profile
            Profile.objects.get_or_create(
                user=leader,
                unit=unit,
                position="Chairman",
                is_active=True
            )
            print(f"Created/Verified: {username}")

if __name__ == "__main__":
    populate()
    print("--- Done! ---")