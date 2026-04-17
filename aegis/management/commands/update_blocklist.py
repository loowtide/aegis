from django.core.management.base import BaseCommand

from ...models import BlockedIP


class Command(BaseCommand):
    help = "Update blocklist"

    def handle(self, *args, **kwargs):
        count = 0
        for ip in BlockedIP.objects.all():
            if ip.has_expired():
                count += 1
                ip.delete()
        if count > 0:
            self.stdout.write(self.style.SUCCESS(f"Unblocked {count} IPs."))
        else:
            self.stdout.write("Nothing to unblock.")
