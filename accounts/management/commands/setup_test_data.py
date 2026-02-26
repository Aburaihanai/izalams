import random
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from accounts.models import State, LGA, Ward, OrganizationUnit, Profile

User = get_user_model()

class Command(BaseCommand):
    help = "Deletes all users and creates fake hierarchical test data"

    def handle(self, *args, **kwargs):
        self.stdout.write("Cleaning database...")
        
        # 1. Delete all existing Users (This also deletes Profiles via CASCADE)
        # We keep the superuser to avoid locking ourselves out
        User.objects.filter(is_superuser=False).delete()
        
        self.stdout.write("Creating Hierarchy and Fake Users...")

        with transaction.atomic():
            # 2. Ensure at least one hierarchy exists
            state, _ = State.objects.get_or_create(name="Kaduna")
            lga, _ = LGA.objects.get_or_create(name="Kaduna North", state=state)
            ward, _ = Ward.objects.get_or_create(name="Unguwan Shanu", lga=lga)

            # 3. Ensure an Organization Unit exists for this Ward
            unit, _ = OrganizationUnit.objects.get_or_create(
                name="Unguwan Shanu Unit",
                category="FAG",
                level="WARD",
                ward=ward
            )

            # 4. Create a Test Leader
            leader = User.objects.create_user(
                username="leader_test",
                first_name="Ibrahim",
                last_name="Musa",
                email="leader@test.com",
                password="password123",
                is_staff=True # Leaders need staff access for your dashboard logic
            )
            Profile.objects.create(
                user=leader,
                unit=unit,
                position="Unit Commander",
                is_active=True
            )

            # 5. Create 10 Fake Members
            education_choices = ['graduate', 'undergraduate', 'secondary']
            courses = ['Islamic Studies', 'Computer Science', 'Arabic', 'Nursing']

            for i in range(1, 11):
                member = User.objects.create_user(
                    username=f"member_{i}",
                    first_name=f"User_{i}",
                    last_name="Test",
                    email=f"user{i}@test.com",
                    password="password123",
                    education_level=random.choice(education_choices),
                    course_of_study=random.choice(courses),
                    graduation_year=random.randint(2015, 2025),
                    is_graduated=True
                )
                
                # Create Profile (Pending Approval)
                Profile.objects.create(
                    user=member,
                    unit=unit,
                    position="Member",
                    is_active=False # This makes them show up in the leader's "Pending" list
                )

        self.stdout.write(self.style.SUCCESS(f"Successfully created 1 Leader and 10 Pending Members for {unit.name}"))