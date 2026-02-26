import json
import os
from django.core.management.base import BaseCommand
from accounts.models import State, LGA
from django.conf import settings

class Command(BaseCommand):
    help = 'Imports States and LGAs from the nigeria_data.json fixture'

    def handle(self, *args, **kwargs):
        # Path to your fixture file
        fixture_path = os.path.join(settings.BASE_DIR, 'accounts', 'fixtures', 'nigeria_data.json')

        try:
            with open(fixture_path, 'r') as f:
                data = json.load(f)

            for entry in data:
                # Create or get the State
                state_obj, created = State.objects.get_or_create(
                    name=entry['name']
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f'Created State: {state_obj.name}'))

                # Create LGAs for this state
                for lga_name in entry['lgas']:
                    lga_obj, created = LGA.objects.get_or_create(
                        state=state_obj,
                        name=lga_name
                    )
            
            self.stdout.write(self.style.SUCCESS('Successfully imported all States and LGAs!'))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'File not found at {fixture_path}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An error occurred: {str(e)}'))