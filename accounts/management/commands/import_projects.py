import pandas as pd
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Project, LecturerProfile

User = get_user_model()

class Command(BaseCommand):
    help = 'Imports projects with safety checks'

    def handle(self, *args, **kwargs):
        self.stdout.write("--- Starting Fresh Data Import ---")

        try:
            df = pd.read_excel('cs_projects_500_clean.xlsx')
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR("Error: File not found. Make sure cs_projects_500_clean.xlsx is in your project root folder."))
            return

        # Clear old data to avoid duplicates (only auto-generated ones)
        Project.objects.all().delete()
        User.objects.filter(username__startswith='lec_').delete()
        self.stdout.write("Old data cleared.")

        for index, row in df.iterrows():
            cat = row['category']
            clean_cat = cat.lower().replace(' ', '_')

            u_name = f"lec_{clean_cat}_{index}"
            s_num = f"STF-{index:04d}-{clean_cat[:3].upper()}"
            l_id = f"LID-{index:04d}-{clean_cat[:3].upper()}"

            user, _ = User.objects.get_or_create(
                username=u_name,
                defaults={'email': f"{u_name}@uni.edu"}
            )

            lec_prof, _ = LecturerProfile.objects.get_or_create(
                user=user,
                defaults={
                    'staff_number': s_num,
                    'lecturer_id': l_id,
                    'department': cat,
                    'area_of_expertise': cat,
                }
            )

            Project.objects.create(
                title=row['title'],
                description=row['description'],
                recommendations=row['recommendations'],
                category=cat,
                year=row['year'],
                status=row['status'],
                lecturer=lec_prof
            )

        self.stdout.write(self.style.SUCCESS(f"Done! Successfully imported {len(df)} projects."))